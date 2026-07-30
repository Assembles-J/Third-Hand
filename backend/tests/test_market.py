import time
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from app.market import MarketDataService
from app.time_utils import BEIJING_TIMEZONE


def test_hong_kong_quote_prefers_spot_snapshot():
    service = MarketDataService()
    spot = pd.DataFrame([{
        "代码": "01810",
        "名称": "小米集团-W",
        "最新价": 32.4,
        "涨跌额": 0.6,
        "涨跌幅": 1.89,
        "今开": 31.9,
        "最高": 32.8,
        "最低": 31.7,
        "昨收": 31.8,
        "成交量": 100,
        "成交额": 200,
    }])
    retrieved_at = datetime(2026, 7, 30, 10, 30, tzinfo=BEIJING_TIMEZONE)
    service._frame = lambda market, force_refresh=False: (spot, retrieved_at, "港股公开快照")

    quote = service._hk_quotes(["01810"])[0]

    assert quote["price"] == 32.4
    assert quote["as_of"] == "2026-07-30"
    assert quote["source"] == "港股公开快照"
    assert "交易时段" in quote["freshness_note"]


def test_auto_provider_prefers_public_spot_over_tushare_daily():
    service = MarketDataService()
    service._provider = "auto"
    service._tushare_token = "configured"
    calls: list[bool] = []
    service._public_a_quotes = lambda stocks, etfs, note, force_refresh=False: [
        calls.append(force_refresh) or {
            "symbol": "600519",
            "name": "贵州茅台",
            "price": 1500.0,
            "currency": "CNY",
            "source": "公开实时快照",
            "retrieved_at": datetime(2026, 7, 30, 10, 30, tzinfo=BEIJING_TIMEZONE),
            "as_of": "2026-07-30",
        }
    ]
    service._tushare_a_quotes = lambda symbols: pytest.fail("auto 模式不应在公开源可用时优先使用盘后日线")

    quote = service.quotes(["600519"], force_refresh=True)[0]

    assert quote["source"] == "公开实时快照"
    assert calls == [True]


def test_force_refresh_bypasses_in_memory_market_frame(monkeypatch):
    service = MarketDataService()
    stale = pd.DataFrame([{"代码": "600519", "最新价": 1400.0}])
    fresh = pd.DataFrame([{"代码": "600519", "最新价": 1500.0}])
    service._cache["a"] = (
        time.monotonic(),
        stale,
        datetime(2026, 7, 29, 15, 0, tzinfo=BEIJING_TIMEZONE),
        "旧内存缓存",
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "akshare",
        SimpleNamespace(stock_zh_a_spot_em=lambda: fresh),
    )

    frame, retrieved_at, source = service._frame("a", force_refresh=True)

    assert float(frame.iloc[0]["最新价"]) == 1500.0
    assert retrieved_at > datetime(2026, 7, 29, 15, 0, tzinfo=BEIJING_TIMEZONE)
    assert source == "东方财富 / AKShare"
