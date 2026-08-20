"""Immutable experiment identity and policy-lineage contracts for N3 evaluation.

ExperimentDefinition identifies exactly which strategy/policy configuration an
evaluation belongs to. It is metadata only: it cannot score decisions, mutate
the formal strategy, create paper orders, or write fills.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
import hashlib
import json

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ExperimentType(str, Enum):
    FORMAL_OBSERVATION = "FORMAL_OBSERVATION"
    FORMAL_REPLAY = "FORMAL_REPLAY"
    AI_SHADOW = "AI_SHADOW"
    AI_PAPER = "AI_PAPER"


class ExperimentStatus(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class ExperimentDefinition(BaseModel):
    """Frozen identity for one experiment version.

    Mutable runtime state belongs in later experiment-run/account models. A
    stored ``(experiment_id, experiment_version)`` definition is append-only.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: str
    experiment_version: str
    experiment_type: ExperimentType
    status: ExperimentStatus

    strategy_id: str
    strategy_version: str

    agent_id: str | None = None
    agent_version: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    prompt_hash: str | None = None

    evidence_schema_version: str
    universe_policy_version: str
    point_in_time_policy_version: str

    action_policy_version: str | None = None
    timeframe_policy_version: str | None = None
    risk_policy_version: str
    sizing_policy_version: str
    execution_policy_version: str

    outcome_policy_version: str
    benchmark_policy_version: str
    sample_quality_policy_version: str
    evaluation_policy_version: str

    initial_capital: Decimal | None = None
    started_at: datetime
    ended_at: datetime | None = None
    created_at: datetime

    @field_validator(
        "experiment_id",
        "experiment_version",
        "strategy_id",
        "strategy_version",
        "evidence_schema_version",
        "universe_policy_version",
        "point_in_time_policy_version",
        "risk_policy_version",
        "sizing_policy_version",
        "execution_policy_version",
        "outcome_policy_version",
        "benchmark_policy_version",
        "sample_quality_policy_version",
        "evaluation_policy_version",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("required experiment identity/version fields must not be blank")
        return normalized

    @field_validator(
        "agent_id",
        "agent_version",
        "model_provider",
        "model_name",
        "model_version",
        "prompt_version",
        "prompt_hash",
        "action_policy_version",
        "timeframe_policy_version",
    )
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("started_at", "ended_at", "created_at")
    @classmethod
    def _timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("experiment timestamps must include timezone information")
        return value

    @field_validator("initial_capital")
    @classmethod
    def _initial_capital_non_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("initial_capital must be >= 0")
        return value

    @model_validator(mode="after")
    def _validate_contract(self) -> "ExperimentDefinition":
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at must not be earlier than started_at")

        formal_types = {ExperimentType.FORMAL_OBSERVATION, ExperimentType.FORMAL_REPLAY}
        ai_fields = (
            self.agent_id,
            self.agent_version,
            self.model_provider,
            self.model_name,
            self.model_version,
            self.prompt_version,
            self.prompt_hash,
        )
        if self.experiment_type in formal_types:
            if any(value is not None for value in ai_fields):
                raise ValueError("formal experiments must not carry AI-agent/model lineage")
            if not self.action_policy_version or not self.timeframe_policy_version:
                raise ValueError(
                    "formal experiments require action_policy_version and timeframe_policy_version"
                )
        else:
            required_ai = {
                "agent_id": self.agent_id,
                "agent_version": self.agent_version,
                "model_provider": self.model_provider,
                "model_name": self.model_name,
                "model_version": self.model_version,
                "prompt_version": self.prompt_version,
                "prompt_hash": self.prompt_hash,
            }
            missing = [name for name, value in required_ai.items() if not value]
            if missing:
                raise ValueError(f"AI experiments require lineage fields: {', '.join(missing)}")

        return self

    def canonical_payload(self) -> dict[str, object]:
        """Return the stable JSON-compatible representation used for lineage."""
        return self.model_dump(mode="json", exclude_none=False)

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @property
    def definition_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


__all__ = ["ExperimentDefinition", "ExperimentStatus", "ExperimentType"]
