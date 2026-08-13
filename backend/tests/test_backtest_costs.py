import pytest

from app.backtest_costs import calculate_trade_costs


def test_a_share_stock_only_charges_stamp_tax_on_sell():
    buy = calculate_trade_costs(asset_class="a_share_stock", side="BUY", quantity=100, price=10)
    sell = calculate_trade_costs(asset_class="a_share_stock", side="SELL", quantity=100, price=10)
    assert buy.stamp_tax == 0
    assert sell.stamp_tax == pytest.approx(0.5)


def test_hk_stock_charges_stamp_tax_on_both_sides_and_etf_does_not():
    buy = calculate_trade_costs(asset_class="hk_stock", side="BUY", quantity=100, price=10)
    sell = calculate_trade_costs(asset_class="hk_stock", side="SELL", quantity=100, price=10)
    etf = calculate_trade_costs(asset_class="a_share_etf", side="SELL", quantity=100, price=10)
    assert buy.stamp_tax == sell.stamp_tax == pytest.approx(1)
    assert etf.stamp_tax == 0
