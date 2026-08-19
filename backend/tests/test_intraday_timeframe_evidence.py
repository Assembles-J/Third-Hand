from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.atomic_intraday import IntradayTimeframeAtomicSource
from app.atomic_models import AtomicEvidenceSnapshot, AtomicFactRecord, EvidenceAvailabilityRecord
from app.intraday_research_authority import IntradayAuthoritySafeResearchAggregator
from app.intraday_timeframes import _completed_buckets, build_intraday_timeframe_snapshots
from app.research_assessment import ResearchAggregator


BEIJING = timezone(timedelta(hours=8))
HONG_KONG = timezone(timedelta(hours=8))


class FakeCalendar:
    def __init__(self, latest="2026-08-19"):
        self.latest = latest

    def latest_completed_session_date(self, _market, _moment):
        return self.latest


def _minute_rows(day: str, start_hour: int, start_minute: int, count: int, *, source="fixture"):
    start = datetime.fromisoformat(f"{day}T{start_hour:02d}:{start_minute:02d}:00+08:00")
    rows = []
    for index in range(count):
        moment = start + timedelta(minutes=index)
        base = 10 + index * 0.001
        rows.append({
            "bar_time": moment.isoformat(),
            "open": base,
            "close": base + 0.01,
            "high": base + 0.02,
            "low": base - 0.01,
            "volume": 100 + index,
            "amount": 1000 + index,
            "source": source,
            "updated_at": (moment + timedelta(seconds=3)).isoformat(),
        })
    return rows


def _full_cn_day(day: str):
    return [
        *_minute_rows(day, 9, 30, 120),
        *_minute_rows(day, 13, 0, 120),
    ]


def test_current_incomplete_five_minute_bucket_is_excluded():
    rows = _minute_rows("2026-08-19", 9, 30, 33)  # through 10:02
    snapshots = build_intraday_timeframe_snapshots(
        rows,
        market="CN",
        analysis_at=datetime(2026, 8, 19, 10, 3, tzinfo=BEIJING),
        calendar=FakeCalendar("2026-08-18"),
    )
    by_timeframe = {item.timeframe: item for item in snapshots}

    assert by_timeframe["5m"].last_completed_bar == "2026-08-19T10:00:00+08:00"
    assert by_timeframe["5m"].as_of == "2026-08-19T10:00:00+08:00"
    assert by_timeframe["5m"].availability == "MISSING"  # only six completed buckets, technical minimum is 12
    assert "intraday.insufficient_completed_buckets" in by_timeframe["5m"].reason_codes


def test_cn_sixty_minute_buckets_never_bridge_the_lunch_break():
    rows = [
        *_minute_rows("2026-08-19", 10, 30, 60),  # 10:30-11:29
        *_minute_rows("2026-08-19", 13, 0, 60),   # 13:00-13:59
    ]
    buckets = _completed_buckets(
        rows,
        market="CN",
        timezone_name="Asia/Shanghai",
        minutes=60,
        analysis_at=datetime(2026, 8, 19, 14, 1, tzinfo=BEIJING),
    )

    assert [(item["start"], item["end"]) for item in buckets] == [
        ("2026-08-19T10:30:00+08:00", "2026-08-19T11:30:00+08:00"),
        ("2026-08-19T13:00:00+08:00", "2026-08-19T14:00:00+08:00"),
    ]


def test_same_frozen_intraday_rows_produce_identical_timeframe_hashes():
    rows = [
        *_full_cn_day("2026-08-17"),
        *_full_cn_day("2026-08-18"),
        *_full_cn_day("2026-08-19"),
    ]
    kwargs = dict(
        market="CN",
        analysis_at=datetime(2026, 8, 19, 15, 10, tzinfo=BEIJING),
        calendar=FakeCalendar("2026-08-19"),
    )
    first = build_intraday_timeframe_snapshots(rows, **kwargs)
    second = build_intraday_timeframe_snapshots(list(rows), **kwargs)

    assert first == second
    assert {item.timeframe: item.source_hash for item in first} == {
        item.timeframe: item.source_hash for item in second
    }
    assert {item.timeframe: item.availability for item in first} == {
        "60m": "AVAILABLE",
        "15m": "AVAILABLE",
        "5m": "AVAILABLE",
    }


