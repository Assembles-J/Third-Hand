"""Versioned, deterministic model-routing policy for research explanation only."""
from __future__ import annotations

from dataclasses import dataclass

from app import decision_config as config


@dataclass(frozen=True)
class ModelSelection:
    tier: str
    model: str | None
    thinking: bool
    max_tokens: int
    escalation_reasons: tuple[str, ...] = ()


class ModelPolicy:
    """Choose a model tier from evidence complexity, never from an action."""

    version = config.MODEL_POLICY_VERSION

    def select(self, atomic_evidence, *, default_model: str | None, reasoning_model: str | None,
               default_max_tokens: int) -> ModelSelection:
        conflicts = tuple(getattr(atomic_evidence, "conflicts", ()) or ())
        facts = tuple(getattr(atomic_evidence, "facts", ()) or ())
        reasons: list[str] = []
        if any(getattr(item, "severity", "") == "high" for item in conflicts):
            reasons.append("high_severity_evidence_conflict")
        if len(conflicts) >= 2:
            reasons.append("multiple_evidence_conflicts")
        if sum(1 for item in facts if getattr(item, "materiality", "") == "high") >= 4:
            reasons.append("high_materiality_fact_density")
        if reasons:
            return ModelSelection(
                tier="PRO_ESCALATION", model=reasoning_model, thinking=True,
                max_tokens=min(2400, max(1200, default_max_tokens)),
                escalation_reasons=tuple(reasons),
            )
        return ModelSelection(
            tier="FLASH_DEFAULT", model=default_model, thinking=False,
            max_tokens=default_max_tokens,
        )


__all__ = ["ModelPolicy", "ModelSelection"]
