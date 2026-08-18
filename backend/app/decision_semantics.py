"""Phase-4 entry/position semantics derived from legacy policy candidates.

This adapter makes the intent of the existing action vocabulary explicit while
the legacy action remains the execution compatibility field.  In particular, a
non-entry candidate for a held position becomes HOLD, never REDUCE.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from app import decision_config as config

if TYPE_CHECKING:
    from app.decision_models import ActionCandidate, DecisionContext


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


__all__ = ["DecisionArbiter", "EntryDecision", "PositionDecision"]
