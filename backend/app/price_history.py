"""Background collection and normalization of daily prices for held securities."""
from __future__ import annotations

from datetime import date, timedelta
import os

from app.decimal_utils import decimal_text


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
        """Fetch outside request handling, then persist normalized daily OHLCV bars."""
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
                columns = {"open": "open", "close": "close", "high": "high", "low": "low", "volume": "volume", "amount": "amount"}
            elif kind == "etf":
                frame = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
                date_values = frame["日期"]
                columns = {"open": "开盘", "close": "收盘", "high": "最高", "low": "最低", "volume": "成交量", "amount": "成交额"}
            else:
                frame = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
                date_values = frame["日期"]
                columns = {"open": "开盘", "close": "收盘", "high": "最高", "low": "最低", "volume": "成交量", "amount": "成交额"}
            if frame is None or frame.empty:
                raise PriceHistoryUnavailable("历史行情为空。")
            bars = []
            for index, day in enumerate(date_values):
                close = decimal_text(frame.iloc[index].get(columns["close"]))
                if close is None:
                    continue
                bars.append({
                    "trading_date": str(day)[:10], "open": decimal_text(frame.iloc[index].get(columns["open"])),
                    "close": close, "high": decimal_text(frame.iloc[index].get(columns["high"])),
                    "low": decimal_text(frame.iloc[index].get(columns["low"])),
                    "volume": decimal_text(frame.iloc[index].get(columns["volume"])),
                    "amount": decimal_text(frame.iloc[index].get(columns["amount"])),
                    "adjustment": "qfq", "source": "AKShare daily history",
                })
        except PriceHistoryUnavailable:
            raise
        except Exception as error:
            bars = self._tushare_bars(symbol, start)
            if not bars:
                raise PriceHistoryUnavailable("历史行情源暂时不可用。") from error
        store.save_daily_prices(symbol, bars)
        return len(bars)

    def _tushare_bars(self, symbol: str, start: str) -> list[dict[str, object]]:
        """Use end-of-day Tushare data when an AKShare public endpoint is unavailable."""
        token = os.getenv("TUSHARE_TOKEN", "").strip()
        if not token or len(symbol) == 5:
            return []
        try:
            import tushare as ts
            client = ts.pro_api(token)
            exchange = "BJ" if symbol.startswith(("4", "8")) else ("SH" if symbol.startswith(("5", "6", "9")) else "SZ")
            is_etf = self._kind(symbol) == "etf"
            frame = (client.fund_daily if is_etf else client.daily)(ts_code=f"{symbol}.{exchange}", start_date=start)
            if frame is None or frame.empty:
                return []
            return [{
                "trading_date": str(row["trade_date"]), "open": decimal_text(row.get("open")),
                "close": decimal_text(row.get("close")), "high": decimal_text(row.get("high")),
                "low": decimal_text(row.get("low")), "volume": decimal_text(row.get("vol")),
                "amount": decimal_text(row.get("amount")), "adjustment": "provider-default",
                "source": "Tushare daily history",
            } for _, row in frame.iterrows() if decimal_text(row.get("close")) is not None]
        except Exception:
            return []
