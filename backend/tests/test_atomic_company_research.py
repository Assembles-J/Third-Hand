import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app import decision_config as config
from app.atomic_company_builder import CompanyAwareAtomicEvidenceBuilder
from app.atomic_company_research import CompanyResearchAtomicSource
from app.atomic_evidence import AtomicEvidenceSnapshotBuilder
from app.atomic_evidence_runtime import install as install_atomic_runtime
from app.decision_models import (
    AccountSnapshot,
    ActionCandidate,
    ActionGate,
    DailyBarSummary,
    DecisionContext,
    DecisionQualitySummary,
    EvidenceItem,
    InstrumentSnapshot,
    QuoteSnapshot,
    SourceFreshness,
)
from app.decision_orchestrator import DecisionOrchestrator
from app.infrastructure.database.company_intelligence_repository import CompanyIntelligenceRepository
from app.infrastructure.database.research_data_repository import ResearchDataRepository
from app.storage import PortfolioStore


BJ = timezone(timedelta(hours=8))
DECISION_AT = datetime(2026, 8, 17, 16, 0, tzinfo=BJ)


def _decision_context() -> DecisionContext:
    quality = DecisionQualitySummary(
        status="degraded",
        score_percent=90,
        warnings=("risk unavailable", "market_regime unavailable", "events unavailable", "relative_strength unavailable", "trade_plan.auto_draft unavailable"),
        source_freshness=(
            SourceFreshness(source_key="quote", as_of="2026-08-17", status="fresh"),
            SourceFreshness(source_key="daily_bars", as_of="2026-08-17", status="fresh"),
            SourceFreshness(source_key="risk", status="unavailable"),
            SourceFreshness(source_key="market_regime", status="unavailable"),
        ),
        action_gates=(
            ActionGate(action="OPEN", permission="blocked", unavailable_fields=("risk", "market_regime")),
            ActionGate(action="ADD", permission="blocked"),
            ActionGate(action="HOLD", permission="allowed"),
            ActionGate(action="WATCH", permission="allowed"),
            ActionGate(action="REDUCE", permission="allowed"),
            ActionGate(action="EXIT", permission="allowed"),
        ),
    )
    return DecisionContext(
        context_id="decision-ctx",
        symbol="01810",
        name="Xiaomi",
        generated_at=DECISION_AT,
        decision_horizon="swing",
        account=AccountSnapshot(available_cash=100_000, total_market_value=0, total_assets=100_000, cash_percent=100),
        position=None,
        quote=QuoteSnapshot(price=25.88, source="fixture", as_of="2026-08-17", retrieved_at=DECISION_AT.isoformat()),
        daily_bars=DailyBarSummary(count=60, first_trading_date="2026-05-25", last_trading_date="2026-08-17", last_close=25.88, source="fixture"),
        technical=None,
        risk=None,
        market_regime=None,
        relative_strength=None,
        events=(),
        trade_plan=None,
        personal_rule=None,
        instrument=InstrumentSnapshot(symbol="01810", market="HK", currency="HKD", lot_size=None, price_tick=None, source="fixture", as_of="2026-08-17"),
        data_quality=quality,
        source_versions={"context_schema": "context-v1"},
        input_hash="formal-input-does-not-contain-company-research",
    )


def _save_snapshot(
    research: ResearchDataRepository,
    data_type: str,
    payload,
    *,
    available_at="2026-08-17T15:00:00+08:00",
):
    snapshot_id = research.save_snapshot(
        data_type=data_type,
        symbol="01810",
        query_hash=f"query-{data_type}-{available_at}",
        schema_version="research-data-v1",
        payload=payload,
        provider="AKShare",
        source_reference=f"Eastmoney/AKShare {data_type}",
        as_of="2026-06-30T00:00:00+08:00",
        available_at=available_at,
        fetched_at=available_at,
        expires_at="2026-08-24T15:00:00+08:00",
        coverage_keys=(),
        freshness_status="fresh",
    )
    snapshot = research.get_snapshot(snapshot_id)
    assert snapshot is not None
    return snapshot


