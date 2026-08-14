from app.recommendations import candidate, evaluations, first_fill


def _bars(close: float = 10.0) -> list[dict]:
    return [
        {"trading_date": f"2026-01-{index + 1:02d}", "open": close, "high": close + 1,
         "low": close - 1, "close": close}
        for index in range(60)
    ]


def _plan() -> dict:
    return {"enabled": True, "structured_conditions": []}


def test_candidate_blocks_without_quote_history_or_enabled_plan():
    blocked = candidate("600519", None, None, [], None)

    assert blocked == {
        "symbol": "600519", "status": "blocked",
        "blocked_reasons": ["quote_or_daily_history_missing"],
        "automatic_execution": False,
    }


def test_candidate_keeps_current_cash_based_sizing_contract():
    result = candidate("600519", None, {"price": 10}, _bars(), _plan(), available_cash=10_000)

    assert result["status"] == "ready"
    assert result["action"] == "add"
    assert result["suggested_quantity"] == 200
    assert result["quantity_status"] == "cash_based_25_percent_100_share_lot"
    assert result["automatic_execution"] is False


def test_trim_candidate_uses_quarter_of_existing_position():
    result = candidate("600519", {"quantity": 401}, {"price": 10}, _bars(), _plan(), available_cash=0)

    assert result["action"] == "trim"
    assert result["suggested_quantity"] == 100
    assert result["quantity_status"] == "position_based_25_percent"


def test_first_fill_and_evaluation_keep_trim_pnl_direction():
    recommendation = {"action": "trim", "price_zone": {"low": 10, "high": 11}, "generated_trading_date": "2026-07-31"}
    bars = [
        {"trading_date": "2026-08-01", "open": 10.5, "high": 11, "low": 10, "close": 10.5},
        {"trading_date": "2026-08-02", "open": 9, "high": 9.5, "low": 8.5, "close": 9},
    ]

    fill, index = first_fill(recommendation, bars)
    result = evaluations(fill, index, bars, 100, "trim")

    assert fill == {"price": 10.5 * (1 - 0.0005), "date": "2026-08-01"}
    assert index == 0
    assert result[0]["gross_pnl"] > 0
    assert result[0]["mfe_percent"] > 0
    assert result[0]["mae_percent"] < 0


def test_first_fill_never_uses_the_generation_day_or_earlier_bars():
    recommendation = {"action": "add", "price_zone": {"low": 9, "high": 11}, "generated_trading_date": "2026-08-02"}
    bars = [
        {"trading_date": "2026-08-01", "open": 10, "high": 11, "low": 9, "close": 10},
        {"trading_date": "2026-08-02", "open": 10, "high": 11, "low": 9, "close": 10},
        {"trading_date": "2026-08-03", "open": 10.5, "high": 11, "low": 10, "close": 10.5},
    ]

    fill, index = first_fill(recommendation, bars)

    assert index == 2
    assert fill["date"] == "2026-08-03"


def test_evaluations_include_the_60_day_horizon_when_future_bars_exist():
    bars = [
        {"trading_date": f"2026-09-{index + 1:02d}", "open": 10, "high": 11, "low": 9, "close": 10}
        for index in range(61)
    ]

    result = evaluations({"price": 10, "date": "2026-09-01"}, 0, bars, 100, "add")

    assert result[-1]["horizon"] == 60
    assert "mfe_percent" in result[-1] and "mae_percent" in result[-1]
