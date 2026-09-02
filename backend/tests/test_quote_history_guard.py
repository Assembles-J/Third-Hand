from __future__ import annotations

import json

from app.storage import PortfolioStore
from quote_history_guard import TRIGGER_NAME, install_quote_history_guard


def test_quote_history_guard_keeps_only_latest_row_per_symbol(tmp_path):
    store = PortfolioStore(tmp_path / "quotes.db")
    install_quote_history_guard(store)

    store.save_quotes([
        {"symbol": "600519", "price": 100.0},
        {"symbol": "000001", "price": 10.0},
    ])
    store.save_quotes([
        {"symbol": "600519", "price": 101.0},
        {"symbol": "000001", "price": 11.0},
    ])

    with store._connect() as connection:  # noqa: SLF001 - persistence regression assertion
        rows = connection.execute(
            "SELECT symbol, payload FROM market_quote_history ORDER BY symbol"
        ).fetchall()
        trigger = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND name=?",
            (TRIGGER_NAME,),
        ).fetchone()

    assert trigger is not None
    assert len(rows) == 2
    assert {row["symbol"]: json.loads(row["payload"])["price"] for row in rows} == {
        "000001": 11.0,
        "600519": 101.0,
    }


def test_quote_history_guard_does_not_change_latest_quote_cache(tmp_path):
    store = PortfolioStore(tmp_path / "quotes.db")
    install_quote_history_guard(store)

    store.save_quotes([{"symbol": "600519", "price": 100.0}])
    store.save_quotes([{"symbol": "600519", "price": 102.5}])

    assert store.cached_quotes(["600519"])[0]["price"] == 102.5
    summary = store.admin_summary()
    assert summary["market_history_count"] == 1
    assert summary["latest_market_at"] is not None
