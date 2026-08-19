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
from app.atomic_models import (
    AtomicEvidenceSnapshot,
    AtomicFactRecord,
    FinancialCurrentConfirmation,
    FinancialLatestPeriodStatus,
)


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
    # Compatibility field: this remains the deterministic historical evidence
    # aggregate. New callers should read historical_trend explicitly.
    aggregate_bias: ResearchState
    historical_trend: ResearchState = "INSUFFICIENT"
    current_confirmation: FinancialCurrentConfirmation = "UNKNOWN"
    latest_observed_period: str | None = None
    expected_report_at: str | None = None
    latest_period_status: FinancialLatestPeriodStatus = "UNKNOWN"
    currentness_reason_codes: tuple[str, ...] = ()


class ResearchAssessment(ResearchModel):
    evidence_snapshot_hash: str
    fundamental_vector: FundamentalVector
    technical_state: DimensionAssessment
    event_state: DimensionAssessment
    expectation_state: DimensionAssessment
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


class ResearchAssessmentValidation(ResearchModel):
    valid: bool
    violations: tuple[str, ...] = ()


_FUNDAMENTAL_DIMENSIONS = {
    "growth": frozenset({
        "revenue", "revenue_yoy_percent", "gross_profit", "gross_profit_yoy_percent",
        "holder_profit", "holder_profit_yoy_percent",
    }),
    "profitability": frozenset({"gross_margin_percent", "net_margin_percent"}),
    "cashflow": frozenset({"operating_cashflow_to_sales_percent"}),
    "capital_efficiency": frozenset({"roe_percent", "roic_percent"}),
}


def _aggregate_state(assessments: tuple[DimensionAssessment, ...]) -> ResearchState:
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


class FactPolarityPolicy:
    """Atomic fact polarity is the only directional authority in Phase 3."""

    version = config.FACT_POLARITY_POLICY_VERSION

    @staticmethod
    def classify(fact: AtomicFactRecord) -> str:
        return fact.polarity


class DimensionAggregator:
    """Aggregate fact polarity without source-level sentiment or model output."""

    version = config.DIMENSION_AGGREGATION_POLICY_VERSION

    def __init__(self, polarity_policy: FactPolarityPolicy | None = None) -> None:
        self.polarity_policy = polarity_policy or FactPolarityPolicy()

    def assess(self, dimension: str, facts: tuple[AtomicFactRecord, ...], *, conflicted: bool = False) -> DimensionAssessment:
        facts = tuple(sorted(facts, key=lambda item: item.fact_id))
        supportive = tuple(item.fact_id for item in facts if self.polarity_policy.classify(item) == "SUPPORTIVE")
        adverse = tuple(item.fact_id for item in facts if self.polarity_policy.classify(item) == "ADVERSE")
        neutral = tuple(item.fact_id for item in facts if self.polarity_policy.classify(item) == "NEUTRAL_MATERIAL")
        unresolved = tuple(item.fact_id for item in facts if self.polarity_policy.classify(item) in {"CONFLICT", "MISSING"})
        directional = len(supportive) + len(adverse)
        if conflicted or any(self.polarity_policy.classify(item) == "CONFLICT" for item in facts):
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


class FundamentalAggregationPolicy:
    version = config.FUNDAMENTAL_AGGREGATION_POLICY_VERSION

    @staticmethod
    def aggregate(dimensions: tuple[DimensionAssessment, ...]) -> ResearchState:
        return _aggregate_state(dimensions)


class ResearchAggregationPolicy:
    version = config.RESEARCH_AGGREGATION_POLICY_VERSION

    @staticmethod
    def aggregate(dimensions: tuple[DimensionAssessment, ...], *, has_conflicts: bool) -> ResearchState:
        return "CONFLICT" if has_conflicts else _aggregate_state(dimensions)


