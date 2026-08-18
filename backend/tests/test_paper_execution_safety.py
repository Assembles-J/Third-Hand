from datetime import datetime, timedelta, timezone
from pathlib import Path

import app.storage as storage_module
from app.storage import PortfolioStore


BEIJING = timezone(timedelta(hours=8))


def test_account_projects_next_day_sellability_without_a_sell_attempt(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioStore(tmp_path / "paper-t1-display.db")
    store.save_paper_account(10_000)
    day_one = datetime(2026, 8, 17, 10, 0, tzinfo=BEIJING)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_one)
    store.execute_paper_trade(
        trade_id="display-buy", symbol="600000", name="test", side="BUY",
        quantity=100, price=10, decision_id="display-buy", reason="display seed",
    )
    today = store.paper_account()["positions"][0]
    assert today["sellable_quantity"] == 0
    assert today["locked_quantity"] == 100
    assert today["next_eligible_sell_at"] is not None

    day_two = datetime(2026, 8, 18, 10, 0, tzinfo=BEIJING)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_two)
    tomorrow = store.paper_account()["positions"][0]
    assert tomorrow["sellable_quantity"] == 100
    assert tomorrow["locked_quantity"] == 0
    # Reading the account projection must not need an attempted SELL to update
    # the stored lot state.
    assert store.paper_position_lots("600000")[0]["settlement_state"] == "SETTLED"


def test_t1_deferral_is_idempotent_and_newer_decision_supersedes_active_intent(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioStore(tmp_path / "paper-t1-deferral.db")
    now = datetime(2026, 8, 17, 10, 0, tzinfo=BEIJING)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: now)
    first = store.defer_paper_execution(
        decision_id="first", symbol="600000", action="REDUCE", requested_quantity=100,
        max_executable_quantity=0, reason_code="paper_t1_unsellable_quantity",
        next_eligible_at="2026-08-18T09:30:00+08:00",
    )
    second = store.defer_paper_execution(
        decision_id="second", symbol="600000", action="REDUCE", requested_quantity=100,
        max_executable_quantity=0, reason_code="paper_t1_unsellable_quantity",
        next_eligible_at="2026-08-18T09:30:00+08:00",
    )
    assert first["decision_id"] == "first"
    assert second["decision_id"] == "second"
    assert len(store.paper_execution_deferrals(symbol="600000", state="active")) == 1
    assert store.paper_execution_deferrals(symbol="600000", state="superseded")[0]["decision_id"] == "first"

    repeated = store.defer_paper_execution(
        decision_id="second", symbol="600000", action="REDUCE", requested_quantity=100,
        max_executable_quantity=0, reason_code="paper_t1_unsellable_quantity",
        next_eligible_at="2026-08-18T09:30:00+08:00",
    )
    assert repeated["decision_id"] == "second"

    next_day = datetime(2026, 8, 18, 10, 0, tzinfo=BEIJING)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: next_day)
    assert store.supersede_due_paper_execution_deferrals("600000") == 1
    assert store.paper_execution_deferrals(symbol="600000", state="active") == []
    assert {item["decision_id"] for item in store.paper_execution_deferrals(symbol="600000", state="superseded")} == {"first", "second"}
