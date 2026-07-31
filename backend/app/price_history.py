"""Background collection and normalization of daily prices for held securities."""
from __future__ import annotations

from datetime import date, timedelta


class PriceHistoryUnavailable(RuntimeError):
    pass


class PriceHistoryService:
    LOOKBACK_DAYS = 800

    @staticmethod
    def _kind(symbol: str) -> str:
        if len(symbol) == 5 and symbol.isdigit():
            return "hk"
        if len(symbol) == 6 and symbol.startswith(("15", "16", "51", "56", "58")):
            return "etf"
        return "a"

    def refresh(self, store, symbol: str) -> int:
        """Fetch outside request handling, then persist only normalized daily OHLC."""
        symbol = symbol.strip().upper()
        try:
            import akshare as ak
        except ImportError as error:
            raise PriceHistoryUnavailable("未安装历史行情依赖。") from error
        start = (date.today() - timedelta(days=self.LOOKBACK_DAYS)).strftime("%Y%m%d")
        end = date.today().strftime("%Y%m%d")
        try:
            kind = self._kind(symbol)
            if kind == "hk":
                frame = ak.stock_hk_daily(symbol=symbol)
                date_values = frame.index
                close_values, high_values, low_values = frame["close"], frame["high"], frame["low"]
            elif kind == "etf":
                frame = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
                date_values = frame["日期"]
                close_values, high_values, low_values = frame["收盘"], frame["最高"], frame["最低"]
            else:
                frame = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
                date_values = frame["日期"]
                close_values, high_values, low_values = frame["收盘"], frame["最高"], frame["最低"]
            if frame is None or frame.empty:
                raise PriceHistoryUnavailable("历史行情为空。")
            bars = [
                {
                    "trading_date": str(day)[:10], "close": float(close),
                    "high": float(high), "low": float(low), "source": "AKShare daily history",
                }
                for day, close, high, low in zip(date_values, close_values, high_values, low_values)
                if close is not None
            ]
        except PriceHistoryUnavailable:
            raise
        except Exception as error:
            raise PriceHistoryUnavailable("历史行情源暂时不可用。") from error
        store.save_daily_prices(symbol, bars)
        return len(bars)
