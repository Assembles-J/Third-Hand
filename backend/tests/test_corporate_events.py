from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app import decision_config as config
from app.corporate_events import CorporateEventService, install, pre_event_policy_blockers
from app.data_quality import summarize_data_quality
from app.decision_context import DecisionContextBuilder
from app.decision_models import EventSnapshot
from app.evidence_engine import EvidenceEngine


HK_TZ = ZoneInfo("Asia/Hong_Kong")


class FakeCalendar:
    def session_dates(self, market, _start, _end):
        assert market == "HK"
        return ["2026-08-17", "2026-08-18", "2026-08-19"]


class RollingCalendar:
    def session_dates(self, market, start, _end):
        assert market == "HK"
        if start <= "2026-08-17":
            return ["2026-08-17", "2026-08-18", "2026-08-19"]
        return ["2026-08-19", "2026-08-20", "2026-08-21"]


class EventStore:
    def __init__(self):
        self.values = {}

    def instrument_metadata(self, symbol):
        assert symbol == "01810"
        return {
            "symbol": "01810", "market": "HK", "currency": "HKD",
            "lot_size": 200, "price_tick": "0.02", "source": "fixture",
            "as_of": "2026-08-17",
        }

    def cached_market_intelligence(self, key):
        return self.values.get(key)

    def save_market_intelligence(self, key, payload):
        self.values[key] = dict(payload)

    def cached_content(self, _symbols, limit=10):
        return []


def test_corporate_event_service_normalizes_hk_earnings_and_reuses_daily_cache():
    calls = []

    def fetcher(date_text):
        calls.append(date_text)
        if date_text == "20260818":
            return [{
                "股票代码": "1810",
                "交易所": "HK",
                "股票简称": "小米集团-W",
                "财报期": "2026年中报",
            }]
        return []

    store = EventStore()
    service = CorporateEventService(fetcher=fetcher, calendar=FakeCalendar())
    now = datetime(2026, 8, 17, 16, 0, tzinfo=HK_TZ)

    first = service.refresh(store, ["01810"], now=now)["01810"]
    second = service.refresh(store, ["01810"], now=now)["01810"]

    assert calls == ["20260817", "20260818", "20260819"]
    assert second == first
    assert first["status"] == "ready"
    assert first["market"] == "HK"
    assert len(first["events"]) == 1
    event = first["events"][0]
    assert event["symbol"] == "01810"
    assert event["scheduled_at"] == "2026-08-18"
    assert event["event_type"] == "earnings_report"
    assert event["impact"] == "neutral"
    assert event["evidence_polarity"] == "NEUTRAL_MATERIAL"
    assert event["verification_level"] == "secondary_calendar"
    assert event["source_rank"] == 30
    assert event["lifecycle_status"] == "SCHEDULED"
    assert event["policy_eligible"] is True
    assert store.values["corporate_events:01810"]["events"][0]["event_id"] == event["event_id"]


def test_post_event_refresh_preserves_unresolved_earnings_obligation():
    calls = []

    def fetcher(date_text):
        calls.append(date_text)
        if date_text == "20260818":
            return [{
                "股票代码": "1810",
                "交易所": "HK",
                "股票简称": "小米集团-W",
                "财报期": "2026年中报",
            }]
        return []

    store = EventStore()
    service = CorporateEventService(fetcher=fetcher, calendar=RollingCalendar())
    before = service.refresh(
        store,
        ["01810"],
        now=datetime(2026, 8, 17, 16, 0, tzinfo=HK_TZ),
    )["01810"]
    event_id = before["events"][0]["event_id"]

    after = service.refresh(
        store,
        ["01810"],
        now=datetime(2026, 8, 19, 10, 0, tzinfo=HK_TZ),
    )["01810"]

    assert after["window_dates"] == ["2026-08-19", "2026-08-20", "2026-08-21"]
    assert len(after["events"]) == 1
    event = after["events"][0]
    assert event["event_id"] == event_id
    assert event["scheduled_at"] == "2026-08-18"
    assert event["lifecycle_status"] == "RELEASE_EXPECTED"

    # Compatibility projection keeps an unresolved expected report visible to
    # frozen Evidence/currentness even though its date is now in the past.
    context_event = DecisionContextBuilder(store)._events("01810", "HK")[0]
    evidence = EvidenceEngine._events(SimpleNamespace(events=(context_event,)))
    assert context_event.lifecycle == "upcoming"
    assert evidence[0].evidence_id == f"event.upcoming.earnings_report.{event_id}"
    assert evidence[0].value == "2026-08-18"


