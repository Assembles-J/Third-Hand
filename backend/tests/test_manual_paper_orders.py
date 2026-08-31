from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

import app.storage as storage_module
from app.application_services.paper.manual_order import (
    ManualPaperOrderRejected,
    ManualPaperOrderService,
)
from app.storage import PortfolioStore


CN_TZ = timezone(timedelta(hours=8))


def _save_quote(
    store: PortfolioStore,
    *,
    symbol: str,
    name: str,
    price: float,
    observed_at: datetime,
    currency: str = "CNY",
) -> None:
    payload = {
        "symbol": symbol,
        "name": name,
        "price": price,
        "currency": currency,
        "source": "manual-order-test",
        "as_of": observed_at.isoformat(),
        "retrieved_at": observed_at.isoformat(),
        "is_realtime": True,
    }
    with store._connect() as connection:
        connection.execute(
            "INSERT INTO market_quote_cache (symbol,payload,updated_at) VALUES (?,?,?) "
            "ON CONFLICT(symbol) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at",
            (symbol, json.dumps(payload), observed_at.isoformat()),
        )


def _save_cn_metadata(store: PortfolioStore, symbol: str) -> None:
    store.save_instrument_metadata(
        {
            "symbol": symbol,
            "market": "CN",
            "currency": "CNY",
            "lot_size": 100,
            "price_tick": "0.01",
            "source": "test",
            "as_of": "2026-08-31",
        }
    )


def test_user_manual_cn_buy_is_audited_and_idempotent(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioStore(tmp_path / "manual-buy.db")
    store.save_paper_account(100_000)
    _save_cn_metadata(store, "600519")
    now = datetime(2026, 8, 31, 10, 0, tzinfo=CN_TZ)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: now)
    _save_quote(store, symbol="600519", name="Moutai", price=10.0, observed_at=now)
    service = ManualPaperOrderService(store, now_provider=lambda: now, max_quote_age_seconds=120)

    result = service.submit(
        client_order_id="android-001",
        symbol="600519",
        side="BUY",
        quantity=100,
    )

    assert result["status"] == "executed"
    assert result["idempotent_replay"] is False
    fill = result["fill"]
    assert fill["id"] == "manual:android-001"
    assert fill["decision_id"] is None
    assert fill["reason"] == "user_manual_paper_order:android-001"
    assert fill["fill_price_mode"] == "USER_MANUAL_LATEST_ELIGIBLE_OBSERVED_QUOTE"
    assert fill["price"] == 10.0

    replay = service.submit(
        client_order_id="android-001",
        symbol="600519",
        side="BUY",
        quantity=100,
    )
    assert replay["idempotent_replay"] is True

    with store._connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) AS count FROM paper_trading_logs WHERE id='manual:android-001'"
        ).fetchone()["count"] == 1

    position = store.paper_account()["positions"][0]
    assert position["quantity"] == 100
    assert position["sellable_quantity"] == 0
    assert position["locked_quantity"] == 100


def test_user_manual_cn_sell_respects_t1_then_sells_next_session(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioStore(tmp_path / "manual-sell.db")
    store.save_paper_account(100_000)
    _save_cn_metadata(store, "600519")
    day_one = datetime(2026, 8, 31, 10, 0, tzinfo=CN_TZ)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_one)
    _save_quote(store, symbol="600519", name="Moutai", price=10.0, observed_at=day_one)
    service = ManualPaperOrderService(store, now_provider=lambda: day_one, max_quote_age_seconds=120)
    service.submit(client_order_id="buy-001", symbol="600519", side="BUY", quantity=100)

    with pytest.raises(ManualPaperOrderRejected) as blocked:
        service.submit(client_order_id="sell-same-day", symbol="600519", side="SELL", quantity=100)
    assert blocked.value.reason_code == "paper_manual_order_t1_locked"
    assert blocked.value.capability["sellable_quantity"] == 0
    assert blocked.value.capability["locked_quantity"] == 100

    day_two = datetime(2026, 9, 1, 10, 0, tzinfo=CN_TZ)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_two)
    _save_quote(store, symbol="600519", name="Moutai", price=11.0, observed_at=day_two)
    next_service = ManualPaperOrderService(store, now_provider=lambda: day_two, max_quote_age_seconds=120)

    capability = next_service.capability("600519")
    assert capability["sellable_quantity"] == 100
    assert capability["locked_quantity"] == 0
    assert capability["max_sell_quantity"] == 100

    sold = next_service.submit(
        client_order_id="sell-next-day",
        symbol="600519",
        side="SELL",
        quantity=100,
    )
    assert sold["fill"]["side"] == "SELL"
    assert sold["fill"]["price"] == 11.0
    assert store.paper_account()["positions"] == []


