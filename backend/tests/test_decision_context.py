from app.data_quality import summarize_data_quality
from app.decision_context import DecisionContextBuilder
from app.storage import PortfolioStore


def _bars():
    return [{
        "trading_date": f"2026-07-{index + 1:02d}", "open": 10, "close": 10 + index / 10,
        "high": 11 + index / 10, "low": 9 + index / 10, "source": "test",
    } for index in range(60)]


def _plan():
    return {
        "id": "plan-1", "symbol": "600519", "horizon": "swing", "thesis": "test",
        "market_expectation": "test", "catalysts": [], "entry_condition": "entry",
        "add_condition": "add", "reduce_condition": "reduce", "exit_condition": "exit",
        "max_position_percent": 15, "risk_budget_percent": 3, "enabled": True, "version": 1,
    }


def test_context_builder_has_stable_input_hash_and_does_not_need_an_action(tmp_path):
    store = PortfolioStore(tmp_path / "context.db")
    store.add("holding-1", "600519", "test", 100, 10)
    store.save_available_cash(1000)
    store.save_quotes([{"symbol": "600519", "price": 12, "currency": "CNY", "source": "test", "as_of": "2026-07-31", "retrieved_at": "2026-07-31T10:00:00+08:00"}])
    store.save_daily_prices("600519", _bars())
    store.save_risk({"symbol": "600519", "as_of": "2026-07-31", "sample_count": 60, "historical_downside_probability": 10, "annualized_volatility_percent": 20, "risk_level": "low"})
    store.save_trade_plan(_plan())
    store.save_personal_rule({"id": "rule-1", "scope": "global", "symbol": None, "max_position_percent": 20, "loss_review_percent": 15, "volatility_review_percent": 50, "enabled": True, "version": 1, "updated_at": "2026-07-31T10:00:00+08:00"})
    store.save_instrument_metadata({"symbol": "600519", "market": "CN", "currency": "CNY", "lot_size": 100, "price_tick": "0.01", "source": "test", "as_of": "2026-07-31"})

    first, second = DecisionContextBuilder(store).build(" 600519 "), DecisionContextBuilder(store).build("600519")

    assert first.symbol == "600519"
    assert first.input_hash == second.input_hash
    assert first.position.market_value == 1200
    assert first.data_quality.status == "degraded"
    assert first.data_quality.missing_fields == ()
    assert not hasattr(first, "action")


def test_data_quality_blocks_missing_required_inputs_and_degrades_optional_inputs():
    result = summarize_data_quality(
        has_quote=False, daily_bar_count=59, total_assets_available=False, plan_enabled=False,
        has_risk=False, has_market_regime=False, has_relative_strength=False, has_events=False,
    )

    assert result.status == "blocked"
    assert result.missing_fields == ("quote.price", "daily_bars.minimum_60", "account.total_assets", "trade_plan.enabled")
    assert "risk unavailable" in result.warnings