def test_official_event_source_outranks_secondary_and_keeps_conflict_auditable():
    def secondary_fetcher(date_text):
        if date_text == "20260819":
            return [{
                "股票代码": "1810",
                "交易所": "HK",
                "股票简称": "小米集团-W",
                "财报期": "2026年中报",
            }]
        return []

    official_calls = []

    def official_fetcher(*, symbol, market, now):
        official_calls.append((symbol, market, now.date().isoformat()))
        return [{
            "symbol": "01810",
            "market": "HK",
            "name": "小米集团-W",
            "period": "2026年中报",
            "scheduled_date": "2026-08-18",
            "source": "HKEX",
            "source_reference": "https://www1.hkexnews.hk/fixture",
            "verification_level": "official",
            "parser_version": "hkex-fixture-v1",
        }]

    store = EventStore()
    service = CorporateEventService(
        fetcher=secondary_fetcher,
        official_fetcher=official_fetcher,
        calendar=FakeCalendar(),
    )
    now = datetime(2026, 8, 17, 16, 0, tzinfo=HK_TZ)

    first = service.refresh(store, ["01810"], now=now)["01810"]
    second = service.refresh(store, ["01810"], now=now)["01810"]

    assert official_calls == [("01810", "HK", "2026-08-17")]
    assert second == first
    assert len(first["events"]) == 1
    event = first["events"][0]
    assert event["source"] == "HKEX"
    assert event["verification_level"] == "official"
    assert event["source_rank"] == 10
    assert event["scheduled_at"] == "2026-08-18"
    assert event["conflict_status"] == "CONFLICTED"
    assert event["conflict_dates"] == ["2026-08-18", "2026-08-19"]
    assert set(event["conflict_sources"]) == {"HKEX", "Baidu 股市通财报日历 via AKShare"}
    assert first["official_source_status"] == "ready"
    assert any(item["lifecycle_status"] == "SUPERSEDED" for item in first["event_history"])


def test_next_session_earnings_blocks_new_risk_but_later_event_does_not():
    analysis_at = datetime(2026, 8, 17, 16, 0, tzinfo=HK_TZ)
    near = EventSnapshot(
        event_id="near",
        title="次日业绩",
        source="fixture",
        event_type="earnings_report",
        lifecycle="upcoming",
        scheduled_at="2026-08-18",
        impact="neutral",
        evidence_polarity="NEUTRAL_MATERIAL",
        verification_level="secondary_calendar",
        policy_eligible=True,
    )
    far = near.model_copy(update={"event_id": "far", "scheduled_at": "2026-08-19"})

    assert pre_event_policy_blockers((near,), market="HK", analysis_at=analysis_at, calendar=FakeCalendar()) == (
        "event_risk.upcoming_earnings:near",
    )
    assert pre_event_policy_blockers((far,), market="HK", analysis_at=analysis_at, calendar=FakeCalendar()) == ()
    assert config.PRE_EVENT_BLOCK_SESSIONS == 1
    assert config.audit_version_snapshot()["corporate_event_policy_version"] == "corporate-event-v2-persistent-lifecycle"


def test_event_policy_blocker_changes_open_add_gates_not_data_quality_or_defensive_gates():
    common = dict(
        has_quote=True,
        daily_bar_count=60,
        total_assets_available=True,
        plan_enabled=True,
        has_risk=True,
        has_market_regime=True,
        has_relative_strength=True,
        has_events=True,
        has_instrument=True,
        has_position=True,
        has_personal_rule=True,
        quote_as_of="2026-08-17T15:50:00+08:00",
        quote_retrieved_at="2026-08-17T15:50:01+08:00",
        daily_bar_as_of="2026-08-17",
        risk_as_of="2026-08-17",
        market_as_of="2026-08-17",
        market="HK",
    )
    baseline = summarize_data_quality(**common)
    gated = summarize_data_quality(
        **common,
        event_policy_blockers=("event_risk.upcoming_earnings:near",),
    )

    assert gated.status == baseline.status
    assert gated.score_percent == baseline.score_percent
    assert gated.missing_fields == baseline.missing_fields
    assert gated.stale_fields == baseline.stale_fields
    assert gated.warnings == baseline.warnings
    gates = {item.action: item for item in gated.action_gates}
    assert "event_risk.upcoming_earnings:near" in gates["OPEN"].reasons
    assert "event_risk.upcoming_earnings:near" in gates["ADD"].reasons
    assert gates["OPEN"].permission == "blocked"
    assert gates["ADD"].permission == "blocked"
    for action in ("HOLD", "WATCH", "REDUCE", "EXIT"):
        assert "event_risk.upcoming_earnings:near" not in gates[action].reasons


