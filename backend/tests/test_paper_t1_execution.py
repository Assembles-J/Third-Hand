from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

import app.storage as storage_module
from app.storage import PortfolioStore


BEIJING = timezone(timedelta(hours=8))


def test_t1_blocks_only_today_buy_quantity_in_mixed_inventory(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioStore(tmp_path / "paper-t1-mixed.db")
    store.save_paper_account(10_000)

    day_one = datetime(2026, 8, 17, 10, 0, tzinfo=BEIJING)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_one)
    store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600000", name="浦发银行", side="BUY",
        quantity=100, price=10, decision_id="day-one-buy", reason="seed old inventory",
    )

    day_two = datetime(2026, 8, 18, 10, 0, tzinfo=BEIJING)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_two)
    store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600000", name="浦发银行", side="BUY",
        quantity=100, price=10, decision_id="day-two-buy", reason="today buy",
    )

    # The 100 shares carried from the prior trading day remain sellable.
    sale = store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600000", name="浦发银行", side="SELL",
        quantity=100, price=11, decision_id="sell-old-lot", reason="sell old inventory",
    )
    assert sale["quantity"] == 100
    assert store.paper_account()["positions"][0]["quantity"] == 100

    # The remaining 100 shares were bought today and are T+1 locked.
    with pytest.raises(ValueError, match="paper_t1_unsellable_quantity"):
        store.execute_paper_trade(
            trade_id=str(uuid4()), symbol="600000", name="浦发银行", side="SELL",
            quantity=100, price=11, decision_id="sell-today-lot", reason="must be blocked",
        )
