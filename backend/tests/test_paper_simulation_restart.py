from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from app import decision_config as config
from app.application_services.paper.simulation_schema import ensure_paper_simulation_epoch_schema
from app.application_services.paper.simulation_session import (
    PaperRuntimeStateService,
    PaperSimulationRestartRejected,
    PaperSimulationService,
)
from app.paper_runtime import pending_current_version_decision_symbols
from app.storage import PortfolioStore


CN_TZ = timezone(timedelta(hours=8))


def _formal_report(*, policy_version: str, generated_at: datetime, action: str = "BUY") -> dict[str, object]:
    return {
        "policy_version": policy_version,
        "candidate_selection_version": config.CANDIDATE_SELECTION_VERSION,
        "audit_versions": {"execution_policy_version": config.EXECUTION_POLICY_VERSION},
        "formal_action": action,
        "generated_at": generated_at.isoformat(),
        "decision_memory": {"review_after": (generated_at + timedelta(minutes=5)).isoformat()},
    }


def _insert_decision(store: PortfolioStore, *, decision_id: str, symbol: str, report: dict[str, object], created_at: datetime) -> None:
    with store._connect() as connection:
        connection.execute(
            "INSERT INTO decision_reports (decision_id,context_id,symbol,input_hash,payload,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                decision_id,
                f"context-{decision_id}",
                symbol,
                f"hash-{decision_id}",
                json.dumps(report, ensure_ascii=False),
                created_at.isoformat(),
            ),
        )


def _set_active_epoch_start(store: PortfolioStore, started_at: datetime) -> None:
    with store._connect() as connection:
        connection.execute(
            "UPDATE paper_simulation_epochs SET started_at=? WHERE status='active'",
            (started_at.isoformat(),),
        )


def test_restart_archives_active_state_without_deleting_trade_history(tmp_path: Path) -> None:
    store = PortfolioStore(tmp_path / "restart.db")
    store.save_paper_account(100_000)
    ensure_paper_simulation_epoch_schema(store)
    epoch_start = datetime(2026, 9, 2, 9, 0, tzinfo=CN_TZ)
    before = datetime(2026, 9, 2, 9, 31, tzinfo=CN_TZ)
    restart_at = datetime(2026, 9, 2, 12, 0, tzinfo=CN_TZ)
    _set_active_epoch_start(store, epoch_start)

    with store._connect() as connection:
        connection.execute(
            "UPDATE account_cash SET available_cash=99000,updated_at=? WHERE account_id='default'",
            (before.isoformat(),),
        )
        connection.execute(
            "INSERT INTO paper_trading_positions (symbol,name,quantity,average_cost,updated_at) VALUES (?,?,?,?,?)",
            ("600000", "浦发银行", 100.0, 10.0, before.isoformat()),
        )
        connection.execute(
            "INSERT INTO paper_position_lots "
            "(lot_id,symbol,market,currency,quantity,acquired_at,cost_basis,sellable_quantity,settlement_state,updated_at,sellable_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "lot-old",
                "600000",
                "CN",
                "CNY",
                100.0,
                before.isoformat(),
                10.0,
                0.0,
                "PENDING_T1",
                before.isoformat(),
                (before + timedelta(days=1)).isoformat(),
            ),
        )
        connection.execute(
            "INSERT INTO paper_trading_logs "
            "(id,symbol,name,side,quantity,price,fee,cash_before,cash_after,decision_id,reason,status,executed_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "old-fill",
                "600000",
                "浦发银行",
                "BUY",
                100.0,
                10.0,
                0.0,
                100000.0,
                99000.0,
                "old-decision",
                "test",
                "executed",
                before.isoformat(),
            ),
        )
        connection.execute(
            "INSERT INTO paper_trading_equity_snapshots "
            "(total_equity,available_cash,market_value,total_pnl,recorded_at) VALUES (?,?,?,?,?)",
            (100000.0, 99000.0, 1000.0, 0.0, before.isoformat()),
        )
        connection.execute(
            "INSERT INTO paper_execution_deferrals "
            "(decision_id,symbol,action,requested_quantity,max_executable_quantity,reason_code,next_eligible_at,state,created_at,resolved_at,detail) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "deferred-old",
                "600000",
                "EXIT",
                100.0,
                0.0,
                "paper_t1_unsellable_quantity",
                (before + timedelta(days=1)).isoformat(),
                "active",
                before.isoformat(),
                None,
                "{}",
            ),
        )

    callbacks: list[str] = []
    service = PaperSimulationService(
        store,
        now_provider=lambda: restart_at,
        on_restart=lambda: callbacks.append("reset"),
    )
    result = service.restart(initial_cash=50_000, client_restart_id="android-restart-1")

    assert result["status"] == "restarted"
    assert result["idempotent_replay"] is False
    assert result["epoch"]["sequence"] == 2
    assert result["account"]["positions"] == []
    assert result["account"]["available_cash"] == 50_000
    assert result["account"]["total_equity"] == 50_000
    assert result["account"]["initial_cash"] == 50_000
    assert result["account"]["total_pnl"] == 0
    assert callbacks == ["reset"]

    with store._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM paper_trading_logs WHERE id='old-fill'").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM paper_trading_logs WHERE side='SELL'").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM paper_trading_equity_snapshots").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM paper_trading_positions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM paper_position_lots WHERE quantity>0").fetchone()[0] == 0
        assert connection.execute(
            "SELECT state FROM paper_execution_deferrals WHERE decision_id='deferred-old'"
        ).fetchone()["state"] == "superseded"
        archived = connection.execute(
            "SELECT status,archive_payload FROM paper_simulation_epochs WHERE sequence=1"
        ).fetchone()
        assert archived["status"] == "archived"
        payload = json.loads(str(archived["archive_payload"]))
        assert payload["positions"][0]["symbol"] == "600000"
        assert payload["paper_log_count"] == 1
        flows = connection.execute(
            "SELECT amount,flow_type FROM paper_trading_cash_flows ORDER BY occurred_at,id"
        ).fetchall()
        assert len(flows) == 3
        assert {str(row["flow_type"]) for row in flows} == {"deposit", "epoch_rebase", "opening_balance"}
        assert sum(float(row["amount"]) for row in flows) == 50_000

    replay = service.restart(initial_cash=50_000, client_restart_id="android-restart-1")
    assert replay["idempotent_replay"] is True
    assert replay["epoch"]["sequence"] == 2
    assert callbacks == ["reset"]

    with pytest.raises(PaperSimulationRestartRejected, match="paper_restart_request_conflict"):
        service.restart(initial_cash=60_000, client_restart_id="android-restart-1")
    assert service.current_epoch()["sequence"] == 2
    assert store.paper_account()["available_cash"] == 50_000