class ResearchAggregator:
    """Build a reproducible ResearchAssessment from a frozen Atomic snapshot."""

    version = config.RESEARCH_AGGREGATION_POLICY_VERSION

    def __init__(
        self,
        dimension_aggregator: DimensionAggregator | None = None,
        fundamental_policy: FundamentalAggregationPolicy | None = None,
        research_policy: ResearchAggregationPolicy | None = None,
    ) -> None:
        self.dimension_aggregator = dimension_aggregator or DimensionAggregator()
        self.fundamental_policy = fundamental_policy or FundamentalAggregationPolicy()
        self.research_policy = research_policy or ResearchAggregationPolicy()

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
        historical_trend = self.fundamental_policy.aggregate(fundamental_dimensions)
        currentness = snapshot.financial_currentness
        fundamental = FundamentalVector(
            dimensions=fundamental_dimensions,
            aggregate_bias=historical_trend,
            historical_trend=historical_trend,
            current_confirmation=currentness.current_confirmation if currentness else "UNKNOWN",
            latest_observed_period=currentness.latest_observed_period if currentness else None,
            expected_report_at=currentness.expected_report_at if currentness else None,
            latest_period_status=currentness.latest_period_status if currentness else "UNKNOWN",
            currentness_reason_codes=currentness.reason_codes if currentness else ("financial_currentness_unavailable",),
        )
        technical = self.dimension_aggregator.assess(
            "technical",
            tuple(fact for fact in snapshot.facts if fact.dimension.startswith("technical_")),
        )
        event = self.dimension_aggregator.assess(
            "event",
            tuple(fact for fact in snapshot.facts if fact.dimension == "corporate_event"),
        )
        expectation = self.dimension_aggregator.assess(
            "expectation",
            tuple(
                fact for fact in snapshot.facts
                if fact.dimension in {"expectation", "valuation"}
                or fact.metric.startswith(("expectation.", "valuation."))
            ),
        )
        market = self.dimension_aggregator.assess(
            "market",
            tuple(fact for fact in snapshot.facts if fact.dimension in {"market_context", "relative_strength"}),
        )
        states = (*fundamental_dimensions, technical, event, expectation, market)
        unresolved_items = [
            f"availability:{item.capability}"
            for item in snapshot.availability
            if item.status in {"missing", "stale", "conflicted"}
        ]
        if currentness is not None and fundamental.current_confirmation != "CONFIRMED":
            unresolved_items.append(
                f"currentness:fundamental_current_confirmation:{fundamental.current_confirmation}"
            )
        unresolved = tuple(sorted(unresolved_items))
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
            expectation_state=expectation,
            market_context=market,
            research_bias=self.research_policy.aggregate(states, has_conflicts=bool(snapshot.conflicts)),
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
                "fact_polarity": self.dimension_aggregator.polarity_policy.version,
                "dimension": self.dimension_aggregator.version,
                "financial_currentness": currentness.policy_version if currentness else config.FINANCIAL_CURRENTNESS_POLICY_VERSION,
                "fundamental": self.fundamental_policy.version,
                "research": self.research_policy.version,
            },
        )


class SemanticInvariantValidator:
    """Reject internally contradictory deterministic research assessments."""

    version = config.SEMANTIC_INVARIANT_VALIDATOR_VERSION

    def validate(
        self,
        snapshot: AtomicEvidenceSnapshot,
        assessment: ResearchAssessment,
    ) -> ResearchAssessmentValidation:
        violations: list[str] = []
        known_fact_ids = {item.fact_id for item in snapshot.facts}
        top_level_buckets = (
            assessment.supportive_fact_ids,
            assessment.adverse_fact_ids,
            assessment.neutral_material_fact_ids,
        )
        for fact_id in {item for bucket in top_level_buckets for item in bucket}:
            if fact_id not in known_fact_ids:
                violations.append(f"unknown_fact_id:{fact_id}")
        if any(set(left).intersection(right) for index, left in enumerate(top_level_buckets) for right in top_level_buckets[index + 1:]):
            violations.append("fact_bucket_overlap")
        if snapshot.conflicts and assessment.research_bias != "CONFLICT":
            violations.append("snapshot_conflict_requires_conflict_research_bias")
        if not snapshot.conflicts and assessment.research_bias == "CONFLICT":
            violations.append("conflict_research_bias_requires_snapshot_conflict")
        if assessment.decision_confidence is not None:
            violations.append("decision_confidence_requires_phase4_decision_arbiter")
        if assessment.evidence_snapshot_hash != snapshot.snapshot_hash:
            violations.append("evidence_snapshot_hash_mismatch")
        if assessment.fundamental_vector.historical_trend != assessment.fundamental_vector.aggregate_bias:
            violations.append("historical_trend_must_match_compat_aggregate_bias")
        if snapshot.financial_currentness is not None:
            if assessment.fundamental_vector.current_confirmation != snapshot.financial_currentness.current_confirmation:
                violations.append("financial_current_confirmation_mismatch")
            if assessment.fundamental_vector.latest_period_status != snapshot.financial_currentness.latest_period_status:
                violations.append("financial_latest_period_status_mismatch")
        return ResearchAssessmentValidation(
            valid=not violations,
            violations=tuple(sorted(violations)),
        )


__all__ = [
    "DimensionAggregator", "DimensionAssessment", "FactPolarityPolicy",
    "FundamentalAggregationPolicy", "FundamentalVector", "ResearchAggregationPolicy",
    "ResearchAssessment", "ResearchAssessmentValidation", "ResearchAggregator",
    "SemanticInvariantValidator",
]
