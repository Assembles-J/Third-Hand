"""Deterministic continuity policy for repeated formal decisions."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Mapping

from pydantic import BaseModel, ConfigDict, Field

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
    input_changed: bool = False
    material_change: bool
    material_change_reason: str
    material_fingerprint: dict[str, object] = Field(default_factory=dict)
    material_change_components: tuple[str, ...] = ()
    cooldown_until: str | None = None
    review_after: str | None = None
    invalidation_conditions: tuple[str, ...] = ()
    continuity_policy_version: str = config.DECISION_CONTINUITY_POLICY_VERSION


class DecisionContinuityPolicy:
    """Preserve a formal action until a strategy-relevant state changes."""

    version = config.DECISION_CONTINUITY_POLICY_VERSION

    def assess(
        self,
        context: DecisionContext,
        proposed_action: FormalDecisionAction,
        prior_report: Mapping[str, object] | None,
        research_assessment=None,
        timeframe_state: Mapping[str, object] | None = None,
    ) -> tuple[FormalDecisionAction, DecisionMemory]:
        state = "HOLDING" if context.position is not None else "FLAT"
        fingerprint = self._material_fingerprint(
            context,
            research_assessment,
            timeframe_state=timeframe_state,
        )
        if not prior_report:
            return proposed_action, self._memory(
                context, state=state, action=proposed_action, prior=None,
                input_changed=True, material=True, reason="initial_decision",
                fingerprint=fingerprint, components=("initial_decision",),
            )

        prior_action = formal_action_from_report(prior_report)
        prior_state = self._state_for_report(prior_report)
        gate_changed = self._gate_fingerprint(prior_report.get("data_quality")) != self._gate_fingerprint(context.data_quality.model_dump(mode="json"))
        input_changed = str(prior_report.get("input_hash") or "") != context.input_hash
        state_changed = prior_state != state
        prior_fingerprint = self._prior_fingerprint(prior_report)
        if gate_changed:
            material, reason, components = True, "hard_gate_changed", ("action_gates",)
        elif state_changed:
            material, reason, components = True, "position_state_changed", ("position_state",)
        elif prior_fingerprint is None:
            # Historical reports predate the material fingerprint. Preserve the
            # prior safety behavior once during migration, then persist the new
            # fingerprint for all subsequent comparisons.
            material = input_changed
            reason = "legacy_prior_input_changed" if input_changed else "no_material_change"
            components = ("legacy_fingerprint_unavailable",) if input_changed else ()
        elif prior_fingerprint != fingerprint:
            components = self._changed_components(prior_fingerprint, fingerprint)
            material, reason = True, "material_fingerprint_changed"
        else:
            material, reason, components = False, "no_material_change", ()
        effective_action = proposed_action if material or proposed_action == prior_action else prior_action
        if effective_action != proposed_action:
            reason = "continuity_preserved_prior_action"
        return effective_action, self._memory(
            context, state=state, action=effective_action, prior=prior_report,
            input_changed=input_changed, material=material, reason=reason,
            fingerprint=fingerprint, components=components,
        )

    def _memory(self, context: DecisionContext, *, state: str, action: FormalDecisionAction,
                prior: Mapping[str, object] | None, input_changed: bool, material: bool,
                reason: str, fingerprint: dict[str, object], components: tuple[str, ...]) -> DecisionMemory:
        prior_memory = prior.get("decision_memory") if isinstance(prior, Mapping) else None
        entry_episode_id = getattr(getattr(context, "position", None), "entry_episode_id", None)
        episode_id = (
            str(entry_episode_id)
            if entry_episode_id
            else (
            str(prior_memory.get("episode_id"))
            if isinstance(prior_memory, Mapping) and prior_memory.get("episode_id") and not material
            else self._episode_id(context.symbol, state, prior.get("decision_id") if prior else None)
            )
        )
        generated_at = context.generated_at
        cooldown_until = (generated_at + timedelta(minutes=15)).isoformat() if action in {"BUY", "ADD", "REDUCE", "EXIT"} else None
        return DecisionMemory(
            prior_decision_id=str(prior.get("decision_id")) if prior and prior.get("decision_id") else None,
            episode_id=episode_id,
            last_action=action,
            position_age=self._position_age(context),
            input_changed=input_changed,
            material_change=material,
            material_change_reason=reason,
            material_fingerprint=fingerprint,
            material_change_components=components,
            cooldown_until=cooldown_until,
            review_after=(generated_at + timedelta(days=1)).isoformat(),
        )

    @staticmethod
    def _episode_id(symbol: str, state: str, seed: object) -> str:
        value = f"{symbol.strip().upper()}|{state}|{seed or 'initial'}"
        return f"episode-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"

    @staticmethod
    def _position_age(context: DecisionContext) -> int | None:
        opened_at = getattr(getattr(context, "position", None), "opened_at", None)
        if not opened_at:
            return None
        try:
            opened = datetime.fromisoformat(str(opened_at).replace("Z", "+00:00"))
            if opened.tzinfo is None:
                opened = opened.replace(tzinfo=context.generated_at.tzinfo)
            return max(0, (context.generated_at - opened).days)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _material_fingerprint(
        context: DecisionContext,
        research_assessment=None,
        *,
        timeframe_state: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        """Return only strategy-relevant state; never include quote/bar timestamps.

        ``input_hash`` remains the complete audit hash. This compact projection
        answers the different question of whether a new conclusion is allowed
        to replace the prior episode's formal action. Multi-timeframe policy may
        contribute only its discrete approved states, never raw bar timestamps,
        prices, source hashes or retrieval times.
        """
        position = getattr(context, "position", None)
        plan = getattr(context, "trade_plan", None)
        quote = getattr(context, "quote", None)
        invalidation = getattr(plan, "invalidation_price", None) if plan is not None else None
        try:
            price_state = (
                "NO_INVALIDATION"
                if invalidation is None or quote is None or getattr(quote, "price", None) is None
                else "AT_OR_BELOW_INVALIDATION"
                if float(quote.price) <= float(invalidation)
                else "ABOVE_INVALIDATION"
            )
        except (TypeError, ValueError):
            price_state = "INVALIDATION_UNAVAILABLE"
        quality = getattr(context, "data_quality", None)
        technical = getattr(context, "technical", None)
        regime = getattr(context, "market_regime", None)
        risk = getattr(context, "risk", None)
        events = getattr(context, "events", ()) or ()
        event_state = tuple(sorted(
            f"{getattr(item, 'event_type', 'unknown')}:{getattr(item, 'lifecycle', 'unknown')}:{getattr(item, 'scheduled_at', None)}"
            for item in events
            if bool(getattr(item, "policy_eligible", False))
        ))
        research_veto_state = "UNAVAILABLE"
        if research_assessment is not None:
            try:
                adverse = str(getattr(research_assessment, "research_bias", "")).upper() == "ADVERSE"
                evidenced = float(getattr(research_assessment, "evidence_confidence", 0.0)) >= config.RESEARCH_ADVERSE_MIN_EVIDENCE_CONFIDENCE
                research_veto_state = "ADVERSE_NEW_RISK_VETO" if adverse and evidenced else "NO_ADVERSE_NEW_RISK_VETO"
            except (TypeError, ValueError):
                research_veto_state = "UNAVAILABLE"
        structured_conditions = getattr(plan, "structured_conditions", ()) if plan is not None else ()
        plan_contract = {
            "plan_id": getattr(plan, "plan_id", None), "version": getattr(plan, "version", None),
            "enabled": getattr(plan, "enabled", None), "invalidation_price": invalidation,
            "conditions": structured_conditions,
        }
        approved_timeframe_state = dict(timeframe_state or {})
        return {
            "position_state": "HOLDING" if position is not None else "FLAT",
            "position_quantity": float(getattr(position, "quantity", 0.0)) if position is not None else 0.0,
            "quality_status": getattr(quality, "status", "unknown"),
            "action_gate_hash": DecisionContinuityPolicy._gate_fingerprint(
                quality.model_dump(mode="json") if quality is not None and hasattr(quality, "model_dump") else {}
            ),
            "plan_contract_hash": hashlib.sha256(json.dumps(plan_contract, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest(),
            "price_state": price_state,
            "technical_state": tuple(getattr(technical, field, None) for field in ("trend", "trend_label", "rsi_state")),
            "risk_level": getattr(risk, "risk_level", None),
            "market_regime": (getattr(regime, "status", None), getattr(regime, "regime", None)),
            "event_state": event_state,
            "research_veto_state": research_veto_state,
            "timeframe_policy_state": approved_timeframe_state,
        }

    @staticmethod
    def _prior_fingerprint(report: Mapping[str, object]) -> dict[str, object] | None:
        memory = report.get("decision_memory")
        fingerprint = memory.get("material_fingerprint") if isinstance(memory, Mapping) else None
        return dict(fingerprint) if isinstance(fingerprint, Mapping) else None

    @staticmethod
    def _changed_components(previous: Mapping[str, object], current: Mapping[str, object]) -> tuple[str, ...]:
        return tuple(key for key in sorted(set(previous) | set(current)) if previous.get(key) != current.get(key))

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
