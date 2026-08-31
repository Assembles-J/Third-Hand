from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import app.paper_legacy_lot_recovery as recovery_module
import app.storage as storage_module
from app.paper_legacy_lot_recovery import reconcile_missing_position_lots
from app.storage import PortfolioStore


CN_TZ = timezone(timedelta(hours=8))


def _delete_lots(store: PortfolioStore, symbol: str) -> None:
    with store._connect() as connection:
        connection.execute("DELETE FROM paper_position_lots WHERE symbol=?", (symbol,))


def test_legacy_cn_position_is_recovered_before_later_sellability_projection(
    tmp_path: Path, monkeypatch
) -> None:
    store = PortfolioStore(tmp_path / "legacy-cn.db")
    store.save_paper_account(100_000)

    bought_at = datetime(2026, 8, 18, 10, 13, tzinfo=CN_TZ)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: bought_at)
    store.execute_paper_trade(
        trade_id=str(uuid4()),
        symbol="002174",
        name="test",
        side="BUY",
        quantity=900,
        price=13.56,
        decision_id="legacy-buy",
        reason="legacy fixture",
    )
    _delete_lots(store, "002174")

    later = datetime(2026, 8, 31, 15, 20, tzinfo=CN_TZ)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: later)
    monkeypatch.setattr(recovery_module, "beijing_now", lambda: later)

    outcome = reconcile_missing_position_lots(store)

    assert outcome == {"recovered": ("002174",), "failed": ()}
    position = next(p for p in store.paper_account()["positions"] if p["symbol"] == "002174")
    assert position["quantity"] == 900
    assert position["sellable_quantity"] == 900
    assert position["locked_quantity"] == 0
    assert position["next_eligible_sell_at"] is None

    lots = store.paper_position_lots("002174")
    assert len(lots) == 1
    assert lots[0]["acquired_at"] == bought_at.isoformat()
    assert lots[0]["quantity"] == 900
    assert lots[0]["sellable_quantity"] == 900
    assert lots[0]["settlement_state"] == "SETTLED"

    # Repeated recovery/read is idempotent and cannot duplicate FIFO lots.
    assert reconcile_missing_position_lots(store) == {"recovered": (), "failed": ()}
    assert len(store.paper_position_lots("002174")) == 1


def test_legacy_recovery_refuses_to_invent_inventory_when_ledger_mismatches(
    tmp_path: Path, monkeypatch
) -> None:
    store = PortfolioStore(tmp_path / "legacy-mismatch.db")
    store.save_paper_account(100_000)

    bought_at = datetime(2026, 8, 18, 10, tzinfo=CN_TZ)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: bought_at)
    store.execute_paper_trade(
        trade_id=str(uuid4()),
        symbol="000620",
        name="test",
        side="BUY",
        quantity=100,
        price=3.41,
        decision_id="legacy-buy-mismatch",
        reason="legacy fixture",
    )
    _delete_lots(store, "000620")
    with store._connect() as connection:
        connection.execute(
            "UPDATE paper_trading_positions SET quantity=200 WHERE symbol='000620'"
        )

    later = datetime(2026, 8, 31, 15, 20, tzinfo=CN_TZ)
    monkeypatch.setattr(recovery_module, "beijing_now", lambda: later)

    outcome = reconcile_missing_position_lots(store)

    assert outcome == {"recovered": (), "failed": ("000620",)}
    assert store.paper_position_lots("000620") == []


def test_legacy_hk_lot_recovery_does_not_apply_cn_t1_lock(
    tmp_path: Path, monkeypatch
) -> None:
    store = PortfolioStore(tmp_path / "legacy-hk.db")
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

    acquired_at = datetime(2026, 8, 31, 10, 0, tzinfo=CN_TZ).isoformat()
    with store._connect() as connection:
        connection.execute(
            "INSERT INTO paper_trading_positions (symbol,name,quantity,average_cost,updated_at) "
            "VALUES (?,?,?,?,?)",
            ("01810", "Xiaomi", 200.0, 36.0, acquired_at),
        )
        connection.execute(
            "INSERT INTO paper_trading_logs "
            "(id,symbol,name,side,quantity,price,fee,cash_before,cash_after,decision_id,reason,status,executed_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-hk-buy",
                "01810",
                "Xiaomi",
                "BUY",
                200.0,
                36.0,
                0.0,
                100_000.0,
                100_000.0,
                None,
                "legacy read-only fixture",
                "executed",
                acquired_at,
            ),
        )

    same_day = datetime(2026, 8, 31, 15, 0, tzinfo=CN_TZ)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: same_day)
    monkeypatch.setattr(recovery_module, "beijing_now", lambda: same_day)

    outcome = reconcile_missing_position_lots(store)

    assert outcome == {"recovered": ("01810",), "failed": ()}
    lot = store.paper_position_lots("01810")[0]
    assert lot["market"] == "HK"
    assert lot["currency"] == "HKD"
    assert lot["settlement_state"] == "SETTLED"
    assert lot["sellable_quantity"] == 200

    position = next(p for p in store.paper_account()["positions"] if p["symbol"] == "01810")
    assert position["sellable_quantity"] == 200
    assert position["locked_quantity"] == 0
