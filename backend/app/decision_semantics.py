"""Phase-4 entry/position semantics derived from legacy policy candidates.

This adapter makes the intent of the existing action vocabulary explicit while
the legacy action remains the execution compatibility field.  In particular, a
non-entry candidate for a held position becomes HOLD, never REDUCE.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

from app import decision_config as config

if TYPE_CHECKING:
    from app.decision_models import ActionCandidate, DecisionContext


FormalDecisionAction = Literal["BUY", "WAIT", "HOLD", "ADD", "REDUCE", "EXIT", "BLOCKED"]


class DecisionSemanticModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EntryDecision(DecisionSemanticModel):
    action: Literal["BUY", "WAIT", "BLOCKED"]
    decision_confidence: float = Field(ge=0, le=1)
    reason_codes: tuple[str, ...] = ()


class PositionDecision(DecisionSemanticModel):
    action: Literal["HOLD", "ADD", "REDUCE", "EXIT", "BLOCKED"]
    decision_confidence: float = Field(ge=0, le=1)
    reason_codes: tuple[str, ...] = ()


class DecisionArbiter:
    """Translate candidate actions by portfolio state; ResearchAssessment is not input."""

    version = config.DECISION_ARBITER_POLICY_VERSION

    def arbitrate(
        self,
        context: DecisionContext,
        candidates: tuple[ActionCandidate, ...],
    ) -> EntryDecision | PositionDecision:
        candidate = candidates[0] if candidates else None
        if candidate is None:
            if context.position is None:
                return EntryDecision(
                    action="BLOCKED",
                    decision_confidence=1,
                    reason_codes=("action_candidate_missing",),
                )
            return PositionDecision(
                action="BLOCKED",
                decision_confidence=1,
                reason_codes=("action_candidate_missing",),
            )
        reasons = tuple(dict.fromkeys((*candidate.triggered_rule_ids, *candidate.blocked_reasons)))
        confidence = candidate.policy_score
        if context.position is None:
            if candidate.action == "OPEN":
                return EntryDecision(action="BUY", decision_confidence=confidence, reason_codes=reasons)
            if candidate.action == "BLOCKED":
                return EntryDecision(action="BLOCKED", decision_confidence=confidence, reason_codes=reasons)
            return EntryDecision(
                action="WAIT",
                decision_confidence=confidence,
                reason_codes=tuple(dict.fromkeys((*reasons, f"legacy_candidate:{candidate.action}"))),
            )
        if candidate.action in {"ADD", "REDUCE", "EXIT", "HOLD"}:
            return PositionDecision(action=candidate.action, decision_confidence=confidence, reason_codes=reasons)
        if candidate.action == "BLOCKED":
            return PositionDecision(action="BLOCKED", decision_confidence=confidence, reason_codes=reasons)
        return PositionDecision(
            action="HOLD",
            decision_confidence=confidence,
            reason_codes=tuple(dict.fromkeys((*reasons, f"legacy_candidate:{candidate.action}", "position.no_reduce_without_position_risk_rule"))),
        )


def formal_action_from_report(report: Mapping[str, object]) -> FormalDecisionAction:
    """Read the semantic authority from a report with a safe legacy fallback."""
    allowed = {"BUY", "WAIT", "HOLD", "ADD", "REDUCE", "EXIT", "BLOCKED"}
    formal = str(report.get("formal_action") or "").upper()
    if formal in allowed:
        return formal  # type: ignore[return-value]
    for field in ("entry_decision", "position_decision"):
        decision = report.get(field)
        if isinstance(decision, Mapping):
            action = str(decision.get("action") or "").upper()
            if action in allowed:
                return action  # type: ignore[return-value]
    legacy = str(report.get("action") or "").upper()
    return {
        "OPEN": "BUY", "WATCH": "WAIT", "HOLD": "HOLD", "ADD": "ADD",
        "REDUCE": "REDUCE", "EXIT": "EXIT", "BLOCKED": "BLOCKED",
    }.get(legacy, "BLOCKED")  # type: ignore[return-value]


def execution_side(formal_action: FormalDecisionAction) -> Literal["BUY", "SELL"] | None:
    if formal_action in {"BUY", "ADD"}:
        return "BUY"
    if formal_action in {"REDUCE", "EXIT"}:
        return "SELL"
    return None


def action_gate_for(formal_action: FormalDecisionAction) -> Literal["OPEN", "ADD"] | None:
    return {"BUY": "OPEN", "ADD": "ADD"}.get(formal_action)  # type: ignore[return-value]


__all__ = [
    "DecisionArbiter", "EntryDecision", "FormalDecisionAction", "PositionDecision",
    "action_gate_for", "execution_side", "formal_action_from_report",
]
