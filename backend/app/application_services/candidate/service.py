"""Candidate-management use cases.

This service schedules research effort only.  It never calls ActionPolicy,
PositionSizing or execution and every activation rule is RESEARCH_ONLY.
"""
from __future__ import annotations

from datetime import datetime

from app.domain.candidate.activation import validate_rule
from app.domain.candidate.lifecycle import (
    NEW,
    transition_decision,
    validate_priority,
    validate_source_type,
    validate_status,
)


class CandidateService:
    def __init__(self, repository) -> None:
        self.repository = repository

    @staticmethod
    def _symbol(value: str) -> str:
        symbol = str(value or "").strip().upper()
        if not symbol:
            raise ValueError("candidate symbol must not be blank")
        return symbol

    def add_manual_candidate(
        self,
        *,
        symbol: str,
        name: str,
        research_priority: str = "L2",
        reason: str = "",
    ) -> dict[str, object]:
        symbol = self._symbol(symbol)
        priority = validate_priority(research_priority)
        source_type = validate_source_type("USER_ADDED")
        existing = self.repository.get(symbol)
        status = str(existing.get("lifecycle_status")) if existing else NEW
        if status == "ARCHIVED":
            status = NEW
        result = self.repository.upsert_entry(
            symbol=symbol,
            name=str(name or symbol).strip() or symbol,
            research_priority=priority,
            lifecycle_status=status,
            reason=reason,
        )
        self.repository.add_source(
            symbol=symbol,
            source_type=source_type,
            source_key="manual",
            reason=reason,
        )
        self.repository.record_event(
            symbol=symbol,
            event_type="manual_candidate_added",
            detail={"research_priority": priority, "reason": reason},
        )
        return self.repository.get(symbol) or result

    def transition(
        self,
        symbol: str,
        *,
        lifecycle_status: str,
        reason: str | None = None,
        cooldown_until: str | None = None,
    ) -> dict[str, object]:
        symbol = self._symbol(symbol)
        current = self.repository.get(symbol)
        if not current:
            raise KeyError(symbol)
        target = validate_status(lifecycle_status)
        decision = transition_decision(str(current["lifecycle_status"]), target)
        if not decision.allowed:
            raise ValueError(decision.reason)
        if cooldown_until:
            datetime.fromisoformat(cooldown_until)
        updated = self.repository.update_lifecycle(
            symbol=symbol,
            lifecycle_status=target,
            reason=reason,
            cooldown_until=cooldown_until,
        )
        self.repository.record_event(
            symbol=symbol,
            event_type="lifecycle_transition",
            from_status=decision.from_status,
            to_status=decision.to_status,
            detail={"reason": reason or decision.reason, "cooldown_until": cooldown_until},
        )
        return updated

    def change_priority(self, symbol: str, *, research_priority: str) -> dict[str, object]:
        symbol = self._symbol(symbol)
        priority = validate_priority(research_priority)
        updated = self.repository.update_priority(symbol=symbol, research_priority=priority)
        self.repository.record_event(
            symbol=symbol,
            event_type="priority_changed",
            detail={"research_priority": priority},
        )
        return updated

    def add_activation_rule(
        self,
        symbol: str,
        *,
        rule_type: str,
        metric: str,
        operator: str,
        value: object,
        reason: str,
        source: str = "user",
    ) -> dict[str, object]:
        symbol = self._symbol(symbol)
        normalized_type, metric, operator, value = validate_rule(
            rule_type=rule_type,
            metric=metric,
            operator=operator,
            value=value,
        )
        rule = self.repository.add_activation_rule(
            symbol=symbol,
            rule_type=normalized_type,
            metric=metric,
            operator=operator,
            value=value,
            reason=reason,
            source=source,
        )
        self.repository.record_event(
            symbol=symbol,
            event_type="activation_rule_added",
            detail={
                "rule_id": rule.get("rule_id"),
                "rule_type": normalized_type,
                "metric": metric,
                "operator": operator,
                "value": value,
                "usage_scope": "RESEARCH_ONLY",
            },
        )
        return rule

    def set_activation_rule_enabled(self, symbol: str, rule_id: str, *, enabled: bool) -> dict[str, object]:
        symbol = self._symbol(symbol)
        rule = self.repository.activation_rule(rule_id)
        if not rule or str(rule["symbol"]).upper() != symbol:
            raise KeyError(rule_id)
        updated = self.repository.set_activation_rule_enabled(rule_id, enabled=enabled)
        self.repository.record_event(
            symbol=symbol,
            event_type="activation_rule_enabled" if enabled else "activation_rule_disabled",
            detail={"rule_id": rule_id},
        )
        return updated

    def record_analysis_result(
        self,
        symbol: str,
        *,
        analysis_version: str,
        thesis_hash: str | None,
        summary: str,
        lifecycle_status: str,
        cooldown_until: str | None,
    ) -> dict[str, object]:
        symbol = self._symbol(symbol)
        target = validate_status(lifecycle_status)
        current = self.repository.get(symbol)
        if not current:
            raise KeyError(symbol)
        decision = transition_decision(str(current["lifecycle_status"]), target)
        if not decision.allowed:
            raise ValueError(decision.reason)
        if not str(analysis_version or "").strip():
            raise ValueError("analysis_version must not be blank")
        if cooldown_until:
            datetime.fromisoformat(cooldown_until)
        return self.repository.record_analysis_result(
            symbol=symbol,
            analysis_version=str(analysis_version).strip(),
            thesis_hash=str(thesis_hash).strip() if thesis_hash else None,
            summary=summary,
            cooldown_until=cooldown_until,
            lifecycle_status=target,
        )

    def get(self, symbol: str) -> dict[str, object]:
        result = self.repository.get(self._symbol(symbol))
        if not result:
            raise KeyError(symbol)
        return result

    def list(self, **filters) -> list[dict[str, object]]:
        status = filters.get("lifecycle_status")
        priority = filters.get("research_priority")
        if status:
            filters["lifecycle_status"] = validate_status(str(status))
        if priority:
            filters["research_priority"] = validate_priority(str(priority))
        return self.repository.list(**filters)
