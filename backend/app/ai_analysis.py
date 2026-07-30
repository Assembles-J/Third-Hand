"""Configurable financial AI analysis provider.

Supports a self-hosted FinGPT OpenAI-compatible endpoint and DeepSeek fallback.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass

from app.time_utils import beijing_now


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    model: str
    key: str = ""

    def endpoint(self) -> str:
        url = self.base_url.rstrip("/")
        return url if url.endswith("chat/completions") else url + "/chat/completions"


class AiAnalysisService:
    def __init__(self, store) -> None:
        self.store = store
        self.providers = self._providers()
        self.timeout = int(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "30"))

    def _providers(self) -> list[Provider]:
        mode = os.getenv("THIRD_HAND_AI_PROVIDER", "auto").lower()
        result = []
        fingpt = os.getenv("FINGPT_BASE_URL", "").strip()
        deepseek = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if mode in {"auto", "fingpt"} and fingpt:
            result.append(Provider("fingpt", fingpt, os.getenv("FINGPT_MODEL", "fingpt")))
        if mode in {"auto", "deepseek", "fingpt"} and deepseek:
            result.append(Provider("deepseek", os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"), os.getenv("DEEPSEEK_MODEL", "deepseek-chat"), deepseek))
        return result

    def enrich(self, item: dict[str, object]) -> dict[str, object]:
        if not self.providers:
            return item
        cached = self.store.cached_analysis(str(item["id"]))
        if cached:
            return {**item, "ai_analysis": cached}
        for provider in self.providers:
            try:
                analysis = self._call(provider, item)
                self.store.save_analysis(str(item["id"]), analysis)
                return {**item, "ai_analysis": analysis}
            except Exception:
                continue
        return item

    def _call(self, provider: Provider, item: dict[str, object]) -> dict[str, object]:
        prompt = json.dumps({
            "title": item.get("title"),
            "source": item.get("source_name"),
            "symbols": item.get("related_symbols", []),
            "summary": item.get("explanation", ""),
            "rules": self.store.research_rules(),
        }, ensure_ascii=False)
        payload = json.dumps({
            "model": provider.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": "仅基于事实分析金融信息，不预测价格，不提供买卖建议。输出JSON event_type impact summary verify_items confidence。"},
                {"role": "user", "content": prompt},
            ],
        }, ensure_ascii=False).encode()
        headers = {"Content-Type": "application/json"}
        if provider.key:
            headers["Authorization"] = "Bearer " + provider.key
        request = urllib.request.Request(provider.endpoint(), data=payload, headers=headers)
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read())
        content = body["choices"][0]["message"]["content"]
        if isinstance(content, str):
            analysis = json.loads(content.replace("```json", "").replace("```", ""))
        else:
            raise ValueError("invalid model response")
        analysis["provider"] = provider.name
        analysis["model"] = provider.model
        analysis["generated_at"] = beijing_now().isoformat()
        return analysis
