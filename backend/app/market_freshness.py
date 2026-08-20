"""Reusable freshness rules for market quote execution and display surfaces."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.time_utils import BEIJING_TIMEZONE, beijing_now
from app.trading_calendar import TradingCalendarService


DEFAULT_MAX_AGE = timedelta(minutes=20)


def _parse_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=BEIJING_TIMEZONE)
    return timestamp.astimezone(BEIJING_TIMEZONE)


def quote_is_fresh(
    quote: dict[str, object],
    *,
    max_age: timedelta = DEFAULT_MAX_AGE,
    now: datetime | None = None,
) -> bool:
    """Execution freshness: only permit a recently retrieved quote.

    This remains intentionally strict for decision/execution gates.  A valid
    completed-session close may still be displayable after twenty minutes, but
    it must not become an executable quote merely because the UI can show it.
    """
    timestamp = _parse_timestamp(quote.get("retrieved_at"))
    if timestamp is None:
        return False
    reference = now or beijing_now()
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=BEIJING_TIMEZONE)
    age = reference.astimezone(BEIJING_TIMEZONE) - timestamp
    return timedelta(0) <= age <= max_age


def quote_freshness_status(
    quote: dict[str, object],
    *,
    max_age: timedelta = DEFAULT_MAX_AGE,
    now: datetime | None = None,
) -> str:
    """Return the status used by numeric-recommendation / execution hard gates."""
    return "stored" if quote_is_fresh(quote, max_age=max_age, now=now) else "stale_fallback"


def quote_display_status(
    quote: dict[str, object],
    symbol: str,
    *,
    max_age: timedelta = DEFAULT_MAX_AGE,
    now: datetime | None = None,
    trading_calendar: TradingCalendarService | None = None,
) -> str:
    """Classify a quote for read-only UI without weakening execution safety.

    Values:
    - ``live``: recently retrieved and usable as current display data;
    - ``refreshing``: a bounded upstream refresh was queued for the stored row;
    - ``session_close``: old by wall-clock age, but its ``as_of`` belongs to the
      latest *completed* exchange session while the symbol market is closed;
    - ``stale``: older than the latest completed session, or stale while open;
    - ``unavailable``: no priced quote exists.

    ``session_close`` is deliberately display-only.  Paper execution continues
    to use ``quote_is_fresh`` plus its market-session/fresh-observation gates.
    """
    if quote.get("price") is None:
        return "unavailable"
    if quote_is_fresh(quote, max_age=max_age, now=now):
        return "live"
    if str(quote.get("refresh_status") or "").lower() == "pending":
        return "refreshing"

    calendar = trading_calendar or TradingCalendarService()
    reference = calendar.normalize_moment(now)
    if calendar.is_symbol_market_open(symbol, reference):
        return "stale"

    as_of = _parse_timestamp(quote.get("as_of"))
    if as_of is None:
        raw_as_of = str(quote.get("as_of") or "").strip()
        if len(raw_as_of) >= 10:
            quote_session_date = raw_as_of[:10]
        else:
            return "stale"
    else:
        quote_session_date = as_of.date().isoformat()

    completed_session = calendar.latest_completed_symbol_session_date(symbol, reference)
    if completed_session and quote_session_date == completed_session:
        return "session_close"
    return "stale"
