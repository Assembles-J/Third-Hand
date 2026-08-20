from datetime import datetime, timedelta

from app.market_freshness import quote_display_status, quote_is_fresh
from app.time_utils import BEIJING_TIMEZONE
from app.trading_calendar import TradingCalendarService


def bj(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=BEIJING_TIMEZONE)


def test_timezone_aware_timestamp_is_not_falsey_by_fallthrough():
    now = bj(2026, 8, 19, 14, 0)
    quote = {"retrieved_at": "2026-08-19T13:50:00+08:00"}

    assert quote_is_fresh(quote, now=now) is True


def test_timezone_aware_old_timestamp_is_stale():
    now = bj(2026, 8, 19, 14, 0)
    quote = {"retrieved_at": "2026-08-19T13:20:00+08:00"}

    assert quote_is_fresh(quote, now=now) is False


def test_naive_beijing_timestamp_remains_supported():
    now = bj(2026, 8, 19, 14, 0)
    quote = {"retrieved_at": "2026-08-19T13:50:00"}

    assert quote_is_fresh(quote, now=now) is True


def test_current_day_completed_cn_session_is_displayable_after_close():
    calendar = TradingCalendarService()
    now = bj(2026, 8, 19, 21, 47)
    quote = {
        "price": 88.66,
        "as_of": "2026-08-19T15:00:00+08:00",
        "retrieved_at": "2026-08-19T15:00:10+08:00",
        "refresh_status": "stored",
    }

    assert quote_is_fresh(quote, now=now) is False
    assert quote_display_status(quote, "002594", now=now, trading_calendar=calendar) == "session_close"


def test_prior_cn_session_stays_visibly_stale_after_close():
    calendar = TradingCalendarService()
    now = bj(2026, 8, 19, 21, 47)
    quote = {
        "price": 88.66,
        "as_of": "2026-08-18T15:00:00+08:00",
        "retrieved_at": "2026-08-18T15:00:10+08:00",
        "refresh_status": "stored",
    }

    assert quote_display_status(quote, "002594", now=now, trading_calendar=calendar) == "stale"


def test_old_quote_while_market_open_is_stale_not_session_close():
    calendar = TradingCalendarService()
    now = bj(2026, 8, 19, 14, 0)
    quote = {
        "price": 88.66,
        "as_of": "2026-08-19T13:20:00+08:00",
        "retrieved_at": "2026-08-19T13:20:00+08:00",
        "refresh_status": "stored",
    }

    assert quote_display_status(quote, "002594", now=now, trading_calendar=calendar) == "stale"


def test_pending_refresh_is_distinct_from_stale():
    now = bj(2026, 8, 19, 14, 0)
    quote = {
        "price": 88.66,
        "as_of": "2026-08-19T13:20:00+08:00",
        "retrieved_at": "2026-08-19T13:20:00+08:00",
        "refresh_status": "pending",
    }

    assert quote_display_status(quote, "002594", now=now) == "refreshing"
