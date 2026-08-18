"""Canonical market-input selection for formal research and execution gating.

This module does not fetch data.  It reconciles already persisted quote, daily
bar and risk timestamps into one deterministic view so callers cannot silently
mix a stale quote with newer technical/risk inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app import decision_config as config
from app.decision_models import SourceFreshness
from app.freshness import evaluate_freshness, evaluate_session_freshness


@dataclass(frozen=True, slots=True)
class CanonicalMarketSnapshot:
    market: str | None
    quote_freshness: SourceFreshness
    daily_freshness: SourceFreshness
    risk_freshness: SourceFreshness
    daily_bar_as_of: str | None
    daily_close: float | None
    execution_price: float | None
    execution_price_source: str
    display_price: float | None
    display_price_source: str
    technical_reference_price: float | None
    technical_reference_source: str
    technical_reference_fresh: bool
    risk_policy_usable: bool
    conflict_codes: tuple[str, ...]


def _date(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        try:
            return datetime.fromisoformat(text[:10]).date().isoformat()
        except (TypeError, ValueError):
            return None


def build_canonical_market_snapshot(
    *,
    market: str | None,
    quote_price: float | None,
    quote_as_of: str | None,
    quote_retrieved_at: str | None,
    daily_close: float | None,
    daily_bar_as_of: str | None,
    risk_as_of: str | None,
    now: datetime | None = None,
) -> CanonicalMarketSnapshot:
    """Return one deterministic authority view over persisted market inputs.

    A fresh quote may be used for execution only when it is not observably older
    than the canonical daily bar.  When the quote is stale/conflicted, a fresh
    completed daily close may still be used for display and technical research,
    but never as an executable quote.
    """

    quote_freshness = evaluate_freshness(
        "quote",
        as_of=quote_as_of,
        retrieved_at=quote_retrieved_at,
        max_age_seconds=config.QUOTE_MAX_AGE_SECONDS,
        now=now,
    )
    daily_freshness = evaluate_session_freshness(
        "daily_bars",
        as_of=daily_bar_as_of,
        market=market,
        max_age_seconds=config.DAILY_BAR_MAX_AGE_DAYS * 86_400,
        now=now,
    )
    risk_freshness = evaluate_session_freshness(
        "risk",
        as_of=risk_as_of,
        market=market,
        max_age_seconds=config.RISK_MAX_AGE_DAYS * 86_400,
        now=now,
    )

    quote_date = _date(quote_as_of)
    daily_date = _date(daily_bar_as_of)
    risk_date = _date(risk_as_of)

    conflicts: list[str] = []
    if quote_date and daily_date and quote_date < daily_date:
        conflicts.append("quote_older_than_daily_bar")
    if risk_date and daily_date and risk_date < daily_date:
        conflicts.append("risk_older_than_daily_bar")

    quote_conflicted = "quote_older_than_daily_bar" in conflicts
    risk_conflicted = "risk_older_than_daily_bar" in conflicts
    quote_execution_usable = (
        quote_price is not None
        and quote_freshness.status == "fresh"
        and not quote_conflicted
    )
    daily_research_usable = daily_close is not None and daily_freshness.status == "fresh"

    if quote_execution_usable:
        execution_price = float(quote_price)
        execution_source = "quote"
    else:
        execution_price = None
        execution_source = "unavailable"

    if quote_execution_usable:
        display_price = float(quote_price)
        display_source = "quote"
    elif daily_research_usable:
        display_price = float(daily_close)
        display_source = "daily_close"
    elif quote_price is not None:
        display_price = float(quote_price)
        display_source = "stale_quote"
    elif daily_close is not None:
        display_price = float(daily_close)
        display_source = "stale_daily_close"
    else:
        display_price = None
        display_source = "unavailable"

    if quote_execution_usable:
        technical_reference_price = float(quote_price)
        technical_reference_source = "quote"
        technical_reference_fresh = True
    elif daily_research_usable:
        technical_reference_price = float(daily_close)
        technical_reference_source = "daily_close"
        technical_reference_fresh = True
    elif daily_close is not None:
        # Historical/offline review may still render technical relationships,
        # but the freshness flag keeps callers from presenting it as current.
        technical_reference_price = float(daily_close)
        technical_reference_source = "stale_daily_close"
        technical_reference_fresh = False
    elif quote_price is not None:
        technical_reference_price = float(quote_price)
        technical_reference_source = "stale_quote"
        technical_reference_fresh = False
    else:
        technical_reference_price = None
        technical_reference_source = "unavailable"
        technical_reference_fresh = False

    return CanonicalMarketSnapshot(
        market=market,
        quote_freshness=quote_freshness,
        daily_freshness=daily_freshness,
        risk_freshness=risk_freshness,
        daily_bar_as_of=daily_bar_as_of,
        daily_close=float(daily_close) if daily_close is not None else None,
        execution_price=execution_price,
        execution_price_source=execution_source,
        display_price=display_price,
        display_price_source=display_source,
        technical_reference_price=technical_reference_price,
        technical_reference_source=technical_reference_source,
        technical_reference_fresh=technical_reference_fresh,
        risk_policy_usable=(risk_freshness.status == "fresh" and not risk_conflicted),
        conflict_codes=tuple(conflicts),
    )


__all__ = ["CanonicalMarketSnapshot", "build_canonical_market_snapshot"]
