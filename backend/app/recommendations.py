"""Deterministic research candidates and daily-bar paper-trading evaluation."""
from __future__ import annotations
from math import floor

HORIZONS = (1, 5, 20, 60)
FEE_RATE = 0.0003
SLIPPAGE_RATE = 0.0005


def candidate(symbol: str, holding: dict | None, quote: dict | None, bars: list[dict], plan: dict | None, available_cash: float = 0.0) -> dict:
    if not quote or quote.get("price") is None or len(bars) < 60:
        return {"symbol": symbol, "status": "blocked", "blocked_reasons": ["quote_or_daily_history_missing"], "automatic_execution": False}
    closes = [float(x["close"]) for x in bars]
    high20, low20 = max(closes[-20:]), min(closes[-20:])
    price = float(quote["price"])
    # A reproducible zone derived from current price and recent range; no LLM input.
    low, high = round(max(low20, price * .97), 2), round(min(high20, price * 1.01), 2)
    if low > high: low, high = high, low
    # A stock without a saved trading plan is kept in observation mode.  This
    # lets a new user discover candidates without inventing a buy instruction.
    action = "trim" if holding and price >= high20 else ("add" if plan and plan.get("enabled") else "watch")
    quantity = None
    quantity_status = "cash_missing"
    if holding and action == "trim":
        quantity = max(1, floor(float(holding["quantity"]) * .25))
        quantity_status = "position_based_25_percent"
    elif action == "add" and available_cash > 0:
        # Reserve 75% of cash and size the candidate in whole 100-share lots.
        quantity = floor((available_cash * .25) / price / 100) * 100
        quantity_status = "cash_based_25_percent_100_share_lot" if quantity > 0 else "cash_insufficient_for_one_lot"
    structured = list((plan or {}).get("structured_conditions") or [])
    conditions = structured or [{"trigger": action, "field": "close", "operator": "between", "value": [low, high]}]
    if action == "add":
        conditions.append({"field": "plan_enabled", "operator": "equals", "value": True})
    return {"symbol": symbol, "status": "ready", "action": action, "price_zone": {"low": low, "high": high}, "invalidation_price": round(low * .97, 2), "suggested_quantity": quantity, "quantity_status": quantity_status, "conditions": conditions, "trigger_events": [{"event_type": "condition_checked", "trading_date": bars[-1].get("trading_date"), "trigger_price": price, "conditions": conditions, "matched": low <= price <= high}], "automatic_execution": False, "evaluation_version": "paper-evaluation-v2"}


def first_fill(recommendation: dict, bars: list[dict]) -> tuple[dict | None, int | None]:
    generated_trading_date = recommendation.get("generated_trading_date")
    if not generated_trading_date:
        return None, None
    zone = recommendation["price_zone"]
    for index, bar in enumerate(bars):
        if str(bar["trading_date"]) <= str(generated_trading_date):
            continue
        open_, high, low = (float(bar.get(key) or bar["close"]) for key in ("open", "high", "low"))
        if recommendation["action"] == "add" and (open_ <= zone["high"] or low <= zone["high"]):
            return {"price": min(open_, zone["high"]) * (1 + SLIPPAGE_RATE), "date": bar["trading_date"]}, index
        if recommendation["action"] == "trim" and (open_ >= zone["low"] or high >= zone["low"]):
            return {"price": max(open_, zone["low"]) * (1 - SLIPPAGE_RATE), "date": bar["trading_date"]}, index
    return None, None


def evaluations(fill: dict, fill_index: int, bars: list[dict], quantity: float, action: str = "add") -> list[dict]:
    result = []
    entry = float(fill["price"])
    for horizon in HORIZONS:
        if fill_index + horizon >= len(bars):
            continue
        window = bars[fill_index:fill_index + horizon + 1]
        mark = float(window[-1]["close"])
        gross = (mark - entry) * quantity * (-1 if action == "trim" else 1)
        fees = (entry + mark) * quantity * FEE_RATE
        high, low = max(float(x.get("high") or x["close"]) for x in window), min(float(x.get("low") or x["close"]) for x in window)
        favorable, adverse = ((entry - low) / entry * 100, (entry - high) / entry * 100) if action == "trim" else ((high / entry - 1) * 100, (low / entry - 1) * 100)
        result.append({"horizon": horizon, "evaluation_date": window[-1]["trading_date"], "fill_price": entry, "mark_price": mark, "gross_pnl": gross, "net_pnl": gross - fees, "return_percent": (gross - fees) / (entry * quantity) * 100, "mfe_percent": favorable, "mae_percent": adverse, "fee_rate": FEE_RATE, "slippage_rate": SLIPPAGE_RATE})
    return result
