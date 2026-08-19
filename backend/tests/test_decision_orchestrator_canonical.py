from datetime import date, timedelta

from app import decision_config as config
from app.action_policy import ActionPolicyEngine
from app.decision_context import DecisionContextBuilder
from app.decision_orchestrator import DecisionOrchestrator
from app.evidence_engine import EvidenceEngine
from app.storage import PortfolioStore
from app.time_utils import beijing_now
from app.trading_calendar import TradingCalendarService


class _Sizing:
    def size(self, _context, _action):
        raise AssertionError("sizing is disabled in these tests")


class _Ai:
    def assess(self, *_args, **_kwargs):
        raise AssertionError("AI is disabled in these tests")


class _Guard:
    def guard(self, _candidates, _assessment):
        return None


def _sessions(market: str, count: int = 60) -> list[str]:
    service = TradingCalendarService()
    now = beijing_now()
    completed = service.latest_completed_session_date(market, now)
    assert completed is not None
    end = date.fromisoformat(completed)
    sessions = service.session_dates(
        market,
        (end - timedelta(days=140)).isoformat(),
        completed,
    )
    assert len(sessions) >= count
    return sessions[-count:]


def _store_with_hk_conflict(tmp_path, *, with_position: bool) -> PortfolioStore:
    store = PortfolioStore(tmp_path / "canonical-report.db")
    sessions = _sessions("HK")
    completed, older = sessions[-1], sessions[-2]
    now = beijing_now()

    if with_position:
        store.add("holding-1", "01810", "Xiaomi", 2_000, 30)
    store.save_available_cash(10_000)
    store.save_quotes([{
        "symbol": "01810",
        "price": 27.06,
        "change_percent": 9.9,
        "volume": 100_000,
        "currency": "HKD",
        "source": "test",
        "as_of": older,
        # Retrieval is current; observed market date is still older than daily.
        "retrieved_at": now.isoformat(),
    }])
    bars = [{
        "trading_date": session,
        "open": 26,
        "close": 26,
        "high": 27,
        "low": 25,
        "source": "test",
    } for session in sessions]
    bars[-1]["close"] = 25.88
    store.save_daily_prices("01810", bars)
    store.save_risk({
        "symbol": "01810",
        "as_of": completed,
        "sample_count": 60,
        "historical_downside_probability": 10,
        "annualized_volatility_percent": 20,
        "risk_level": "low",
    })
    store.save_instrument_metadata({
        "symbol": "01810",
        "market": "HK",
        "currency": "HKD",
        "lot_size": 200,
        "price_tick": "0.02",
        "source": "test",
        "as_of": completed,
    })
    if with_position:
        store.save_personal_rule({
            "id": "rule-1",
            "scope": "global",
            "symbol": None,
            "max_position_percent": 1,
            "loss_review_percent": 15,
            "volatility_review_percent": 50,
            "enabled": True,
            "version": 1,
            "updated_at": now.isoformat(),
        })
    return store


def test_decision_report_uses_canonical_daily_display_when_quote_conflicts(tmp_path, monkeypatch):
    store = _store_with_hk_conflict(tmp_path, with_position=False)
    context = DecisionContextBuilder(store).build("01810")
    monkeypatch.setattr(config, "DECISION_AI_ENABLED", False)
    monkeypatch.setattr(config, "DECISION_SIZING_ENABLED", False)

    report = DecisionOrchestrator(
        EvidenceEngine(), ActionPolicyEngine(), _Sizing(), _Ai(), _Guard()
    ).generate(context)

    assert "consistency.quote_older_than_daily_bar" in context.data_quality.warnings
    assert report.market_price == 25.88
    assert report.market_change_percent is None
    assert report.market_as_of == context.daily_bars.last_trading_date
    assert report.execution_eligible_after is None
    assert report.operation_items[0].reference_price == 25.88

    # StrategyProfile is identity/audit metadata around the existing authority
    # chain; it must bind to the actual policies without changing the action.
    assert report.strategy is not None
    assert report.strategy.strategy_id == "SWING_V1"
    assert report.strategy.strategy_version == "1.0.0"
    assert report.strategy.policy_versions["action_policy"] == report.policy_version
    assert report.timeframe_authority is not None
    assert (
        report.strategy.policy_versions["timeframe_authority"]
        == report.timeframe_authority.policy_version
    )


def test_consistency_conflict_cannot_generate_reduce_from_stale_position_valuation(tmp_path):
    store = _store_with_hk_conflict(tmp_path, with_position=True)
    context = DecisionContextBuilder(store).build("01810")
    evidence = EvidenceEngine().build(context)

    assert "position.above_max" in {item.evidence_id for item in evidence}
    assert "consistency.quote_older_than_daily_bar" in context.data_quality.warnings

    candidates = ActionPolicyEngine().evaluate(context, evidence)

    assert all(candidate.action != "REDUCE" for candidate in candidates)
