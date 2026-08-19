"""Decision Workspace read model over already-authoritative decision state.

This service is intentionally read-only. It composes persisted formal decision,
DecisionMemory and paper-ledger projections for product visibility; it does not
re-run policy, mutate continuity, calculate sellability, or execute trades.
"""
from __future__ import annotations

from collections.abc import Mapping


class DecisionWorkspaceService:
    def __init__(self, store) -> None:
        self.store = store

    def latest(self, symbol: str) -> dict[str, object]:
        normalized = str(symbol or "").strip().upper()
        if not normalized:
            raise ValueError("symbol is required")

        reports = list(self.store.decision_reports(normalized, 10) or [])
        if not reports:
            raise KeyError("decision workspace not found")
        current = dict(reports[0])
        memory = current.get("decision_memory")
        memory_map = dict(memory) if isinstance(memory, Mapping) else {}
        prior = self._prior_report(reports, memory_map.get("prior_decision_id"))

        paper_account = self.store.paper_account() or {}
        positions = paper_account.get("positions") or [] if isinstance(paper_account, Mapping) else []
        position = next(
            (dict(item) for item in positions if isinstance(item, Mapping) and str(item.get("symbol") or "").strip().upper() == normalized),
            None,
        )
        deferral_loader = getattr(self.store, "paper_execution_deferrals", None)
        deferrals = (
            list(deferral_loader(symbol=normalized, state="active", limit=20) or [])
            if callable(deferral_loader)
            else []
        )

        quality = current.get("data_quality")
        quality_map = dict(quality) if isinstance(quality, Mapping) else {}
        current_action = self._formal_action(current)
        prior_action = self._formal_action(prior) if prior is not None else None

        return {
            "symbol": normalized,
            "name": str(current.get("name") or normalized),
            "decision_id": str(current.get("decision_id") or ""),
            "generated_at": current.get("generated_at"),
            "formal_action": current_action,
            "summary": str(current.get("summary") or ""),
            "strategy": current.get("strategy"),
            "timeframe_authority": current.get("timeframe_authority"),
            "what_changed": {
                "prior_decision_id": memory_map.get("prior_decision_id"),
                "prior_action": prior_action,
                "current_action": current_action,
                "input_changed": bool(memory_map.get("input_changed", False)),
                "material_change": bool(memory_map.get("material_change", False)),
                "material_change_reason": str(memory_map.get("material_change_reason") or "unavailable"),
                "material_change_components": list(memory_map.get("material_change_components") or []),
                "position_age": memory_map.get("position_age"),
                "cooldown_until": memory_map.get("cooldown_until"),
                "review_after": memory_map.get("review_after"),
                "invalidation_conditions": list(memory_map.get("invalidation_conditions") or []),
                "continuity_policy_version": memory_map.get("continuity_policy_version"),
            },
            "paper_risk": {
                "position_present": position is not None,
                "quantity": position.get("quantity") if position else None,
                "sellable_quantity": position.get("sellable_quantity") if position else None,
                "locked_quantity": position.get("locked_quantity") if position else None,
                "next_eligible_sell_at": position.get("next_eligible_sell_at") if position else None,
                "active_deferrals": [
                    {
                        "decision_id": item.get("decision_id"),
                        "action": item.get("action"),
                        "reason_code": item.get("reason_code"),
                        "next_eligible_at": item.get("next_eligible_at"),
                        "state": item.get("state"),
                    }
                    for item in deferrals
                    if isinstance(item, Mapping)
                ],
            },
            "data_quality": {
                "status": quality_map.get("status"),
                "score_percent": quality_map.get("score_percent"),
                "missing_fields": list(quality_map.get("missing_fields") or []),
                "stale_fields": list(quality_map.get("stale_fields") or []),
                "warnings": list(quality_map.get("warnings") or []),
            },
        }

    @staticmethod
    def _formal_action(report: Mapping[str, object] | None) -> str | None:
        if not report:
            return None
        value = report.get("formal_action") or report.get("action")
        return str(value).upper() if value is not None else None

    @staticmethod
    def _prior_report(reports: list[object], prior_decision_id: object) -> Mapping[str, object] | None:
        target = str(prior_decision_id or "")
        if target:
            for item in reports[1:]:
                if isinstance(item, Mapping) and str(item.get("decision_id") or "") == target:
                    return item
        return reports[1] if len(reports) > 1 and isinstance(reports[1], Mapping) else None


__all__ = ["DecisionWorkspaceService"]
