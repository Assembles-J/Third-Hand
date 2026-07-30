"""Versioned, validated DeepSeek analysis for portfolio-related content."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from threading import Lock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.llm_client import DeepSeekClient, LlmClientError, LlmResponse
from app.time_utils import beijing_now

logger = logging.getLogger(__name__)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class AiAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    impact: Literal["positive", "negative", "neutral", "uncertain"]
    summary: str = Field(min_length=1, max_length=800)
    verify_items: list[str] = Field(default_factory=list, max_length=8)
    confidence: Literal["low", "medium", "high"]

    @field_validator("event_type", "summary")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("verify_items")
    @classmethod
    def normalize_verify_items(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            text = str(value).strip()
            if text and text not in normalized:
                normalized.append(text[:240])
        return normalized


class AiAnalysisResult(AiAnalysisOutput):
    analysis_version: str
    model: str
    model_mode: Literal["non-thinking", "thinking"]
    prompt_version: str
    schema_version: str
    generated_at: datetime
    content_hash: str
    input_hash: str
    rules_hash: str
    user_context_hash: str
    cache_key: str
    response_id: str | None = None
    finish_reason: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0


class AnalysisContext(BaseModel):
    content_id: str
    content_hash: str
    input_hash: str
    rules_hash: str
    user_context_hash: str
    cache_key: str
    payload: dict[str, object]


class AiAnalysisService:
    DEFAULT_PROMPT_VERSION = "news-analysis-prompt-v2"
    DEFAULT_SCHEMA_VERSION = "news-analysis-schema-v2"
    ANALYSIS_VERSION = "news-analysis-v2"

    def __init__(
        self,
        store,
        client: DeepSeekClient | None = None,
        *,
        model: str | None = None,
        prompt_version: str | None = None,
        schema_version: str | None = None,
        schema_retries: int | None = None,
    ) -> None:
        self.store = store
        self.client = client or DeepSeekClient()
        self.model = model or os.getenv("DEEPSEEK_MODEL", self.client.settings.model).strip()
        self.prompt_version = prompt_version or os.getenv(
            "AI_ANALYSIS_PROMPT_VERSION", self.DEFAULT_PROMPT_VERSION
        ).strip()
        self.schema_version = schema_version or os.getenv(
            "AI_ANALYSIS_SCHEMA_VERSION", self.DEFAULT_SCHEMA_VERSION
        ).strip()
        self.schema_retries = schema_retries if schema_retries is not None else self._schema_retries_from_env()
        self.max_tokens = self._max_tokens_from_env()
        self._inflight: set[str] = set()
        self._inflight_lock = Lock()

    @staticmethod
    def _schema_retries_from_env() -> int:
        try:
            return min(2, max(0, int(os.getenv("AI_ANALYSIS_SCHEMA_RETRIES", "1"))))
        except ValueError:
            return 1

    @staticmethod
    def _max_tokens_from_env() -> int:
        try:
            return min(4000, max(300, int(os.getenv("AI_ANALYSIS_MAX_TOKENS", "900"))))
        except ValueError:
            return 900

    def cached(self, item: dict[str, object]) -> dict[str, object] | None:
        context = self._build_context(item)
        cached = self.store.cached_analysis(context.cache_key)
        if not cached:
            return None
        try:
            return AiAnalysisResult.model_validate(cached).model_dump(mode="json")
        except ValidationError:
            logger.warning("AI 分析缓存校验失败 cache_key=%s", context.cache_key)
            return None

    def enrich(self, item: dict[str, object]) -> dict[str, object]:
        if not self.client.enabled:
            return item
        context = self._build_context(item)
        cached = self.store.cached_analysis(context.cache_key)
        if cached:
            try:
                validated = AiAnalysisResult.model_validate(cached)
                return {**item, "ai_analysis": validated.model_dump(mode="json")}
            except ValidationError:
                logger.warning("忽略无效 AI 分析缓存 cache_key=%s", context.cache_key)

        with self._inflight_lock:
            if context.cache_key in self._inflight:
                return item
            self._inflight.add(context.cache_key)
        try:
            response, output = self._generate(context)
            result = AiAnalysisResult(
                **output.model_dump(),
                analysis_version=self.ANALYSIS_VERSION,
                model=response.model,
                model_mode="non-thinking",
                prompt_version=self.prompt_version,
                schema_version=self.schema_version,
                generated_at=beijing_now(),
                content_hash=context.content_hash,
                input_hash=context.input_hash,
                rules_hash=context.rules_hash,
                user_context_hash=context.user_context_hash,
                cache_key=context.cache_key,
                response_id=response.response_id,
                finish_reason=response.finish_reason,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                latency_ms=response.latency_ms,
            )
            payload = result.model_dump(mode="json")
            self.store.save_analysis(
                cache_key=context.cache_key,
                content_id=context.content_id,
                content_hash=context.content_hash,
                input_hash=context.input_hash,
                rules_hash=context.rules_hash,
                user_context_hash=context.user_context_hash,
                model=result.model,
                prompt_version=self.prompt_version,
                schema_version=self.schema_version,
                payload=payload,
                metadata={
                    "response_id": result.response_id,
                    "finish_reason": result.finish_reason,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "total_tokens": result.total_tokens,
                    "latency_ms": result.latency_ms,
                },
            )
            return {**item, "ai_analysis": payload}
        except LlmClientError as error:
            logger.warning(
                "AI 分析请求失败 content_id=%s code=%s status=%s retryable=%s",
                context.content_id,
                error.code,
                error.status_code,
                error.retryable,
            )
            return item
        except (ValidationError, ValueError, json.JSONDecodeError) as error:
            logger.warning("AI 分析输出无效 content_id=%s error=%s", context.content_id, error)
            return item
        except Exception:
            logger.exception("AI 分析异常 content_id=%s", context.content_id)
            return item
        finally:
            with self._inflight_lock:
                self._inflight.discard(context.cache_key)

    def _generate(self, context: AnalysisContext) -> tuple[LlmResponse, AiAnalysisOutput]:
        messages = self._messages(context.payload)
        for attempt in range(self.schema_retries + 1):
            response = self.client.chat_json(
                messages,
                model=self.model,
                max_tokens=self.max_tokens,
                thinking=False,
            )
            try:
                output = AiAnalysisOutput.model_validate_json(self._clean_json(response.content))
                return response, output
            except (ValidationError, json.JSONDecodeError, ValueError) as error:
                logger.warning(
                    "DeepSeek JSON Schema 校验失败 content_id=%s attempt=%s error=%s",
                    context.content_id,
                    attempt + 1,
                    error,
                )
                if attempt >= self.schema_retries:
                    raise
                messages = [
                    *messages,
                    {
                        "role": "user",
                        "content": "上一次输出未通过 JSON Schema 校验。请只重新输出符合示例的 JSON 对象，不要添加 Markdown。",
                    },
                ]
        raise AssertionError("unreachable")

    def _build_context(self, item: dict[str, object]) -> AnalysisContext:
        content_id = str(item["id"])
        symbol = str(item["related_symbols"][0]) if item.get("related_symbols") else None
        cases = [self._case_payload(case) for case in self.store.learning_cases(symbol)[:3]]
        research_rules = self.store.research_rules()
        personal_rules = self.store.personal_rules()
        content = {
            "id": content_id,
            "title": item.get("title"),
            "source_name": item.get("source_name"),
            "source_url": item.get("source_url"),
            "published_at": item.get("published_at"),
            "related_symbols": item.get("related_symbols", []),
            "explanation": item.get("explanation"),
            "body_text": item.get("body_text"),
            "raw_content": item.get("raw_content"),
        }
        rules_hash = _sha256({"research_rules": research_rules, "personal_rules": personal_rules})
        user_context_hash = _sha256(cases)
        content_hash = _sha256(content)
        payload: dict[str, object] = {
            "content": content,
            "research_rules": research_rules,
            "personal_rules": personal_rules,
            "personal_review_cases": cases,
        }
        input_hash = _sha256(payload)
        cache_key = _sha256({
            "content_hash": content_hash,
            "input_hash": input_hash,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "schema_version": self.schema_version,
            "rules_hash": rules_hash,
            "user_context_hash": user_context_hash,
        })
        return AnalysisContext(
            content_id=content_id,
            content_hash=content_hash,
            input_hash=input_hash,
            rules_hash=rules_hash,
            user_context_hash=user_context_hash,
            cache_key=cache_key,
            payload=payload,
        )

    @staticmethod
    def _case_payload(case: dict[str, object]) -> dict[str, object]:
        evidence_links = case.get("evidence_links", [])
        if isinstance(evidence_links, str):
            try:
                evidence_links = json.loads(evidence_links)
            except json.JSONDecodeError:
                evidence_links = []
        return {
            "lesson": case.get("lesson"),
            "outcome": case.get("outcome"),
            "position_band": case.get("position_band"),
            "planned_action": case.get("planned_action"),
            "confidence": case.get("confidence"),
            "evidence_links": evidence_links,
        }

    @staticmethod
    def _messages(payload: dict[str, object]) -> list[dict[str, str]]:
        example = {
            "event_type": "share_repurchase",
            "impact": "uncertain",
            "summary": "公司披露了回购进展，但当前输入缺少公告正文和实际金额，暂不能判断业务影响。",
            "verify_items": ["打开原始公告核对已回购金额、数量和用途"],
            "confidence": "low",
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是投资研究事实核验助手。仅依据输入内容分析；缺少正文时必须明确说明。"
                    "不得预测价格，不得提供买卖建议，不得把推断写成事实。"
                    "只输出一个 JSON 对象，不要输出 Markdown。"
                    f"输出必须符合此示例及枚举：{_canonical_json(example)}"
                ),
            },
            {"role": "user", "content": _canonical_json(payload)},
        ]

    @staticmethod
    def _clean_json(content: str) -> str:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()
        return text
