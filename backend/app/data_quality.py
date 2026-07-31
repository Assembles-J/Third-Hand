"""Deterministic phase-1 data-quality classification for decision contexts."""
from __future__ import annotations

from app.decision_models import DataQualitySummary


def summarize_data_quality(*, has_quote: bool, daily_bar_count: int, total_assets_available: bool,
                           plan_enabled: bool, has_risk: bool, has_market_regime: bool,
                           has_relative_strength: bool, has_events: bool) -> DataQualitySummary:
    missing: list[str] = []
    degraded: list[str] = []
    if not has_quote:
        missing.append("quote.price")
    if daily_bar_count < 60:
        missing.append("daily_bars.minimum_60")
    if not total_assets_available:
        missing.append("account.total_assets")
    if not plan_enabled:
        missing.append("trade_plan.enabled")
    if not has_risk:
        degraded.append("risk")
    if not has_market_regime:
        degraded.append("market_regime")
    if not has_relative_strength:
        degraded.append("relative_strength")
    if not has_events:
        degraded.append("events")

    status = "blocked" if missing else "degraded" if degraded else "ready"
    score = max(0, 100 - len(missing) * 20 - len(degraded) * 5)
    return DataQualitySummary(
        status=status, score_percent=score, missing_fields=tuple(missing),
        stale_fields=(), warnings=tuple(f"{field} unavailable" for field in degraded),
    )