def _save_company_context(store, *, generated_at="2026-08-17T15:30:00+08:00", future_dataset=False):
    research = ResearchDataRepository(store)
    profit_payload = {
        "annual_driver_history": [{
            "report_date": "2026-06-30",
            "revenue": 100.0,
            "revenue_yoy_percent": -10.9,
            "gross_profit": 22.0,
            "gross_profit_yoy_percent": -14.2,
            "holder_profit": 4.7,
            "holder_profit_yoy_percent": 5.0,
            "operating_cashflow_to_sales_percent": 8.5,
            "roe_percent": 7.2,
            "roic_percent": 5.1,
        }]
    }
    margin_payload = {
        "company_margin_history": [{
            "report_date": "2026-06-30",
            "revenue": 100.0,
            "gross_profit": 22.0,
            "gross_margin_percent": 22.0,
            "net_margin_percent": 4.8,
        }]
    }
    profit = _save_snapshot(
        research,
        "company_profit_cashflow_drivers",
        profit_payload,
        available_at="2026-08-17T17:00:00+08:00" if future_dataset else "2026-08-17T15:00:00+08:00",
    )
    margin = _save_snapshot(research, "company_margin_structure", margin_payload)

    payload = {
        "symbol": "01810",
        "name": "Xiaomi",
        "research_priority": "holding",
        "analysis_depth": "standard",
        "version": "company-context-v2",
        "datasets": {
            "profit_cashflow_drivers": profit_payload,
            "margin_structure": margin_payload,
        },
        "dataset_refs": [
            {
                "dataset_key": "profit_cashflow_drivers",
                "data_type": "company_profit_cashflow_drivers",
                "snapshot_id": profit.snapshot_id,
                "payload_hash": profit.payload_hash,
                "provider": profit.provider,
                "as_of": profit.as_of,
                "available_at": profit.available_at,
                "freshness_status": "fresh",
            },
            {
                "dataset_key": "margin_structure",
                "data_type": "company_margin_structure",
                "snapshot_id": margin.snapshot_id,
                "payload_hash": margin.payload_hash,
                "provider": margin.provider,
                "as_of": margin.as_of,
                "available_at": margin.available_at,
                "freshness_status": "fresh",
            },
        ],
        "missing_datasets": ["valuation_framework"],
        "stale_datasets": [],
        "source_snapshot_ids": [profit.snapshot_id, margin.snapshot_id],
        "generated_at": generated_at,
        "policy": {"usage_scope": "RESEARCH_ONLY", "formal_trade_authority": False},
    }
    company = CompanyIntelligenceRepository(store).save_context(payload)
    return {"company": company, "profit": profit, "margin": margin}


def test_company_repository_replays_latest_context_at_or_before_cutoff(tmp_path):
    store = PortfolioStore(tmp_path / "company-pit.db")
    repo = CompanyIntelligenceRepository(store)
    base = {
        "symbol": "01810", "name": "Xiaomi", "research_priority": "holding",
        "analysis_depth": "standard", "version": "company-context-v2",
        "datasets": {}, "dataset_refs": [], "missing_datasets": [], "stale_datasets": [],
        "source_snapshot_ids": [], "policy": {"usage_scope": "RESEARCH_ONLY", "formal_trade_authority": False},
    }
    old = repo.save_context({**base, "generated_at": "2026-08-17T10:00:00+08:00"})
    repo.save_context({**base, "generated_at": "2026-08-17T18:00:00+08:00"})

    replay = repo.latest_context_at_or_before("01810", "2026-08-17T16:00:00+08:00")

    assert replay is not None
    assert replay["context_id"] == old["context_id"]
    assert replay["generated_at"] == "2026-08-17T10:00:00+08:00"


def test_company_atomic_source_emits_mixed_polarity_from_one_persisted_snapshot(tmp_path):
    store = PortfolioStore(tmp_path / "company-facts.db")
    saved = _save_company_context(store)

    result = CompanyResearchAtomicSource(store).build(_decision_context())
    by_metric = {fact.metric: fact for fact in result.facts}
    availability = {item.capability: item for item in result.availability}
    profit = saved["profit"]

    assert by_metric["revenue_yoy_percent"].polarity == "ADVERSE"
    assert by_metric["holder_profit_yoy_percent"].polarity == "SUPPORTIVE"
    assert by_metric["gross_margin_percent"].polarity == "NEUTRAL_MATERIAL"
    assert by_metric["revenue_yoy_percent"].source_evidence_id == f"research_snapshot:{profit.snapshot_id}"
    assert by_metric["holder_profit_yoy_percent"].source_evidence_id == f"research_snapshot:{profit.snapshot_id}"
    assert by_metric["revenue_yoy_percent"].source_reference == "Eastmoney/AKShare company_profit_cashflow_drivers"
    assert by_metric["revenue_yoy_percent"].available_at == "2026-08-17T15:00:00+08:00"
    assert by_metric["revenue_yoy_percent"].comparison_adequacy == "adequate"
    assert by_metric["gross_margin_percent"].comparison_adequacy == "partial"
    assert availability["company_dataset.profit_cashflow_drivers"].status == "available"
    assert availability["company_dataset.margin_structure"].status == "available"
    assert availability["company_dataset.valuation_framework"].status == "missing"
    assert availability["company_research"].status == "degraded"
    assert f"company_context:{saved['company']['context_id']}" in availability["company_research"].source_keys