def test_context_reads_only_same_market_scheduled_event_as_neutral_material():
    store = EventStore()
    store.values["corporate_events:01810"] = {
        "status": "ready",
        "symbol": "01810",
        "market": "HK",
        "events": [{
            "event_id": "xiaomi-results",
            "symbol": "01810",
            "market": "HK",
            "event_type": "earnings_report",
            "title": "小米集团-W 2026年中报计划披露",
            "scheduled_at": "2026-08-18",
            "impact": "neutral",
            "evidence_polarity": "NEUTRAL_MATERIAL",
            "verification_level": "secondary_calendar",
            "policy_eligible": True,
            "source": "fixture",
            "source_reference": "https://example.com/calendar",
            "summary": "方向未知的重要事件",
        }],
    }

    event = DecisionContextBuilder(store)._events("01810", "HK")[0]

    assert event.lifecycle == "upcoming"
    assert event.event_type == "earnings_report"
    assert event.impact == "neutral"
    assert event.evidence_polarity == "NEUTRAL_MATERIAL"
    assert event.policy_eligible is True

    store.values["corporate_events:01810"]["market"] = "CN"
    store.values["corporate_events:01810"]["events"][0]["market"] = "CN"
    assert DecisionContextBuilder(store)._events("01810", "HK") == ()


def test_upcoming_earnings_evidence_is_neutral_policy_fact_not_directional_signal():
    event = EventSnapshot(
        event_id="xiaomi-results",
        title="中报计划披露",
        source="fixture",
        source_reference="https://example.com/calendar",
        event_type="earnings_report",
        lifecycle="upcoming",
        scheduled_at="2026-08-18",
        impact="neutral",
        evidence_polarity="NEUTRAL_MATERIAL",
        verification_level="secondary_calendar",
        policy_eligible=True,
        summary="方向未知的重要事件",
    )

    evidence = EvidenceEngine._events(SimpleNamespace(events=(event,)))

    assert len(evidence) == 1
    item = evidence[0]
    assert item.evidence_id == "event.upcoming.earnings_report.xiaomi-results"
    assert item.direction == "neutral"
    assert item.usage_scope == "POLICY"
    assert item.value == "2026-08-18"
    assert item.source_reference == "https://example.com/calendar"


def test_runtime_install_keeps_paper_decision_local_first_and_refreshes_on_scheduler(monkeypatch):
    order = []

    def derived(symbols, trigger, force_history=False, run_id=None):
        order.append(("derived", tuple(symbols), trigger))
        return "derived-result"

    def refresh(self, _store, symbols, *, now):
        order.append(("events", tuple(symbols), now.isoformat()))
        return {symbol: {"events": []} for symbol in symbols}

    monkeypatch.setattr(CorporateEventService, "refresh", refresh)
    module = SimpleNamespace(
        refresh_derived_cache=derived,
        store=object(),
        beijing_now=lambda: datetime(2026, 8, 17, 16, 0, tzinfo=HK_TZ),
        logger=SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None),
    )

    install(module)
    assert module.refresh_derived_cache(["01810"], "paper-trading-decision") == "derived-result"
    assert order == [("derived", ("01810",), "paper-trading-decision")]

    assert module.refresh_derived_cache(["01810"], "scheduler-trading-session") == "derived-result"
    assert order[-2] == ("derived", ("01810",), "scheduler-trading-session")
    assert order[-1][0:2] == ("events", ("01810",))


def test_runtime_scheduler_event_failure_does_not_abort_derived_refresh(monkeypatch):
    def failing_refresh(self, _store, _symbols, *, now):
        raise RuntimeError("calendar unavailable")

    monkeypatch.setattr(CorporateEventService, "refresh", failing_refresh)
    module = SimpleNamespace(
        refresh_derived_cache=lambda *_args, **_kwargs: "derived-result",
        store=object(),
        beijing_now=lambda: datetime(2026, 8, 17, 16, 0, tzinfo=HK_TZ),
        logger=SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None),
    )

    install(module)
    assert module.refresh_derived_cache(["01810"], "scheduler-trading-session") == "derived-result"
