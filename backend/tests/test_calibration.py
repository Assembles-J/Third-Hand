from app.calibration import summarize_calibration


def test_risk_review_calibration_uses_saved_entry_price_and_future_closes():
    summary = summarize_calibration(
        [{"entry_date": "2026-01-02", "entry_price": 10}],
        [
            {"trading_date": "2026-01-02", "close": 10},
            {"trading_date": "2026-01-03", "close": 9},
            {"trading_date": "2026-01-04", "close": 8},
            {"trading_date": "2026-01-05", "close": 8},
            {"trading_date": "2026-01-06", "close": 8},
            {"trading_date": "2026-01-07", "close": 8},
        ],
        "risk_review",
    )

    assert summary["horizons"]["1"]["average_return_percent"] == -10.0
    assert summary["horizons"]["1"]["rule_alignment_rate_percent"] == 100.0
    assert summary["horizons"]["5"]["sample_count"] == 1
    assert summary["horizons"]["20"]["sample_count"] == 0
