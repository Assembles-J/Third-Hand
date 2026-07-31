import json

import httpx
import pytest

from app.ai_analysis import AiAnalysisOutput, AiAnalysisService
from app.llm_client import (
    DeepSeekClient,
    DeepSeekSettings,
    LlmClientError,
    LlmResponse,
    LlmUsage,
)
from app.storage import PortfolioStore


VALID_ANALYSIS = {
    "event_type": "share_repurchase",
    "impact": "uncertain",
    "summary": "公司披露回购进展，但当前输入缺少公告正文。",
    "verify_items": ["核对实际回购金额和用途"],
    "confidence": "low",
}


class FakeStore:
    def __init__(self):
        self.cache = {}
        self.saved = []

    def cached_analysis(self, cache_key):
        return self.cache.get(cache_key)

    def save_analysis(self, **record):
        self.saved.append(record)
        self.cache[record["cache_key"]] = record["payload"]

    def learning_cases(self, symbol):
        return [{
            "lesson": "先读原文",
            "outcome": "完成核验",
            "position_band": "低仓位",
            "planned_action": "继续观察",
            "confidence": 0.7,
            "evidence_links": ["https://example.com/evidence"],
        }]

    def research_rules(self):
        return [{"id": "event-verify", "version": "v1", "guidance": "核对正式公告"}]

    def personal_rules(self):
        return [{"id": "global", "version": 1, "enabled": True}]


class FakeClient:
    def __init__(self, contents):
        self.settings = DeepSeekSettings(api_key="test-key")
        self.enabled = True
        self.contents = list(contents)
        self.calls = []

    def chat_json(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        content = self.contents.pop(0)
        return LlmResponse(
            content=content,
            response_id=f"response-{len(self.calls)}",
            model=kwargs["model"],
            finish_reason="stop",
            usage=LlmUsage(prompt_tokens=100, completion_tokens=40, total_tokens=140),
            latency_ms=250,
        )


def content_item(title="公司发布回购进展"):
    return {
        "id": "news-1",
        "title": title,
        "source_name": "交易所公告",
        "source_url": "https://example.com/news-1",
        "published_at": "2026-07-30T18:00:00+08:00",
        "related_symbols": ["600519"],
        "explanation": "公告与持仓相关。",
    }


def test_deepseek_client_retries_rate_limit_and_records_usage():
    attempts = []
    delays = []

    def handler(request):
        attempts.append(json.loads(request.content))
        if len(attempts) == 1:
            return httpx.Response(429, json={"error": {"message": "busy"}})
        return httpx.Response(200, json={
            "id": "chat-1",
            "model": "deepseek-v4-flash",
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(VALID_ANALYSIS)}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        })

    settings = DeepSeekSettings(
        api_key="test-key",
        max_retries=1,
        retry_base_seconds=0.25,
    )
    client = DeepSeekClient(
        settings,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=delays.append,
    )

    result = client.chat_json([{"role": "user", "content": "test"}])

    assert len(attempts) == 2
    assert delays == [0.25]
    assert attempts[0]["model"] == "deepseek-v4-flash"
    assert attempts[0]["thinking"] == {"type": "disabled"}
    assert attempts[0]["response_format"] == {"type": "json_object"}
    assert result.response_id == "chat-1"
    assert result.usage.total_tokens == 30


