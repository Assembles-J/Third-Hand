"""Deterministic Phase-3 aggregation of Atomic Evidence.

Research assessments describe evidence only.  They intentionally contain no
trade action and are therefore safe to attach to the legacy decision report
before Phase 4 introduces a DecisionArbiter.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app import decision_config as config
from app.atomic_models import AtomicEvidenceSnapshot, AtomicFactRecord


ResearchState = Literal[
    "SUPPORTIVE", "ADVERSE", "MIXED", "NEUTRAL", "INSUFFICIENT", "CONFLICT",
]


class ResearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DimensionAssessment(ResearchModel):
    dimension: str
    state: ResearchState
    score: float = Field(ge=-1, le=1)
    evidence_confidence: float = Field(ge=0, le=1)
    supportive_fact_ids: tuple[str, ...] = ()
    adverse_fact_ids: tuple[str, ...] = ()
    neutral_material_fact_ids: tuple[str, ...] = ()
    unresolved_fact_ids: tuple[str, ...] = ()


class FundamentalVector(ResearchModel):
    dimensions: tuple[DimensionAssessment, ...]
    aggregate_bias: ResearchState


class ResearchAssessment(ResearchModel):
    evidence_snapshot_hash: str
    fundamental_vector: FundamentalVector
    technical_state: DimensionAssessment
    event_state: DimensionAssessment
    market_context: DimensionAssessment
    research_bias: ResearchState
    evidence_confidence: float = Field(ge=0, le=1)
    research_conviction: float = Field(ge=0, le=1)
    # There is no DecisionArbiter until Phase 4.  A missing value is deliberate:
    # it prevents callers from mistaking research certainty for action certainty.
    decision_confidence: None = None
    supportive_fact_ids: tuple[str, ...] = ()
    adverse_fact_ids: tuple[str, ...] = ()
    neutral_material_fact_ids: tuple[str, ...] = ()
    unresolved_fact_ids: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    aggregation_policy_versions: dict[str, str]
    model_run_ids: tuple[str, ...] = ()


_FUNDAMENTAL_DIMENSIONS = {
    "growth": frozenset({
        "revenue", "revenue_yoy_percent", "gross_profit", "gross_profit_yoy_percent",
        "holder_profit", "holder_profit_yoy_percent",
    }),
    "profitability": frozenset({"gross_margin_percent", "net_margin_percent"}),
    "cashflow": frozenset({"operating_cashflow_to_sales_percent"}),
    "capital_efficiency": frozenset({"roe_percent", "roic_percent"}),
}


class DimensionAggregator:
    """Aggregate fact polarity without source-level sentiment or model output."""

    version = config.DIMENSION_AGGREGATION_POLICY_VERSION

    def assess(self, dimension: str, facts: tuple[AtomicFactRecord, ...], *, conflicted: bool = False) -> DimensionAssessment:
        facts = tuple(sorted(facts, key=lambda item: item.fact_id))
        supportive = tuple(item.fact_id for item in facts if item.polarity == "SUPPORTIVE")
        adverse = tuple(item.fact_id for item in facts if item.polarity == "ADVERSE")
        neutral = tuple(item.fact_id for item in facts if item.polarity == "NEUTRAL_MATERIAL")
        unresolved = tuple(item.fact_id for item in facts if item.polarity in {"CONFLICT", "MISSING"})
        directional = len(supportive) + len(adverse)
        if conflicted or any(item.polarity == "CONFLICT" for item in facts):
            state = "CONFLICT"
        elif supportive and adverse:
            state = "MIXED"
        elif supportive:
            state = "SUPPORTIVE"
        elif adverse:
            state = "ADVERSE"
        elif neutral:
            state = "NEUTRAL"
        else:
            state = "INSUFFICIENT"
        score = (len(supportive) - len(adverse)) / directional if directional else 0.0
        confidence = sum(item.confidence for item in facts) / len(facts) if facts else 0.0
        if state == "CONFLICT":
            confidence = min(confidence, .25)
        return DimensionAssessment(
            dimension=dimension,
            state=state,
            score=score,
            evidence_confidence=confidence,
            supportive_fact_ids=supportive,
            adverse_fact_ids=adverse,
            neutral_material_fact_ids=neutral,
            unresolved_fact_ids=unresolved,
        )


class ResearchAggregator:
    """Build a reproducible ResearchAssessment from a frozen Atomic snapshot."""

    version = config.RESEARCH_AGGREGATION_POLICY_VERSION

    def __init__(self, dimension_aggregator: DimensionAggregator | None = None) -> None:
        self.dimension_aggregator = dimension_aggregator or DimensionAggregator()

    def build(self, snapshot: AtomicEvidenceSnapshot) -> ResearchAssessment:
        facts_by_metric: dict[str, list[AtomicFactRecord]] = defaultdict(list)
        for fact in snapshot.facts:
            facts_by_metric[fact.metric].append(fact)
        research_snapshot_sources = {
            source
            for conflict in snapshot.conflicts
            for source in conflict.affected_sources
            if source.startswith("research_snapshot:")
        }

        fundamental_dimensions = tuple(
            self.dimension_aggregator.assess(
                name,
                tuple(fact for metric in metrics for fact in facts_by_metric.get(metric, ())),
                conflicted=any(
                    fact.source_evidence_id in research_snapshot_sources
                    for metric in metrics for fact in facts_by_metric.get(metric, ())
                ),
            )
            for name, metrics in _FUNDAMENTAL_DIMENSIONS.items()
        )
        fundamental = FundamentalVector(
            dimensions=fundamental_dimensions,
            aggregate_bias=self._state(fundamental_dimensions),
        )
        technical = self.dimension_aggregator.assess(
            "technical",
            tuple(fact for fact in snapshot.facts if fact.dimension.startswith("technical_")),
        )
        event = self.dimension_aggregator.assess(
            "event",
            tuple(fact for fact in snapshot.facts if fact.dimension == "corporate_event"),
        )
        market = self.dimension_aggregator.assess(
            "market",
            tuple(fact for fact in snapshot.facts if fact.dimension in {"market_context", "relative_strength"}),
        )
        states = (*fundamental_dimensions, technical, event, market)
        unresolved = tuple(sorted(
            f"availability:{item.capability}"
            for item in snapshot.availability
            if item.status in {"missing", "stale", "conflicted"}
        ))
        facts = tuple(sorted(snapshot.facts, key=lambda item: item.fact_id))
        evidence_confidence = sum(item.confidence for item in facts) / len(facts) if facts else 0.0
        if snapshot.conflicts:
            evidence_confidence = min(evidence_confidence, .25)
        directional = sum(
            len(item.supportive_fact_ids) + len(item.adverse_fact_ids)
            for item in states
        )
        conviction = min(1.0, directional / 4) * evidence_confidence
        return ResearchAssessment(
            evidence_snapshot_hash=snapshot.snapshot_hash,
            fundamental_vector=fundamental,
            technical_state=technical,
            event_state=event,
            market_context=market,
            research_bias="CONFLICT" if snapshot.conflicts else self._state(states),
            evidence_confidence=evidence_confidence,
            research_conviction=conviction,
            supportive_fact_ids=tuple(item.fact_id for item in facts if item.polarity == "SUPPORTIVE"),
            adverse_fact_ids=tuple(item.fact_id for item in facts if item.polarity == "ADVERSE"),
            neutral_material_fact_ids=tuple(item.fact_id for item in facts if item.polarity == "NEUTRAL_MATERIAL"),
            unresolved_fact_ids=unresolved,
            invalidation_conditions=tuple(sorted({
                *(f"conflict:{item.code}" for item in snapshot.conflicts),
                *(f"unavailable:{item.capability}" for item in snapshot.availability if item.status == "missing"),
            })),
            aggregation_policy_versions={
                "dimension": self.dimension_aggregator.version,
                "fundamental": config.FUNDAMENTAL_AGGREGATION_POLICY_VERSION,
                "research": self.version,
            },
        )

    @staticmethod
    def _state(assessments: tuple[DimensionAssessment, ...]) -> ResearchState:
        states = {item.state for item in assessments}
        if "CONFLICT" in states:
            return "CONFLICT"
        if "SUPPORTIVE" in states and "ADVERSE" in states:
            return "MIXED"
        if "MIXED" in states:
            return "MIXED"
        if "SUPPORTIVE" in states:
            return "SUPPORTIVE"
        if "ADVERSE" in states:
            return "ADVERSE"
        if "NEUTRAL" in states:
            return "NEUTRAL"
        return "INSUFFICIENT"


__all__ = [
    "DimensionAggregator", "DimensionAssessment", "FundamentalVector",
    "ResearchAssessment", "ResearchAggregator",
]
