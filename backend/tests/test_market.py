import time
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from app.market import MarketDataService, MarketDataUnavailable
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


def test_a_share_quote_falls_back_to_sina_when_eastmoney_is_unavailable(monkeypatch):
    sina = pd.DataFrame([{
        "代码": "sz002594", "名称": "比亚迪", "最新价": 91.15,
        "涨跌额": -3.3, "涨跌幅": -3.49, "昨收": 94.45, "今开": 96.03,
        "最高": 96.59, "最低": 90.88, "成交量": 123, "成交额": 456,
        "时间戳": "15:00:00",
        "\u4e70\u5165": 91.14,
        "\u5356\u51fa": 91.15,
        "\u91cf\u6bd4": 1.26,
        "\u6362\u624b\u7387": 2.31,
    }])
    monkeypatch.setitem(
        __import__("sys").modules,
        "akshare",
        SimpleNamespace(
            stock_zh_a_spot_em=lambda: (_ for _ in ()).throw(ConnectionError("eastmoney unavailable")),
            stock_zh_a_spot=lambda: sina,
        ),
    )

    quote = MarketDataService().quotes(["002594"], force_refresh=True)[0]

    assert quote["price"] == 91.15
    assert quote["source"] == "Sina Finance / AKShare"
    assert quote["bid_price"] == 91.14
    assert quote["ask_price"] == 91.15
    assert quote["volume_ratio"] == 1.26
    assert quote["turnover_rate"] == 2.31


def test_a_share_order_book_exposes_five_levels_and_volumes(monkeypatch):
    book = pd.DataFrame([
        {"item": "buy_1", "value": 10.44}, {"item": "buy_1_vol", "value": 369000},
        {"item": "buy_2", "value": 10.43}, {"item": "buy_2_vol", "value": 835900},
        {"item": "sell_1", "value": 10.45}, {"item": "sell_1_vol", "value": 233900},
        {"item": "sell_2", "value": 10.46}, {"item": "sell_2_vol", "value": 1608400},
    ])
    monkeypatch.setitem(
        __import__("sys").modules,
        "akshare",
        SimpleNamespace(stock_bid_ask_em=lambda symbol: book),
    )

    order_book = MarketDataService._a_order_book("000001")

    assert order_book["bid_price"] == 10.44
    assert order_book["ask_price"] == 10.45
    assert order_book["bid_levels"] == [
        {"price": 10.44, "volume": 369000}, {"price": 10.43, "volume": 835900},
    ]
    assert order_book["ask_levels"] == [
        {"price": 10.45, "volume": 233900}, {"price": 10.46, "volume": 1608400},
    ]


def test_invalid_symbol_does_not_discard_valid_quote():
    service = MarketDataService()
    service._provider = "akshare"
    service._public_a_quotes = lambda stocks, etfs, note, force_refresh=False: [{
        "symbol": "600519",
        "name": "贵州茅台",
        "price": 1500.0,
        "currency": "CNY",
        "source": "测试行情",
        "retrieved_at": datetime(2026, 7, 30, 10, 30, tzinfo=BEIJING_TIMEZONE),
    }]

    quotes = service.quotes(["600519", "BAD"])

    assert [quote["symbol"] for quote in quotes] == ["600519", "BAD"]
    assert quotes[0]["price"] == 1500.0
    assert quotes[1]["error_code"] == "invalid_symbol"


def test_universe_snapshot_uses_tushare_only_after_akshare_chain_fails(monkeypatch):
    service = MarketDataService()
    service._frame = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        MarketDataUnavailable("AKShare unavailable", "akshare_chain_unavailable")
    )
    recovered = [{"symbol": "600519", "price": 1500.0, "source": "Tushare Pro 全市场日线"}]
    service._tushare_a_share_universe = lambda error: recovered

    assert service.a_share_universe_snapshot(force_refresh=True) == recovered


def test_universe_snapshot_reports_unavailable_when_akshare_and_tushare_fail():
    service = MarketDataService()
    service._frame = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        MarketDataUnavailable("AKShare unavailable", "akshare_chain_unavailable")
    )
    service._tushare_a_share_universe = lambda error: (_ for _ in ()).throw(
        MarketDataUnavailable("all sources unavailable", "all_market_sources_unavailable")
    )

    with pytest.raises(MarketDataUnavailable, match="all sources unavailable") as error:
        service.a_share_universe_snapshot(force_refresh=True)

    assert error.value.code == "all_market_sources_unavailable"


def test_a_share_name_lookup_uses_dedicated_code_directory(monkeypatch):
    service = MarketDataService()
    monkeypatch.setitem(
        __import__("sys").modules,
        "akshare",
        SimpleNamespace(stock_info_a_code_name=lambda: pd.DataFrame([{"code": "600519", "name": "贵州茅台"}])),
    )

    frame, _, source = service._directory_frame("a")

    assert frame.iloc[0]["代码"] == "600519"
    assert frame.iloc[0]["名称"] == "贵州茅台"
    assert source == "AKShare A 股代码表"


def test_name_lookup_continues_when_one_market_directory_fails():
    service = MarketDataService()
    a_directory = (
        pd.DataFrame([{"代码": "600519", "名称": "贵州茅台"}]),
        datetime(2026, 7, 30, 10, 30, tzinfo=BEIJING_TIMEZONE),
        "A 股代码表",
    )

    def directory(market):
        if market == "a":
            return a_directory
        raise MarketDataUnavailable(f"{market} 代码表失败", "symbol_directory_unavailable")

    service._directory_frame = directory

    results = service.lookup_symbols(["贵州茅台", "不存在"])

    assert results[0]["matches"][0]["symbol"] == "600519"
    assert results[0]["lookup_status"] == "matched"
    assert results[1]["lookup_status"] == "partial_failure"
