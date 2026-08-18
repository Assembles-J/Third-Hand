from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from pydantic import BaseModel, Field

from app.mandatory_acquisition import (
    ACQUISITION_LATEST_KEY_PREFIX,
    AcquisitionAwareContextBuilder,
    ResearchAcquisitionOrchestrator,
    bind_acquisition_manifests,
    requirement_action,
)


def test_requirement_state_turns_registered_local_miss_into_fetch():
    assert requirement_action("LOCAL_FRESH_HIT", True) == "REUSE"
    assert requirement_action("LOCAL_STALE_HIT", True) == "REFRESH"
    assert requirement_action("LOCAL_MISS", True) == "FETCH"
    assert requirement_action("LOCAL_MISS", False) == "UNAVAILABLE"
    assert requirement_action("LOCAL_STALE_HIT", False) == "UNAVAILABLE"


class _Store:
    def __init__(self):
        self.market = {}

    def cached_market_intelligence(self, key):
        return self.market.get(key)

    def save_market_intelligence(self, key, payload):
        self.market[key] = dict(payload)
        return self.market[key]


class _ContextBuilder:
    def __init__(self):
        self.market_refreshed = False

    def build(self, symbol):
        state = "fresh" if self.market_refreshed else "stale"
        items = [
            SimpleNamespace(source_key="quote", status=state),
            SimpleNamespace(source_key="daily_bars", status=state),
            SimpleNamespace(source_key="risk", status=state),
            SimpleNamespace(source_key="market_regime", status="unknown"),
        ]
        return SimpleNamespace(
            data_quality=SimpleNamespace(source_freshness=items),
            instrument=None,
            quote=SimpleNamespace(as_of="2026-08-18" if self.market_refreshed else "2026-08-07"),
            daily_bars=SimpleNamespace(last_trading_date="2026-08-18" if self.market_refreshed else "2026-08-17"),
            risk=SimpleNamespace(as_of="2026-08-18" if self.market_refreshed else "2026-08-04"),
            market_regime=None,
        )


class _CompanyService:
    def __init__(self):
        self.fetched = False
        self.build_calls = 0

    def requirements(self, symbol, *, research_priority=None):
        return {
            "symbol": symbol,
            "research_priority": research_priority or "L3",
            "required_datasets": [
                {
                    "dataset_key": "financial_summary",
                    "local_status": "LOCAL_FRESH_HIT" if self.fetched else "LOCAL_MISS",
                    "freshness_status": "fresh" if self.fetched else "missing",
                    "provider_registered": True,
                },
                {
                    "dataset_key": "risks_catalysts",
                    "local_status": "LOCAL_MISS",
                    "freshness_status": "missing",
                    "provider_registered": False,
                },
            ],
        }

    def build_context(self, symbol, *, research_priority=None, allow_remote=True):
        assert allow_remote is True
        self.build_calls += 1
        self.fetched = True
        return {
            "symbol": symbol,
            "research_priority": research_priority or "L3",
            "dataset_refs": [
                {
                    "dataset_key": "financial_summary",
                    "provider": "fixture-provider",
                    "payload_hash": "financial-hash",
                    "as_of": "2025-12-31T00:00:00+08:00",
                    "available_at": "2026-08-18T19:40:00+08:00",
                    "freshness_status": "fresh",
                }
            ],
            "missing_datasets": ["risks_catalysts"],
            "research_ready": False,
        }


class _CorporateEventService:
    def __init__(self):
        self.calls = 0

    def refresh(self, store, symbols, *, now):
        self.calls += 1
        symbol = symbols[0]
        bundle = {
            "status": "ready",
            "symbol": symbol,
            "market": "HK",
            "window_dates": ["2026-08-18", "2026-08-19", "2026-08-20"],
            "events": [
                {
                    "event_id": "corp-xiaomi-earnings",
                    "symbol": symbol,
                    "market": "HK",
                    "event_type": "earnings_report",
                    "scheduled_at": "2026-08-18",
                }
            ],
            "source": "fixture-calendar",
            "retrieved_at": now.isoformat(),
            "unavailable_dates": [],
        }
        store.save_market_intelligence(f"corporate_events:{symbol}", bundle)
        return {symbol: bundle}


def test_acquisition_fetches_registered_miss_and_preserves_unregistered_gap():
    store = _Store()
    builder = _ContextBuilder()
    company = _CompanyService()
    events = _CorporateEventService()
    quote_calls = []
    derived_calls = []

    def fetch_quotes(symbols, **kwargs):
        quote_calls.append((tuple(symbols), kwargs))

    def refresh_derived(symbols, trigger, **kwargs):
        derived_calls.append((tuple(symbols), trigger, kwargs))
        builder.market_refreshed = True

    service = ResearchAcquisitionOrchestrator(
        store=store,
        context_builder=builder,
        company_service=company,
        corporate_event_service=events,
        fetch_quotes=fetch_quotes,
        refresh_derived=refresh_derived,
        now=lambda: datetime(2026, 8, 18, 19, 40, tzinfo=timezone.utc),
    )

    result = service.acquire(
        "01810",
        research_priority="L3",
        trigger="api-formal-decision",
    )
    manifest = result.manifest
    by_key = {item["requirement_key"]: item for item in manifest["items"]}

    assert company.build_calls == 1
    assert len(quote_calls) == 1
    assert len(derived_calls) == 1
    assert events.calls == 1

    financial = by_key["financial_summary"]
    assert financial["pre_state"] == "LOCAL_MISS"
    assert financial["action"] == "FETCH"
    assert financial["attempted"] is True
    assert financial["post_state"] == "LOCAL_FRESH_HIT"
    assert financial["attempt_status"] == "ok"
    assert financial["provider"] == "fixture-provider"

    missing = by_key["risks_catalysts"]
    assert missing["action"] == "UNAVAILABLE"
    assert missing["attempted"] is False
    assert missing["post_state"] == "LOCAL_MISS"
    assert missing["error_code"] == "provider_unregistered"

    event = by_key["corporate_events"]
    assert event["attempted"] is True
    assert event["post_state"] == "READY"

    assert by_key["quote"]["post_state"] == "fresh"
    assert by_key["daily_bars"]["post_state"] == "fresh"
    assert by_key["risk"]["post_state"] == "fresh"
    assert by_key["market_regime"]["action"] == "UNAVAILABLE"
    assert manifest["status"] == "degraded"

    latest = store.market[f"{ACQUISITION_LATEST_KEY_PREFIX}01810"]
    assert latest["manifest_id"] == manifest["manifest_id"]
    assert latest["manifest_hash"] == manifest["manifest_hash"]


