"""Deterministic continuity policy for repeated formal decisions."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import TYPE_CHECKING, Mapping

from pydantic import BaseModel, ConfigDict

from app import decision_config as config
from app.decision_semantics import FormalDecisionAction, formal_action_from_report

if TYPE_CHECKING:
    from app.decision_models import DecisionContext


class DecisionMemory(BaseModel):
    """Auditable relationship between a decision and its prior episode state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prior_decision_id: str | None = None
    episode_id: str
    last_action: FormalDecisionAction
    position_age: int | None = None
    material_change: bool
    material_change_reason: str
    cooldown_until: str | None = None
    review_after: str | None = None
    invalidation_conditions: tuple[str, ...] = ()
    continuity_policy_version: str = config.DECISION_CONTINUITY_POLICY_VERSION


class DecisionContinuityPolicy:
    """Preserve a formal action when the decision inputs and hard gates agree."""

    version = config.DECISION_CONTINUITY_POLICY_VERSION

    def assess(
        self,
        context: DecisionContext,
        proposed_action: FormalDecisionAction,
        prior_report: Mapping[str, object] | None,
    ) -> tuple[FormalDecisionAction, DecisionMemory]:
        state = "HOLDING" if context.position is not None else "FLAT"
        if not prior_report:
            return proposed_action, self._memory(
                context, state=state, action=proposed_action, prior=None,
                material=True, reason="initial_decision",
            )

        prior_action = formal_action_from_report(prior_report)
        prior_state = self._state_for_report(prior_report)
        gate_changed = self._gate_fingerprint(prior_report.get("data_quality")) != self._gate_fingerprint(context.data_quality.model_dump(mode="json"))
        input_changed = str(prior_report.get("input_hash") or "") != context.input_hash
        state_changed = prior_state != state
        if gate_changed:
            material, reason = True, "hard_gate_changed"
        elif state_changed:
            material, reason = True, "position_state_changed"
        elif input_changed:
            material, reason = True, "decision_input_changed"
        else:
            material, reason = False, "no_material_change"
        effective_action = proposed_action if material or proposed_action == prior_action else prior_action
        if effective_action != proposed_action:
            reason = "continuity_preserved_prior_action"
        return effective_action, self._memory(
            context, state=state, action=effective_action, prior=prior_report,
            material=material, reason=reason,
        )

    def _memory(self, context: DecisionContext, *, state: str, action: FormalDecisionAction,
                prior: Mapping[str, object] | None, material: bool, reason: str) -> DecisionMemory:
        prior_memory = prior.get("decision_memory") if isinstance(prior, Mapping) else None
        episode_id = (
            str(prior_memory.get("episode_id"))
            if isinstance(prior_memory, Mapping) and prior_memory.get("episode_id") and not material
            else self._episode_id(context.symbol, state, prior.get("decision_id") if prior else None)
        )
        generated_at = context.generated_at
        cooldown_until = (generated_at + timedelta(minutes=15)).isoformat() if action in {"BUY", "ADD", "REDUCE", "EXIT"} else None
        return DecisionMemory(
            prior_decision_id=str(prior.get("decision_id")) if prior and prior.get("decision_id") else None,
            episode_id=episode_id,
            last_action=action,
            position_age=None,
            material_change=material,
            material_change_reason=reason,
            cooldown_until=cooldown_until,
            review_after=(generated_at + timedelta(days=1)).isoformat(),
        )

    @staticmethod
    def _episode_id(symbol: str, state: str, seed: object) -> str:
        value = f"{symbol.strip().upper()}|{state}|{seed or 'initial'}"
        return f"episode-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"

    @staticmethod
    def _state_for_report(report: Mapping[str, object]) -> str:
        decision = report.get("position_decision") or report.get("entry_decision")
        if isinstance(decision, Mapping):
            return "HOLDING" if str(decision.get("prior_state") or "").upper() == "HOLDING" else "FLAT"
        return "HOLDING" if formal_action_from_report(report) in {"HOLD", "ADD", "REDUCE", "EXIT"} else "FLAT"

    @staticmethod
    def _gate_fingerprint(value: object) -> str:
        if isinstance(value, Mapping):
            gates = value.get("action_gates") or []
        else:
            gates = []
        return hashlib.sha256(json.dumps(gates, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


__all__ = ["DecisionContinuityPolicy", "DecisionMemory"]
