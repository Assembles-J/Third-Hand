"""Reusable freshness gate for computations that need a current market quote."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.time_utils import BEIJING_TIMEZONE, beijing_now


DEFAULT_MAX_AGE = timedelta(minutes=20)


def quote_is_fresh(quote: dict[str, object], *, max_age: timedelta = DEFAULT_MAX_AGE, now: datetime | None = None) -> bool:
    """Only permit a quote when its retrieval timestamp is recent and parseable."""
    retrieved_at = quote.get("retrieved_at")
    if not retrieved_at:
        return False
    try:
        timestamp = datetime.fromisoformat(str(retrieved_at).replace("Z", "+00:00"))
    except ValueError:
        return False
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=BEIJING_TIMEZONE)
        reference = now or beijing_now()
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=BEIJING_TIMEZONE)
        return reference.astimezone(BEIJING_TIMEZONE) - timestamp.astimezone(BEIJING_TIMEZONE) <= max_age


def quote_freshness_status(quote: dict[str, object], *, max_age: timedelta = DEFAULT_MAX_AGE, now: datetime | None = None) -> str:
    """Return the API status used by later numeric-recommendation hard gates."""
    return "stored" if quote_is_fresh(quote, max_age=max_age, now=now) else "stale_fallback"