def test_restart_epoch_blocks_old_frozen_decision_from_reentering_execution_queue(tmp_path: Path) -> None:
    store = PortfolioStore(tmp_path / "decision-boundary.db")
    store.save_paper_account(100_000)
    ensure_paper_simulation_epoch_schema(store)
    policy_version = "policy-test-v1"
    epoch_start = datetime(2026, 9, 2, 9, 0, tzinfo=CN_TZ)
    before = datetime(2026, 9, 2, 9, 31, tzinfo=CN_TZ)
    restart_at = datetime(2026, 9, 2, 12, 0, tzinfo=CN_TZ)
    _set_active_epoch_start(store, epoch_start)
    old_report = _formal_report(policy_version=policy_version, generated_at=before, action="BUY")
    _insert_decision(
        store,
        decision_id="old-buy",
        symbol="600000",
        report=old_report,
        created_at=before,
    )

    assert pending_current_version_decision_symbols(store, policy_version=policy_version) == ("600000",)

    service = PaperSimulationService(store, now_provider=lambda: restart_at)
    service.restart(initial_cash=100_000, client_restart_id="restart-decision-boundary")

    assert pending_current_version_decision_symbols(store, policy_version=policy_version) == ()

    fresh_at = restart_at + timedelta(minutes=1)
    fresh_report = _formal_report(policy_version=policy_version, generated_at=fresh_at, action="BUY")
    _insert_decision(
        store,
        decision_id="fresh-buy",
        symbol="600000",
        report=fresh_report,
        created_at=fresh_at,
    )
    assert pending_current_version_decision_symbols(store, policy_version=policy_version) == ("600000",)


def test_runtime_state_explains_no_trade_instead_of_looking_dead(tmp_path: Path) -> None:
    store = PortfolioStore(tmp_path / "runtime-state.db")
    store.save_paper_account(100_000)
    ensure_paper_simulation_epoch_schema(store)
    settings = store.system_settings()
    store.save_system_settings({**settings, "paper_trading_enabled": True})
    service = PaperSimulationService(store)
    now = datetime(2026, 9, 2, 10, 15, tzinfo=CN_TZ)
    _set_active_epoch_start(store, datetime(2026, 9, 2, 9, 0, tzinfo=CN_TZ))
    with store._connect() as connection:
        connection.execute(
            "INSERT INTO simulation_runs "
            "(run_id,trigger,started_at,finished_at,status,symbol_count,generated,executed,skipped,message) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                "no-trade-run",
                "scheduler",
                now.isoformat(),
                now.isoformat(),
                "completed",
                3,
                3,
                0,
                0,
                "本轮 formal actions 均为 HOLD / WAIT，没有新的 BUY/SELL。",
            ),
        )

    runtime = PaperRuntimeStateService(
        store,
        service,
        schedule_state=lambda: {
            "mode": "DISCOVERY",
            "pending_symbols": [],
            "due_review_symbols": [],
            "candidate_scan_enabled": True,
            "seconds_until_candidate_scan": 300,
            "seconds_until_company_research": 1200,
        },
        runtime_snapshot=lambda: {
            "paper_state": {
                "running": False,
                "last_finished_at": now.isoformat(),
                "last_message": "本轮完成",
            },
            "market_refresh_state": {"last_success_at": now.isoformat()},
            "seconds_until_review": 240,
        },
    ).state()

    assert runtime["runtime_status"] == "monitoring"
    assert runtime["mode_label"] == "空仓找机会"
    assert runtime["pending_execution_count"] == 0
    assert "HOLD / WAIT" in runtime["no_trade_reason"]
    assert runtime["seconds_until_candidate_scan"] == 300
    assert runtime["last_market_refresh_at"] == now.isoformat()
