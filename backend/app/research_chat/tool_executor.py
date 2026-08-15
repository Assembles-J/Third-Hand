"""Read-only/proposal-only Research Chat tool execution.

The executor only reads persisted local state or returns an explicit confirmation
proposal. Direct paper-ledger mutation was removed; formal execution remains the
current-version DecisionReport -> next eligible observed quote path.
"""
from __future__ import annotations

from typing import Any

from .tool_registry import ALLOWED_TOOLS


class ToolExecutor:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def _symbol(args: dict[str, Any], context) -> str:
        value = args.get("symbol") or getattr(context, "symbol", "")
        symbol = str(value or "").strip().upper()
        if not symbol:
            raise ValueError("tool_symbol_required")
        return symbol

    @staticmethod
    def _json_safe(value):
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {str(key): ToolExecutor._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [ToolExecutor._json_safe(item) for item in value]
        return value

    def _optional_store_call(self, names: tuple[str, ...], *args):
        for method_name in names:
            method = getattr(self.store, method_name, None)
            if not callable(method):
                continue
            try:
                return method(*args)
            except TypeError:
                try:
                    return method(args[0]) if args else method()
                except TypeError:
                    continue
        return None

    def execute(self, name, args, context):
        if name not in ALLOWED_TOOLS:
            raise ValueError(f"unknown_tool:{name}")
        args = dict(args or {})

        if name == "request_user_input":
            questions = args.get("questions") or []
            if not isinstance(questions, list) or not 1 <= len(questions) <= 3:
                raise ValueError("tool_invalid_arguments")
            return {"clarification": True, "questions": [str(question)[:240] for question in questions]}

        if name == "propose_data_change":
            target = str(args.get("target") or "")
            operation = str(args.get("operation") or "")
            payload = args.get("payload") or {}
            if target not in {"holding", "watchlist", "trade_plan"}:
                raise ValueError("tool_invalid_arguments")
            if operation not in {"create", "update", "delete"} or not isinstance(payload, dict):
                raise ValueError("tool_invalid_arguments")
            return {
                "requires_confirmation": True,
                "confirmation_required": True,
                "automatic_execution": False,
                "target": target,
                "operation": operation,
                "payload": self._json_safe(payload),
            }

        symbol = self._symbol(args, context)

        if name == "get_current_quote":
            return self._json_safe(self.store.cached_quotes([symbol]))

        if name == "get_intraday_history":
            # Research Chat is a consumer of the scheduler-owned local data
            # plane. This tool deliberately has no provider/refresh branch.
            limit = max(20, min(int(args.get("limit") or 240), 1000))
            return self._json_safe(self.store.intraday_prices(symbol, limit))

        if name == "get_daily_history":
            limit = max(1, min(int(args.get("limit") or 60), 240))
            return self._json_safe(self.store.daily_prices(symbol, limit))

        if name == "request_daily_history_refresh":
            required_days = max(30, min(int(args.get("required_days") or 60), 240))
            available_days = len(self.store.daily_prices(symbol, required_days))
            needed = available_days < required_days
            return {
                "requires_confirmation": needed,
                "confirmation_required": needed,
                "automatic_execution": False,
                "action": "daily_history_refresh",
                "symbol": symbol,
                "required_days": required_days,
                "available_days": available_days,
            }

        if name == "get_position_snapshot":
            holdings = self.store.list()
            holding = next(
                (item for item in holdings if str(item.get("symbol") or "").strip().upper() == symbol),
                None,
            )
            paper_position = None
            paper_account = getattr(self.store, "paper_account", None)
            if callable(paper_account):
                account = paper_account() or {}
                paper_position = next(
                    (item for item in account.get("positions", []) if str(item.get("symbol") or "").strip().upper() == symbol),
                    None,
                )
            return self._json_safe({"holding": holding, "paper_position": paper_position})

        if name == "get_risk_snapshot":
            return self._json_safe(self.store.cached_risk(symbol))

        if name == "get_company_fundamentals":
            return self._json_safe(self.store.instrument_metadata(symbol))

        if name in {"get_announcement_timeline", "get_company_news"}:
            limit = max(1, min(int(args.get("limit") or 20), 50))
            content = self.store.cached_content([symbol], limit=max(limit * 3, limit))
            if name == "get_announcement_timeline":
                rows = [
                    item for item in content
                    if str(item.get("source_type") or "").lower() == "announcement"
                    or str(item.get("id") or "").startswith("announcement-")
                ]
            else:
                rows = [
                    item for item in content
                    if str(item.get("source_type") or "").lower() != "announcement"
                    and not str(item.get("id") or "").startswith("announcement-")
                ]
            return self._json_safe(rows[:limit])

        if name == "get_research_evidence":
            context_events = getattr(context, "events", ()) or ()
            events = [self._json_safe(item) for item in context_events]
            reports = self._optional_store_call(("research_reports", "latest_research_reports"), symbol, 5)
            return self._json_safe({"events": events, "research_reports": reports or []})

        if name == "get_research_thesis":
            thesis = self._optional_store_call(
                ("latest_research_thesis", "research_thesis", "research_thesis_versions"),
                symbol,
            )
            return self._json_safe(thesis)

        if name == "get_decision_report":
            reports = self.store.decision_reports(symbol, 1)
            return self._json_safe(reports[0] if reports else None)

        raise ValueError(f"unknown_tool:{name}")
