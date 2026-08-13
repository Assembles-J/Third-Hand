"""Deterministic phase-1 data-quality classification for decision contexts."""
from __future__ import annotations

from app import decision_config as config
from app.decision_models import ActionGate, DecisionQualitySummary
from app.freshness import evaluate_freshness


def summarize_data_quality(*, has_quote: bool, daily_bar_count: int, total_assets_available: bool,
                           plan_enabled: bool, has_risk: bool, has_market_regime: bool,
                           has_relative_strength: bool, has_events: bool, has_instrument: bool = False,
                           has_position: bool = False, has_personal_rule: bool = False,
                           quote_as_of: str | None = None, quote_retrieved_at: str | None = None,
                           daily_bar_as_of: str | None = None, risk_as_of: str | None = None,
                           market_as_of: str | None = None, market_retrieved_at: str | None = None) -> DecisionQualitySummary:
    missing: list[str] = []
    degraded: list[str] = []
    if not has_quote:
        missing.append("quote.price")
    # These fields reduce confidence or disable only the affected calculation;
    # they must not stop qualitative research or a defensive review.
    if daily_bar_count < 60:
        degraded.append("daily_bars.minimum_60")
    if not total_assets_available:
        degraded.append("account.total_assets")
    if not plan_enabled:
        degraded.append("trade_plan.auto_draft")
    if not has_risk:
        degraded.append("risk")
    if not has_market_regime:
        degraded.append("market_regime")
    if not has_relative_strength:
        degraded.append("relative_strength")
    if not has_events:
        degraded.append("events")

    freshness = (
        evaluate_freshness("quote", as_of=quote_as_of, retrieved_at=quote_retrieved_at, max_age_seconds=config.QUOTE_MAX_AGE_SECONDS),
        evaluate_freshness("daily_bars", as_of=daily_bar_as_of, retrieved_at=None, max_age_seconds=config.DAILY_BAR_MAX_AGE_DAYS * 86_400),
        evaluate_freshness("risk", as_of=risk_as_of, retrieved_at=None, max_age_seconds=config.RISK_MAX_AGE_DAYS * 86_400),
        evaluate_freshness("market_intelligence", as_of=market_as_of, retrieved_at=market_retrieved_at, max_age_seconds=config.MARKET_INTELLIGENCE_MAX_AGE_SECONDS),
    )
    stale = tuple(item.source_key for item in freshness if item.status in {"stale", "unknown"})
    status = "blocked" if missing else "degraded" if degraded or stale else "ready"
    score = max(0, 100 - len(missing) * 20 - len(degraded) * 5)
    open_required = ("quote.price", "daily_bars.minimum_60", "risk", "account.total_assets", "market_regime", "instrument")
    open_unavailable = [field for field in open_required if field in {"daily_bars.minimum_60", "risk", "account.total_assets", "market_regime"} and field in degraded]
    if not has_quote:
        open_unavailable.append("quote.price")
    if not has_instrument:
        open_unavailable.append("instrument")
    if any(item.source_key in {"quote", "daily_bars", "risk", "market_intelligence"} and item.status != "fresh" for item in freshness):
        open_unavailable.extend(f"{item.source_key}.{item.status}" for item in freshness if item.source_key in {"quote", "daily_bars", "risk", "market_intelligence"} and item.status != "fresh")
    open_gate = ActionGate(action="OPEN", permission="blocked" if open_unavailable else "allowed", required_fields=open_required, unavailable_fields=tuple(open_unavailable), reasons=tuple(f"data_quality.{item}" for item in open_unavailable))
    add_required = (*open_required, "position", "personal_rule")
    add_unavailable = [*open_unavailable]
    if not has_position:
        add_unavailable.append("position")
    if not has_personal_rule:
        add_unavailable.append("personal_rule")
    add_gate = ActionGate(action="ADD", permission="blocked" if add_unavailable else "allowed", required_fields=add_required, unavailable_fields=tuple(add_unavailable), reasons=tuple(f"data_quality.{item}" for item in add_unavailable))
    defensive_permission = "blocked" if not has_quote else "research_only" if stale else "allowed"
    defensive_reason = tuple(f"data_quality.{item}" for item in ((*missing, *stale) if defensive_permission != "allowed" else ()))
    gates = (open_gate, add_gate,
             ActionGate(action="HOLD", permission=defensive_permission, reasons=defensive_reason),
             ActionGate(action="WATCH", permission=defensive_permission, reasons=defensive_reason),
             ActionGate(action="REDUCE", permission=defensive_permission, reasons=defensive_reason),
             ActionGate(action="EXIT", permission=defensive_permission, reasons=defensive_reason))
    return DecisionQualitySummary(
        status=status, score_percent=score, missing_fields=tuple(missing),
        stale_fields=stale, warnings=tuple(f"{field} unavailable" for field in degraded),
        source_freshness=freshness, action_gates=gates,
    )
