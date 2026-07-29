"""Optional, cached DeepSeek fact-focused analysis for portfolio news."""
from __future__ import annotations
import json, os, urllib.request

class AiAnalysisService:
    def __init__(self, store) -> None: self.store, self.key = store, os.getenv("DEEPSEEK_API_KEY", "")
    def enrich(self, item: dict[str, object]) -> dict[str, object]:
        if not self.key: return item
        cached = self.store.cached_analysis(str(item["id"]))
        if cached: return {**item, "ai_analysis": cached}
        symbol = str(item["related_symbols"][0]) if item.get("related_symbols") else None
        cases = self.store.learning_cases(symbol)[:3]
        prompt = {"title": item["title"], "source": item["source_name"], "symbols": item["related_symbols"], "personal_review_cases":[{"lesson":case["lesson"],"outcome":case["outcome"],"position_band":case["position_band"],"planned_action":case["planned_action"],"confidence":case["confidence"],"evidence_links":json.loads(case["evidence_links"])} for case in cases]}
        body = json.dumps({"model":"deepseek-chat","temperature":0.2,"max_tokens":350,"response_format":{"type":"json_object"},"messages":[{"role":"system","content":"仅依据输入事实分析，不预测价格、不提供买卖建议。输出JSON：event_type,impact(positive|negative|neutral|uncertain),summary,verify_items,confidence(low|medium|high)。"},{"role":"user","content":json.dumps(prompt, ensure_ascii=False)}]}).encode()
        request = urllib.request.Request("https://api.deepseek.com/chat/completions", data=body, headers={"Authorization":f"Bearer {self.key}","Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(request, timeout=15) as response: result = json.loads(response.read())
            analysis = json.loads(result["choices"][0]["message"]["content"])
            self.store.save_analysis(str(item["id"]), analysis)
            return {**item, "ai_analysis": analysis}
        except Exception: return item
