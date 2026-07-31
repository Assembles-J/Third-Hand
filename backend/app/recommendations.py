"""Deterministic research candidates and daily-bar paper-trading evaluation."""
from __future__ import annotations
from math import floor

HORIZONS = (1, 5, 20, 60)
FEE_RATE = 0.0003
SLIPPAGE_RATE = 0.0005


def candidate(symbol: str, holding: dict | None, quote: dict | None, bars: list[dict], plan: dict | None) -> dict:
    if not quote or quote.get("price") is None or len(bars) < 60 or not plan or not plan.get("enabled"):
        return {"symbol": symbol, "status": "blocked", "blocked_reasons": ["quote_or_daily_history_or_enabled_plan_missing"], "automatic_execution": False}
    closes = [float(x["close"]) for x in bars]
    high20, low20 = max(closes[-20:]), min(closes[-20:])
    price = float(quote["price"])
    # A reproducible zone derived from current price and recent range; no LLM input.
    low, high = round(max(low20, price * .97), 2), round(min(high20, price * 1.01), 2)
    if low > high: low, high = high, low
    action = "trim" if holding and price >= high20 else "add"
    quantity = None
    if holding and action == "trim":
        quantity = max(1, floor(float(holding["quantity"]) * .25))
    return {"symbol": symbol, "status": "ready", "action": action, "price_zone": {"low": low, "high": high}, "invalidation_price": round(low * .97, 2), "suggested_quantity": quantity, "quantity_status": "position_based" if quantity else "cash_missing", "conditions": [{"field": "close", "operator": "between", "value": [low, high]}, {"field": "plan_enabled", "operator": "equals", "value": True}], "automatic_execution": False, "evaluation_version": "daily_bar_assumption_v1"}


def first_fill(recommendation: dict, bars: list[dict]) -> tuple[dict | None, int | None]:
    zone = recommendation["price_zone"]
    for index, bar in enumerate(bars):
        open_, high, low = (float(bar.get(key) or bar["close"]) for key in ("open", "high", "low"))
        if recommendation["action"] == "add" and (open_ <= zone["high"] or low <= zone["high"]):
            return {"price": min(open_, zone["high"]) * (1 + SLIPPAGE_RATE), "date": bar["trading_date"]}, index
        if recommendation["action"] == "trim" and (open_ >= zone["low"] or high >= zone["low"]):
            return {"price": max(open_, zone["low"]) * (1 - SLIPPAGE_RATE), "date": bar["trading_date"]}, index
    return None, None


def evaluations(fill: dict, fill_index: int, bars: list[dict], quantity: float) -> list[dict]:
    result = []
    entry = float(fill["price"])
    for horizon in HORIZONS:
        if fill_index + horizon >= len(bars):
            continue
        window = bars[fill_index:fill_index + horizon + 1]
        mark = float(window[-1]["close"])
        gross = (mark - entry) * quantity
        fees = (entry + mark) * quantity * FEE_RATE
        result.append({"horizon": horizon, "evaluation_date": window[-1]["trading_date"], "fill_price": entry, "mark_price": mark, "gross_pnl": gross, "net_pnl": gross - fees, "return_percent": (gross - fees) / (entry * quantity) * 100, "mfe_percent": (max(float(x.get("high") or x["close"]) for x in window) / entry - 1) * 100, "mae_percent": (min(float(x.get("low") or x["close"]) for x in window) / entry - 1) * 100, "fee_rate": FEE_RATE, "slippage_rate": SLIPPAGE_RATE})
    return result
