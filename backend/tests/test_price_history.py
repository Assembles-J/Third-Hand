from datetime import datetime, timedelta
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from app.market_freshness import quote_freshness_status
from app.price_history import PriceHistoryService, PriceHistoryUnavailable
from app.storage import PortfolioStore


def test_daily_price_schema_migrates_and_persists_full_ohlcv(tmp_path):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute("""CREATE TABLE daily_price_cache (
            symbol TEXT NOT NULL, trading_date TEXT NOT NULL, close REAL NOT NULL,
            high REAL, low REAL, source TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY (symbol, trading_date))""")
    store = PortfolioStore(database)
    store.save_daily_prices("600519", [{
        "trading_date": "2026-07-30", "open": "1500.10", "close": "1505.20",
        "high": "1510.00", "low": "1498.00", "volume": "123456", "amount": "1000000.50",
        "adjustment": "qfq", "source": "test",
    }])
    assert store.daily_prices("600519") == [{
        "trading_date": "2026-07-30", "open": "1500.10", "close": 1505.2, "high": 1510.0,
        "low": 1498.0, "volume": "123456", "amount": "1000000.50", "adjustment": "qfq", "source": "test",
        "amplitude_percent": None, "change_percent": None, "change_amount": None, "turnover_rate": None,
    }]


def test_daily_price_persists_market_activity_fields(tmp_path):
    store = PortfolioStore(tmp_path / "activity.db")
    store.save_daily_prices("600519", [{
        "trading_date": "2026-07-30", "close": 10, "volume": 123, "amount": 456,
        "amplitude_percent": 2.1, "change_percent": 1.2, "change_amount": 0.12,
        "turnover_rate": 3.4, "source": "test",
    }])
    bar = store.daily_prices("600519")[0]
    assert bar["amplitude_percent"] == "2.1"
    assert bar["change_percent"] == "1.2"
    assert bar["change_amount"] == "0.12"
    assert bar["turnover_rate"] == "3.4"


def test_instrument_metadata_keeps_unknown_lot_size_null(tmp_path):
    store = PortfolioStore(tmp_path / "metadata.db")
    saved = store.save_instrument_metadata({
        "symbol": "01810", "market": "HK", "currency": "HKD", "lot_size": None,
        "price_tick": "0.01", "source": "test", "as_of": "2026-07-30",
    })
    assert saved["lot_size"] is None
    assert store.instrument_metadata("01810")["lot_size"] is None


def test_quote_freshness_gate_rejects_stale_or_missing_timestamps():
    now = datetime(2026, 7, 30, 10, 30)
    assert quote_freshness_status({"retrieved_at": (now - timedelta(minutes=5)).isoformat()}, now=now) == "stored"
    assert quote_freshness_status({"retrieved_at": (now - timedelta(minutes=21)).isoformat()}, now=now) == "stale_fallback"
    assert quote_freshness_status({}, now=now) == "stale_fallback"


class _Row(dict):
    pass


class _Iloc:
    def __init__(self, rows): self.rows = rows
    def __getitem__(self, index): return _Row(self.rows[index])


class _Frame:
    def __init__(self, rows, dates=None):
        self.rows = rows
        self.index = dates or []
        self.columns = list(rows[0]) if rows else []
        self.empty = not rows
        self.iloc = _Iloc(rows)
    def __getitem__(self, key): return [row[key] for row in self.rows]


def test_price_history_preserves_ohlcv_for_a_etf_and_hk(monkeypatch, tmp_path):
    a_frame = _Frame([{"日期": "2026-07-30", "开盘": "10.01", "收盘": "10.20", "最高": "10.30", "最低": "9.90", "成交量": "100", "成交额": "1000"}])
    etf_frame = _Frame([{"日期": "2026-07-30", "开盘": "1.01", "收盘": "1.02", "最高": "1.03", "最低": "1.00", "成交量": "200", "成交额": "2000"}])
    hk_frame = _Frame([{"open": "20.01", "close": "20.20", "high": "20.30", "low": "19.90", "volume": "300", "amount": "3000"}], ["2026-07-30"])
    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(
        stock_zh_a_hist=lambda **_: a_frame, fund_etf_hist_em=lambda **_: etf_frame,
        stock_hk_daily=lambda **_: hk_frame,
    ))
    store = PortfolioStore(tmp_path / "history.db")
    service = PriceHistoryService()
    for symbol in ("600519", "510300", "01810"):
        assert service.refresh(store, symbol) == 1
        bar = store.daily_prices(symbol)[0]
        assert bar["open"] is not None and bar["volume"] is not None and bar["amount"] is not None
        assert bar["adjustment"] == "qfq"


def test_hk_refresh_uses_provider_date_column_and_replaces_legacy_row_indexes(monkeypatch, tmp_path):
    hk_frame = _Frame([{
        "date": "2026-07-30", "open": "20.01", "close": "20.20", "high": "20.30",
        "low": "19.90", "volume": "300", "amount": "3000",
    }], [999])
    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(stock_hk_daily=lambda **_: hk_frame))
    store = PortfolioStore(tmp_path / "history.db")
    store.save_daily_prices("01810", [{
        "trading_date": "999", "open": "20", "close": "20", "high": "20", "low": "20", "source": "legacy",
    }])

    assert PriceHistoryService().refresh(store, "01810") == 1
    assert [item["trading_date"] for item in store.daily_prices("01810")] == ["2026-07-30"]


def test_daily_history_failure_logs_akshare_and_tushare_status(monkeypatch, tmp_path, caplog):
    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(
        stock_zh_a_hist=lambda **_: (_ for _ in ()).throw(ConnectionError("upstream timed out")),
    ))
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)

    with caplog.at_level("WARNING"):
        with pytest.raises(PriceHistoryUnavailable, match="AKShare 失败"):
            PriceHistoryService().refresh(PortfolioStore(tmp_path / "history.db"), "600519")

    assert "provider=akshare" in caplog.text
    assert "ConnectionError" in caplog.text
    assert "provider=tushare" in caplog.text
    assert "reason=tushare_token_missing" in caplog.text
