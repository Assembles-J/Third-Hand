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
PositionState = Literal["FLAT", "ENTRY_PENDING", "HOLDING", "REDUCE_PENDING", "EXIT_PENDING", "BLOCKED"]


class DecisionSemanticModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EntryDecision(DecisionSemanticModel):
    action: Literal["BUY", "WAIT", "BLOCKED"]
    decision_confidence: float = Field(ge=0, le=1)
    prior_state: Literal["FLAT"] = "FLAT"
    next_state: PositionState
    reason_codes: tuple[str, ...] = ()


class PositionDecision(DecisionSemanticModel):
    action: Literal["HOLD", "ADD", "REDUCE", "EXIT", "BLOCKED"]
    decision_confidence: float = Field(ge=0, le=1)
    prior_state: Literal["HOLDING"] = "HOLDING"
    next_state: PositionState
    reason_codes: tuple[str, ...] = ()


class DecisionArbiter:
    """Translate policy candidates by position state and bounded research input.

    Research can only veto *new* incremental risk when its deterministic
    aggregate is adverse and sufficiently evidenced. It cannot upgrade an
    action, invent a SELL/EXIT, or override a hard ActionPolicy gate.
    """

    version = config.DECISION_ARBITER_POLICY_VERSION

    def arbitrate(
        self,
        context: DecisionContext,
        candidates: tuple[ActionCandidate, ...],
        research_assessment=None,
    ) -> EntryDecision | PositionDecision:
        candidate = candidates[0] if candidates else None
        if candidate is None:
            if context.position is None:
                return EntryDecision(
                    action="BLOCKED",
                    decision_confidence=1,
                    next_state="BLOCKED",
                    reason_codes=("action_candidate_missing",),
                )
            return PositionDecision(
                action="BLOCKED",
                decision_confidence=1,
                next_state="BLOCKED",
                reason_codes=("action_candidate_missing",),
            )
        reasons = tuple(dict.fromkeys((*candidate.triggered_rule_ids, *candidate.blocked_reasons)))
        confidence = candidate.policy_score
        if context.position is None:
            if candidate.action == "OPEN":
                research_reason = self._adverse_new_risk_reason(research_assessment)
                if research_reason:
                    return EntryDecision(
                        action="WAIT",
                        decision_confidence=min(confidence, float(getattr(research_assessment, "evidence_confidence", 0.0))),
                        next_state="FLAT",
                        reason_codes=tuple(dict.fromkeys((*reasons, research_reason))),
                    )
                return EntryDecision(action="BUY", decision_confidence=confidence, next_state="ENTRY_PENDING", reason_codes=reasons)
            if candidate.action == "BLOCKED":
                return EntryDecision(action="BLOCKED", decision_confidence=confidence, next_state="BLOCKED", reason_codes=reasons)
            gate_reasons = self._gate_reasons(context, "OPEN")
            return EntryDecision(
                action="WAIT",
                decision_confidence=confidence,
                next_state="FLAT",
                reason_codes=tuple(dict.fromkeys((*reasons, *gate_reasons, f"legacy_candidate:{candidate.action}"))),
            )
        if candidate.action in {"ADD", "REDUCE", "EXIT", "HOLD"}:
            research_reason = self._adverse_new_risk_reason(research_assessment) if candidate.action == "ADD" else None
            if research_reason:
                return PositionDecision(
                    action="HOLD",
                    decision_confidence=min(confidence, float(getattr(research_assessment, "evidence_confidence", 0.0))),
                    next_state="HOLDING",
                    reason_codes=tuple(dict.fromkeys((*reasons, research_reason))),
                )
            next_state = {
                "ADD": "HOLDING", "HOLD": "HOLDING", "REDUCE": "REDUCE_PENDING", "EXIT": "EXIT_PENDING",
            }[candidate.action]
            return PositionDecision(action=candidate.action, decision_confidence=confidence, next_state=next_state, reason_codes=reasons)
        if candidate.action == "BLOCKED":
            return PositionDecision(action="BLOCKED", decision_confidence=confidence, next_state="BLOCKED", reason_codes=reasons)
        return PositionDecision(
            action="HOLD",
            decision_confidence=confidence,
            next_state="HOLDING",
            reason_codes=tuple(dict.fromkeys((*reasons, f"legacy_candidate:{candidate.action}", "position.no_reduce_without_position_risk_rule"))),
        )

    @staticmethod
    def _gate_reasons(context: DecisionContext, action: str) -> tuple[str, ...]:
        quality = getattr(context, "data_quality", None)
        gates = getattr(quality, "action_gates", ()) if quality is not None else ()
        gate = next((item for item in gates if item.action == action), None)
        return tuple(gate.reasons) if gate and gate.permission == "blocked" else ()

    @staticmethod
    def _adverse_new_risk_reason(research_assessment) -> str | None:
        if research_assessment is None:
            return None
        if str(getattr(research_assessment, "research_bias", "")).upper() != "ADVERSE":
            return None
        try:
            confidence = float(getattr(research_assessment, "evidence_confidence", 0.0))
        except (TypeError, ValueError):
            return None
        if confidence < config.RESEARCH_ADVERSE_MIN_EVIDENCE_CONFIDENCE:
            return None
        return "research.adverse_new_risk_veto"


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
    "DecisionArbiter", "EntryDecision", "FormalDecisionAction", "PositionDecision", "PositionState",
    "action_gate_for", "execution_side", "formal_action_from_report",
]
