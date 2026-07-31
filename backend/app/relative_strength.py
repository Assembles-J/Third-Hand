"""Compare a holding with a user-confirmed daily benchmark."""
from __future__ import annotations


class RelativeStrengthService:
    def assess(self, stock_bars, benchmark_symbol: str | None, benchmark_name: str | None) -> dict[str, object]:
        if not benchmark_symbol:
            return {"status": "not_configured", "note": "请先在交易计划中确认比较基准。"}
        try:
            import akshare as ak
            frame = ak.stock_zh_index_daily_em(symbol=benchmark_symbol)
            benchmark = [float(value) for value in frame["close"].tolist()]
            stock = [float(item["close"]) for item in stock_bars]
            if len(stock) < 21 or len(benchmark) < 21:
                raise ValueError("历史日线不足")
            values = {}
            for days in (5, 20):
                stock_return = (stock[-1] / stock[-days - 1] - 1) * 100
                benchmark_return = (benchmark[-1] / benchmark[-days - 1] - 1) * 100
                values[str(days)] = {"stock_return_percent": round(stock_return, 2), "benchmark_return_percent": round(benchmark_return, 2), "relative_return_percent": round(stock_return - benchmark_return, 2)}
            relative_20 = values["20"]["relative_return_percent"]
            return {"status": "ready", "benchmark_symbol": benchmark_symbol, "benchmark_name": benchmark_name or benchmark_symbol, "horizons": values, "label": "相对强" if relative_20 >= 3 else "相对弱" if relative_20 <= -3 else "与基准接近", "note": "基于日线收盘价的相对收益，不构成交易信号。"}
        except Exception as error:
            return {"status": "unavailable", "benchmark_symbol": benchmark_symbol, "benchmark_name": benchmark_name or benchmark_symbol, "note": f"相对强弱暂不可用：{error}"}
