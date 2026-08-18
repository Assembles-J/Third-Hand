from pathlib import Path
import sqlite3
from datetime import datetime, timezone, timedelta
from threading import Event, Thread
import time
from uuid import uuid4

import pytest

import app.storage as storage_module
from app.storage import PortfolioStore


def test_paper_ledger_moves_cash_and_blocks_duplicate_decision(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioStore(tmp_path / "paper.db")
    store.save_paper_account(1_000)
    day_one = datetime(2026, 8, 12, 10, tzinfo=timezone(timedelta(hours=8)))
    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_one)
    buy = store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600519", name="茅台", side="BUY", quantity=100,
        price=8, decision_id="decision-1", reason="test",
    )
    assert buy["fee"] == 5
    assert buy["cash_after"] == 195
    account_after_buy = store.paper_account()
    assert account_after_buy["positions"][0]["quantity"] == 100
    assert account_after_buy["positions"][0]["average_cost"] == 8.05
    with pytest.raises(ValueError, match="already_executed"):
        store.execute_paper_trade(
            trade_id=str(uuid4()), symbol="600519", name="茅台", side="BUY", quantity=100,
            price=8, decision_id="decision-1", reason="duplicate",
        )
    with pytest.raises(ValueError, match="t1_unsellable"):
        store.execute_paper_trade(
            trade_id=str(uuid4()), symbol="600519", name="茅台", side="SELL", quantity=100,
            price=10, decision_id="decision-t1", reason="same-day sale",
        )
    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_one.replace(day=13))
    sale = store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600519", name="茅台", side="SELL", quantity=100,
        price=10, decision_id="decision-2", reason="test",
    )
    assert sale["fee"] == 6
    assert sale["cash_after"] == 1_189
    assert store.paper_account()["positions"] == []
    snapshot = store.record_paper_equity_snapshot()
    assert snapshot["total_equity"] == 1_189
    assert store.paper_equity_snapshots()[-1]["total_pnl"] == 189


def test_manual_cash_adjustment_is_external_flow_not_trading_profit(tmp_path: Path) -> None:
    store = PortfolioStore(tmp_path / "cash-flow.db")
    store.save_available_cash(10_000)
    store.save_available_cash(60_000)

    account = store.paper_account()

    assert account["net_contributions"] == 60_000
    assert account["total_pnl"] == 0
    assert account["total_return_percent"] == 0


def test_paper_ledger_rejects_cash_and_position_overruns(tmp_path: Path) -> None:
    store = PortfolioStore(tmp_path / "paper.db")
    store.save_paper_account(100)
    with pytest.raises(ValueError, match="insufficient_paper_cash"):
        store.execute_paper_trade(trade_id=str(uuid4()), symbol="000001", name="平安", side="BUY", quantity=100, price=2, decision_id=None, reason="test")
    with pytest.raises(ValueError, match="paper_t1_unsellable_quantity"):
        store.execute_paper_trade(trade_id=str(uuid4()), symbol="000001", name="平安", side="SELL", quantity=1, price=2, decision_id=None, reason="test")
    with pytest.raises(ValueError, match="market_lot"):
        store.execute_paper_trade(trade_id=str(uuid4()), symbol="000001", name="平安", side="BUY", quantity=101, price=1, decision_id=None, reason="test")


def test_non_cn_paper_trade_never_inherits_cn_lot_or_fee_rules(tmp_path: Path) -> None:
    store = PortfolioStore(tmp_path / "hk-paper-rules.db")
    store.save_paper_account(10_000)
    store.save_instrument_metadata({
        "symbol": "01810", "market": "HK", "currency": "HKD", "lot_size": 200,
        "price_tick": "0.02", "source": "test", "as_of": "2026-08-17",
    })

    with pytest.raises(ValueError, match="fee_schedule_unconfigured"):
        store.execute_paper_trade(
            trade_id=str(uuid4()), symbol="01810", name="Xiaomi", side="BUY", quantity=200,
            price=20, decision_id="hk-buy", reason="must not use CN paper fees",
        )


