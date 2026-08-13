"""Deterministic cost calculation; no network or ledger side effects."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app import backtest_config as config

AssetClass = Literal["a_share_stock", "a_share_etf", "hk_stock"]
Side = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class TradeCosts:
    commission: float
    stamp_tax: float
    slippage: float
    total: float
    cost_model_version: str = config.COST_MODEL_VERSION


def calculate_trade_costs(*, asset_class: AssetClass, side: Side, quantity: float, price: float) -> TradeCosts:
    if quantity <= 0 or price <= 0:
        raise ValueError("quantity_and_price_must_be_positive")
    gross = quantity * price
    commission = max(config.MIN_COMMISSION_CNY, gross * config.COMMISSION_RATE)
    slippage = gross * config.SLIPPAGE_BPS / 10_000
    stamp_tax = 0.0
    if side == "SELL" and asset_class == "a_share_stock": stamp_tax = gross * config.A_SHARE_STOCK_SELL_STAMP_TAX_RATE
    elif side == "SELL" and asset_class == "a_share_etf": stamp_tax = gross * config.A_SHARE_ETF_SELL_STAMP_TAX_RATE
    elif asset_class == "hk_stock": stamp_tax = gross * (config.HK_STOCK_BUY_STAMP_TAX_RATE if side == "BUY" else config.HK_STOCK_SELL_STAMP_TAX_RATE)
    return TradeCosts(commission=commission, stamp_tax=stamp_tax, slippage=slippage, total=commission + stamp_tax + slippage)
