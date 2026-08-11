"""Explainable, bounded scoring for the daily opportunity pool.

The score ranks what deserves review; it is not a forecast or an instruction to
buy.  Confidence measures evidence quality, while upside likelihood is a
heuristic direction estimate kept separate from risk.
"""
from __future__ import annotations

from statistics import mean


def _bounded(value: float) -> int:
    return max(0, min(100, round(value)))


def score_opportunity(
    *,
    quote: dict | None,
    bars: list[dict],
    risk: dict | None,
    sector_change_percent: float | None,
    sources: list[str],
) -> dict[str, object]:
    closes = [float(item["close"]) for item in bars if item.get("close") is not None]
    price = float((quote or {}).get("price") or (closes[-1] if closes else 0))
    has_history = len(closes) >= 60
    has_risk = bool(risk and risk.get("status") not in {"data_insufficient", "unavailable"})
    quote_fresh = bool(quote and quote.get("price") is not None and not quote.get("error_code"))

    trend = momentum = 0.0
    if len(closes) >= 20 and price > 0:
        average20 = mean(closes[-20:])
        trend = 18 if price >= average20 else 4
        momentum = max(-12, min(18, (price / closes[-6] - 1) * 180)) if len(closes) >= 6 and closes[-6] else 0
    volume_ratio = float((quote or {}).get("volume_ratio") or 0)
    volume = 10 if volume_ratio >= 1.5 else 6 if volume_ratio >= 1 else 2
    sector = max(-8, min(15, (sector_change_percent or 0) * 3))
    downside = float((risk or {}).get("historical_downside_probability") or 0)
    volatility = float((risk or {}).get("annualized_volatility_percent") or 0)
    risk_penalty = min(24, downside * 0.45 + max(0, volatility - 28) * 0.35)

    # Confidence is evidence coverage and consistency, deliberately not return probability.
    confidence = _bounded(
        (30 if has_history else min(18, len(closes) * 0.3))
        + (22 if quote_fresh else 0)
        + (20 if has_risk else 4)
        + (13 if sector_change_percent is not None else 0)
        + (15 if len(closes) >= 20 else 0)
    )
    upside_likelihood = _bounded(50 + trend + momentum + volume + sector - risk_penalty)
    score = _bounded(upside_likelihood * 0.55 + confidence * 0.35 + (10 if "holding" in sources else 0))
    risk_level = "高" if risk_penalty >= 18 or volatility >= 45 else "中" if risk_penalty >= 9 or volatility >= 30 else "低"
    factors = [
        f"趋势：{'价格在近 20 日均值上方' if trend >= 18 else '趋势尚未转强'}。",
        f"量能：量比 {volume_ratio:.2f}{'，交易活跃度较高' if volume_ratio >= 1.5 else '，未见明显放量'}。",
        f"板块：{'暂无板块数据' if sector_change_percent is None else f'所在板块当日 {sector_change_percent:+.2f}%'}。",
        f"风险：历史下行统计 {downside:.1f}% · 年化波动 {volatility:.1f}%（仅历史参考）。",
        f"证据完整度：{confidence}/100{'，仍在补齐数据' if confidence < 70 else '，可用于观察和复核'}。",
    ]
    return {
        "score": score,
        "confidence": confidence,
        "upside_likelihood": upside_likelihood,
        "risk_level": risk_level,
        "factors": factors,
    }
