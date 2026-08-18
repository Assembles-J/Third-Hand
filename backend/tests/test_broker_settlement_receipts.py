import pytest

from app.storage import PortfolioStore


def test_hk_stock_connect_receipt_preserves_actual_rmb_settlement_and_implied_fx(tmp_path):
    store = PortfolioStore(tmp_path / "stock-connect-receipt.db")

    receipt = store.record_broker_settlement_receipt({
        "symbol": "01810", "market": "HK", "side": "BUY",
        "quantity": 200, "trade_price": 26.4, "trade_currency": "HKD",
        "settlement_currency": "CNY", "gross_settlement_amount": 4556.95,
        "total_fee": 5.92, "net_settlement_amount": 4562.87,
        "broker": "GF_SECURITIES", "occurred_at": "2026-08-13T14:00:00+08:00",
        "source_reference": "user-provided-broker-screenshot",
    })

    assert receipt["implied_fx_rate"] == pytest.approx(4556.95 / (26.4 * 200))
    assert receipt["net_settlement_amount"] == pytest.approx(4562.87)
    stored = store.broker_settlement_receipts("01810")
    assert stored[0]["settlement_currency"] == "CNY"
    assert stored[0]["total_fee"] == pytest.approx(5.92)


def test_receipt_rejects_fee_breakdown_that_does_not_match_the_broker_total(tmp_path):
    store = PortfolioStore(tmp_path / "invalid-receipt.db")

    with pytest.raises(ValueError, match="fee_breakdown_mismatch"):
        store.record_broker_settlement_receipt({
            "symbol": "01810", "market": "HK", "side": "SELL",
            "quantity": 200, "trade_price": 27.72, "trade_currency": "HKD",
            "settlement_currency": "CNY", "gross_settlement_amount": 4769.40,
            "commission": .17, "stamp_duty": 5.16, "other_fee": .61,
            "total_fee": 5.92, "net_settlement_amount": 4763.48,
            "broker": "GF_SECURITIES", "occurred_at": "2026-08-03T14:01:42+08:00",
        })
