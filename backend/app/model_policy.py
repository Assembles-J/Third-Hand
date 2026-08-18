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

    def recover(
        self,
        previous: ModelSelection,
        *,
        reason: str,
        reasoning_model: str | None,
    ) -> ModelSelection:
        """Return the one bounded recovery route for a failed structured reply.

        A retry is deliberately not a blind replay: schema/semantic failures
        promote Flash to the configured reasoning model, while a length-limited
        thinking reply switches to a larger non-thinking structured pass so
        internal reasoning cannot consume the entire JSON output budget.
        """
        reasons = tuple(dict.fromkeys((*previous.escalation_reasons, reason)))
        if reason in {"output_truncated", "empty_content"}:
            if previous.tier == "PRO_STRUCTURED_RECOVERY":
                return previous
            return ModelSelection(
                tier="PRO_STRUCTURED_RECOVERY",
                model=reasoning_model or previous.model,
                thinking=False,
                max_tokens=min(4800, max(2400, previous.max_tokens * 2)),
                escalation_reasons=reasons,
            )
        if reason == "schema_or_semantic_validation_failed":
            if previous.tier == "FLASH_DEFAULT":
                return ModelSelection(
                    tier="PRO_ESCALATION",
                    model=reasoning_model or previous.model,
                    thinking=True,
                    max_tokens=min(3200, max(1200, previous.max_tokens)),
                    escalation_reasons=reasons,
                )
            if previous.tier == "PRO_ESCALATION":
                return ModelSelection(
                    tier="PRO_STRUCTURED_RECOVERY",
                    model=reasoning_model or previous.model,
                    thinking=False,
                    max_tokens=min(4800, max(2400, previous.max_tokens)),
                    escalation_reasons=reasons,
                )
        return previous


__all__ = ["ModelPolicy", "ModelSelection"]