def test_fresh_market_and_company_data_are_reused_without_remote_fetch():
    store = _Store()
    builder = _ContextBuilder()
    builder.market_refreshed = True
    company = _CompanyService()
    company.fetched = True
    events = _CorporateEventService()
    quote_calls = []
    derived_calls = []

    service = ResearchAcquisitionOrchestrator(
        store=store,
        context_builder=builder,
        company_service=company,
        corporate_event_service=events,
        fetch_quotes=lambda *args, **kwargs: quote_calls.append(1),
        refresh_derived=lambda *args, **kwargs: derived_calls.append(1),
        now=lambda: datetime(2026, 8, 18, 19, 40, tzinfo=timezone.utc),
    )

    manifest = service.acquire(
        "01810",
        research_priority="L3",
        trigger="api-formal-decision",
    ).manifest
    by_key = {item["requirement_key"]: item for item in manifest["items"]}

    assert quote_calls == []
    assert derived_calls == []
    assert company.build_calls == 0
    assert by_key["financial_summary"]["action"] == "REUSE"
    assert by_key["quote"]["action"] == "REUSE"


class _FakeGate(BaseModel):
    action: str
    permission: str = "allowed"
    reasons: tuple[str, ...] = ()
    unavailable_fields: tuple[str, ...] = ()


class _FakeQuality(BaseModel):
    status: str = "ready"
    warnings: tuple[str, ...] = ()
    action_gates: tuple[_FakeGate, ...] = Field(default_factory=lambda: (
        _FakeGate(action="OPEN"),
        _FakeGate(action="ADD"),
        _FakeGate(action="WATCH", permission="research_only"),
    ))


class _FakeContext(BaseModel):
    context_id: str = "context-1"
    generated_at: str = "2026-08-18T19:40:00+08:00"
    input_hash: str = "before"
    timeframe_technicals: tuple = ()
    source_versions: dict[str, str] = Field(default_factory=lambda: {"context_schema": "context-v4-single-cny"})
    data_quality: _FakeQuality = Field(default_factory=_FakeQuality)
    symbol: str = "01810"
    value: int = 1


class _FakeDelegate:
    def build(self, symbol, **kwargs):
        return _FakeContext(symbol=symbol)


def test_context_manifest_link_is_request_scoped_and_changes_input_hash():
    builder = AcquisitionAwareContextBuilder(_FakeDelegate())
    manifest = {"manifest_id": "manifest-1", "manifest_hash": "hash-1", "status": "ready", "items": []}

    unbound = builder.build("01810")
    assert "acquisition_manifest_id" not in unbound.source_versions
    assert unbound.input_hash == "before"

    with bind_acquisition_manifests({"01810": manifest}):
        bound = builder.build("01810")

    assert bound.source_versions["acquisition_manifest_id"] == "manifest-1"
    assert bound.source_versions["acquisition_manifest_hash"] == "hash-1"
    assert bound.input_hash != "before"

    after = builder.build("01810")
    assert "acquisition_manifest_id" not in after.source_versions


def test_action_critical_acquisition_gap_blocks_open_add_but_research_only_gap_does_not():
    builder = AcquisitionAwareContextBuilder(_FakeDelegate())
    manifest = {
        "manifest_id": "manifest-2",
        "manifest_hash": "hash-2",
        "status": "degraded",
        "items": [
            {
                "requirement_key": "corporate_events",
                "mandatory_for": ["OPEN", "ADD", "research"],
                "post_state": "UNAVAILABLE",
            },
            {
                "requirement_key": "risks_catalysts",
                "mandatory_for": ["research"],
                "post_state": "LOCAL_MISS",
            },
        ],
    }

    with bind_acquisition_manifests({"01810": manifest}):
        context = builder.build("01810")

    gates = {gate.action: gate for gate in context.data_quality.action_gates}
    assert gates["OPEN"].permission == "blocked"
    assert gates["ADD"].permission == "blocked"
    assert "mandatory_acquisition.degraded" in gates["OPEN"].reasons
    assert gates["OPEN"].unavailable_fields == ("mandatory_acquisition.corporate_events",)
    assert gates["WATCH"].permission == "research_only"
    assert "mandatory_acquisition.risks_catalysts" not in gates["OPEN"].unavailable_fields
