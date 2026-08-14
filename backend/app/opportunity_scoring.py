"""Explainable, bounded scoring for the daily research pool.

This module ranks what deserves review. It does not estimate an upside
probability and must not be interpreted as a buy/sell model. During the frozen
observation phase the legacy ``upside_likelihood`` field remains only as a
neutral compatibility placeholder so existing clients do not break.
"""
from __future__ import annotations

from statistics import mean

from app import decision_config as config


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

    # These components are review-priority heuristics only. Their names avoid
    # probability language because no calibration supports a return forecast.
    trend_attention = momentum_attention = 0.0
    if len(closes) >= 20 and price > 0:
        average20 = mean(closes[-20:])
        trend_attention = 18 if price >= average20 else 4
        momentum_attention = max(-12, min(18, (price / closes[-6] - 1) * 180)) if len(closes) >= 6 and closes[-6] else 0
    volume_ratio = float((quote or {}).get("volume_ratio") or 0)
    volume_attention = 10 if volume_ratio >= 1.5 else 6 if volume_ratio >= 1 else 2
    sector_attention = max(-8, min(15, (sector_change_percent or 0) * 3))
    downside = float((risk or {}).get("historical_downside_probability") or 0)
    volatility = float((risk or {}).get("annualized_volatility_percent") or 0)
    risk_penalty = min(24, downside * 0.45 + max(0, volatility - 28) * 0.35)

    confidence = _bounded(
        (30 if has_history else min(18, len(closes) * 0.3))
        + (22 if quote_fresh else 0)
        + (20 if has_risk else 4)
        + (13 if sector_change_percent is not None else 0)
        + (15 if len(closes) >= 20 else 0)
    )
    research_priority_score = _bounded(
        50 + trend_attention + momentum_attention + volume_attention + sector_attention - risk_penalty
    )
    score = _bounded(research_priority_score * 0.60 + confidence * 0.40)
    risk_level = "高" if risk_penalty >= 18 or volatility >= 45 else "中" if risk_penalty >= 9 or volatility >= 30 else "低"
    factors = [
        f"趋势关注：{'价格在近 20 日均值上方' if trend_attention >= 18 else '趋势尚未转强'}。",
        f"量能关注：量比 {volume_ratio:.2f}{'，交易活跃度较高' if volume_ratio >= 1.5 else '，未见明显放量'}。",
        f"板块背景：{'暂无板块数据' if sector_change_percent is None else f'所在板块当日 {sector_change_percent:+.2f}%'}。",
        f"风险背景：历史下行统计 {downside:.1f}% · 年化波动 {volatility:.1f}%（仅历史参考）。",
        f"证据完整度：{confidence}/100{'，仍在补齐数据' if confidence < 70 else '，可用于观察和复核'}。",
    ]
    return {
        "score": score,
        "research_priority_score": research_priority_score,
        # Compatibility only. Never use, sort, calibrate, display as a forecast,
        # or persist as an outcome probability. Remove after client migration.
        "upside_likelihood": 50,
        "confidence": confidence,
        "risk_level": risk_level,
        "factors": factors,
        "scoring_version": config.OPPORTUNITY_SCORING_VERSION,
    }
