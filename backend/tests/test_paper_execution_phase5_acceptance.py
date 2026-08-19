"""Phase 5 paper-execution acceptance matrix.

These tests exercise the persisted ledger/precheck contracts that the deployed
paper runtime composes.  They intentionally use isolated SQLite state and never
call remote providers or production accounts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import app.storage as storage_module
from app import decision_config as config
from app.execution_precheck import precheck_fill
from app.storage import PortfolioStore


BEIJING = timezone(timedelta(hours=8))


class AlwaysOpenCalendar:
    def is_symbol_market_open(self, _symbol, *, moment):
        return True


def _report(*, action: str, generated_at: str, market_as_of: str, decision_id: str = "decision") -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "action": action,
        "formal_action": action,
        "market_as_of": market_as_of,
        "generated_at": generated_at,
        "data_quality": {
            "action_gates": [
                {"action": "OPEN", "permission": "allowed"},
                {"action": "ADD", "permission": "allowed"},
                {"action": "REDUCE", "permission": "allowed"},
                {"action": "EXIT", "permission": "allowed"},
            ]
        },
        "audit_versions": {"execution_policy_version": config.EXECUTION_POLICY_VERSION},
    }


def _quote(*, observed_at: str, price: float = 10.0) -> dict[str, object]:
    return {
        "price": price,
        "as_of": observed_at,
        "retrieved_at": observed_at,
        "source": "phase5-fixture",
    }


def _seed_cn_instrument(store: PortfolioStore, symbol: str = "600000") -> None:
    store.save_instrument_metadata({
        "symbol": symbol,
        "market": "CN",
        "currency": "CNY",
        "lot_size": 100,
        "price_tick": "0.01",
        "source": "phase5-fixture",
        "as_of": "2026-08-19",
    })


def test_same_day_buy_exit_creates_one_durable_t1_deferral_without_sell_fill(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioStore(tmp_path / "same-day-buy-exit.db")
    store.save_paper_account(20_000)
    _seed_cn_instrument(store)
    now = datetime(2026, 8, 19, 10, 0, tzinfo=BEIJING)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: now)

    store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600000", name="fixture", side="BUY",
        quantity=100, price=10, decision_id="buy-decision", reason="phase5 buy",
    )
    position = store.paper_account()["positions"][0]
    assert position["quantity"] == 100
    assert position["sellable_quantity"] == 0
    assert position["locked_quantity"] == 100
    assert position["next_eligible_sell_at"] is not None

    first = store.defer_paper_execution(
        decision_id="exit-decision", symbol="600000", action="EXIT",
        requested_quantity=100, max_executable_quantity=0,
        reason_code="paper_t1_unsellable_quantity",
        next_eligible_at=position["next_eligible_sell_at"],
    )
    second = store.defer_paper_execution(
        decision_id="exit-decision", symbol="600000", action="EXIT",
        requested_quantity=100, max_executable_quantity=0,
        reason_code="paper_t1_unsellable_quantity",
        next_eligible_at=position["next_eligible_sell_at"],
    )

    assert first["deferral_id"] == second["deferral_id"]
    active = store.paper_execution_deferrals(symbol="600000", state="active")
    assert len(active) == 1
    assert active[0]["decision_id"] == "exit-decision"
    assert active[0]["requested_quantity"] == 100
    assert active[0]["max_executable_quantity"] == 0
    # BUY is the only executed ledger row. No zero-quantity or same-day SELL
    # is manufactured merely because the formal position decision wants EXIT.
    executed = [item for item in store.paper_logs(limit=20) if item["status"] == "executed"]
    assert [(item["side"], item["quantity"]) for item in executed] == [("BUY", 100.0)]


def test_mixed_settled_and_same_day_inventory_exposes_partial_sellability_and_fifo(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioStore(tmp_path / "mixed-lots.db")
    store.save_paper_account(40_000)
    _seed_cn_instrument(store)

    day_one = datetime(2026, 8, 18, 10, 0, tzinfo=BEIJING)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_one)
    store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600000", name="fixture", side="BUY",
        quantity=100, price=10, decision_id="old-buy", reason="settled lot seed",
    )

    day_two = datetime(2026, 8, 19, 10, 0, tzinfo=BEIJING)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_two)
    # Reading the projection settles yesterday's lot before today's ADD.
    settled = store.paper_account()["positions"][0]
    assert settled["sellable_quantity"] == 100
    store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600000", name="fixture", side="BUY",
        quantity=100, price=11, decision_id="today-add", reason="locked lot seed",
    )

    mixed = store.paper_account()["positions"][0]
    assert mixed["quantity"] == 200
    assert mixed["sellable_quantity"] == 100
    assert mixed["locked_quantity"] == 100
    assert mixed["next_eligible_sell_at"] is not None

    # Runtime must cap EXIT/REDUCE before submitting to the ledger. Exercise the
    # same executable quantity against the real lot ledger and verify only the
    # settled FIFO lot is consumed.
    executable_quantity = min(200.0, float(mixed["sellable_quantity"]))
    store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600000", name="fixture", side="SELL",
        quantity=executable_quantity, price=12, decision_id="partial-exit",
        reason="phase5 partial exit",
    )
    after = store.paper_account()["positions"][0]
    assert after["quantity"] == 100
    assert after["sellable_quantity"] == 0
    assert after["locked_quantity"] == 100
    remaining_lots = store.paper_position_lots("600000")
    assert len(remaining_lots) == 1
    assert remaining_lots[0]["quantity"] == 100
    assert remaining_lots[0]["settlement_state"] == "PENDING_T1"


def test_next_session_requires_fresh_later_quote_instead_of_blindly_executing_old_deferral(tmp_path: Path, monkeypatch) -> None:
    store = PortfolioStore(tmp_path / "next-session-recheck.db")
    store.save_paper_account(20_000)
    _seed_cn_instrument(store)
    day_one = datetime(2026, 8, 18, 10, 0, tzinfo=BEIJING)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_one)
    store.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600000", name="fixture", side="BUY",
        quantity=100, price=10, decision_id="buy", reason="seed",
    )
    position = store.paper_account()["positions"][0]
    store.defer_paper_execution(
        decision_id="old-exit", symbol="600000", action="EXIT",
        requested_quantity=100, max_executable_quantity=0,
        reason_code="paper_t1_unsellable_quantity",
        next_eligible_at=position["next_eligible_sell_at"],
    )

    day_two = datetime(2026, 8, 19, 10, 20, tzinfo=BEIJING)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: day_two)
    refreshed = store.paper_account()["positions"][0]
    assert refreshed["sellable_quantity"] == 100
    assert store.supersede_due_paper_execution_deferrals("600000", now=day_two) == 1
    assert store.paper_execution_deferrals(symbol="600000", state="active") == []

    fresh_report = _report(
        action="EXIT",
        generated_at="2026-08-19T10:10:00+08:00",
        market_as_of="2026-08-19T10:10:00+08:00",
        decision_id="fresh-exit",
    )
    same_observation = precheck_fill(
        fresh_report,
        _quote(observed_at="2026-08-19T10:10:00+08:00"),
        symbol="600000", now=day_two, calendar=AlwaysOpenCalendar(),
        max_quote_age_seconds=config.EXECUTION_QUOTE_MAX_AGE_SECONDS,
    )
    stale_observation = precheck_fill(
        fresh_report,
        _quote(observed_at="2026-08-19T09:50:00+08:00"),
        symbol="600000", now=day_two, calendar=AlwaysOpenCalendar(),
        max_quote_age_seconds=900,
    )
    later_fresh = precheck_fill(
        fresh_report,
        _quote(observed_at="2026-08-19T10:15:00+08:00"),
        symbol="600000", now=day_two, calendar=AlwaysOpenCalendar(),
        max_quote_age_seconds=config.EXECUTION_QUOTE_MAX_AGE_SECONDS,
    )

    assert same_observation.allowed is False
    assert same_observation.reason == "execution_not_due_later_quote"
    assert stale_observation.allowed is False
    assert later_fresh.allowed is True


def test_restart_rebuilds_lot_deferral_and_paper_enable_state_from_sqlite(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "restart.db"
    first = PortfolioStore(database)
    first.save_paper_account(20_000)
    first.save_system_settings({"paper_trading_enabled": True})
    _seed_cn_instrument(first)
    now = datetime(2026, 8, 19, 10, 0, tzinfo=BEIJING)
    monkeypatch.setattr(storage_module, "beijing_now", lambda: now)
    first.execute_paper_trade(
        trade_id=str(uuid4()), symbol="600000", name="fixture", side="BUY",
        quantity=100, price=10, decision_id="buy", reason="restart seed",
    )
    position = first.paper_account()["positions"][0]
    first.defer_paper_execution(
        decision_id="exit", symbol="600000", action="EXIT",
        requested_quantity=100, max_executable_quantity=0,
        reason_code="paper_t1_unsellable_quantity",
        next_eligible_at=position["next_eligible_sell_at"],
        detail={"locked_quantity": position["locked_quantity"]},
    )

    # New store instance represents a process/container restart. No in-memory
    # paper-runtime state is reused.
    restarted = PortfolioStore(database)
    account = restarted.paper_account()
    assert restarted.system_settings()["paper_trading_enabled"] is True
    assert account["positions"][0]["quantity"] == 100
    assert account["positions"][0]["sellable_quantity"] == 0
    assert account["positions"][0]["locked_quantity"] == 100
    active = restarted.paper_execution_deferrals(symbol="600000", state="active")
    assert len(active) == 1
    assert active[0]["decision_id"] == "exit"
    assert active[0]["next_eligible_at"] == position["next_eligible_sell_at"]
