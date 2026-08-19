from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.application_services.company.akshare_provider import CompanyAkshareProvider
from app.atomic_models import AtomicFactRecord
from app.financial_announcement_enrichment import FinancialAnnouncementEnricher
from app.financial_currentness import FinancialCurrentnessPolicy
from app.financial_release_refresh_runtime import (
    FINANCIAL_DATA_TYPES,
    REFRESH_REASON,
    install as install_release_refresh,
)


BEIJING = timezone(timedelta(hours=8))
NOW = datetime(2026, 8, 19, 10, 0, tzinfo=BEIJING)


class FakeFrame:
    def __init__(self, rows):
        self.rows = list(rows)
        self.empty = not self.rows

    def head(self, limit):
        return FakeFrame(self.rows[:limit])

    def to_dict(self, orient):
        assert orient == "records"
        return list(self.rows)


class FakeAk:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def stock_financial_hk_analysis_indicator_em(self, *, symbol, indicator):
        self.calls.append((symbol, indicator))
        return FakeFrame(self.rows)


def _financial_fact(*, period_end="2026-06-30", report_type="interim", fact_id="financial"):
    return AtomicFactRecord(
        fact_id=fact_id,
        symbol="01810",
        market="HK",
        domain="fundamental",
        dimension="fundamental_company",
        metric="revenue_yoy_percent",
        value=15.2,
        unit="percent",
        period_end=period_end,
        report_type=report_type,
        observed_at=NOW,
        freshness_status="fresh",
        retrieval_freshness="fresh",
        polarity="SUPPORTIVE",
        materiality="high",
        comparison_adequacy="adequate",
        confidence=.85,
        provenance_hash="a" * 64,
    )


def _event_fact():
    return AtomicFactRecord(
        fact_id="event-release",
        symbol="01810",
        market="HK",
        domain="event",
        dimension="corporate_event",
        metric="event.upcoming.earnings_report.xiaomi-2026-interim",
        value="2026-08-18",
        observed_at=NOW,
        freshness_status="fresh",
        retrieval_freshness="fresh",
        polarity="NEUTRAL_MATERIAL",
        materiality="high",
        comparison_adequacy="partial",
        confidence=.95,
        provenance_hash="b" * 64,
    )


def _event_bundle():
    return {
        "status": "ready",
        "symbol": "01810",
        "market": "HK",
        "events": [{
            "event_id": "xiaomi-2026-interim",
            "event_key": "xiaomi-2026-interim-key",
            "symbol": "01810",
            "market": "HK",
            "event_type": "earnings_report",
            "period": "2026年中报",
            "scheduled_at": "2026-08-18",
            "lifecycle_status": "RELEASE_EXPECTED",
            "verification_level": "official",
            "source_rank": 10,
            "source": "HKEXnews",
            "source_reference": "https://www.hkexnews.hk/fixture.pdf",
            "announced_at": "2026-08-18T19:05:00+08:00",
        }],
        "event_history": [],
    }


def test_hk_financial_provider_uses_report_period_not_annual_only():
    rows = [{
        "REPORT_DATE": "2026-06-30",
        "DATE_TYPE": "中报",
        "OPERATE_INCOME": 116000000000,
        "OPERATE_INCOME_YOY": 12.8,
        "GROSS_PROFIT": 25000000000,
        "GROSS_PROFIT_YOY": 18.0,
        "HOLDER_PROFIT": 12000000000,
        "HOLDER_PROFIT_YOY": 7.2,
        "OCF_SALES": 10.5,
        "ROE_AVG": 8.1,
        "ROIC_YEARLY": 6.4,
    }, {
        "REPORT_DATE": "2025-12-31",
        "DATE_TYPE": "年报",
        "OPERATE_INCOME": 200000000000,
    }]
    ak = FakeAk(rows)
    provider = CompanyAkshareProvider()

    payload, as_of, source = provider._company_profit_cashflow_drivers(ak, "01810")
    margin_payload, margin_as_of, _ = provider._company_margin_structure(ak, "01810")
    summary_payload, summary_as_of, _ = provider._company_financial_summary(ak, "01810")

    assert ak.calls == [
        ("01810", "报告期"),
        ("01810", "报告期"),
        ("01810", "报告期"),
    ]
    assert as_of.startswith("2026-06-30")
    assert margin_as_of.startswith("2026-06-30")
    assert summary_as_of.startswith("2026-06-30")
    assert payload["annual_driver_history"][0]["report_type"] == "interim"
    assert payload["report_period_driver_history"][0]["report_type"] == "interim"
    assert margin_payload["company_margin_history"][0]["report_type"] == "interim"
    assert summary_payload["report_period_indicators"][0]["report_type"] == "interim"
    assert "indicator=报告期" in source


