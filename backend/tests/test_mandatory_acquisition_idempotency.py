from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.mandatory_acquisition import ResearchAcquisitionOrchestrator


class _Store:
    def __init__(self):
        self.values = {}

    def cached_market_intelligence(self, key):
        return self.values.get(key)

    def save_market_intelligence(self, key, value):
        self.values[key] = dict(value)
        return self.values[key]


class _Builder:
    def build(self, symbol):
        freshness = [
            SimpleNamespace(source_key="quote", status="fresh"),
            SimpleNamespace(source_key="daily_bars", status="fresh"),
            SimpleNamespace(source_key="risk", status="fresh"),
            SimpleNamespace(source_key="market_regime", status="fresh"),
        ]
        return SimpleNamespace(
            data_quality=SimpleNamespace(source_freshness=freshness),
            instrument=SimpleNamespace(market="CN", source="fixture", as_of="2026-08-18"),
            quote=SimpleNamespace(as_of="2026-08-18"),
            daily_bars=SimpleNamespace(last_trading_date="2026-08-18"),
            risk=SimpleNamespace(as_of="2026-08-18"),
            market_regime=SimpleNamespace(as_of="2026-08-18"),
        )


class _Company:
    def __init__(self):
        self.build_calls = 0

    def requirements(self, symbol, *, research_priority=None):
        return {
            "symbol": symbol,
            "research_priority": research_priority or "L1",
            "required_datasets": [
                {
                    "dataset_key": "identity_business_model",
                    "local_status": "LOCAL_FRESH_HIT",
                    "freshness_status": "fresh",
                    "provider_registered": True,
                }
            ],
        }

    def latest_context(self, symbol):
        return {
            "dataset_refs": [
                {
                    "dataset_key": "identity_business_model",
                    "provider": "fixture",
                    "payload_hash": "company-hash",
                    "as_of": "2026-08-18T00:00:00+08:00",
                    "available_at": "2026-08-18T19:00:00+08:00",
                    "freshness_status": "fresh",
                }
            ]
        }

    def build_context(self, *args, **kwargs):
        self.build_calls += 1
        raise AssertionError("fresh company data must not be fetched")


class _Events:
    def __init__(self):
        self.calls = 0

    def refresh(self, store, symbols, *, now):
        self.calls += 1
        symbol = symbols[0]
        bundle = {
            "status": "ready",
            "symbol": symbol,
            "market": "CN",
            "window_dates": ["2026-08-18", "2026-08-19", "2026-08-20"],
            "events": [],
            "source": "fixture",
            "retrieved_at": now.isoformat(),
            "unavailable_dates": [],
        }
        store.save_market_intelligence(f"corporate_events:{symbol}", bundle)
        return {symbol: bundle}


def test_duplicate_formal_preflight_reuses_same_recent_manifest(monkeypatch):
    monkeypatch.setenv("MANDATORY_ACQUISITION_COOLDOWN_SECONDS", "60")
    store = _Store()
    events = _Events()
    company = _Company()
    now = datetime(2026, 8, 18, 19, 40, tzinfo=timezone.utc)

    service = ResearchAcquisitionOrchestrator(
        store=store,
        context_builder=_Builder(),
        company_service=company,
        corporate_event_service=events,
        fetch_quotes=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fresh quote must not fetch")),
        refresh_derived=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fresh derived data must not fetch")),
        now=lambda: now,
    )

    first = service.acquire_many(
        ["600519"],
        research_priority=None,
        trigger="api-formal-decision",
    )["600519"]
    second = service.acquire_many(
        ["600519"],
        research_priority=None,
        trigger="api-formal-decision",
    )["600519"]

    assert first["manifest_id"] == second["manifest_id"]
    assert first["manifest_hash"] == second["manifest_hash"]
    assert events.calls == 1
    assert company.build_calls == 0