def test_deepseek_client_opens_circuit_after_consecutive_failures():
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"error": {"message": "unavailable"}})

    settings = DeepSeekSettings(
        api_key="test-key",
        max_retries=0,
        circuit_failure_threshold=2,
    )
    client = DeepSeekClient(
        settings,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    for _ in range(2):
        with pytest.raises(LlmClientError, match="DeepSeek API"):
            client.chat_json([{"role": "user", "content": "test"}])
    with pytest.raises(LlmClientError) as caught:
        client.chat_json([{"role": "user", "content": "test"}])

    assert caught.value.code == "circuit_open"
    assert calls == 2


def test_analysis_output_rejects_unknown_enum():
    with pytest.raises(ValueError):
        AiAnalysisOutput.model_validate({**VALID_ANALYSIS, "impact": "very_good"})


def test_analysis_output_rejects_unknown_schema_fields():
    with pytest.raises(ValueError):
        AiAnalysisOutput.model_validate({**VALID_ANALYSIS, "suggested_quantity": 1000})


def test_analysis_service_validates_metadata_and_reuses_versioned_cache():
    store = FakeStore()
    client = FakeClient([json.dumps(VALID_ANALYSIS)])
    service = AiAnalysisService(store, client, schema_retries=0)

    enriched = service.enrich(content_item())
    cached = service.enrich(content_item())

    assert len(client.calls) == 1
    assert enriched["ai_analysis"]["model"] == "deepseek-v4-flash"
    assert enriched["ai_analysis"]["model_mode"] == "non-thinking"
    assert enriched["ai_analysis"]["prompt_version"] == "news-analysis-prompt-v2"
    assert enriched["ai_analysis"]["schema_version"] == "news-analysis-schema-v2"
    assert enriched["ai_analysis"]["response_id"] == "response-1"
    assert enriched["ai_analysis"]["total_tokens"] == 140
    assert len(enriched["ai_analysis"]["cache_key"]) == 64
    assert len(enriched["ai_analysis"]["rules_hash"]) == 64
    assert len(enriched["ai_analysis"]["user_context_hash"]) == 64
    assert cached["ai_analysis"]["cache_key"] == enriched["ai_analysis"]["cache_key"]
    assert store.saved[0]["metadata"]["latency_ms"] == 250


def test_analysis_cache_changes_with_content_and_prompt_version():
    store = FakeStore()
    client = FakeClient([json.dumps(VALID_ANALYSIS), json.dumps(VALID_ANALYSIS)])
    service = AiAnalysisService(store, client, schema_retries=0)

    first = service.enrich(content_item())
    second = service.enrich(content_item("公司发布新的回购完成公告"))

    assert len(client.calls) == 2
    assert first["ai_analysis"]["cache_key"] != second["ai_analysis"]["cache_key"]

    upgraded_client = FakeClient([json.dumps(VALID_ANALYSIS)])
    upgraded = AiAnalysisService(
        store,
        upgraded_client,
        prompt_version="news-analysis-prompt-v3",
        schema_retries=0,
    ).enrich(content_item())

    assert len(upgraded_client.calls) == 1
    assert upgraded["ai_analysis"]["cache_key"] != first["ai_analysis"]["cache_key"]


def test_analysis_service_retries_invalid_schema_once():
    store = FakeStore()
    client = FakeClient([
        '{"event_type":"repurchase","impact":"impossible"}',
        json.dumps(VALID_ANALYSIS),
    ])
    service = AiAnalysisService(store, client, schema_retries=1)

    enriched = service.enrich(content_item())

    assert len(client.calls) == 2
    assert enriched["ai_analysis"]["event_type"] == "share_repurchase"
    assert "上一次输出未通过" in client.calls[1]["messages"][-1]["content"]


def test_storage_keeps_multiple_versioned_analyses_for_one_content(tmp_path):
    store = PortfolioStore(tmp_path / "third-hand.db")
    common = {
        "content_id": "news-1",
        "content_hash": "content-hash",
        "input_hash": "input-hash",
        "rules_hash": "rules-hash",
        "user_context_hash": "user-context-hash",
        "model": "deepseek-v4-flash",
        "schema_version": "schema-v2",
        "metadata": {},
    }
    store.save_analysis(
        **common,
        cache_key="cache-v2",
        prompt_version="prompt-v2",
        payload={"summary": "v2"},
    )
    store.save_analysis(
        **common,
        cache_key="cache-v3",
        prompt_version="prompt-v3",
        payload={"summary": "v3"},
    )

    assert store.cached_analysis("cache-v2") == {"summary": "v2"}
    assert store.cached_analysis("cache-v3") == {"summary": "v3"}