def test_official_release_enriches_matching_interim_fact_and_currentness_becomes_current():
    class Store:
        def cached_market_intelligence(self, key):
            assert key == "corporate_events:01810"
            return _event_bundle()

    fact = _financial_fact()
    enriched = FinancialAnnouncementEnricher(Store()).enrich(
        SimpleNamespace(symbol="01810"),
        (fact,),
    )[0]

    assert enriched.announced_at == "2026-08-18T19:05:00+08:00"
    assert enriched.provenance_hash != fact.provenance_hash

    facts, currentness = FinancialCurrentnessPolicy().evaluate((enriched, _event_fact()))
    enriched_after_policy = next(item for item in facts if item.fact_id == "financial")
    assert currentness.expected_report_at == "2026-08-18"
    assert currentness.latest_observed_period == "2026-06-30"
    assert currentness.latest_period_status == "CURRENT"
    assert currentness.current_confirmation == "CONFIRMED"
    assert enriched_after_policy.observation_currentness == "CURRENT"


def test_official_interim_release_does_not_stamp_unrelated_old_annual_fact():
    class Store:
        def cached_market_intelligence(self, _key):
            return _event_bundle()

    annual = _financial_fact(period_end="2025-12-31", report_type="annual", fact_id="annual")
    result = FinancialAnnouncementEnricher(Store()).enrich(SimpleNamespace(symbol="01810"), (annual,))[0]
    assert result.announced_at is None
    assert result.provenance_hash == annual.provenance_hash


def test_release_runtime_marks_fresh_financial_requirements_for_bounded_refresh_and_forces_only_financial_types():
    class Store:
        def cached_market_intelligence(self, key):
            assert key == "corporate_events:01810"
            return _event_bundle()

    class Service:
        def __init__(self):
            self.build_calls = []

        def requirements(self, symbol, *, research_priority=None):
            return {
                "symbol": symbol,
                "research_priority": research_priority or "L3",
                "required_datasets": [
                    {"dataset_key": "financial_summary", "data_type": "company_financial_summary", "local_status": "LOCAL_FRESH_HIT", "provider_registered": True},
                    {"dataset_key": "margin_structure", "data_type": "company_margin_structure", "local_status": "LOCAL_FRESH_HIT", "provider_registered": True},
                    {"dataset_key": "identity_business_model", "data_type": "company_identity_business_model", "local_status": "LOCAL_FRESH_HIT", "provider_registered": True},
                ],
            }

        def build_context(self, symbol, *, research_priority=None, allow_remote=True, force_refresh_data_types=(), refresh_reason=None):
            self.build_calls.append({
                "symbol": symbol,
                "priority": research_priority,
                "allow_remote": allow_remote,
                "forced": tuple(force_refresh_data_types),
                "reason": refresh_reason,
            })
            return {"symbol": symbol}

    service = Service()
    # Match production bootstrap: v2 service is the authoritative registered name.
    module = SimpleNamespace(store=Store(), company_intelligence_service_v2=service)
    install_release_refresh(module)

    assert module._financial_release_refresh_runtime_installed is True
    requirements = service.requirements("01810", research_priority="L3")
    by_key = {item["dataset_key"]: item for item in requirements["required_datasets"]}
    assert by_key["financial_summary"]["local_status"] == "LOCAL_STALE_HIT"
    assert by_key["margin_structure"]["local_status"] == "LOCAL_STALE_HIT"
    assert by_key["identity_business_model"]["local_status"] == "LOCAL_FRESH_HIT"
    assert requirements["event_driven_refresh"] == REFRESH_REASON

    service.build_context("01810", research_priority="L3", allow_remote=True)
    call = service.build_calls[-1]
    assert call["forced"] == FINANCIAL_DATA_TYPES
    assert call["reason"] == REFRESH_REASON


def test_release_runtime_does_not_mark_installed_before_v2_service_exists():
    module = SimpleNamespace(store=object())
    install_release_refresh(module)
    assert not hasattr(module, "_financial_release_refresh_runtime_installed")
