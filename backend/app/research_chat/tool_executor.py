"""Bounded local implementation of the Research Chat tool whitelist.

Every tool is read-only or returns a confirmation proposal.  Research Chat has
no direct paper-ledger mutation path; formal execution remains DecisionReport ->
next eligible observed quote -> paper execution.
"""
from __future__ import annotations

import json

from .tool_registry import ALLOWED_TOOLS


class ToolExecutor:
    def __init__(self, store):
        self.store = store

    def execute(self, name, args, context):
        if name not in ALLOWED_TOOLS:
            raise ValueError("tool_not_allowed")

        symbol = str(args.get("symbol") or context.symbol).upper()

        if name == "request_user_input":
            questions = args.get("questions") or []
            if not isinstance(questions, list) or not 1 <= len(questions) <= 3:
                raise ValueError("tool_invalid_arguments")
            return {
                "clarification": True,
                "questions": [str(question)[:240] for question in questions],
            }

        if name == "propose_data_change":
            entity = str(args.get("entity") or "")
            operation = str(args.get("operation") or "")
            if entity not in {"holding", "trade_plan", "personal_rule"} or operation not in {"create", "update", "delete"}:
                raise ValueError("tool_invalid_arguments")
            return {
                "confirmation_required": True,
                "entity": entity,
                "operation": operation,
                "summary": str(args.get("summary") or "")[:500],
                "automatic_execution": False,
            }

        if name == "request_daily_history_refresh":
            available = len(self.store.daily_prices(symbol, 60))
            return {
                "confirmation_required": available < 60,
                "action": "daily_history_refresh",
                "symbol": symbol,
                "required_days": 60,
                "available_days": available,
                "summary": f"当前仅有 {available} 条日线，需要拉取至少 60 条后再继续研究。",
                "automatic_execution": False,
            }

        content = self.store.cached_content([symbol], limit=30)
        announcements = [item for item in content if str(item.get("id", "")).startswith("announcement-")]
        news = [item for item in content if str(item.get("id", "")).startswith("news-")]
        business_evidence = {
            "announcements": announcements,
            "news": news,
            "trade_plan": self.store.trade_plan(symbol),
            "market_regime": context.market_regime.model_dump(mode="json") if context.market_regime else None,
            "relative_strength": context.relative_strength.model_dump(mode="json") if context.relative_strength else None,
            "note": "Publication times and source links are included. Formal announcements take precedence over news when evidence conflicts.",
        }
        mapping = {
            "get_decision_context": context.model_dump(mode="json"),
            "get_holding": self.store.list(),
            "get_account_summary": self.store.available_cash(),
            "get_market_quote": self.store.cached_quotes([symbol]),
            "get_daily_price_summary": self.store.daily_prices(symbol, 60),
            "get_risk_snapshot": self.store.cached_risk(symbol),
            "get_trade_plan": self.store.trade_plan(symbol),
            "get_personal_rule": self.store.personal_rules(),
            "get_previous_decisions": self.store.decision_reports(symbol),
            "get_recommendation_evaluations": self.store.recommendations(symbol),
            "get_event_evidence": [event.model_dump(mode="json") for event in context.events],
            "get_company_announcements": announcements,
            "get_company_news": news,
            "get_business_evidence": business_evidence,
            "get_technical_snapshot": context.technical.model_dump(mode="json") if context.technical else None,
            "get_market_regime": context.market_regime.model_dump(mode="json") if context.market_regime else None,
            "get_relative_strength": context.relative_strength.model_dump(mode="json") if context.relative_strength else None,
            "get_current_decision_report": (self.store.decision_reports(symbol, 1) or [None])[0],
        }
        result = mapping.get(name)
        encoded = json.dumps(result, ensure_ascii=False, default=str)
        if len(encoded) > 12_000:
            result = {"truncated": True, "summary": encoded[:12_000]}
        return result
