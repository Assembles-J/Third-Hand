"""Exchange calendar helpers for market refresh and quote dates."""
from __future__ import annotations

from datetime import datetime, timedelta

import exchange_calendars as xcals
import pandas as pd

from app.market_adapter import market_for_symbol as resolve_market_for_symbol
from app.time_utils import BEIJING_TIMEZONE, beijing_now


class TradingCalendarService:
    """Trading-session checks for mainland China, Hong Kong and US markets."""

    def __init__(self) -> None:
        """Create exchange calendars used by the market adapter boundary."""
        self._calendars = {
            "CN": xcals.get_calendar("XSHG"),
            "HK": xcals.get_calendar("XHKG"),
            "US": xcals.get_calendar("XNYS"),
        }

    @staticmethod
    def market_for_symbol(symbol: str) -> str | None:
        """Compatibility market resolver delegated to ``market_adapter``."""
        return resolve_market_for_symbol(symbol)

    @staticmethod
    def normalize_moment(moment: datetime | None = None) -> datetime:
        if moment is None:
            return beijing_now()

        if moment.tzinfo is None:
            return moment.replace(tzinfo=BEIJING_TIMEZONE)

        return moment.astimezone(BEIJING_TIMEZONE)

    def is_market_open(
        self,
        market: str,
        moment: datetime | None = None,
    ) -> bool:
        calendar = self._calendars.get(market)
        if calendar is None:
            return False

        local_time = self.normalize_moment(moment)
        utc_minute = (
            pd.Timestamp(local_time)
            .tz_convert("UTC")
            .floor("min")
        )

        try:
            # exchange_calendars owns session/open/break/early-close semantics.
            return bool(calendar.is_trading_minute(utc_minute))
        except ValueError:
            return False

    def is_symbol_market_open(
        self,
        symbol: str,
        moment: datetime | None = None,
    ) -> bool:
        market = self.market_for_symbol(symbol)
        if market is None:
            return False

        return self.is_market_open(market, moment)

    def open_symbols(
        self,
        symbols: list[str],
        moment: datetime | None = None,
    ) -> list[str]:
        normalized = list(
            dict.fromkeys(
                symbol.strip().upper()
                for symbol in symbols
                if symbol.strip()
            )
        )

        return [
            symbol
            for symbol in normalized
            if self.is_symbol_market_open(symbol, moment)
        ]

    def latest_session_date(
        self,
        market: str,
        moment: datetime | None = None,
    ) -> str | None:
        """Return the most recent exchange session to which a quote may belong."""
        calendar = self._calendars.get(market)
        if calendar is None:
            return None

        local_time = self.normalize_moment(moment)
        utc_time = pd.Timestamp(local_time).tz_convert("UTC")
        local_date = pd.Timestamp(local_time.date())

        try:
            if calendar.is_session(local_date):
                session_open = calendar.session_open(local_date)

                if utc_time < session_open:
                    previous = calendar.previous_session(local_date)
                    return previous.date().isoformat()

                return local_date.date().isoformat()

            previous = calendar.date_to_session(
                local_date,
                direction="previous",
            )
            return previous.date().isoformat()

        except ValueError:
            return None

    def latest_completed_session_date(
        self,
        market: str,
        moment: datetime | None = None,
    ) -> str | None:
        """Return the latest session whose official close is observable."""
        calendar = self._calendars.get(market)
        if calendar is None:
            return None

        local_time = self.normalize_moment(moment)
        utc_time = pd.Timestamp(local_time).tz_convert("UTC")
        local_date = pd.Timestamp(local_time.date())

        try:
            if calendar.is_session(local_date):
                session_close = calendar.session_close(local_date)
                if utc_time < session_close:
                    return calendar.previous_session(local_date).date().isoformat()
                return local_date.date().isoformat()

            previous = calendar.date_to_session(local_date, direction="previous")
            return previous.date().isoformat()
        except ValueError:
            return None

    def is_post_close_maintenance_window(
        self,
        market: str,
        moment: datetime | None = None,
        *,
        minutes: int = 90,
    ) -> bool:
        """Whether now is inside the bounded post-close daily-data window."""
        calendar = self._calendars.get(market)
        if calendar is None:
            return False

        local_time = self.normalize_moment(moment)
        utc_time = pd.Timestamp(local_time).tz_convert("UTC")
        local_date = pd.Timestamp(local_time.date())
        try:
            if not calendar.is_session(local_date):
                return False
            close_time = calendar.session_close(local_date)
            end_time = close_time + pd.Timedelta(timedelta(minutes=max(1, minutes)))
            return bool(close_time <= utc_time <= end_time)
        except ValueError:
            return False

    def latest_symbol_session_date(
        self,
        symbol: str,
        moment: datetime | None = None,
    ) -> str | None:
        market = self.market_for_symbol(symbol)
        if market is None:
            return None

        return self.latest_session_date(market, moment)

    def latest_completed_symbol_session_date(
        self,
        symbol: str,
        moment: datetime | None = None,
    ) -> str | None:
        market = self.market_for_symbol(symbol)
        if market is None:
            return None
        return self.latest_completed_session_date(market, moment)

    def session_dates(self, market: str, start: str, end: str) -> list[str]:
        """Return exchange session dates in an inclusive ISO date range."""
        calendar = self._calendars.get(market)
        if calendar is None:
            return []
        try:
            return [session.date().isoformat() for session in calendar.sessions_in_range(
                pd.Timestamp(start), pd.Timestamp(end),
            )]
        except ValueError:
            return []