def test_future_dataset_is_not_visible_to_earlier_decision(tmp_path):
    store = PortfolioStore(tmp_path / "company-lookahead.db")
    _save_company_context(store, generated_at="2026-08-17T15:30:00+08:00", future_dataset=True)

    result = CompanyResearchAtomicSource(store).build(_decision_context())
    profit_facts = [fact for fact in result.facts if "profit_cashflow_drivers" in fact.fact_id]
    availability = {item.capability: item for item in result.availability}

    assert profit_facts == []
    assert availability["company_dataset.profit_cashflow_drivers"].status == "missing"
    assert availability["company_dataset.profit_cashflow_drivers"].reason_codes == ("not_available_at_decision_time",)
    # The independently available margin snapshot remains usable.
    assert any(fact.metric == "gross_margin_percent" for fact in result.facts)


def test_future_raw_snapshot_cannot_hide_behind_older_company_ref(tmp_path):
    store = PortfolioStore(tmp_path / "company-raw-lookahead.db")
    saved = _save_company_context(
        store,
        generated_at="2026-08-17T15:30:00+08:00",
        future_dataset=True,
    )

    # Simulate a damaged/backfilled CompanyContext ref claiming that the future
    # underlying snapshot was already available at 15:00. The raw research
    # snapshot still truthfully records 17:00 and must win the point-in-time gate.
    company_context_id = saved["company"]["context_id"]
    with store._connect() as connection:
        row = connection.execute(
            "SELECT payload_json FROM company_research_snapshots WHERE context_id=?",
            (company_context_id,),
        ).fetchone()
        payload = json.loads(str(row["payload_json"]))
        profit_ref = next(
            item for item in payload["dataset_refs"]
            if item["dataset_key"] == "profit_cashflow_drivers"
        )
        profit_ref["available_at"] = "2026-08-17T15:00:00+08:00"
        connection.execute(
            "UPDATE company_research_snapshots SET payload_json=? WHERE context_id=?",
            (json.dumps(payload, ensure_ascii=False), company_context_id),
        )

    result = CompanyResearchAtomicSource(store).build(_decision_context())
    availability = {item.capability: item for item in result.availability}

    assert not any("profit_cashflow_drivers" in fact.fact_id for fact in result.facts)
    assert availability["company_dataset.profit_cashflow_drivers"].status == "missing"
    assert availability["company_dataset.profit_cashflow_drivers"].reason_codes == (
        "research_snapshot_not_available_at_decision_time",
    )


def test_future_company_context_is_not_backfilled_into_historical_decision(tmp_path):
    store = PortfolioStore(tmp_path / "company-context-lookahead.db")
    _save_company_context(store, generated_at="2026-08-17T18:00:00+08:00")

    result = CompanyResearchAtomicSource(store).build(_decision_context())

    assert result.facts == ()
    assert result.availability[0].capability == "company_research"
    assert result.availability[0].status == "missing"
    assert result.availability[0].reason_codes == ("no_point_in_time_context",)


def test_company_aware_builder_changes_only_atomic_shadow_hash_and_keeps_formal_context_unchanged(tmp_path):
    store = PortfolioStore(tmp_path / "company-builder.db")
    _save_company_context(store)
    context = _decision_context()

    snapshot = CompanyAwareAtomicEvidenceBuilder(store).build(context, ())

    assert snapshot.version == config.ATOMIC_EVIDENCE_VERSION == "atomic-evidence-shadow-v2-company-research"
    assert any(fact.domain == "fundamental" for fact in snapshot.facts)
    assert any(item.capability == "company_research" for item in snapshot.availability)
    assert context.input_hash == "formal-input-does-not-contain-company-research"
    assert not hasattr(context, "company_research")