def test_user_manual_order_enforces_cn_lot_size(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioStore(tmp_path / "manual-lot.db")
    store.save_paper_account(100_000)
    _save_cn_metadata(store, "600519")
    now = datetime(2026, 8, 31, 10, 0, tzinfo=CN_TZ)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: now)
    _save_quote(store, symbol="600519", name="Moutai", price=10.0, observed_at=now)
    service = ManualPaperOrderService(store, now_provider=lambda: now, max_quote_age_seconds=120)

    with pytest.raises(ManualPaperOrderRejected) as blocked:
        service.submit(client_order_id="bad-lot", symbol="600519", side="BUY", quantity=150)
    assert blocked.value.reason_code == "paper_manual_order_quantity_violates_lot"
    assert store.paper_account()["positions"] == []


def test_stale_quote_blocks_user_manual_order(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioStore(tmp_path / "manual-stale.db")
    store.save_paper_account(100_000)
    _save_cn_metadata(store, "600519")
    quote_time = datetime(2026, 8, 31, 10, 0, tzinfo=CN_TZ)
    now = datetime(2026, 8, 31, 10, 5, tzinfo=CN_TZ)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: now)
    _save_quote(store, symbol="600519", name="Moutai", price=10.0, observed_at=quote_time)
    service = ManualPaperOrderService(store, now_provider=lambda: now, max_quote_age_seconds=60)

    capability = service.capability("600519")
    assert capability["executable"] is False
    assert "paper_manual_order_quote_stale" in capability["reason_codes"]
    with pytest.raises(ManualPaperOrderRejected) as blocked:
        service.submit(client_order_id="stale-001", symbol="600519", side="BUY", quantity=100)
    assert blocked.value.reason_code == "paper_manual_order_quote_stale"


def test_hk_manual_order_is_explicitly_fail_closed_without_fee_currency_contract(
    tmp_path: Path, monkeypatch
) -> None:
    store = PortfolioStore(tmp_path / "manual-hk.db")
    store.save_paper_account(100_000)
    store.save_instrument_metadata(
        {
            "symbol": "01810",
            "market": "HK",
            "currency": "HKD",
            "lot_size": 200,
            "price_tick": "0.02",
            "source": "test",
            "as_of": "2026-08-31",
        }
    )
    now = datetime(2026, 8, 31, 10, 0, tzinfo=CN_TZ)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: now)
    _save_quote(
        store,
        symbol="01810",
        name="Xiaomi",
        price=36.0,
        observed_at=now,
        currency="HKD",
    )
    service = ManualPaperOrderService(store, now_provider=lambda: now, max_quote_age_seconds=120)

    capability = service.capability("01810")
    assert capability["market"] == "HK"
    assert capability["currency"] == "HKD"
    assert capability["lot_size"] == 200
    assert capability["executable"] is False
    assert "paper_hk_execution_not_configured" in capability["reason_codes"]

    with pytest.raises(ManualPaperOrderRejected) as blocked:
        service.submit(client_order_id="hk-001", symbol="01810", side="BUY", quantity=200)
    assert blocked.value.reason_code == "paper_hk_execution_not_configured"
    assert store.paper_account()["positions"] == []
    with store._connect() as connection:
        assert connection.execute("SELECT COUNT(*) AS count FROM paper_trading_logs").fetchone()["count"] == 0