def test_paper_interval_is_persisted_and_has_a_safe_minimum(tmp_path: Path) -> None:
    store = PortfolioStore(tmp_path / "paper.db")
    assert store.system_settings()["paper_trading_interval_seconds"] == 600
    store.save_system_settings({"paper_trading_enabled": True, "paper_trading_interval_seconds": 1200, "update_check_enabled": True})
    assert store.system_settings()["paper_trading_interval_seconds"] == 1200


def test_paper_fill_keeps_quote_time_source_and_price_semantics(tmp_path: Path) -> None:
    store = PortfolioStore(tmp_path / "paper-audit.db")
    store.save_paper_account(10_000)
    store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600519", name="茅台", side="BUY", quantity=100, price=10,
        decision_id="decision-audit", reason="test", execution_quote_at="2026-08-14T09:31:00+08:00",
        execution_quote_source="test_provider", fill_price_mode="NEXT_ELIGIBLE_OBSERVED_QUOTE",
    )

    log = store.paper_logs(limit=1)[0]
    assert log["execution_quote_at"] == "2026-08-14T09:31:00+08:00"
    assert log["execution_quote_source"] == "test_provider"
    assert log["fill_price_mode"] == "NEXT_ELIGIBLE_OBSERVED_QUOTE"


def test_paper_position_episode_survives_add_and_closes_with_position(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioStore(tmp_path / "episode.db")
    store.save_paper_account(10_000)
    day_one = datetime(2026, 8, 12, 10, tzinfo=timezone(timedelta(hours=8)))
    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_one)
    entry = {
        "episode_id": "episode-entry-1",
        "evidence_snapshot_hash": "atomic-hash",
        "research_assessment_hash": "research-hash",
        "risk_state": {"risk_level": "high"},
        "technical_state": {"technical_state": ["up", "bullish", "neutral"]},
        "market_regime": {"market_regime": ["ready", "risk_on"]},
        "event_state": {"event_state": []},
    }
    store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600519", name="Moutai", side="BUY", quantity=100,
        price=10, decision_id="entry-decision", reason="entry", entry_snapshot=entry,
    )
    store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600519", name="Moutai", side="BUY", quantity=100,
        price=11, decision_id="add-decision", reason="add", entry_snapshot={"episode_id": "must-not-replace"},
    )
    position = store.paper_account()["positions"][0]
    assert position["entry_episode_id"] == "episode-entry-1"
    assert position["entry_decision_id"] == "entry-decision"
    assert position["entry_evidence_snapshot_hash"] == "atomic-hash"
    assert position["entry_risk_state"] == {"risk_level": "high"}

    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_one.replace(day=13))
    store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600519", name="Moutai", side="SELL", quantity=200,
        price=10, decision_id="exit-decision", reason="exit",
    )
    assert store.paper_account()["positions"] == []
    with store._connect() as connection:
        closed_at = connection.execute(
            "SELECT closed_at FROM paper_position_episodes WHERE episode_id='episode-entry-1'"
        ).fetchone()["closed_at"]
    assert closed_at is not None


def test_system_settings_waits_for_a_brief_concurrent_writer(tmp_path: Path) -> None:
    store = PortfolioStore(tmp_path / "locked-settings.db")
    lock_acquired = Event()

    def hold_lock() -> None:
        blocker = sqlite3.connect(store.database_path)
        blocker.execute("BEGIN IMMEDIATE")
        lock_acquired.set()
        time.sleep(0.05)
        blocker.commit()
        blocker.close()

    release_thread = Thread(target=hold_lock)
    release_thread.start()
    assert lock_acquired.wait(timeout=1)
    saved = store.save_system_settings({"update_check_enabled": False})
    release_thread.join()

    assert saved["update_check_enabled"] is False
