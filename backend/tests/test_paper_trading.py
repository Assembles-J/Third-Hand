from pathlib import Path
from uuid import uuid4

import pytest

from app.storage import PortfolioStore


def test_paper_ledger_moves_cash_and_blocks_duplicate_decision(tmp_path: Path) -> None:
    store = PortfolioStore(tmp_path / "paper.db")
    store.save_paper_account(1_000)
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


def test_paper_ledger_rejects_cash_and_position_overruns(tmp_path: Path) -> None:
    store = PortfolioStore(tmp_path / "paper.db")
    store.save_paper_account(100)
    with pytest.raises(ValueError, match="insufficient_paper_cash"):
        store.execute_paper_trade(trade_id=str(uuid4()), symbol="000001", name="平安", side="BUY", quantity=100, price=2, decision_id=None, reason="test")
    with pytest.raises(ValueError, match="insufficient_paper_position"):
        store.execute_paper_trade(trade_id=str(uuid4()), symbol="000001", name="平安", side="SELL", quantity=1, price=2, decision_id=None, reason="test")
    with pytest.raises(ValueError, match="100_share_lot"):
        store.execute_paper_trade(trade_id=str(uuid4()), symbol="000001", name="平安", side="BUY", quantity=101, price=1, decision_id=None, reason="test")


def test_paper_interval_is_persisted_and_has_a_safe_minimum(tmp_path: Path) -> None:
    store = PortfolioStore(tmp_path / "paper.db")
    assert store.system_settings()["paper_trading_interval_seconds"] == 3600
    store.save_system_settings({"paper_trading_enabled": True, "paper_trading_interval_seconds": 1200, "update_check_enabled": True})
    assert store.system_settings()["paper_trading_interval_seconds"] == 1200
