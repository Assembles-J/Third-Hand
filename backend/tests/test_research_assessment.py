from datetime import datetime, timedelta, timezone
from hashlib import sha256

from app.atomic_models import (
    AtomicEvidenceSnapshot,
    AtomicFactRecord,
    EvidenceAvailabilityRecord,
    EvidenceConflictRecord,
)
from app.research_assessment import ResearchAggregator, SemanticInvariantValidator


BJ = timezone(timedelta(hours=8))
NOW = datetime(2026, 8, 17, 16, 0, tzinfo=BJ)


def _fact(fact_id, metric, polarity, *, dimension="fundamental_company", confidence=.75, source_id="research_snapshot:fixture"):
    return AtomicFactRecord(
        fact_id=fact_id,
        symbol="01810",
        market="HK",
        domain="fundamental" if dimension == "fundamental_company" else "trend",
        dimension=dimension,
        metric=metric,
        value=1.0,
        source_evidence_id=source_id,
        source_name="fixture",
        source_timestamp="2026-06-30",
        available_at="2026-08-17T15:00:00+08:00",
        observed_at=NOW,
        freshness_status="fresh",
        polarity=polarity,
        materiality="high",
        comparison_adequacy="adequate",
        confidence=confidence,
        provenance_hash=sha256(fact_id.encode()).hexdigest(),
    )


def _snapshot(*facts, availability=(), conflicts=()):
    return AtomicEvidenceSnapshot(
        version="atomic-fixture-v1",
        context_id="ctx-research",
        context_input_hash="frozen-context",
        symbol="01810",
        market="HK",
        generated_at=NOW,
        facts=tuple(facts),
        availability=tuple(availability),
        conflicts=tuple(conflicts),
        snapshot_hash="a" * 64,
    )


def test_research_assessment_is_order_independent_and_keeps_mixed_facts_separate():
    facts = (
        _fact("fact.revenue", "revenue_yoy_percent", "ADVERSE"),
        _fact("fact.profit", "holder_profit_yoy_percent", "SUPPORTIVE"),
        _fact("fact.margin", "gross_margin_percent", "NEUTRAL_MATERIAL"),
        _fact("fact.trend", "trend.sma20_above_sma60", "SUPPORTIVE", dimension="technical_trend", confidence=.9, source_id="technical:fixture"),
    )
    first = ResearchAggregator().build(_snapshot(*facts))
    second = ResearchAggregator().build(_snapshot(*reversed(facts)))

    assert first == second
    growth = next(item for item in first.fundamental_vector.dimensions if item.dimension == "growth")
    assert growth.state == "MIXED"
    assert growth.supportive_fact_ids == ("fact.profit",)
    assert growth.adverse_fact_ids == ("fact.revenue",)
    assert first.fundamental_vector.aggregate_bias == "MIXED"
    assert first.research_bias == "MIXED"
    assert first.decision_confidence is None
    assert first.model_run_ids == ()
    assert first.aggregation_policy_versions["dimension"] == "dimension-aggregation-v1-fact-polarity"
    assert SemanticInvariantValidator().validate(_snapshot(*facts), first).valid is True


def test_research_assessment_treats_conflict_and_missing_data_as_deterministic_unresolved_state():
    fact = _fact("fact.revenue", "revenue_yoy_percent", "ADVERSE")
    assessment = ResearchAggregator().build(_snapshot(
        fact,
        availability=(EvidenceAvailabilityRecord(
            capability="company_dataset.valuation_framework",
            status="missing",
            reason_codes=("dataset_missing_from_company_context",),
            source_keys=("company_context:fixture",),
        ),),
        conflicts=(EvidenceConflictRecord(
            conflict_id="conflict.profit",
            code="company_dataset_payload_hash_mismatch:profit_cashflow_drivers",
            affected_sources=("research_snapshot:fixture",),
            severity="high",
            policy_effect="shadow_only_no_formal_authority",
        ),),
    ))

    assert assessment.research_bias == "CONFLICT"
    assert assessment.evidence_confidence == .25
    assert assessment.unresolved_fact_ids == ("availability:company_dataset.valuation_framework",)
    assert "unavailable:company_dataset.valuation_framework" in assessment.invalidation_conditions
    assert "conflict:company_dataset_payload_hash_mismatch:profit_cashflow_drivers" in assessment.invalidation_conditions

    invalid = assessment.model_copy(update={"research_bias": "SUPPORTIVE"})
    validation = SemanticInvariantValidator().validate(_snapshot(
        fact,
        conflicts=(EvidenceConflictRecord(
            conflict_id="conflict.profit",
            code="company_dataset_payload_hash_mismatch:profit_cashflow_drivers",
            affected_sources=("research_snapshot:fixture",),
            severity="high",
            policy_effect="shadow_only_no_formal_authority",
        ),),
    ), invalid)
    assert validation.valid is False
    assert "snapshot_conflict_requires_conflict_research_bias" in validation.violations


def test_expectation_facts_have_an_explicit_optional_dimension():
    assessment = ResearchAggregator().build(_snapshot(
        _fact("fact.valuation", "valuation.forward_pe", "SUPPORTIVE", dimension="valuation"),
    ))

    assert assessment.expectation_state.state == "SUPPORTIVE"
    assert assessment.expectation_state.supportive_fact_ids == ("fact.valuation",)
    assert assessment.aggregation_policy_versions["fact_polarity"] == "fact-polarity-v1-atomic-record-authority"
