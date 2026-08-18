from datetime import datetime, timedelta, timezone

from app import decision_config as config
from app.atomic_evidence import AtomicEvidenceSnapshotBuilder, FactExtractor
from app.decision_models import (
    AccountSnapshot,
    ActionCandidate,
    ActionGate,
    DailyBarSummary,
    DecisionContext,
    DecisionQualitySummary,
    EventSnapshot,
    EvidenceItem,
    InstrumentSnapshot,
    QuoteSnapshot,
    SourceFreshness,
)
from app.decision_orchestrator import DecisionOrchestrator


BJ = timezone(timedelta(hours=8))
NOW = datetime(2026, 8, 17, 16, 0, tzinfo=BJ)


def _quality(*, quote=True, conflict=False, risk=False) -> DecisionQualitySummary:
    warnings = []
    missing = []
    if not quote:
        missing.append("quote.price")
    if not risk:
        warnings.append("risk unavailable")
    if conflict:
        warnings.append("consistency.quote_older_than_daily_bar")
    open_unavailable = []
    if not quote:
        open_unavailable.append("quote.price")
    if not risk:
        open_unavailable.append("risk")
    if conflict:
        open_unavailable.append("consistency.quote_older_than_daily_bar")
    return DecisionQualitySummary(
        status="blocked" if missing else "degraded" if warnings else "ready",
        score_percent=80 if warnings else 100,
        missing_fields=tuple(missing),
        warnings=tuple(warnings),
        source_freshness=(
            SourceFreshness(source_key="quote", as_of="2026-08-17", status="fresh" if quote else "unavailable"),
            SourceFreshness(source_key="daily_bars", as_of="2026-08-17", status="fresh"),
            SourceFreshness(source_key="risk", as_of=None, status="unavailable" if not risk else "fresh"),
            SourceFreshness(source_key="market_regime", as_of=None, status="unavailable"),
        ),
        action_gates=(
            ActionGate(
                action="OPEN",
                permission="blocked" if open_unavailable else "allowed",
                unavailable_fields=tuple(open_unavailable),
            ),
            ActionGate(action="ADD", permission="blocked"),
            ActionGate(action="HOLD", permission="allowed" if quote else "blocked"),
            ActionGate(action="WATCH", permission="allowed" if quote else "blocked"),
            ActionGate(action="REDUCE", permission="allowed" if quote else "blocked"),
            ActionGate(action="EXIT", permission="allowed" if quote else "blocked"),
        ),
    )


def _context(*, quote=True, conflict=False, events=(), risk=False) -> DecisionContext:
    return DecisionContext(
        context_id="ctx-atomic",
        symbol="01810",
        name="Xiaomi",
        generated_at=NOW,
        decision_horizon="swing",
        account=AccountSnapshot(
            available_cash=100_000,
            total_market_value=0,
            total_assets=100_000,
            cash_percent=100,
        ),
        position=None,
        quote=QuoteSnapshot(
            price=27.06,
            source="quote-fixture",
            as_of="2026-08-16" if conflict else "2026-08-17",
            retrieved_at=NOW.isoformat(),
        ) if quote else None,
        daily_bars=DailyBarSummary(
            count=60,
            first_trading_date="2026-05-25",
            last_trading_date="2026-08-17",
            last_close=25.88,
            source="daily-fixture",
        ),
        technical=None,
        risk=None,
        market_regime=None,
        relative_strength=None,
        events=tuple(events),
        trade_plan=None,
        personal_rule=None,
        instrument=InstrumentSnapshot(
            symbol="01810",
            market="HK",
            currency="HKD",
            lot_size=None,
            price_tick=None,
            source="instrument-fixture",
            as_of="2026-08-17",
        ),
        data_quality=_quality(quote=quote, conflict=conflict, risk=risk),
        source_versions={"context_schema": "context-v1"},
        input_hash="frozen-input-hash",
    )


def _evidence(*items) -> tuple[EvidenceItem, ...]:
    return tuple(items)


def test_atomic_snapshot_is_deterministic_for_same_frozen_input():
    context = _context()
    evidence = _evidence(EvidenceItem(
        evidence_id="trend.sma20_above_sma60",
        category="trend",
        direction="positive",
        strength=.6,
        title="均线结构偏强",
        description="20 日均线高于 60 日均线",
        value=27.0,
        threshold=26.0,
        source="technical_analysis",
        as_of="2026-08-17",
        fresh=True,
    ))
    builder = AtomicEvidenceSnapshotBuilder()

    first = builder.build(context, evidence)
    second = builder.build(context, evidence)

    assert first == second
    assert first.snapshot_hash == second.snapshot_hash
    assert first.version == config.ATOMIC_EVIDENCE_VERSION
    assert first.shadow_mode is True
    assert len({fact.fact_id for fact in first.facts}) == len(first.facts)
    assert config.audit_version_snapshot()["atomic_evidence_version"] == first.version


def test_same_source_can_emit_supportive_and_adverse_atomic_facts():
    context = _context()
    source = "https://example.com/filing"
    evidence = _evidence(
        EvidenceItem(
            evidence_id="fundamental.revenue_growth",
            category="fundamental",
            direction="positive",
            strength=.8,
            title="收入增长",
            description="收入增长",
            value=12.0,
            threshold=0,
            source="filing",
            source_reference=source,
            as_of="2026-08-17",
            fresh=True,
        ),
        EvidenceItem(
            evidence_id="fundamental.margin_decline",
            category="fundamental",
            direction="negative",
            strength=.8,
            title="利润率下降",
            description="利润率下降",
            value=-3.0,
            threshold=0,
            source="filing",
            source_reference=source,
            as_of="2026-08-17",
            fresh=True,
        ),
    )

    facts = FactExtractor().build(context, evidence)
    source_facts = [fact for fact in facts if fact.source_reference == source]

    assert {fact.polarity for fact in source_facts} == {"SUPPORTIVE", "ADVERSE"}
    assert len({fact.provenance_hash for fact in source_facts}) == 2


