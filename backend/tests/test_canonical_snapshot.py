from datetime import date, datetime, timedelta

from app.canonical_snapshot import build_canonical_market_snapshot
from app.data_quality import summarize_data_quality
from app.decision_context import DecisionContextBuilder
from app.evidence_engine import EvidenceEngine
from app.storage import PortfolioStore
from app.time_utils import BEIJING_TIMEZONE, beijing_now
from app.trading_calendar import TradingCalendarService


def _previous_session(market: str, completed: str) -> str:
    completed_date = date.fromisoformat(completed)
    sessions = TradingCalendarService().session_dates(
        market,
        (completed_date - timedelta(days=10)).isoformat(),
        completed,
    )
    assert len(sessions) >= 2
    return sessions[-2]


def test_canonical_snapshot_rejects_newly_retrieved_but_old_market_date_quote():
    now = datetime(2026, 8, 18, 11, 0, tzinfo=BEIJING_TIMEZONE)
    snapshot = build_canonical_market_snapshot(
        market="HK",
        quote_price=27.06,
        quote_as_of="2026-08-07T16:00:00+08:00",
        quote_retrieved_at=now.isoformat(),
        daily_close=25.88,
        daily_bar_as_of="2026-08-17",
        risk_as_of="2026-08-17",
        now=now,
    )

    # Retrieval is fresh, but the observed quote market date is older than the
    # completed daily bar.  It must not become an executable price.
    assert snapshot.quote_freshness.status == "fresh"
    assert snapshot.conflict_codes == ("quote_older_than_daily_bar",)
    assert snapshot.execution_price is None
    assert snapshot.display_price == 25.88
    assert snapshot.display_price_source == "daily_close"
    assert snapshot.technical_reference_price == 25.88
    assert snapshot.technical_reference_source == "daily_close"


def test_data_quality_blocks_open_and_add_on_cross_source_quote_conflict():
    now = beijing_now()
    calendar = TradingCalendarService()
    completed = calendar.latest_completed_session_date("CN", now)
    assert completed is not None
    older = _previous_session("CN", completed)

    quality = summarize_data_quality(
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
        quote_as_of=older,
        # A fresh retrieval timestamp alone must not hide the old quote date.
        quote_retrieved_at=now.isoformat(),
        daily_bar_as_of=completed,
        risk_as_of=completed,
        market_as_of=completed,
        market="CN",
    )
    gates = {item.action: item for item in quality.action_gates}

    assert quality.status == "degraded"
    assert "consistency.quote_older_than_daily_bar" in quality.warnings
    assert "consistency.quote_older_than_daily_bar" in gates["OPEN"].unavailable_fields
    assert gates["OPEN"].permission == "blocked"
    assert gates["ADD"].permission == "blocked"
    assert gates["REDUCE"].permission == "research_only"


def test_stale_risk_is_visible_but_quarantined_from_policy_evidence(tmp_path):
    store = PortfolioStore(tmp_path / "canonical-risk.db")
    now = beijing_now()
    calendar = TradingCalendarService()
    completed = calendar.latest_completed_session_date("CN", now)
    assert completed is not None
    stale_risk_date = _previous_session("CN", completed)

    store.save_available_cash(10_000)
    store.save_quotes([{
        "symbol": "600519",
        "price": 10,
        "volume": 10_000,
        "currency": "CNY",
        "source": "test",
        "as_of": now.isoformat(),
        "retrieved_at": now.isoformat(),
    }])
    completed_date = date.fromisoformat(completed)
    bars = []
    for index in range(60):
        trading_date = (completed_date - timedelta(days=59 - index)).isoformat()
        bars.append({
            "trading_date": trading_date,
            "open": 10,
            "close": 10,
            "high": 11,
            "low": 9,
            "source": "test",
        })
    bars[-1]["trading_date"] = completed
    store.save_daily_prices("600519", bars)
    store.save_risk({
        "symbol": "600519",
        "as_of": stale_risk_date,
        "sample_count": 60,
        "historical_downside_probability": 99,
        "annualized_volatility_percent": 99,
        "risk_level": "high",
    })
    store.save_instrument_metadata({
        "symbol": "600519",
        "market": "CN",
        "currency": "CNY",
        "lot_size": 100,
        "price_tick": "0.01",
        "source": "test",
        "as_of": completed,
    })

    context = DecisionContextBuilder(store).build("600519")
    evidence = {item.evidence_id: item for item in EvidenceEngine().build(context)}

    assert evidence["risk.historical_downside_high"].usage_scope == "RESEARCH_ONLY"
    assert evidence["risk.historical_downside_high"].fresh is False
    assert evidence["risk.annualized_volatility_high"].usage_scope == "RESEARCH_ONLY"
    assert "consistency.risk_older_than_daily_bar" in context.data_quality.warnings


def test_technical_evidence_uses_newer_daily_close_when_quote_is_older(tmp_path):
    class TechnicalFixture:
        def assess(self, symbol, bars):
            return {
                "as_of": bars[-1]["trading_date"],
                "sample_count": len(bars),
                "trend": "up",
                "trend_label": "均线结构偏强",
                "sma20": 27.655,
                "sma60": 26.499,
                "rsi14": 45.0,
                "rsi_state": "neutral",
                "macd_histogram": -0.2,
                "atr_percent": 2.0,
                "drawdown_60d_percent": -20.12,
            }

    store = PortfolioStore(tmp_path / "canonical-technical.db")
    now = beijing_now()
    calendar = TradingCalendarService()
    completed = calendar.latest_completed_session_date("HK", now)
    assert completed is not None
    older = _previous_session("HK", completed)

    store.save_available_cash(10_000)
    store.save_quotes([{
        "symbol": "01810",
        "price": 27.06,
        "currency": "HKD",
        "source": "test",
        "as_of": older,
        "retrieved_at": now.isoformat(),
    }])
    completed_date = date.fromisoformat(completed)
    bars = []
    for index in range(60):
        trading_date = (completed_date - timedelta(days=59 - index)).isoformat()
        bars.append({
            "trading_date": trading_date,
            "open": 26,
            "close": 26,
            "high": 27,
            "low": 25,
            "source": "test",
        })
    bars[-1]["trading_date"] = completed
    bars[-1]["close"] = 25.88
    store.save_daily_prices("01810", bars)
    store.save_instrument_metadata({
        "symbol": "01810",
        "market": "HK",
        "currency": "HKD",
        "lot_size": 200,
        "price_tick": "0.02",
        "source": "test",
        "as_of": completed,
    })

    context = DecisionContextBuilder(store, technical_service=TechnicalFixture()).build("01810")
    evidence = {item.evidence_id: item for item in EvidenceEngine().build(context)}

    assert "consistency.quote_older_than_daily_bar" in context.data_quality.warnings
    assert evidence["trend.below_sma20_and_sma60"].value == 25.88
    assert evidence["trend.below_sma20_and_sma60"].source == "technical_analysis:daily_close"
    assert "trend.above_sma20" not in evidence
