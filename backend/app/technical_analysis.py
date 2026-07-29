"""Explainable daily technical indicators for evidence, not trading orders."""
from __future__ import annotations
from datetime import date, timedelta

class TechnicalDataUnavailable(RuntimeError): pass

class TechnicalAnalysisService:
    def assess(self, symbol: str) -> dict[str, object]:
        try:
            import akshare as ak
            from ta.momentum import RSIIndicator
            from ta.trend import MACD, SMAIndicator
            from ta.volatility import AverageTrueRange
        except ImportError as error: raise TechnicalDataUnavailable("技术分析依赖未安装。") from error
        try:
            start = (date.today() - timedelta(days=420)).strftime("%Y%m%d")
            frame = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start, end_date=date.today().strftime("%Y%m%d"), adjust="qfq")
            close, high, low = frame["收盘"], frame["最高"], frame["最低"]
            sma20, sma60 = SMAIndicator(close, 20).sma_indicator().iloc[-1], SMAIndicator(close, 60).sma_indicator().iloc[-1]
            rsi = RSIIndicator(close, 14).rsi().iloc[-1]
            macd = MACD(close).macd_diff().iloc[-1]
            atr = AverageTrueRange(high, low, close, 14).average_true_range().iloc[-1]
            drawdown = (close.iloc[-1] / close.tail(60).max() - 1) * 100
            trend = "up" if sma20 >= sma60 else "down"
            return {"trend":trend,"sma20":round(float(sma20),2),"sma60":round(float(sma60),2),"rsi14":round(float(rsi),1),"macd_histogram":round(float(macd),3),"atr14":round(float(atr),2),"drawdown_60d_percent":round(float(drawdown),1)}
        except Exception as error: raise TechnicalDataUnavailable("历史行情不足，无法计算技术指标。") from error
