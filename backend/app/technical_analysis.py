"""Explainable daily technical indicators for evidence, not trading orders."""
from __future__ import annotations

from datetime import date, timedelta


class TechnicalDataUnavailable(RuntimeError):
    pass


class TechnicalAnalysisService:
    def assess(self, symbol: str) -> dict[str, object]:
        try:
            import akshare as ak
            from ta.momentum import RSIIndicator
            from ta.trend import MACD, SMAIndicator
            from ta.volatility import AverageTrueRange
        except ImportError as error:
            raise TechnicalDataUnavailable("技术分析依赖未安装。") from error
        try:
            start = (date.today() - timedelta(days=420)).strftime("%Y%m%d")
            frame = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start, end_date=date.today().strftime("%Y%m%d"), adjust="qfq")
            if frame is None or len(frame.index) < 60:
                raise TechnicalDataUnavailable("至少需要 60 个交易日的历史行情。")
            frame = frame.sort_values("日期")
            close = frame["收盘"].astype(float)
            high = frame["最高"].astype(float)
            low = frame["最低"].astype(float)
            sma20, sma60 = SMAIndicator(close, 20).sma_indicator().iloc[-1], SMAIndicator(close, 60).sma_indicator().iloc[-1]
            rsi = RSIIndicator(close, 14).rsi().iloc[-1]
            macd = MACD(close).macd_diff().iloc[-1]
            atr = AverageTrueRange(high, low, close, 14).average_true_range().iloc[-1]
            latest_close = float(close.iloc[-1])
            drawdown = (close.iloc[-1] / close.tail(60).max() - 1) * 100
            trend = "up" if sma20 >= sma60 else "down"
            if latest_close >= sma20 >= sma60:
                trend_label = "多头排列"
            elif latest_close < sma20 < sma60:
                trend_label = "空头排列"
            elif trend == "up":
                trend_label = "中期偏强"
            else:
                trend_label = "中期偏弱"
            rsi_state = "偏热" if rsi >= 70 else "偏冷" if rsi <= 30 else "中性"
            macd_state = "动能偏强" if macd > 0 else "动能偏弱" if macd < 0 else "动能均衡"
            above_sma20 = latest_close >= sma20
            summary = (
                f"收盘价位于 20 日均线{'上方' if above_sma20 else '下方'}，"
                f"均线结构为{trend_label}；RSI 处于{rsi_state}区，MACD {macd_state}。"
            )
            return {
                "as_of": str(frame["日期"].iloc[-1]),
                "sample_count": len(frame.index),
                "close": round(latest_close, 2),
                "trend": trend,
                "trend_label": trend_label,
                "summary": summary,
                "sma20": round(float(sma20), 2),
                "sma60": round(float(sma60), 2),
                "sma20_distance_percent": round((latest_close / float(sma20) - 1) * 100, 1),
                "sma60_distance_percent": round((latest_close / float(sma60) - 1) * 100, 1),
                "rsi14": round(float(rsi), 1),
                "rsi_state": rsi_state,
                "macd_histogram": round(float(macd), 3),
                "macd_state": macd_state,
                "atr14": round(float(atr), 2),
                "atr_percent": round(float(atr) / latest_close * 100, 1),
                "drawdown_60d_percent": round(float(drawdown), 1),
            }
        except TechnicalDataUnavailable:
            raise
        except Exception as error:
            raise TechnicalDataUnavailable("历史行情不足，无法计算技术指标。") from error
