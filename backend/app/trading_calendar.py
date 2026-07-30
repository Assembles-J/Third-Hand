"""Exchange calendar helpers for market refresh and quote dates."""
from __future__ import annotations

from datetime import datetime

import exchange_calendars as xcals
import pandas as pd

from app.time_utils import BEIJING_TIMEZONE, beijing_now


class TradingCalendarService:
    """Trading-session checks for mainland China and Hong Kong markets."""

    def __init__(self) -> None:
        """
        显式的无参数构造函数。

        外部可以直接调用：

            TradingCalendarService()
        """
        self._calendars = {
            "CN": xcals.get_calendar("XSHG"),
            "HK": xcals.get_calendar("XHKG"),
        }

    @staticmethod
    def market_for_symbol(symbol: str) -> str | None:
        normalized = symbol.strip().upper()

        # 港股，例如 01810
        if len(normalized) == 5 and normalized.isdigit():
            return "HK"

        # A股、ETF，例如 600519、510300
        if len(normalized) == 6 and normalized.isdigit():
            return "CN"

        return None

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
            # 自动判断：
            # 1. 交易日
            # 2. 开盘时间
            # 3. 午间休市
            # 4. 提前收盘
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
        """
        返回行情应归属的最近交易日。

        例如：
        - 周一开盘后拉取：返回周一
        - 周一开盘前拉取：返回上一个交易日
        - 周六拉取：返回周五
        - 法定节假日拉取：返回节前最后交易日
        """
        calendar = self._calendars.get(market)
        if calendar is None:
            return None

        local_time = self.normalize_moment(moment)
        utc_time = pd.Timestamp(local_time).tz_convert("UTC")
        local_date = pd.Timestamp(local_time.date())

        try:
            if calendar.is_session(local_date):
                session_open = calendar.session_open(local_date)

                # 当天尚未开盘，行情一般仍属于前一交易日。
                if utc_time < session_open:
                    previous = calendar.previous_session(local_date)
                    return previous.date().isoformat()

                # 已开盘或已经收盘，行情归属于当天。
                return local_date.date().isoformat()

            previous = calendar.date_to_session(
                local_date,
                direction="previous",
            )
            return previous.date().isoformat()

        except ValueError:
            return None

    def latest_symbol_session_date(
        self,
        symbol: str,
        moment: datetime | None = None,
    ) -> str | None:
        market = self.market_for_symbol(symbol)
        if market is None:
            return None

        return self.latest_session_date(market, moment)