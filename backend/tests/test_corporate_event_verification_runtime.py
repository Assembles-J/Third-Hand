from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.corporate_event_verification_runtime import (
    CORPORATE_EVENT_VERIFICATION_VERSION,
    install,
    reconcile_company_context,
)
from app.financial_release_refresh_runtime import install as install_release_refresh


BEIJING = timezone(timedelta(hours=8))
NOW = datetime(2026, 8, 19, 10, 0, tzinfo=BEIJING)


def _event(*, lifecycle="RELEASE_EXPECTED"):
    return {
        "event_id": "xiaomi-2026-interim",
        "event_key": "xiaomi-2026-interim-key",
        "symbol": "01810",
        "market": "HK",
        "event_type": "earnings_report",
        "period": "2026年中报",
        "scheduled_at": "2026-08-18",
        "lifecycle_status": lifecycle,
        "verification_level": "official",
        "source_rank": 10,
        "source": "HKEXnews",
        "source_reference": "https://www.hkexnews.hk/fixture.pdf",
        "announced_at": "2026-08-18T19:05:00+08:00",
        "policy_eligible": True,
    }


def _company_context(*, report_date="2026-06-30", report_type="interim"):
    return {
        "symbol": "01810",
        "datasets": {
            "financial_summary": {
                "report_period_indicators": [{
                    "REPORT_DATE": report_date,
                    "report_type": report_type,
                    "OPERATE_INCOME": 116000000000,
                }],
            },
        },
        "dataset_refs": [{
            "dataset_key": "financial_summary",
            "data_type": "company_financial_summary",
            "snapshot_id": "snapshot-current",
            "payload_hash": "f" * 64,
            "provider": "AKShare",
            "as_of": report_date,
            "available_at": "2026-08-19T09:58:00+08:00",
            "freshness_status": "fresh",
        }],
    }


class Store:
    def __init__(self, bundle=None):
        self.values = {
            "corporate_events:01810": bundle or {
                "status": "ready",
                "symbol": "01810",
                "market": "HK",
                "events": [_event()],
                "event_history": [],
            }
        }

    def cached_market_intelligence(self, key):
        return self.values.get(key)

    def save_market_intelligence(self, key, payload):
        self.values[key] = dict(payload)


def test_matching_normalized_interim_report_marks_official_event_verified_with_snapshot_lineage():
    store = Store()

    changed = reconcile_company_context(store, "01810", _company_context(), now=NOW)

    assert changed == 1
    bundle = store.values["corporate_events:01810"]
    assert len(bundle["events"]) == 1
    event = bundle["events"][0]
    assert event["lifecycle_status"] == "VERIFIED"
    assert event["verified_at"] == NOW.isoformat()
    assert event["verification_reason"] == "matching_normalized_financial_report"
    assert event["verification_policy_version"] == CORPORATE_EVENT_VERIFICATION_VERSION
    assert event["verification_dataset_key"] == "financial_summary"
    assert event["verification_snapshot_id"] == "snapshot-current"
    assert event["verification_payload_hash"] == "f" * 64
    assert event["verification_report_period"] == "2026-06-30"
    assert event["verification_report_type"] == "interim"


def test_old_annual_report_cannot_verify_current_interim_event():
    store = Store()

    changed = reconcile_company_context(
        store,
        "01810",
        _company_context(report_date="2025-12-31", report_type="annual"),
        now=NOW,
    )

    assert changed == 0
    assert store.values["corporate_events:01810"]["events"][0]["lifecycle_status"] == "RELEASE_EXPECTED"


def test_later_event_refresh_cannot_regress_verified_lifecycle():
    store = Store()
    reconcile_company_context(store, "01810", _company_context(), now=NOW)

    class Service:
        def refresh(self, store_arg, symbols, *, now):
            # Simulate the ordinary provider refresh rebuilding the same official
            # event as non-terminal RELEASED_UNVERIFIED.
            bundle = {
                "status": "ready",
                "symbol": "01810",
                "market": "HK",
                "events": [_event(lifecycle="RELEASED_UNVERIFIED")],
                "event_history": [],
            }
            store_arg.save_market_intelligence("corporate_events:01810", bundle)
            return {"01810": bundle}

    module = SimpleNamespace(store=store, corporate_event_service=Service())
    install(module)
    refreshed = module.corporate_event_service.refresh(
        store,
        ["01810"],
        now=NOW + timedelta(days=1),
    )["01810"]

    event = refreshed["events"][0]
    assert event["lifecycle_status"] == "VERIFIED"
    assert event["verification_snapshot_id"] == "snapshot-current"
    assert event["verification_policy_version"] == CORPORATE_EVENT_VERIFICATION_VERSION


def test_release_refresh_reconciles_event_after_successful_company_build():
    store = Store()

    class CompanyService:
        def requirements(self, symbol, *, research_priority=None):
            return {
                "symbol": symbol,
                "required_datasets": [{
                    "dataset_key": "financial_summary",
                    "data_type": "company_financial_summary",
                    "local_status": "LOCAL_FRESH_HIT",
                    "provider_registered": True,
                }],
            }

        def build_context(self, symbol, *, research_priority=None, allow_remote=True, force_refresh_data_types=(), refresh_reason=None):
            return _company_context()

    service = CompanyService()
    module = SimpleNamespace(store=store, company_intelligence_service=service)
    install_release_refresh(module)

    service.build_context("01810", research_priority="L3", allow_remote=True)

    event = store.values["corporate_events:01810"]["events"][0]
    assert event["lifecycle_status"] == "VERIFIED"
    assert event["verification_snapshot_id"] == "snapshot-current"


def test_verified_event_no_longer_forces_repeated_financial_refresh():
    verified_bundle = {
        "status": "ready",
        "symbol": "01810",
        "market": "HK",
        "events": [{**_event(lifecycle="VERIFIED"), "verified_at": NOW.isoformat()}],
        "event_history": [],
    }
    store = Store(verified_bundle)

    class CompanyService:
        def __init__(self): self.calls = []
        def requirements(self, symbol, *, research_priority=None):
            return {
                "symbol": symbol,
                "required_datasets": [{
                    "dataset_key": "financial_summary",
                    "data_type": "company_financial_summary",
                    "local_status": "LOCAL_FRESH_HIT",
                    "provider_registered": True,
                }],
            }
        def build_context(self, symbol, *, research_priority=None, allow_remote=True, force_refresh_data_types=(), refresh_reason=None):
            self.calls.append(tuple(force_refresh_data_types))
            return _company_context()

    service = CompanyService()
    module = SimpleNamespace(store=store, company_intelligence_service=service)
    install_release_refresh(module)

    requirements = service.requirements("01810", research_priority="L3")
    service.build_context("01810", research_priority="L3", allow_remote=True)

    assert requirements["required_datasets"][0]["local_status"] == "LOCAL_FRESH_HIT"
    assert service.calls == [()]
