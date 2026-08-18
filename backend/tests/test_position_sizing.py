from app.decision_context import DecisionContextBuilder
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

    # risk-sizing-v3 applies one shared concentration authority and converts its
    # target to an executable lot before deriving the remaining ADD capacity:
    #   total_assets = 10_000 cash + 100 shares * 10 = 11_000
    #   risk_capital = 11_000 * 1% = 110;  invalidation = entry * 0.95 = 9.5
    #   risk_per_share = 10 - 9.5 = 0.5  ->  quantity_by_risk = floor(110 / 0.5) = 220
    #   quantity_by_cash = floor(10_000 / 10) = 1000
    #   raw 20% cap target = floor(11_000 * 20% / 10) = 220 shares
    #   executable cap target = floor_to_lot(220, 100) = 200 shares
    #   quantity_by_position_cap = max(0, 200 - 100) = 100
    #   quantity_by_liquidity = floor(2000 * 10%) = 200
    #   suggested = min(220, 1000, 100, 200) = 100
    assert result.status == "ready"
    assert result.quantity_by_risk == 220
    assert result.quantity_by_cash == 1000
    assert result.quantity_by_position_cap == 100
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


def test_t1_locked_position_defers_reduce_and_exit_before_execution(tmp_path):
    context = _context(tmp_path, cap=5)
    locked_position = context.position.model_copy(update={
        "quantity": 1_000.0,
        "sellable_quantity": 0.0,
        "locked_quantity": 1_000.0,
        "next_eligible_sell_at": "2026-08-18T09:30:00+08:00",
    })
    locked = context.model_copy(update={"position": locked_position})

    reduce, exit_ = PositionSizingEngine().size(locked, "REDUCE"), PositionSizingEngine().size(locked, "EXIT")

    assert reduce.execution_disposition == exit_.execution_disposition == "deferred_t1"
    assert reduce.suggested_quantity == exit_.suggested_quantity == 0
    assert reduce.max_executable_quantity == exit_.max_executable_quantity == 0
    assert reduce.blocked_reasons == exit_.blocked_reasons == ("paper_t1_unsellable_quantity",)


def test_exit_sizes_only_the_settled_part_of_a_mixed_t1_position(tmp_path):
    context = _context(tmp_path, cap=5)
    mixed_position = context.position.model_copy(update={
        "quantity": 1_000.0,
        "sellable_quantity": 800.0,
        "locked_quantity": 200.0,
        "next_eligible_sell_at": "2026-08-18T09:30:00+08:00",
    })

    result = PositionSizingEngine().size(context.model_copy(update={"position": mixed_position}), "EXIT")

    assert result.status == "ready"
    assert result.suggested_quantity == result.max_executable_quantity == 800.0
    assert result.target_quantity == 200.0


def test_watch_does_not_produce_a_quantity(tmp_path):
    result = PositionSizingEngine().size(_context(tmp_path), "WATCH")

    assert result.status == "not_applicable"
    assert result.suggested_quantity is None


def test_hk_quote_is_not_executable_in_the_single_cny_paper_ledger(tmp_path):
    context = _context(tmp_path)
    hk_instrument = context.instrument.model_copy(update={"market": "HK", "currency": "HKD", "lot_size": 200})
    result = PositionSizingEngine().size(context.model_copy(update={"instrument": hk_instrument}), "ADD")

    assert result.status == "blocked"
    assert result.suggested_quantity is None
    assert result.blocked_reasons == ("execution_foreign_currency_quote_unsupported",)
