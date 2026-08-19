import hashlib
import json
from pathlib import Path

import httpx
import pytest

from app.decision_ai import DecisionAiService
from app.decision_guard import DecisionGuard
from app.decision_models import ActionCandidate, AiResearchAssessment
from app.llm_client import (
    DeepSeekClient,
    DeepSeekSettings,
    LlmClientError,
    LlmResponse,
    LlmUsage,
)
from app.storage import PortfolioStore


class Store:
    def __init__(self): self.runs = []
    def save_decision_ai_run(self, item): self.runs.append(item)


class Client:
    enabled = True
    def __init__(self, content): self.content = content; self.calls = 0
    def chat_json(self, *_args, **_kwargs):
        self.calls += 1
        return LlmResponse(content=self.content, model="test", latency_ms=1, usage=LlmUsage())


class Context:
    context_id = "context"; input_hash = "hash"; symbol = "600519"
    class data_quality: status = "ready"


def _candidate(action="REDUCE"):
    return ActionCandidate(action=action, priority=80, policy_score=.8)


def _evidence():
    from app.decision_models import EvidenceItem
    return (EvidenceItem(evidence_id="position.above_max", category="position", direction="negative", strength=.7, title="cap", description="cap", source="test", fresh=True),)


def _valid_payload(action="REDUCE"):
    return {
        "thesis_status": "unchanged",
        "preferred_action": action,
        "supporting_evidence_ids": [],
        "opposing_evidence_ids": [],
        "missing_evidence": [],
        "reasoning_steps": [],
        "uncertainty": "low",
        "summary": "recovered",
    }


def test_ai_service_accepts_only_known_evidence_and_policy_candidate():
    payload = {"thesis_status": "weakened", "preferred_action": "REDUCE", "supporting_evidence_ids": ["position.above_max"], "opposing_evidence_ids": [], "missing_evidence": [], "reasoning_steps": [], "uncertainty": "medium", "summary": "reduce"}
    store = Store()
    result = DecisionAiService(store, Client(json.dumps(payload))).assess(Context(), _evidence(), (_candidate(),))

    assert result.status == "succeeded"
    assert result.assessment.preferred_action == "REDUCE"
    assert store.runs[0]["status"] == "succeeded"
    metadata = store.runs[0]["metadata"]
    assert metadata["model_tier"] == "FLASH_DEFAULT"
    assert len(metadata["prompt_hash"]) == 64
    assert len(metadata["evidence_hash"]) == 64
    assert metadata["validation"] == "schema_and_semantic_passed"
    assert metadata["provider_attempt_count"] == 1
    assert metadata["provider_retry_codes"] == []
    assert metadata["runtime_audit_version"] == "decision-ai-runtime-audit-v2-policy-attempt-lineage"
    assert len(metadata["policy_attempts"]) == 1
    assert metadata["policy_attempts"][0]["validation_result"] == "passed"


def test_ai_service_rejects_unknown_evidence_and_preserves_rule_fallback():
    payload = {"thesis_status": "weakened", "preferred_action": "REDUCE", "supporting_evidence_ids": ["unknown"], "opposing_evidence_ids": [], "missing_evidence": [], "reasoning_steps": [], "uncertainty": "medium", "summary": "reduce"}
    store = Store()
    result = DecisionAiService(store, Client(json.dumps(payload))).assess(Context(), _evidence(), (_candidate(),))

    assert result.assessment is None
    assert result.status == "failed"
    assert result.error_code == "invalid_ai_output"
    assert store.runs[-1]["status"] == "failed"
    assert store.runs[-1]["metadata"]["retry_fallback_path"][0]["reason"] == "schema_or_semantic_validation_failed"
    attempts = store.runs[-1]["metadata"]["policy_attempts"]
    assert attempts[0]["validation_stage"] == "semantic"
    assert attempts[0]["validation_error_paths"] == ["evidence_references"]


def test_ai_service_accepts_a_fenced_json_response_and_canonicalizes_a_unique_title():
    payload = {"thesis_status": "weakened", "preferred_action": "REDUCE", "supporting_evidence_ids": ["cap"], "opposing_evidence_ids": [], "missing_evidence": [], "reasoning_steps": [], "uncertainty": "medium", "summary": "需要留意仓位上限。"}
    store = Store()
    result = DecisionAiService(store, Client(f"```json\n{json.dumps(payload)}\n``` ")).assess(Context(), _evidence(), (_candidate(),))

    assert result.status == "succeeded"
    assert result.assessment.supporting_evidence_ids == ("position.above_max",)


