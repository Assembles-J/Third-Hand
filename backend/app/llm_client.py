"""Reliable OpenAI-compatible client for DeepSeek chat completions."""
from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from threading import BoundedSemaphore, Lock
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        logger.warning("%s 不是有效整数，使用默认值 %s", name, default)
        return default


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except ValueError:
        logger.warning("%s 不是有效数字，使用默认值 %s", name, default)
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


class DeepSeekSettings(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    reasoning_model: str = "deepseek-v4-pro"
    timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=2, ge=0, le=8)
    retry_base_seconds: float = Field(default=0.5, ge=0)
    max_concurrency: int = Field(default=4, ge=1, le=100)
    concurrency_wait_seconds: float = Field(default=1.0, ge=0)
    circuit_failure_threshold: int = Field(default=3, ge=1)
    circuit_reset_seconds: float = Field(default=60.0, gt=0)
    trust_environment_proxy: bool = False

    @classmethod
    def from_env(cls) -> "DeepSeekSettings":
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip().rstrip("/")
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip()
        reasoning_model = os.getenv("DEEPSEEK_REASONING_MODEL", "deepseek-v4-pro").strip()
        return cls(
            api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            base_url=base_url or "https://api.deepseek.com",
            model=model or "deepseek-v4-flash",
            reasoning_model=reasoning_model or "deepseek-v4-pro",
            timeout_seconds=_env_float("DEEPSEEK_TIMEOUT_SECONDS", 30.0, 1.0),
            max_retries=_env_int("DEEPSEEK_MAX_RETRIES", 2),
            retry_base_seconds=_env_float("DEEPSEEK_RETRY_BASE_SECONDS", 0.5),
            max_concurrency=_env_int("DEEPSEEK_MAX_CONCURRENCY", 4, 1),
            concurrency_wait_seconds=_env_float("DEEPSEEK_CONCURRENCY_WAIT_SECONDS", 1.0),
            circuit_failure_threshold=_env_int("DEEPSEEK_CIRCUIT_FAILURE_THRESHOLD", 3, 1),
            circuit_reset_seconds=_env_float("DEEPSEEK_CIRCUIT_RESET_SECONDS", 60.0, 1.0),
            trust_environment_proxy=_env_bool("DEEPSEEK_TRUST_ENV_PROXY", False),
        )


class LlmUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LlmResponse(BaseModel):
    content: str
    response_id: str | None = None
    model: str
    finish_reason: str | None = None
    usage: LlmUsage = Field(default_factory=LlmUsage)
    latency_ms: int
    attempt_count: int = 1
    retry_codes: tuple[str, ...] = ()


class LlmClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status_code = status_code


class DeepSeekClient:
    RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    def __init__(
        self,
        settings: DeepSeekSettings | None = None,
        *,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings or DeepSeekSettings.from_env()
        self._http = http_client or httpx.Client(trust_env=self.settings.trust_environment_proxy)
        self._sleep = sleep
        self._monotonic = monotonic
        self._slots = BoundedSemaphore(self.settings.max_concurrency)
        self._circuit_lock = Lock()
        self._consecutive_failures = 0
        self._circuit_opened_at: float | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.api_key)

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int = 900,
        thinking: bool = False,
    ) -> LlmResponse:
        if not self.enabled:
            raise LlmClientError("未配置 DEEPSEEK_API_KEY。", code="not_configured", retryable=False)
        self._ensure_circuit_available()
        if not self._slots.acquire(timeout=self.settings.concurrency_wait_seconds):
            raise LlmClientError("本地 DeepSeek 并发已满。", code="local_rate_limited", retryable=True)

        selected_model = model or self.settings.model
        started_at = self._monotonic()
        retry_codes: list[str] = []
        try:
            for attempt in range(self.settings.max_retries + 1):
                try:
                    result = self._request(messages, selected_model, max_tokens, thinking, started_at)
                    self._record_success()
                    return result.model_copy(update={"attempt_count": attempt + 1, "retry_codes": tuple(retry_codes)})
                except LlmClientError as error:
                    if not error.retryable or attempt >= self.settings.max_retries:
                        error.retry_codes = tuple(retry_codes)  # type: ignore[attr-defined]
                        self._record_failure()
                        logger.warning(
                            "DeepSeek 请求失败 model=%s code=%s status=%s attempts=%s",
                            selected_model,
                            error.code,
                            error.status_code,
                            attempt + 1,
                        )
                        raise
                    retry_codes.append(error.code)
                    delay = self.settings.retry_base_seconds * (2 ** attempt)
                    logger.warning(
                        "DeepSeek 请求重试 model=%s code=%s status=%s attempt=%s delay_seconds=%.2f",
                        selected_model,
                        error.code,
                        error.status_code,
                        attempt + 1,
                        delay,
                    )
                    self._sleep(delay)
            raise AssertionError("unreachable")
        finally:
            self._slots.release()

    def _request(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        thinking: bool,
        started_at: float,
    ) -> LlmResponse:
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "enabled" if thinking else "disabled"},
            "messages": messages,
        }
        try:
            response = self._http.post(
                f"{self.settings.base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.settings.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.settings.timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.TransportError) as error:
            raise LlmClientError("DeepSeek 网络请求失败。", code="transport_error", retryable=True) from error

        if not 200 <= response.status_code < 300:
            retryable = response.status_code in self.RETRYABLE_STATUS_CODES
            raise LlmClientError(
                "DeepSeek API 返回错误。",
                code="http_error",
                retryable=retryable,
                status_code=response.status_code,
            )
        try:
            body: dict[str, Any] = response.json()
            choice = body["choices"][0]
            content = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise LlmClientError("DeepSeek 响应结构无效。", code="invalid_response", retryable=True) from error
        if not isinstance(content, str) or not content.strip():
            raise LlmClientError("DeepSeek 返回空内容。", code="empty_content", retryable=True)
        if choice.get("finish_reason") == "length":
            raise LlmClientError("DeepSeek 输出被截断。", code="output_truncated", retryable=False)

        usage = body.get("usage") or {}
        result = LlmResponse(
            content=content.strip(),
            response_id=str(body["id"]) if body.get("id") else None,
            model=str(body.get("model") or model),
            finish_reason=choice.get("finish_reason"),
            usage=LlmUsage(
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                total_tokens=int(usage.get("total_tokens") or 0),
            ),
            latency_ms=max(0, int((self._monotonic() - started_at) * 1000)),
        )
        logger.info(
            "DeepSeek 请求成功 model=%s response_id=%s latency_ms=%s total_tokens=%s",
            result.model,
            result.response_id,
            result.latency_ms,
            result.usage.total_tokens,
        )
        return result

    def _ensure_circuit_available(self) -> None:
        with self._circuit_lock:
            if self._circuit_opened_at is None:
                return
            elapsed = self._monotonic() - self._circuit_opened_at
            if elapsed >= self.settings.circuit_reset_seconds:
                self._circuit_opened_at = None
                self._consecutive_failures = 0
                return
        raise LlmClientError("DeepSeek 熔断器已开启。", code="circuit_open", retryable=True)

    def _record_success(self) -> None:
        with self._circuit_lock:
            self._consecutive_failures = 0
            self._circuit_opened_at = None

    def _record_failure(self) -> None:
        with self._circuit_lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.settings.circuit_failure_threshold:
                self._circuit_opened_at = self._monotonic()
                logger.error(
                    "DeepSeek 熔断器开启 failures=%s reset_seconds=%s",
                    self._consecutive_failures,
                    self.settings.circuit_reset_seconds,
                )