def test_runtime_installer_replaces_only_atomic_shadow_builder(tmp_path):
    store = PortfolioStore(tmp_path / "company-runtime.db")
    original = object()
    orchestrator = SimpleNamespace(atomic_evidence_builder=original)
    module = SimpleNamespace(store=store, decision_orchestrator=orchestrator)

    install_atomic_runtime(module)

    assert isinstance(orchestrator.atomic_evidence_builder, CompanyAwareAtomicEvidenceBuilder)
    assert orchestrator.atomic_evidence_builder.base_builder is original
    assert module._atomic_evidence_runtime_installed is True


class _FrozenEvidenceEngine:
    def __init__(self, evidence):
        self.evidence = evidence

    def build(self, _context):
        return self.evidence


class _FrozenPolicy:
    version = "xiaomi-frozen-policy-v1"

    def evaluate(self, _context, _evidence):
        return (ActionCandidate(action="WATCH", priority=30, policy_score=.3),)


class _NoSizing:
    def size(self, *_args, **_kwargs):
        raise AssertionError("the frozen shadow benchmark disables sizing")


class _NoAi:
    def assess(self, *_args, **_kwargs):
        raise AssertionError("Atomic Evidence must not enter the AI prompt in Phase 2")


class _NoopGuard:
    def guard(self, _candidates, _assessment):
        return None


def _frozen_report(context, evidence, builder):
    return DecisionOrchestrator(
        _FrozenEvidenceEngine(evidence),
        _FrozenPolicy(),
        _NoSizing(),
        _NoAi(),
        _NoopGuard(),
        atomic_evidence_builder=builder,
    ).generate(context)


def test_xiaomi_frozen_shadow_benchmark_is_reproducible_and_action_isolated(tmp_path, monkeypatch):
    """Phase-2 acceptance: research facts remain auditable, never authoritative."""
    store = PortfolioStore(tmp_path / "xiaomi-frozen-shadow.db")
    saved = _save_company_context(store)
    context = _decision_context()
    evidence = (EvidenceItem(
        evidence_id="trend.sma20_above_sma60",
        category="trend",
        direction="positive",
        strength=.6,
        title="Frozen technical input",
        description="This is the complete formal input for the benchmark.",
        value=True,
        source="frozen-fixture",
        as_of="2026-08-17",
        fresh=True,
    ),)
    shadow_builder = CompanyAwareAtomicEvidenceBuilder(store)

    first = shadow_builder.build(context, evidence)
    second = shadow_builder.build(context, evidence)
    baseline = AtomicEvidenceSnapshotBuilder().build(context, evidence)
    availability = {item.capability: item for item in first.availability}
    facts = {item.metric: item for item in first.facts}

    # A frozen context produces byte-stable shadow evidence.  Adding Company
    # Research changes only the shadow snapshot, not the formal input hash.
    assert first == second
    assert first.snapshot_hash == second.snapshot_hash
    assert first.snapshot_hash != baseline.snapshot_hash
    assert context.input_hash == "formal-input-does-not-contain-company-research"
    assert availability["company_dataset.valuation_framework"].status == "missing"

    # One raw filing can retain both directions, each traceable to the exact
    # persisted snapshot and point-in-time availability boundary.
    revenue = facts["revenue_yoy_percent"]
    profit = facts["holder_profit_yoy_percent"]
    assert revenue.polarity == "ADVERSE"
    assert profit.polarity == "SUPPORTIVE"
    assert revenue.source_evidence_id == f"research_snapshot:{saved['profit'].snapshot_id}"
    assert revenue.source_reference == saved["profit"].source_reference
    assert revenue.available_at == saved["profit"].available_at
    assert revenue.provenance_hash != profit.provenance_hash

    monkeypatch.setattr(config, "DECISION_AI_ENABLED", False)
    monkeypatch.setattr(config, "DECISION_SIZING_ENABLED", False)
    legacy_report = _frozen_report(context, evidence, AtomicEvidenceSnapshotBuilder())
    shadow_report = _frozen_report(context, evidence, shadow_builder)

    # The action was frozen before Atomic Evidence and must remain identical
    # when point-in-time Company Research is present.
    assert legacy_report.action == shadow_report.action == "WATCH"
    assert legacy_report.action_candidates == shadow_report.action_candidates
    assert shadow_report.atomic_evidence_shadow.snapshot_hash == first.snapshot_hash
    assert shadow_report.research_assessment is not None
    assert shadow_report.research_assessment.research_bias == "MIXED"
    assert shadow_report.research_assessment.decision_confidence is None
