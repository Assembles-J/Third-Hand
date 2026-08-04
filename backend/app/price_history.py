"""Background collection and normalization of daily prices for held securities."""
from __future__ import annotations

from datetime import date, timedelta, datetime
import logging
import math
import os

from app.decimal_utils import decimal_text
from app.time_utils import beijing_now
from app.trading_calendar import TradingCalendarService


logger = logging.getLogger(__name__)


class PriceHistoryUnavailable(RuntimeError):
    pass


class PriceHistoryService:
    DEFAULT_LOOKBACK_DAYS = 183
    MAX_LOOKBACK_DAYS = 3650

    def __init__(self, trading_calendar: TradingCalendarService | None = None) -> None:
        self._trading_calendar = trading_calendar or TradingCalendarService()

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

    @staticmethod
    def _has_finite_ohlc(bar: dict[str, object]) -> bool:
        """SQLite converts NaN to NULL, which violates the intraday OHLC schema."""
        try:
            return all(math.isfinite(float(bar[field])) for field in ("open", "close", "high", "low"))
        except (KeyError, TypeError, ValueError):
            return False

    def refresh(self, store, symbol: str, start_date: str | None = None, end_date: str | None = None) -> int:
        """Fill only missing daily-session ranges and preserve cached history."""
        symbol = symbol.strip().upper()
        market = "HK" if self._kind(symbol) == "hk" else "CN"
        latest = self._trading_calendar.latest_session_date(market) or beijing_now().date().isoformat()
        try:
            end_day = date.fromisoformat(end_date) if end_date else date.fromisoformat(latest)
            start_day = date.fromisoformat(start_date) if start_date else end_day - timedelta(days=self.DEFAULT_LOOKBACK_DAYS)
        except ValueError as error:
            raise PriceHistoryUnavailable("日期范围格式应为 YYYY-MM-DD。") from error
        if start_day > end_day or (end_day - start_day).days > self.MAX_LOOKBACK_DAYS:
            raise PriceHistoryUnavailable("日期范围无效或超过十年上限。")
        start = start_day.isoformat()
        end = end_day.isoformat()
        expected = self._trading_calendar.session_dates(market, start, end)
        existing = {str(item["trading_date"]) for item in store.daily_prices(symbol, 1000)}
        missing = [session for session in expected if session not in existing]
        if not missing:
            return len(existing)
        groups: list[tuple[str, str]] = []
        group_start = missing[0]
        previous = missing[0]
        expected_positions = {session: index for index, session in enumerate(expected)}
        for session in missing[1:]:
            if expected_positions[session] != expected_positions[previous] + 1:
                groups.append((group_start, previous))
                group_start = session
            previous = session
        groups.append((group_start, previous))
        for range_start, range_end in groups:
            self._refresh_range(store, symbol, range_start.replace("-", ""), range_end.replace("-", ""))
        return len(store.daily_prices(symbol, 1000))

    def _refresh_range(self, store, symbol: str, start: str, end: str) -> int:
        """Fetch outside request handling, then persist normalized daily OHLCV bars."""
        symbol = symbol.strip().upper()
        try:
            import akshare as ak
        except ImportError as error:
            raise PriceHistoryUnavailable("未安装历史行情依赖。") from error
        akshare_error: Exception | None = None
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
        except PriceHistoryUnavailable as error:
            akshare_error = error
            logger.warning(
                "历史日线获取失败 provider=akshare symbol=%s reason=%s",
                symbol,
                error,
            )
        except Exception as error:
            akshare_error = error
            logger.exception(
                "历史日线获取失败 provider=akshare symbol=%s error_type=%s",
                symbol,
                type(error).__name__,
            )
        if akshare_error is not None:
            # Tencent is independent from the Eastmoney endpoint behind
            # ``stock_zh_a_hist``. Tushare remains the final fallback.
            bars = self._tencent_bars(symbol, start, end)
            if not bars:
                bars = self._tushare_bars(symbol, start, end)
            if not bars:
                raise PriceHistoryUnavailable(
                    "历史日线不可用：AKShare、Tencent 均失败，Tushare 未返回可用数据；"
                    "请查看各 provider 日志。"
                ) from akshare_error
        else:
            logger.info(
                "历史日线获取成功 provider=akshare symbol=%s bar_count=%s",
                symbol,
                len(bars),
            )
        # Tencent daily data can lag after the close. Fill only a missing
        # completed-session bar from Sina's independently sourced 1-minute feed.
        self._append_sina_closing_bar(symbol, bars)
        if not bars:
            raise PriceHistoryUnavailable("行情源未返回可用的交易日期。")
        store.save_daily_prices(symbol, bars)
        return len(bars)

    def _tencent_bars(self, symbol: str, start: str, end: str) -> list[dict[str, object]]:
        """Fetch A-share daily history from Tencent when Eastmoney is down."""
        if self._kind(symbol) != "a":
            return []
        try:
            import akshare as ak
            exchange = "sh" if symbol.startswith(("5", "6", "9")) else "sz"
            frame = ak.stock_zh_a_hist_tx(
                symbol=f"{exchange}{symbol}", start_date=start, end_date=end, adjust="qfq",
            )
            if frame is None or frame.empty:
                raise ValueError("empty_response")
            bars = []
            for index, day in enumerate(frame["date"]):
                trading_date = self._trading_date(day)
                row = frame.iloc[index]
                close = decimal_text(row.get("close"))
                if trading_date is None or close is None:
                    continue
                bars.append({
                    "trading_date": trading_date, "open": decimal_text(row.get("open")),
                    "close": close, "high": decimal_text(row.get("high")),
                    "low": decimal_text(row.get("low")), "volume": decimal_text(row.get("volume")),
                    "amount": decimal_text(row.get("amount")), "adjustment": "qfq",
                    "source": "Tencent daily history",
                })
            if bars:
                logger.info("历史日线获取成功 provider=tencent symbol=%s bar_count=%s", symbol, len(bars))
            else:
                logger.warning("历史日线获取失败 provider=tencent symbol=%s reason=no_usable_close", symbol)
            return bars
        except Exception as error:
            logger.warning(
                "历史日线获取失败 provider=tencent symbol=%s error_type=%s",
                symbol, type(error).__name__,
            )
            return []

    def _append_sina_closing_bar(self, symbol: str, bars: list[dict[str, object]]) -> None:
        """Append a complete post-close A-share bar from Sina minute history."""
        now = beijing_now()
        if self._kind(symbol) != "a" or now.hour < 15:
            return
        today = now.date().isoformat()
        if any(str(bar.get("trading_date")) == today for bar in bars):
            return
        try:
            import akshare as ak
            exchange = "sh" if symbol.startswith(("5", "6", "9")) else "sz"
            frame = ak.stock_zh_a_minute(symbol=f"{exchange}{symbol}", period="1", adjust="qfq")
            if frame is None or frame.empty:
                return
            rows = []
            for index, value in enumerate(frame["day"]):
                if str(value)[:10] != today:
                    continue
                row = frame.iloc[index]
                if decimal_text(row.get("close")) is not None:
                    rows.append(row)
            if not rows:
                return
            volumes = [float(row.get("volume")) for row in rows if decimal_text(row.get("volume")) is not None]
            amounts = [float(row.get("amount")) for row in rows if decimal_text(row.get("amount")) is not None]
            bars.append({
                "trading_date": today, "open": decimal_text(rows[0].get("open")),
                "close": decimal_text(rows[-1].get("close")),
                "high": decimal_text(max(float(row.get("high")) for row in rows)),
                "low": decimal_text(min(float(row.get("low")) for row in rows)),
                "volume": decimal_text(sum(volumes)) if volumes else None,
                "amount": decimal_text(sum(amounts)) if amounts else None,
                "adjustment": "qfq", "source": "Sina minute aggregation",
            })
            logger.info("历史日线补齐成功 provider=sina_minute symbol=%s trading_date=%s", symbol, today)
        except Exception as error:
            logger.warning(
                "历史日线补齐跳过 provider=sina_minute symbol=%s error_type=%s",
                symbol, type(error).__name__,
            )

    def refresh_intraday(self, store, symbol: str) -> int:
        """Persist one-minute OHLCV bars; callers run this only in background jobs."""
        symbol = symbol.strip().upper()
        if self._kind(symbol) == "hk":
            raise PriceHistoryUnavailable("港股分钟行情源尚未配置")
        try:
            import akshare as ak
            today = beijing_now().date().isoformat()
            cached_today = [
                item for item in store.intraday_prices(symbol, 1500)
                if str(item.get("bar_time", ""))[:10] == today
            ]
            latest_cached = str(cached_today[-1]["bar_time"])[:19] if cached_today else None
            if beijing_now().hour >= 15 and latest_cached and latest_cached.endswith("15:00:00"):
                return len(cached_today)
            request_start = latest_cached or f"{today} 09:30:00"
            try:
                frame = ak.stock_zh_a_hist_min_em(symbol=symbol, start_date=request_start, end_date=f"{today} 15:00:00", period="1", adjust="")
                source = "AKShare stock_zh_a_hist_min_em"
            except Exception as eastmoney_error:
                logger.warning(
                    "Minute data Eastmoney unavailable; falling back to Sina symbol=%s error_type=%s",
                    symbol, type(eastmoney_error).__name__,
                )
                exchange = "sh" if symbol.startswith(("5", "6", "9")) else "sz"
                frame = ak.stock_zh_a_minute(symbol=f"{exchange}{symbol}", period="1", adjust="qfq")
                source = "Sina Finance minute / AKShare"
        except Exception as error:
            raise PriceHistoryUnavailable("分钟行情源暂时不可用") from error
        if frame is None or frame.empty:
            raise PriceHistoryUnavailable("分钟行情为空或尚未开盘")
        bars = []
        for _, row in frame.iterrows():
            try:
                if source == "Sina Finance minute / AKShare":
                    bars.append({
                        "bar_time": str(row["day"])[:19], "open": float(row["open"]),
                        "close": float(row["close"]), "high": float(row["high"]),
                        "low": float(row["low"]), "volume": float(row["volume"]),
                        "amount": float(row["amount"]), "average_price": None, "source": source,
                    })
                else:
                    values = list(row.values)
                    # Eastmoney's documented column order: time, open, close, high, low, volume, amount, amplitude, change, change amount, turnover.
                    bars.append({"bar_time": str(values[0])[:19], "open": float(values[1]), "close": float(values[2]), "high": float(values[3]), "low": float(values[4]), "volume": float(values[5]) if len(values) > 5 else None, "amount": float(values[6]) if len(values) > 6 else None, "average_price": None, "source": source})
            except (TypeError, ValueError, IndexError):
                continue
        valid_bars = [bar for bar in bars if self._has_finite_ohlc(bar)]
        discarded = len(bars) - len(valid_bars)
        if discarded:
            logger.warning(
                "Discarded intraday bars with missing or non-finite OHLC symbol=%s source=%s count=%s",
                symbol, source, discarded,
            )
        if not valid_bars:
            raise PriceHistoryUnavailable("分钟行情未返回可写入的 OHLC 数据")
        store.save_intraday_prices(symbol, valid_bars)
        return len(valid_bars)

    def _tushare_bars(self, symbol: str, start: str, end: str) -> list[dict[str, object]]:
        """Use end-of-day Tushare data when an AKShare public endpoint is unavailable."""
        token = os.getenv("TUSHARE_TOKEN", "").strip()
        if not token:
            logger.warning(
                "历史日线备用源跳过 provider=tushare symbol=%s reason=tushare_token_missing",
                symbol,
            )
            return []
        if len(symbol) == 5:
            logger.warning(
                "历史日线备用源跳过 provider=tushare symbol=%s reason=hk_not_supported",
                symbol,
            )
            return []
        try:
            import tushare as ts
            client = ts.pro_api(token)
            exchange = "BJ" if symbol.startswith(("4", "8")) else ("SH" if symbol.startswith(("5", "6", "9")) else "SZ")
            is_etf = self._kind(symbol) == "etf"
            frame = (client.fund_daily if is_etf else client.daily)(ts_code=f"{symbol}.{exchange}", start_date=start, end_date=end)
            if frame is None or frame.empty:
                logger.warning(
                    "历史日线获取失败 provider=tushare symbol=%s reason=empty_response",
                    symbol,
                )
                return []
            bars = [{
                "trading_date": str(row["trade_date"]), "open": decimal_text(row.get("open")),
                "close": decimal_text(row.get("close")), "high": decimal_text(row.get("high")),
                "low": decimal_text(row.get("low")), "volume": decimal_text(row.get("vol")),
                "amount": decimal_text(row.get("amount")), "adjustment": "provider-default",
                "source": "Tushare daily history",
            } for _, row in frame.iterrows() if decimal_text(row.get("close")) is not None]
            if bars:
                logger.info(
                    "历史日线获取成功 provider=tushare symbol=%s bar_count=%s",
                    symbol,
                    len(bars),
                )
            else:
                logger.warning(
                    "历史日线获取失败 provider=tushare symbol=%s reason=no_usable_close",
                    symbol,
                )
            return bars
        except Exception as error:
            logger.exception(
                "历史日线获取失败 provider=tushare symbol=%s error_type=%s",
                symbol,
                type(error).__name__,
            )
            return []