def test_ai_service_recovers_a_truncated_thinking_request_with_larger_structured_pass():
    class TruncatingClient(Client):
        def chat_json(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                error = LlmClientError(
                    "truncated",
                    code="output_truncated",
                    retryable=False,
                    finish_reason="length",
                    reasoning_present=True,
                    reasoning_length=321,
                    reasoning_hash="a" * 64,
                    usage=LlmUsage(completion_tokens=3200, total_tokens=4000),
                )
                error.attempt_count = 1
                raise error
            return LlmResponse(
                content=json.dumps(_valid_payload()),
                model="test", latency_ms=1, usage=LlmUsage(),
            )

    store = Store()
    client = TruncatingClient("")
    result = DecisionAiService(store, client).assess(Context(), _evidence(), (_candidate(),))

    assert result.status == "succeeded"
    assert client.calls == 2
    metadata = store.runs[-1]["metadata"]
    assert metadata["model_tier"] == "PRO_STRUCTURED_RECOVERY"
    assert metadata["thinking"] is False
    assert metadata["max_tokens"] >= 2400
    assert metadata["retry_fallback_path"][0]["reason"] == "output_truncated"
    first = metadata["policy_attempts"][0]
    assert first["finish_reason"] == "length"
    assert first["reasoning_present"] is True
    assert first["reasoning_length"] == 321
    assert first["reasoning_hash"] == "a" * 64


def test_ai_service_promotes_flash_validation_failure_to_reasoning_model():
    valid = json.dumps({
        "thesis_status": "weakened", "preferred_action": "REDUCE",
        "supporting_evidence_ids": [], "opposing_evidence_ids": [],
        "missing_evidence": [], "reasoning_steps": [], "uncertainty": "medium", "summary": "recovered",
    })

    class RepairingClient(Client):
        def chat_json(self, *_args, **kwargs):
            self.calls += 1
            self.last_kwargs = kwargs
            return LlmResponse(
                content="not-json" if self.calls == 1 else valid,
                model="test", latency_ms=1, usage=LlmUsage(),
            )

    store = Store()
    client = RepairingClient("")
    result = DecisionAiService(store, client).assess(Context(), _evidence(), (_candidate(),))

    assert result.status == "succeeded"
    assert client.calls == 2
    metadata = store.runs[-1]["metadata"]
    assert metadata["model_tier"] == "PRO_ESCALATION"
    assert metadata["thinking"] is True
    assert metadata["retry_fallback_path"][0]["from_tier"] == "FLASH_DEFAULT"
    assert metadata["retry_fallback_path"][0]["to_tier"] == "PRO_ESCALATION"
    assert metadata["policy_attempts"][0]["validation_stage"] == "schema"


def test_ai_service_recovers_compound_invalid_then_truncated_output():
    valid = json.dumps({
        "thesis_status": "unchanged", "preferred_action": "REDUCE",
        "supporting_evidence_ids": [], "opposing_evidence_ids": [],
        "missing_evidence": [], "reasoning_steps": [], "uncertainty": "low", "summary": "recovered",
    })

    class CompoundClient(Client):
        def chat_json(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return LlmResponse(content="not-json", model="flash", latency_ms=1, usage=LlmUsage())
            if self.calls == 2:
                error = LlmClientError("truncated", code="output_truncated", retryable=False, finish_reason="length")
                error.attempt_count = 1
                raise error
            return LlmResponse(content=valid, model="pro", latency_ms=1, usage=LlmUsage())

    store = Store()
    client = CompoundClient("")
    result = DecisionAiService(store, client).assess(Context(), _evidence(), (_candidate(),))

    assert result.status == "succeeded"
    assert client.calls == 3
    metadata = store.runs[-1]["metadata"]
    assert metadata["model_tier"] == "PRO_STRUCTURED_RECOVERY"
    assert [item["reason"] for item in metadata["retry_fallback_path"]] == [
        "schema_or_semantic_validation_failed", "output_truncated",
    ]
    assert [item["outcome"] for item in metadata["policy_attempts"]] == [
        "validation_failed", "provider_error", "succeeded",
    ]


def test_ai_service_recovers_empty_content_with_structured_fallback():
    valid = json.dumps({
        "thesis_status": "unchanged", "preferred_action": "REDUCE",
        "supporting_evidence_ids": [], "opposing_evidence_ids": [],
        "missing_evidence": [], "reasoning_steps": [], "uncertainty": "low", "summary": "recovered",
    })

    class EmptyThenValidClient(Client):
        def chat_json(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                error = LlmClientError("empty", code="empty_content", retryable=True)
                error.attempt_count = 3
                error.retry_codes = ("empty_content", "empty_content")
                raise error
            return LlmResponse(content=valid, model="pro", latency_ms=1, usage=LlmUsage())

    store = Store()
    result = DecisionAiService(store, EmptyThenValidClient("")).assess(Context(), _evidence(), (_candidate(),))

    assert result.status == "succeeded"
    metadata = store.runs[-1]["metadata"]
    assert metadata["model_tier"] == "PRO_STRUCTURED_RECOVERY"
    assert metadata["policy_attempts"][0]["provider_attempt_count"] == 3
    assert metadata["policy_attempts"][0]["provider_retry_codes"] == ["empty_content", "empty_content"]


def test_ai_service_records_compound_empty_then_structured_invalid_and_fails_closed():
    hidden_reasoning = "do not persist this hidden reasoning"
    hidden_hash = hashlib.sha256(hidden_reasoning.encode()).hexdigest()

    class CompoundFailureClient(Client):
        def chat_json(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                error = LlmClientError(
                    "empty",
                    code="empty_content",
                    retryable=True,
                    finish_reason="stop",
                    reasoning_present=True,
                    reasoning_length=len(hidden_reasoning),
                    reasoning_hash=hidden_hash,
                )
                error.attempt_count = 3
                error.retry_codes = ("empty_content", "empty_content")
                raise error
            return LlmResponse(content="not-json", model="pro", latency_ms=2, usage=LlmUsage())

    store = Store()
    result = DecisionAiService(store, CompoundFailureClient("")).assess(Context(), _evidence(), (_candidate(),))

    assert result.status == "failed"
    assert result.error_code == "invalid_ai_output"
    metadata = store.runs[-1]["metadata"]
    assert metadata["final_fail_closed_reason"] == "schema_validation_failed"
    assert len(metadata["policy_attempts"]) == 2
    assert metadata["policy_attempts"][0]["provider_error_code"] == "empty_content"
    assert metadata["policy_attempts"][0]["reasoning_hash"] == hidden_hash
    assert metadata["policy_attempts"][1]["validation_stage"] == "schema"
    serialized = json.dumps(metadata, ensure_ascii=False)
    assert hidden_reasoning not in serialized


def test_deepseek_truncation_preserves_finish_and_reasoning_fingerprint_without_raw_reasoning():
    hidden_reasoning = "private chain of thought fixture"

    def handler(_request):
        return httpx.Response(200, json={
            "id": "response-1",
            "model": "deepseek-v4-pro",
            "choices": [{
                "message": {"content": "", "reasoning_content": hidden_reasoning},
                "finish_reason": "length",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3200, "total_tokens": 3210},
        })

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = DeepSeekClient(
        DeepSeekSettings(api_key="test", max_retries=0),
        http_client=http_client,
        sleep=lambda _seconds: None,
        monotonic=lambda: 1.0,
    )

    with pytest.raises(LlmClientError) as captured:
        client.chat_json([{"role": "user", "content": "JSON only"}], model="deepseek-v4-pro", thinking=True)

    error = captured.value
    assert error.code == "output_truncated"
    assert error.finish_reason == "length"
    assert error.attempt_count == 1
    assert error.content_present is False
    assert error.reasoning_present is True
    assert error.reasoning_length == len(hidden_reasoning)
    assert error.reasoning_hash == hashlib.sha256(hidden_reasoning.encode()).hexdigest()
    assert error.usage.completion_tokens == 3200
    assert hidden_reasoning not in repr(error.__dict__)


def test_guard_rejects_ai_action_outside_policy_candidates():
    assessment = AiResearchAssessment(thesis_status="unknown", preferred_action="ADD", uncertainty="high", summary="add")

    assert DecisionGuard().guard((_candidate("REDUCE"),), assessment) is None


def test_persisted_model_audit_is_readable_without_secrets(tmp_path: Path):
    store = PortfolioStore(tmp_path / "model-audit.db")
    store.save_decision_ai_run({
        "run_id": "run-1", "context_id": "context-1", "input_hash": "input-1",
        "status": "succeeded", "error_code": None, "payload": {},
        "metadata": {"prompt_hash": "a" * 64, "retry_fallback_path": []},
        "created_at": "2026-08-18T10:00:00+08:00",
    })

    audit = store.decision_ai_runs("context-1")

    assert audit[0]["metadata"]["prompt_hash"] == "a" * 64
    assert "api_key" not in audit[0]["metadata"]