def test_missing_latest_session_is_explicitly_stale_not_neutral():
    rows = [
        *_full_cn_day("2026-08-17"),
        *_full_cn_day("2026-08-18"),
    ]
    snapshots = build_intraday_timeframe_snapshots(
        rows,
        market="CN",
        analysis_at=datetime(2026, 8, 19, 15, 10, tzinfo=BEIJING),
        calendar=FakeCalendar("2026-08-19"),
    )

    assert all(item.availability == "STALE" for item in snapshots)
    assert all(item.freshness_status == "stale" for item in snapshots)
    assert all("intraday.latest_completed_bucket_missing" in item.reason_codes for item in snapshots)


def test_intraday_atomic_source_is_local_only_and_exposes_availability_and_provenance():
    rows = [
        *_full_cn_day("2026-08-17"),
        *_full_cn_day("2026-08-18"),
        *_full_cn_day("2026-08-19"),
    ]

    class Store:
        def __init__(self): self.calls = []
        def intraday_prices(self, symbol, limit=5000):
            self.calls.append((symbol, limit))
            return rows

    store = Store()
    source = IntradayTimeframeAtomicSource(store, calendar=FakeCalendar("2026-08-19"))
    context = SimpleNamespace(
        symbol="600000",
        instrument=SimpleNamespace(market="CN"),
        generated_at=datetime(2026, 8, 19, 15, 10, tzinfo=BEIJING),
        input_hash="frozen-input",
    )
    result = source.build(context)

    assert store.calls == [("600000", 5000)]
    assert {item.capability: item.status for item in result.availability} == {
        "intraday.15m": "available",
        "intraday.5m": "available",
        "intraday.60m": "available",
    }
    assert {item.dimension for item in result.facts} == {
        "intraday_research_60m", "intraday_research_15m", "intraday_research_5m",
    }
    assert all(item.domain == "intraday_research" for item in result.facts)
    assert all(item.polarity == "NEUTRAL_MATERIAL" for item in result.facts)
    assert all(len(item.provenance_hash) == 64 for item in result.facts)
    assert any(item.metric == "intraday.60m.trend_structure" for item in result.facts)


def _fact(fact_id, *, dimension, polarity, confidence):
    return AtomicFactRecord(
        fact_id=fact_id,
        symbol="600000",
        market="CN",
        domain="trend" if not dimension.startswith("intraday") else "intraday_research",
        dimension=dimension,
        metric=fact_id,
        value="fixture",
        observed_at=datetime(2026, 8, 19, 15, 10, tzinfo=BEIJING),
        freshness_status="fresh",
        polarity=polarity,
        materiality="high",
        comparison_adequacy="adequate",
        confidence=confidence,
        provenance_hash="a" * 64 if "daily" in fact_id else "b" * 64,
    )


def test_intraday_research_cannot_change_formal_deterministic_research_before_phase48():
    daily = _fact(
        "daily.technical.adverse",
        dimension="technical_trend",
        polarity="ADVERSE",
        confidence=.9,
    )
    intraday = _fact(
        "intraday.5m.noise",
        dimension="intraday_research_5m",
        polarity="NEUTRAL_MATERIAL",
        confidence=.1,
    )
    baseline = AtomicEvidenceSnapshot(
        version="fixture",
        context_id="ctx",
        context_input_hash="input",
        symbol="600000",
        market="CN",
        generated_at=datetime(2026, 8, 19, 15, 10, tzinfo=BEIJING),
        facts=(daily,),
        availability=(),
        conflicts=(),
        snapshot_hash="1" * 64,
    )
    full = baseline.model_copy(update={
        "facts": (daily, intraday),
        "availability": (
            EvidenceAvailabilityRecord(
                capability="intraday.5m",
                status="missing",
                reason_codes=("fixture",),
                source_keys=("intraday_price_cache",),
            ),
        ),
        "snapshot_hash": "2" * 64,
    })

    expected = ResearchAggregator().build(baseline)
    actual = IntradayAuthoritySafeResearchAggregator().build(full)

    assert actual.research_bias == expected.research_bias
    assert actual.technical_state == expected.technical_state
    assert actual.evidence_confidence == expected.evidence_confidence
    assert actual.research_conviction == expected.research_conviction
    assert actual.evidence_snapshot_hash == full.snapshot_hash
    assert actual.aggregation_policy_versions["intraday_authority"] == "intraday-research-authority-v1-no-formal-effect"
