"""Shared immutable primitives for N3 evaluation contracts.

These types describe auditable outcome state only. They do not resolve market
history, score a strategy, change a Formal Decision, or write paper fills.
"""
from __future__ import annotations

from enum import Enum
import hashlib
import json

from pydantic import BaseModel, ConfigDict


class EvaluationContract(BaseModel):
    """Frozen deterministic base used by N3 policy/outcome records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def canonical_payload(self) -> dict[str, object]:
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
    def contract_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class OutcomeStatus(str, Enum):
    """Lifecycle shared by decision, execution and episode outcomes."""

    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INVALID = "INVALID"


class ExecutionDisposition(str, Enum):
    """What happened to an action at the execution boundary."""

    PENDING = "PENDING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EXECUTED = "EXECUTED"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    BLOCKED = "BLOCKED"
    DEFERRED = "DEFERRED"
    EXPIRED = "EXPIRED"


class ActionOutcomeClass(str, Enum):
    """Terminal action-quality label assigned only after outcome resolution."""

    FAVORABLE = "FAVORABLE"
    UNFAVORABLE = "UNFAVORABLE"
    MIXED = "MIXED"
    NEUTRAL = "NEUTRAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ActionOutcomeDimension(str, Enum):
    """Versioned questions used to judge each Formal Action."""

    ENTRY_QUALITY = "ENTRY_QUALITY"
    FORWARD_RETURN = "FORWARD_RETURN"
    MFE_MAE = "MFE_MAE"
    TARGET_BEFORE_STOP = "TARGET_BEFORE_STOP"

    AVOIDED_LOSS = "AVOIDED_LOSS"
    MISSED_OPPORTUNITY = "MISSED_OPPORTUNITY"
    LATER_ENTRY_AVAILABILITY = "LATER_ENTRY_AVAILABILITY"

    CONTINUATION_QUALITY = "CONTINUATION_QUALITY"

    RISK_REDUCTION_QUALITY = "RISK_REDUCTION_QUALITY"
    AVOIDED_DOWNSIDE = "AVOIDED_DOWNSIDE"
    OPPORTUNITY_COST = "OPPORTUNITY_COST"

    EXIT_QUALITY = "EXIT_QUALITY"
    PREMATURE_EXIT_OPPORTUNITY_COST = "PREMATURE_EXIT_OPPORTUNITY_COST"

    GATE_CORRECTNESS = "GATE_CORRECTNESS"
    DATA_QUALITY_ATTRIBUTION = "DATA_QUALITY_ATTRIBUTION"


__all__ = [
    "ActionOutcomeClass",
    "ActionOutcomeDimension",
    "EvaluationContract",
    "ExecutionDisposition",
    "OutcomeStatus",
]
