"""Deterministic phase-1 data-quality classification for decision contexts."""
from __future__ import annotations

from app import decision_config as config
from app.canonical_snapshot import build_canonical_market_snapshot
from app.decision_models import ActionGate, DecisionQualitySummary
from app.freshness import evaluate_session_freshness


def summarize_data_quality(*, has_quote: bool, daily_bar_count: int, total_assets_available: bool,
                           plan_enabled: bool, has_risk: bool, has_market_regime: bool,
                           has_relative_strength: bool, has_events: bool, has_instrument: bool = False,
                           has_position: bool = False, has_personal_rule: bool = False,
                           quote_as_of: str | None = None, quote_retrieved_at: str | None = None,
                           daily_bar_as_of: str | None = None, risk_as_of: str | None = None,
                           market_as_of: str | None = None, market_retrieved_at: str | None = None,
                           market: str | None = None,
                           event_policy_blockers: tuple[str, ...] = ()) -> DecisionQualitySummary:
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

    # Canonicalize quote/daily/risk time semantics once. In addition to normal
    # freshness this detects cross-source contradictions such as a quote whose
    # observed market date predates the latest completed daily bar. Retrieval
    # time alone must never make that contradiction executable.
    canonical = build_canonical_market_snapshot(
        market=market,
        quote_price=1.0 if has_quote else None,
        quote_as_of=quote_as_of,
        quote_retrieved_at=quote_retrieved_at,
        daily_close=1.0 if daily_bar_count else None,
        daily_bar_as_of=daily_bar_as_of,
        risk_as_of=risk_as_of,
    )
    market_freshness = evaluate_session_freshness(
        "market_regime",
        as_of=market_as_of,
        market=market,
        max_age_seconds=config.MARKET_INTELLIGENCE_MAX_AGE_SECONDS,
    )
    freshness = (
        canonical.quote_freshness,
        canonical.daily_freshness,
        canonical.risk_freshness,
        market_freshness,
    )
    stale = tuple(item.source_key for item in freshness if item.status in {"stale", "unknown"})
    conflict_warnings = tuple(f"consistency.{code}" for code in canonical.conflict_codes)
    status = "blocked" if missing else "degraded" if degraded or stale or conflict_warnings else "ready"
    score = max(0, 100 - len(missing) * 20 - len(degraded) * 5 - len(conflict_warnings) * 10)
    open_required = ("quote.price", "daily_bars.minimum_60", "risk", "account.total_assets", "market_regime", "instrument")
    open_unavailable = [field for field in open_required if field in {"daily_bars.minimum_60", "risk", "account.total_assets", "market_regime"} and field in degraded]
    if not has_quote:
        open_unavailable.append("quote.price")
    if not has_instrument:
        open_unavailable.append("instrument")

    # Presence and freshness are different failure modes. Only add a freshness
    # blocker when the corresponding source actually exists.
    freshness_by_key = {item.source_key: item for item in freshness}
    present_for_open = {
        "quote": has_quote,
        "daily_bars": daily_bar_count >= 60,
        "risk": has_risk,
        "market_regime": has_market_regime,
    }
    for source_key, present in present_for_open.items():
        item = freshness_by_key[source_key]
        if present and item.status != "fresh":
            open_unavailable.append(f"{source_key}.{item.status}")

    # Cross-source conflicts are hard OPEN/ADD blockers even when every source
    # is individually fresh. For example, a newly retrieved but old-market-date
    # quote cannot be mixed with a newer daily bar.
    open_unavailable.extend(conflict_warnings)

    # A known near-term corporate event is not missing/stale data and therefore
    # does not lower the data-quality score. It is a separate deterministic
    # policy constraint: block only prospective risk (OPEN/ADD) while leaving
    # defensive position-management verbs available under their existing gates.
    event_blockers = tuple(dict.fromkeys(str(item) for item in event_policy_blockers if str(item)))
    open_gate = ActionGate(
        action="OPEN",
        permission="blocked" if open_unavailable or event_blockers else "allowed",
        required_fields=open_required,
        unavailable_fields=tuple(open_unavailable),
        reasons=tuple(f"data_quality.{item}" for item in open_unavailable) + event_blockers,
    )
    add_required = (*open_required, "position", "personal_rule")
    add_unavailable = [*open_unavailable]
    if not has_position:
        add_unavailable.append("position")
    if not has_personal_rule:
        add_unavailable.append("personal_rule")
    add_gate = ActionGate(
        action="ADD",
        permission="blocked" if add_unavailable or event_blockers else "allowed",
        required_fields=add_required,
        unavailable_fields=tuple(add_unavailable),
        reasons=tuple(f"data_quality.{item}" for item in add_unavailable) + event_blockers,
    )
    defensive_permission = "blocked" if not has_quote else "research_only" if stale or conflict_warnings else "allowed"
    defensive_inputs = (*missing, *stale, *conflict_warnings) if defensive_permission != "allowed" else ()
    defensive_reason = tuple(f"data_quality.{item}" for item in defensive_inputs)
    gates = (
        open_gate,
        add_gate,
        ActionGate(action="HOLD", permission=defensive_permission, reasons=defensive_reason),
        ActionGate(action="WATCH", permission=defensive_permission, reasons=defensive_reason),
        ActionGate(action="REDUCE", permission=defensive_permission, reasons=defensive_reason),
        ActionGate(action="EXIT", permission=defensive_permission, reasons=defensive_reason),
    )
    return DecisionQualitySummary(
        status=status,
        score_percent=score,
        missing_fields=tuple(missing),
        stale_fields=stale,
        warnings=tuple(f"{field} unavailable" for field in degraded) + conflict_warnings,
        source_freshness=freshness,
        action_gates=gates,
    )
