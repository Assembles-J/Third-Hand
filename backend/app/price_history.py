"""Background collection and normalization of daily prices for held securities."""
from __future__ import annotations

from datetime import date, timedelta, datetime
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

    @staticmethod
    def _trading_date(value: object) -> str | None:
        """Return an ISO trading date and reject provider row indexes such as ``999``."""
        raw = str(value).strip()
        candidate = raw[:10]
        if len(raw) >= 8 and raw[:8].isdigit():
            candidate = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError:
            return None

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
                columns_available = set(getattr(frame, "columns", ()))
                # AKShare's HK endpoint returns a RangeIndex and an explicit `date`
                # column. Never persist that RangeIndex as a trading date.
                date_column = next((name for name in ("date", "Date", "日期") if name in columns_available), None)
                date_values = frame[date_column] if date_column else frame.index
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
                trading_date = self._trading_date(day)
                if trading_date is None:
                    continue
                close = decimal_text(frame.iloc[index].get(columns["close"]))
                if close is None:
                    continue
                bars.append({
                    "trading_date": trading_date, "open": decimal_text(frame.iloc[index].get(columns["open"])),
                    "close": close, "high": decimal_text(frame.iloc[index].get(columns["high"])),
                    "low": decimal_text(frame.iloc[index].get(columns["low"])),
                    "volume": decimal_text(frame.iloc[index].get(columns["volume"])),
                    "amount": decimal_text(frame.iloc[index].get(columns["amount"])),
                    "amplitude_percent": decimal_text(frame.iloc[index].get("振幅")),
                    "change_percent": decimal_text(frame.iloc[index].get("涨跌幅")),
                    "change_amount": decimal_text(frame.iloc[index].get("涨跌额")),
                    "turnover_rate": decimal_text(frame.iloc[index].get("换手率")),
                    "adjustment": "qfq", "source": "AKShare daily history",
                })
        except PriceHistoryUnavailable:
            raise
        except Exception as error:
            bars = self._tushare_bars(symbol, start)
            if not bars:
                raise PriceHistoryUnavailable("历史行情源暂时不可用。") from error
        if not bars:
            raise PriceHistoryUnavailable("行情源未返回可用的交易日期。")
        # A successful refresh is authoritative for one symbol. Replacing instead of
        # upserting also purges legacy malformed dates already stored in the cache.
        store.replace_daily_prices(symbol, bars)
        return len(bars)

    def refresh_intraday(self, store, symbol: str) -> int:
        """Persist one-minute OHLCV bars; callers run this only in background jobs."""
        symbol = symbol.strip().upper()
        if self._kind(symbol) == "hk":
            raise PriceHistoryUnavailable("港股分钟行情源尚未配置")
        try:
            import akshare as ak
            today = datetime.now().strftime("%Y-%m-%d")
            frame = ak.stock_zh_a_hist_min_em(symbol=symbol, start_date=f"{today} 09:30:00", end_date=f"{today} 15:00:00", period="1", adjust="")
        except Exception as error:
            raise PriceHistoryUnavailable("分钟行情源暂时不可用") from error
        if frame is None or frame.empty:
            raise PriceHistoryUnavailable("分钟行情为空或尚未开盘")
        bars = []
        for _, row in frame.iterrows():
            try:
                values = list(row.values)
                # Eastmoney's documented column order: time, open, close, high, low, volume, amount, amplitude, change, change amount, turnover.
                bars.append({"bar_time": str(values[0])[:19], "open": float(values[1]), "close": float(values[2]), "high": float(values[3]), "low": float(values[4]), "volume": float(values[5]) if len(values) > 5 else None, "amount": float(values[6]) if len(values) > 6 else None, "average_price": None, "source": "AKShare stock_zh_a_hist_min_em"})
            except (TypeError, ValueError, IndexError):
                continue
        store.save_intraday_prices(symbol, bars)
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
