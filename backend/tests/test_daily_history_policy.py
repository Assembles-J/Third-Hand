from __future__ import annotations

import sqlite3

import pytest

from app.daily_history_policy import MIGRATION_ID, _migrate_daily_price_cache, install
from app.price_history import PriceHistoryService
from app.storage import PortfolioStore


install()


def _dirty_store(tmp_path) -> PortfolioStore:
    store = PortfolioStore(tmp_path / "daily-policy.db")
    with store._connect() as connection:
        connection.execute("DELETE FROM schema_migrations WHERE migration_id=?", (MIGRATION_ID,))
        connection.execute(
            """INSERT INTO daily_price_cache
            (symbol,trading_date,open,close,high,low,volume,amount,adjustment,source,updated_at)
            VALUES ('000001','20260813','10','10',10,10,'100','1000','provider-default','Tushare daily history','2026-08-14T00:00:00Z')"""
        )
        connection.execute(
            """INSERT INTO daily_price_cache
            (symbol,trading_date,open,close,high,low,volume,amount,adjustment,source,updated_at)
            VALUES ('000002','20260813','20','20',20,20,'100','1000','qfq','legacy qfq','2026-08-14T00:00:00Z')"""
        )
        connection.execute(
            """INSERT INTO daily_price_cache
            (symbol,trading_date,open,close,high,low,volume,amount,adjustment,source,updated_at)
            VALUES ('000002','2026-08-13','20','20',20,20,'100','1000','qfq','Tencent daily history','2026-08-14T01:00:00Z')"""
        )
        connection.execute(
            "INSERT OR REPLACE INTO risk_cache(symbol,payload,updated_at) VALUES ('000001','{}','2026-08-14T00:00:00Z')"
        )
    return store


def test_migration_quarantines_non_qfq_and_deduplicates_dates(tmp_path):
    store = _dirty_store(tmp_path)

    _migrate_daily_price_cache(store)

    with store._connect() as connection:
        formal = connection.execute(
            "SELECT symbol,trading_date,adjustment,source FROM daily_price_cache ORDER BY symbol,trading_date"
        ).fetchall()
        quarantine = connection.execute(
            "SELECT symbol,trading_date,quarantine_reason FROM daily_price_quarantine ORDER BY id"
        ).fetchall()
        risk = connection.execute("SELECT count(*) FROM risk_cache WHERE symbol='000001'").fetchone()[0]

    assert [tuple(row) for row in formal] == [
        ("000002", "2026-08-13", "qfq", "Tencent daily history")
    ]
    assert any(tuple(row) == ("000001", "20260813", "non_qfq") for row in quarantine)
    assert risk == 0


def test_formal_cache_rejects_non_qfq_writes(tmp_path):
    store = PortfolioStore(tmp_path / "contract.db")

    with pytest.raises(ValueError, match="qfq"):
        store.save_daily_prices(
            "000001",
            [{
                "trading_date": "2026-08-14",
                "open": 10,
                "close": 10,
                "high": 10,
                "low": 10,
                "adjustment": "provider-default",
                "source": "bad-provider",
            }],
        )


def test_formal_cache_normalizes_compact_qfq_date(tmp_path):
    store = PortfolioStore(tmp_path / "normalize.db")
    store.save_daily_prices(
        "000001",
        [{
            "trading_date": "20260814",
            "open": 10,
            "close": 10,
            "high": 10,
            "low": 10,
            "adjustment": "qfq",
            "source": "test",
        }],
    )
    assert store.daily_prices("000001")[-1]["trading_date"] == "2026-08-14"


def test_a_share_missing_range_prefers_tencent(monkeypatch):
    service = PriceHistoryService()
    calls: list[str] = []

    def tencent(*args, **kwargs):
        calls.append("tencent")
        return [{
            "trading_date": "2026-08-14",
            "open": "10",
            "close": "10",
            "high": "10",
            "low": "10",
            "adjustment": "qfq",
            "source": "Tencent daily history",
        }]

    def tushare(*args, **kwargs):
        calls.append("tushare")
        return []

    monkeypatch.setattr(service, "_tencent_bars", tencent)
    monkeypatch.setattr(service, "_tushare_bars", tushare)
    monkeypatch.setattr(service, "_append_sina_closing_bar", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_record_attempt", lambda *args, **kwargs: None)

    class Store:
        saved = None

        def save_daily_prices(self, symbol, bars):
            self.saved = (symbol, bars)

    store = Store()
    count = service._refresh_range(store, "600519", "20260814", "20260814")

    assert count == 1
    assert calls == ["tencent"]
    assert store.saved[0] == "600519"