def test_quote_daily_conflict_is_explicit_without_contaminating_daily_close():
    context = _context(conflict=True)

    snapshot = AtomicEvidenceSnapshotBuilder().build(context, ())
    facts = {fact.fact_id: fact for fact in snapshot.facts}
    availability = {item.capability: item for item in snapshot.availability}

    assert snapshot.conflicts[0].code == "consistency.quote_older_than_daily_bar"
    assert snapshot.conflicts[0].affected_sources == ("quote", "daily_bars")
    assert availability["quote"].status == "conflicted"
    assert facts["atomic.raw.quote.price"].polarity == "CONFLICT"
    assert facts["atomic.raw.quote.price"].value == 27.06
    assert facts["atomic.raw.daily_bars.last_close"].polarity == "NEUTRAL_MATERIAL"
    assert facts["atomic.raw.daily_bars.last_close"].value == 25.88


def test_upcoming_secondary_earnings_remains_neutral_material_atomic_fact():
    event = EventSnapshot(
        event_id="xiaomi-results",
        title="中报计划披露",
        source="secondary-calendar",
        source_reference="https://example.com/calendar",
        event_type="earnings_report",
        lifecycle="upcoming",
        scheduled_at="2026-08-18",
        impact="neutral",
        evidence_polarity="NEUTRAL_MATERIAL",
        verification_level="secondary_calendar",
        policy_eligible=True,
    )
    context = _context(events=(event,))
    evidence = _evidence(EvidenceItem(
        evidence_id="event.upcoming.earnings_report.xiaomi-results",
        category="event",
        direction="neutral",
        strength=.8,
        title="已知财报披露日",
        description="方向未知但重要",
        value="2026-08-18",
        source="secondary-calendar",
        source_reference="https://example.com/calendar",
        as_of="2026-08-18",
        fresh=True,
        usage_scope="POLICY",
    ))

    fact = next(
        item for item in FactExtractor().build(context, evidence)
        if item.source_evidence_id == "event.upcoming.earnings_report.xiaomi-results"
    )

    assert fact.polarity == "NEUTRAL_MATERIAL"
    assert fact.materiality == "high"
    assert fact.confidence == .75
    assert fact.source_reference == "https://example.com/calendar"


def test_availability_mirrors_existing_quality_semantics_instead_of_inventing_new_truth():
    missing_quote = AtomicEvidenceSnapshotBuilder().build(_context(quote=False), ())
    degraded_risk = AtomicEvidenceSnapshotBuilder().build(_context(quote=True, risk=False), ())

    missing = {item.capability: item for item in missing_quote.availability}
    degraded = {item.capability: item for item in degraded_risk.availability}

    assert missing["quote"].status == "missing"
    assert "quote.price" in missing["quote"].reason_codes
    # Existing DecisionQuality treats absent risk as degraded, not a context-level
    # hard missing field. Atomic Evidence must mirror that authority exactly.
    assert degraded["risk"].status == "degraded"
    assert "risk unavailable" in degraded["risk"].reason_codes


class _EvidenceEngine:
    def __init__(self, evidence):
        self.evidence = evidence

    def build(self, _context):
        return self.evidence


class _Policy:
    version = "policy-fixture"

    def __init__(self):
        self.called = False

    def evaluate(self, _context, _evidence):
        self.called = True
        return (ActionCandidate(action="WATCH", priority=30, policy_score=.3),)


class _AtomicSpy:
    def __init__(self, policy):
        self.policy = policy
        self.builder = AtomicEvidenceSnapshotBuilder()
        self.called = False

    def build(self, context, evidence):
        assert self.policy.called is True
        self.called = True
        return self.builder.build(context, evidence)


class _Sizing:
    def size(self, *_args, **_kwargs):
        raise AssertionError("sizing is disabled")


class _Ai:
    def assess(self, *_args, **_kwargs):
        raise AssertionError("AI is disabled")


class _Guard:
    def guard(self, _candidates, _assessment):
        return None


def test_orchestrator_builds_atomic_shadow_only_after_policy_and_does_not_change_action(monkeypatch):
    context = _context()
    evidence = _evidence(EvidenceItem(
        evidence_id="data_quality.summary",
        category="data_quality",
        direction="uncertain",
        strength=.8,
        title="数据质量",
        description="fixture",
        value="degraded",
        source="decision_context",
        as_of=NOW,
        fresh=True,
    ))
    policy = _Policy()
    atomic = _AtomicSpy(policy)
    monkeypatch.setattr(config, "DECISION_AI_ENABLED", False)
    monkeypatch.setattr(config, "DECISION_SIZING_ENABLED", False)

    report = DecisionOrchestrator(
        _EvidenceEngine(evidence),
        policy,
        _Sizing(),
        _Ai(),
        _Guard(),
        atomic_evidence_builder=atomic,
    ).generate(context)

    assert policy.called is True
    assert atomic.called is True
    assert report.action == "WATCH"
    assert report.action_candidates[0].action == "WATCH"
    assert report.atomic_evidence_shadow is not None
    assert report.atomic_evidence_shadow.shadow_mode is True
    serialized = report.model_dump(mode="json")
    assert serialized["atomic_evidence_shadow"]["snapshot_hash"] == report.atomic_evidence_shadow.snapshot_hash
