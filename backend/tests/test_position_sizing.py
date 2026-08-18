from app.decision_context import DecisionContextBuilder
from app.decision_models import FxRateSnapshot
from app.position_sizing import PositionSizingEngine
from app.storage import PortfolioStore


def _context(tmp_path, *, volume=2000, lot_size=100, cap=50):
    store = PortfolioStore(tmp_path / "sizing.db")
    store.add("holding-1", "600519", "test", 100, 10)
    store.save_available_cash(10_000)
    store.save_quotes([{ "symbol": "600519", "price": 10, "volume": volume, "currency": "CNY", "source": "test", "as_of": "2026-07-31", "retrieved_at": "2026-07-31T10:00:00+08:00"}])
    store.save_daily_prices("600519", [{"trading_date": f"2026-06-{index + 1:02d}", "open": 10, "close": 10, "high": 11, "low": 9, "source": "test"} for index in range(60)])
    store.save_risk({"symbol": "600519", "as_of": "2026-07-31", "sample_count": 60, "historical_downside_probability": 10, "annualized_volatility_percent": 20, "risk_level": "low"})
    store.save_trade_plan({"id": "plan-1", "symbol": "600519", "horizon": "swing", "thesis": "test", "market_expectation": "test", "catalysts": [], "entry_condition": "entry", "add_condition": "add", "reduce_condition": "reduce", "exit_condition": "exit", "max_position_percent": cap, "risk_budget_percent": 3, "invalidation_price": 9, "enabled": True, "version": 1})
    store.save_instrument_metadata({"symbol": "600519", "market": "CN", "currency": "CNY", "lot_size": lot_size, "price_tick": "0.01", "source": "test", "as_of": "2026-07-31"})
    return DecisionContextBuilder(store).build("600519")


def test_add_size_is_limited_by_risk_cash_position_liquidity_and_lot(tmp_path):
    result = PositionSizingEngine().size(_context(tmp_path), "ADD")

    # risk-sizing-v1 applies one system-wide policy (not per-stock plan values):
    #   total_assets = 10_000 cash + 100 shares * 10 = 11_000
    #   risk_capital = 11_000 * 1% = 110;  invalidation = entry * 0.95 = 9.5
    #   risk_per_share = 10 - 9.5 = 0.5  ->  quantity_by_risk = floor(110 / 0.5) = 220
    #   quantity_by_cash = floor(10_000 / 10) = 1000
    #   quantity_by_position_cap = max(0, floor(11_000 * 20% / 10) - 100) = 120
    #   quantity_by_liquidity = floor(2000 * 10%) = 200
    #   suggested = min(220, 1000, 120, 200) rounded to the 100-share lot = 100
    assert result.status == "ready"
    assert result.quantity_by_risk == 220
    assert result.quantity_by_cash == 1000
    assert result.quantity_by_position_cap == 120
    assert result.quantity_by_liquidity == 200
    assert result.suggested_quantity == 100
    assert result.target_quantity == 200
    assert result.lot_size == 100


def test_size_blocks_when_the_most_constrained_result_is_below_one_lot(tmp_path):
    result = PositionSizingEngine().size(_context(tmp_path, volume=500), "ADD")

    assert result.status == "blocked"
    assert result.suggested_quantity is None
    assert result.blocked_reasons == ("quantity_below_one_lot",)


def test_reduce_never_exceeds_current_quantity_and_exit_closes_all(tmp_path):
    context = _context(tmp_path, cap=5)
    engine = PositionSizingEngine()
    reduce, exit_ = engine.size(context, "REDUCE"), engine.size(context, "EXIT")

    assert reduce.status == "ready"
    assert 0 <= reduce.suggested_quantity <= context.position.quantity
    assert exit_.suggested_quantity == context.position.quantity
    assert exit_.target_quantity == 0


def test_watch_does_not_produce_a_quantity(tmp_path):
    result = PositionSizingEngine().size(_context(tmp_path), "WATCH")

    assert result.status == "not_applicable"
    assert result.suggested_quantity is None


def test_hk_rmb_settlement_requires_an_observed_hkd_to_cny_rate_before_sizing(tmp_path):
    context = _context(tmp_path)
    hk_instrument = context.instrument.model_copy(update={"market": "HK", "currency": "HKD", "lot_size": 200})
    result = PositionSizingEngine().size(context.model_copy(update={"instrument": hk_instrument}), "ADD")

    assert result.status == "blocked"
    assert result.suggested_quantity is None
    assert result.blocked_reasons == ("execution_fx_rate_missing",)


def test_market_execution_precheck_never_sizes_unconfigured_fee_market(tmp_path):
    context = _context(tmp_path)
    hk_instrument = context.instrument.model_copy(update={"market": "HK", "currency": "HKD", "lot_size": 200})
    hk_account = context.account.model_copy(update={"account_currency": "HKD"})
    result = PositionSizingEngine().size(
        context.model_copy(update={"instrument": hk_instrument, "account": hk_account}), "ADD"
    )

    assert result.status == "blocked"
    assert result.suggested_quantity is None
    assert result.blocked_reasons == ("execution_fee_schedule_unconfigured",)


def test_hk_rmb_settlement_reaches_fee_guard_when_exact_fx_rate_is_present(tmp_path):
    context = _context(tmp_path)
    hk_instrument = context.instrument.model_copy(update={"market": "HK", "currency": "HKD", "lot_size": 200})
    fx_rate = FxRateSnapshot(
        from_currency="HKD", to_currency="CNY", rate=.93, source="broker_settlement_quote",
        as_of="2026-08-13T14:00:00+08:00", retrieved_at="2026-08-13T14:00:01+08:00",
    )

    result = PositionSizingEngine().size(
        context.model_copy(update={"instrument": hk_instrument, "fx_rate": fx_rate}), "ADD"
    )

    assert result.status == "blocked"
    assert result.blocked_reasons == ("execution_fee_schedule_unconfigured",)
