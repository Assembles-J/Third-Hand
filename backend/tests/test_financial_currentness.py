from datetime import datetime, timedelta, timezone
from hashlib import sha256

from app import decision_config as config
from app.atomic_models import AtomicEvidenceSnapshot, AtomicFactRecord
from app.financial_currentness import FinancialCurrentnessPolicy
from app.research_assessment import ResearchAggregator, SemanticInvariantValidator


BJ = timezone(timedelta(hours=8))
NOW = datetime(2026, 8, 18, 21, 0, tzinfo=BJ)


def _fact(
    fact_id: str,
    *,
    metric: str,
    value=1.0,
    period_end: str | None = "2025-12-31",
    announced_at: str | None = None,
    polarity: str = "SUPPORTIVE",
    dimension: str = "fundamental_company",
    domain: str = "fundamental",
):
    return AtomicFactRecord(
        fact_id=fact_id,
        symbol="01810",
        market="HK",
        domain=domain,
        dimension=dimension,
        metric=metric,
        value=value,
        period_end=period_end,
        announced_at=announced_at,
        source_evidence_id="research_snapshot:fixture" if domain == "fundamental" else "event:fixture",
        source_name="fixture",
        source_timestamp=period_end,
        available_at="2026-08-18T19:40:59+08:00",
        retrieved_at="2026-08-18T19:40:59+08:00",
        observed_at=NOW,
        freshness_status="fresh",
        retrieval_freshness="fresh",
        polarity=polarity,
        materiality="high",
        comparison_adequacy="adequate" if domain == "fundamental" else "not_applicable",
        confidence=.75,
        provenance_hash=sha256(fact_id.encode()).hexdigest(),
    )


def _earnings_event(date_text="2026-08-18"):
    return _fact(
        "event.earnings",
        metric="event.upcoming.earnings_report.corp-xiaomi",
        value=date_text,
        period_end=date_text,
        polarity="NEUTRAL_MATERIAL",
        dimension="corporate_event",
        domain="event",
    )


def _snapshot(facts, currentness):
    return AtomicEvidenceSnapshot(
        version=config.ATOMIC_EVIDENCE_VERSION,
        context_id="ctx-currentness",
        context_input_hash="frozen-input",
        symbol="01810",
        market="HK",
        generated_at=NOW,
        facts=tuple(facts),
        availability=(),
        conflicts=(),
        financial_currentness=currentness,
        snapshot_hash="a" * 64,
    )


def test_fetched_today_old_report_is_pending_on_same_day_earnings_event():
    old = _fact("financial.old", metric="revenue_yoy_percent", period_end="2025-12-31")
    annotated, currentness = FinancialCurrentnessPolicy().evaluate((old, _earnings_event()))
    financial = next(item for item in annotated if item.fact_id == "financial.old")

    assert financial.retrieval_freshness == "fresh"
    assert financial.observation_currentness == "PENDING_EXPECTED_REPORT"
    assert financial.expected_report_at == "2026-08-18"
    assert currentness.latest_observed_period == "2025-12-31"
    assert currentness.latest_period_status == "PENDING_EXPECTED_REPORT"
    assert currentness.current_confirmation == "PENDING"
    assert currentness.reason_codes == ("earnings_report_pending:2026-08-18",)


def test_verified_new_report_requires_report_announcement_not_retrieval_timestamp():
    current = _fact(
        "financial.current",
        metric="revenue_yoy_percent",
        period_end="2026-06-30",
        announced_at="2026-08-18T18:00:00+08:00",
    )
    annotated, currentness = FinancialCurrentnessPolicy().evaluate((current, _earnings_event()))
    financial = next(item for item in annotated if item.fact_id == "financial.current")

    assert financial.observation_currentness == "CURRENT"
    assert currentness.latest_observed_period == "2026-06-30"
    assert currentness.latest_period_status == "CURRENT"
    assert currentness.current_confirmation == "CONFIRMED"


def test_missing_report_period_never_becomes_current_from_fresh_retrieval_alone():
    unknown_period = _fact("financial.unknown", metric="revenue", period_end=None)
    annotated, currentness = FinancialCurrentnessPolicy().evaluate((unknown_period,))
    financial = annotated[0]

    assert financial.retrieval_freshness == "fresh"
    assert financial.observation_currentness == "UNKNOWN"
    assert currentness.latest_period_status == "UNKNOWN"
    assert currentness.current_confirmation == "UNKNOWN"


def test_historical_support_remains_supportive_while_current_confirmation_is_pending():
    historical = _fact(
        "financial.supportive",
        metric="revenue_yoy_percent",
        period_end="2025-12-31",
        polarity="SUPPORTIVE",
    )
    facts, currentness = FinancialCurrentnessPolicy().evaluate((historical, _earnings_event()))
    snapshot = _snapshot(facts, currentness)

    assessment = ResearchAggregator().build(snapshot)

    assert assessment.fundamental_vector.aggregate_bias == "SUPPORTIVE"
    assert assessment.fundamental_vector.historical_trend == "SUPPORTIVE"
    assert assessment.fundamental_vector.current_confirmation == "PENDING"
    assert assessment.fundamental_vector.latest_period_status == "PENDING_EXPECTED_REPORT"
    assert assessment.fundamental_vector.expected_report_at == "2026-08-18"
    assert "currentness:fundamental_current_confirmation:PENDING" in assessment.unresolved_fact_ids
    assert assessment.aggregation_policy_versions["financial_currentness"] == config.FINANCIAL_CURRENTNESS_POLICY_VERSION
    assert assessment.aggregation_policy_versions["fundamental"] == config.FUNDAMENTAL_AGGREGATION_POLICY_VERSION
    assert SemanticInvariantValidator().validate(snapshot, assessment).valid is True


def test_financial_conflict_never_becomes_confirmed_currentness():
    historical = _fact("financial.conflict", metric="revenue_yoy_percent")
    _, currentness = FinancialCurrentnessPolicy().evaluate(
        (historical, _earnings_event()),
        has_financial_conflict=True,
    )

    assert currentness.latest_period_status == "UNKNOWN"
    assert currentness.current_confirmation == "CONFLICTED"
    assert currentness.reason_codes == ("financial_source_conflict",)
