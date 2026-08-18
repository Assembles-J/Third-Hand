"""Strict schemas for v3 Atomic Evidence shadow mode.

These records describe source-linked facts, deterministic data availability and
cross-source conflicts. They are deliberately action-free: Phase 2 may observe
and persist them, but ActionPolicy and execution must not consume them yet.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AtomicPolarity = Literal[
    "SUPPORTIVE",
    "ADVERSE",
    "NEUTRAL_MATERIAL",
    "CONFLICT",
    "MISSING",
]
FreshnessStatus = Literal["fresh", "stale", "unknown", "unavailable"]
AvailabilityStatus = Literal["available", "degraded", "missing", "stale", "conflicted"]
Materiality = Literal["low", "medium", "high"]
ComparisonAdequacy = Literal["adequate", "partial", "not_applicable", "unknown"]


class AtomicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AtomicFactRecord(AtomicModel):
    fact_id: str
    symbol: str
    market: str | None = None
    domain: str
    dimension: str
    metric: str
    value: float | str | bool | None = None
    unit: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    comparison_type: str | None = None
    source_evidence_id: str | None = None
    source_timestamp: str | None = None
    observed_at: datetime
    freshness_status: FreshnessStatus
    polarity: AtomicPolarity
    materiality: Materiality
    comparison_adequacy: ComparisonAdequacy
    confidence: float = Field(ge=0, le=1)
    provenance_hash: str = Field(pattern="^[a-f0-9]{64}$")


class EvidenceAvailabilityRecord(AtomicModel):
    capability: str
    status: AvailabilityStatus
    reason_codes: tuple[str, ...] = ()
    source_keys: tuple[str, ...] = ()


class EvidenceConflictRecord(AtomicModel):
    conflict_id: str
    code: str
    affected_sources: tuple[str, ...]
    severity: Literal["low", "medium", "high"]
    policy_effect: str


class AtomicEvidenceSnapshot(AtomicModel):
    version: str
    context_id: str
    context_input_hash: str
    symbol: str
    market: str | None = None
    generated_at: datetime
    facts: tuple[AtomicFactRecord, ...]
    availability: tuple[EvidenceAvailabilityRecord, ...]
    conflicts: tuple[EvidenceConflictRecord, ...]
    snapshot_hash: str = Field(pattern="^[a-f0-9]{64}$")
    shadow_mode: Literal[True] = True


__all__ = [
    "AtomicEvidenceSnapshot",
    "AtomicFactRecord",
    "AtomicPolarity",
    "EvidenceAvailabilityRecord",
    "EvidenceConflictRecord",
]
