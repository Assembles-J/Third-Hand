"""Paper-simulation restart epochs and runtime observability.

The active simulated account is mutable state, while fills, decisions and run audit
are historical evidence.  A restart therefore archives the active state and opens
an empty epoch instead of deleting historical rows or fabricating SELL trades.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from uuid import uuid4

from app.time_utils import beijing_now


class PaperSimulationRestartRejected(ValueError):
    """Raised when a restart request cannot be applied safely."""


@dataclass(frozen=True)
class PaperSimulationEpoch:
    epoch_id: str
    sequence: int
    status: str
    started_at: str
    ended_at: str | None
    initial_cash: float
    end_total_equity: float | None
    end_cash: float | None
    end_market_value: float | None
    restart_request_id: str | None

    @classmethod
    def from_row(cls, row) -> "PaperSimulationEpoch":
        return cls(
            epoch_id=str(row["epoch_id"]),
            sequence=int(row["sequence"]),
            status=str(row["status"]),
            started_at=str(row["started_at"]),
            ended_at=str(row["ended_at"]) if row["ended_at"] else None,
            initial_cash=float(row["initial_cash"]),
            end_total_equity=float(row["end_total_equity"]) if row["end_total_equity"] is not None else None,
            end_cash=float(row["end_cash"]) if row["end_cash"] is not None else None,
            end_market_value=float(row["end_market_value"]) if row["end_market_value"] is not None else None,
            restart_request_id=str(row["restart_request_id"]) if row["restart_request_id"] else None,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "epoch_id": self.epoch_id,
            "sequence": self.sequence,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "initial_cash": self.initial_cash,
            "end_total_equity": self.end_total_equity,
            "end_cash": self.end_cash,
            "end_market_value": self.end_market_value,
            "restart_request_id": self.restart_request_id,
        }


class PaperSimulationService:
    def __init__(
        self,
        store,
        *,
        on_restart: Callable[[], None] | None = None,
        now_provider: Callable[[], datetime] = beijing_now,
    ) -> None:
        self.store = store
        self.on_restart = on_restart or (lambda: None)
        self.now_provider = now_provider

    def current_epoch(self) -> dict[str, object]:
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT * FROM paper_simulation_epochs WHERE status='active' "
                "ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
        if row is None:
            raise PaperSimulationRestartRejected("paper_simulation_epoch_missing")
        return PaperSimulationEpoch.from_row(row).as_dict()

    def epochs(self, limit: int = 20) -> list[dict[str, object]]:
        with self.store._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM paper_simulation_epochs ORDER BY sequence DESC LIMIT ?",
                (max(1, min(int(limit), 100)),),
            ).fetchall()
        return [PaperSimulationEpoch.from_row(row).as_dict() for row in rows]

    def restart(
        self,
        *,
        initial_cash: float,
        client_restart_id: str,
    ) -> dict[str, object]:
        initial_cash = float(initial_cash)
        request_id = str(client_restart_id).strip()
        if initial_cash <= 0:
            raise PaperSimulationRestartRejected("paper_restart_initial_cash_must_be_positive")
        if not request_id:
            raise PaperSimulationRestartRejected("paper_restart_client_id_required")

        # Idempotency is checked before any active-state mutation. A client id may
        # replay only the exact original request, just like the manual-order path.
        with self.store._connect() as connection:
            prior = connection.execute(
                "SELECT * FROM paper_simulation_epochs WHERE restart_request_id=?",
                (request_id,),
            ).fetchone()
        if prior is not None:
            epoch = PaperSimulationEpoch.from_row(prior)
            if abs(epoch.initial_cash - initial_cash) > 1e-9:
                raise PaperSimulationRestartRejected("paper_restart_request_conflict")
            if epoch.status != "active":
                raise PaperSimulationRestartRejected("paper_restart_request_already_archived")
            return {
                "status": "restarted",
                "idempotent_replay": True,
                "archived_epoch_id": None,
                "epoch": epoch.as_dict(),
                "account": self.store.paper_account(),
            }

        now = self.now_provider().isoformat()
        account_before = self.store.paper_account()
        run_id = f"paper-restart-{uuid4()}"
        new_epoch_id = f"paper-epoch-{uuid4()}"

        with self.store._connect() as connection:
            active = connection.execute(
                "SELECT * FROM paper_simulation_epochs WHERE status='active' "
                "ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            if active is None:
                raise PaperSimulationRestartRejected("paper_simulation_epoch_missing")

            current = PaperSimulationEpoch.from_row(active)
            sequence = current.sequence + 1
            positions = [dict(row) for row in connection.execute(
                "SELECT * FROM paper_trading_positions ORDER BY symbol"
            ).fetchall()]
            lots = [dict(row) for row in connection.execute(
                "SELECT * FROM paper_position_lots WHERE quantity > 0 ORDER BY symbol, acquired_at, lot_id"
            ).fetchall()]
            active_deferrals = [dict(row) for row in connection.execute(
                "SELECT * FROM paper_execution_deferrals WHERE state='active' ORDER BY created_at"
            ).fetchall()]
            epoch_cash_flows = [dict(row) for row in connection.execute(
                "SELECT * FROM paper_trading_cash_flows WHERE occurred_at>=? ORDER BY occurred_at, id",
                (current.started_at,),
            ).fetchall()]
            contribution_total = float(connection.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM paper_trading_cash_flows"
            ).fetchone()["total"])
            log_count = int(connection.execute(
                "SELECT COUNT(*) FROM paper_trading_logs WHERE executed_at>=?",
                (current.started_at,),
            ).fetchone()[0])
            run_count = int(connection.execute(
                "SELECT COUNT(*) FROM simulation_runs WHERE started_at>=?",
                (current.started_at,),
            ).fetchone()[0])

            archive_payload = json.dumps(
                {
                    "account": account_before,
                    "positions": positions,
                    "position_lots": lots,
                    "active_deferrals": active_deferrals,
                    "cash_flows": epoch_cash_flows,
                    "paper_log_count": log_count,
                    "simulation_run_count": run_count,
                    "archive_reason": "user_restart",
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )

            connection.execute(
                "UPDATE paper_simulation_epochs SET status='archived', ended_at=?, "
                "end_total_equity=?, end_cash=?, end_market_value=?, archive_payload=? "
                "WHERE epoch_id=? AND status='active'",
                (
                    now,
                    float(account_before.get("total_equity") or 0.0),
                    float(account_before.get("available_cash") or 0.0),
                    float(account_before.get("market_value") or 0.0),
                    archive_payload,
                    current.epoch_id,
                ),
            )

            # Active inventory is intentionally cleared, not converted into fake
            # SELL fills. Historical executions remain immutable in the log.
            connection.execute("DELETE FROM paper_trading_positions")
            connection.execute("DELETE FROM paper_position_lots")
            connection.execute(
                "UPDATE paper_position_episodes SET closed_at=? "
                "WHERE closed_at IS NULL",
                (now,),
            )
            connection.execute(
                "UPDATE paper_execution_deferrals SET state='superseded', resolved_at=? "
                "WHERE state='active'",
                (now,),
            )

            # The legacy account projection derives its return baseline from the
            # sum of cash-flow rows. Preserve those rows as immutable history and
            # append an explicit rebase that cancels the prior contribution basis;
            # the following opening balance then becomes the fresh epoch baseline.
            if abs(contribution_total) > 1e-9:
                connection.execute(
                    "INSERT INTO paper_trading_cash_flows (id,amount,flow_type,note,occurred_at) VALUES (?,?,?,?,?)",
                    (
                        str(uuid4()),
                        -contribution_total,
                        "epoch_rebase",
                        f"归档模拟轮次 #{current.sequence} 的历史资金基准",
                        now,
                    ),
                )

            # Paper trading currently shares the one simulated cash ledger. The
            # restart is the explicit USER authority to rebase that ledger.
            connection.execute(
                "INSERT INTO account_cash (account_id,available_cash,updated_at) VALUES ('default',?,?) "
                "ON CONFLICT(account_id) DO UPDATE SET available_cash=excluded.available_cash, updated_at=excluded.updated_at",
                (initial_cash, now),
            )
            connection.execute(
                "INSERT INTO paper_trading_accounts (account_id,available_cash,initial_cash,enabled,updated_at) "
                "VALUES ('default',?,?,COALESCE((SELECT enabled FROM paper_trading_accounts WHERE account_id='default'),0),?) "
                "ON CONFLICT(account_id) DO UPDATE SET available_cash=excluded.available_cash, "
                "initial_cash=excluded.initial_cash, updated_at=excluded.updated_at",
                (initial_cash, initial_cash, now),
            )
            connection.execute(
                "INSERT INTO paper_trading_cash_flows (id,amount,flow_type,note,occurred_at) VALUES (?,?,?,?,?)",
                (str(uuid4()), initial_cash, "opening_balance", f"模拟轮次 #{sequence} 初始资金", now),
            )
            connection.execute(
                "INSERT INTO paper_simulation_epochs "
                "(epoch_id,sequence,status,started_at,ended_at,initial_cash,end_total_equity,end_cash,end_market_value,restart_request_id,archive_payload,created_at) "
                "VALUES (?,?, 'active', ?, NULL, ?, NULL, NULL, NULL, ?, '{}', ?)",
                (new_epoch_id, sequence, now, initial_cash, request_id, now),
            )
            connection.execute(
                "INSERT INTO paper_trading_equity_snapshots "
                "(total_equity,available_cash,market_value,total_pnl,recorded_at) VALUES (?,?,?,?,?)",
                (initial_cash, initial_cash, 0.0, 0.0, now),
            )
            connection.execute(
                "INSERT INTO simulation_runs "
                "(run_id,trigger,started_at,finished_at,status,symbol_count,generated,executed,skipped,message) "
                "VALUES (?,?,?,?,'completed',0,0,0,0,?)",
                (
                    run_id,
                    "user-restart",
                    now,
                    now,
                    f"模拟轮次 #{sequence} 已重新开始：空仓，初始资金 ¥{initial_cash:.2f}",
                ),
            )

        # Scheduler timestamps are process-local, so reset them only after the DB
        # transaction has committed successfully.
        self.on_restart()
        return {
            "status": "restarted",
            "idempotent_replay": False,
            "archived_epoch_id": current.epoch_id,
            "epoch": self.current_epoch(),
            "account": self.store.paper_account(),
        }


class PaperRuntimeStateService:
    """Compose human-readable runtime facts without granting trade authority."""

    def __init__(
        self,
        store,
        simulation_service: PaperSimulationService,
        *,
        schedule_state: Callable[[], dict[str, object]],
        runtime_snapshot: Callable[[], dict[str, object]],
    ) -> None:
        self.store = store
        self.simulation_service = simulation_service
        self.schedule_state = schedule_state
        self.runtime_snapshot = runtime_snapshot

    @staticmethod
    def _mode_label(mode: str, has_positions: bool) -> str:
        if mode == "FULL_FOCUS":
            return "接近满仓，仅管理已有仓位"
        if mode == "HOLDING_FOCUS":
            return "持仓优先"
        if has_positions:
            return "持仓管理 + 寻找新机会"
        return "空仓找机会"

    def _latest_activity(self, epoch_start: str) -> dict[str, object]:
        with self.store._connect() as connection:
            latest_run = connection.execute(
                "SELECT * FROM simulation_runs WHERE started_at>=? ORDER BY started_at DESC LIMIT 1",
                (epoch_start,),
            ).fetchone()
            latest_poll = connection.execute(
                "SELECT * FROM simulation_runs WHERE started_at>=? AND trigger='scheduler-execution' "
                "ORDER BY started_at DESC LIMIT 1",
                (epoch_start,),
            ).fetchone()
            stage_rows = connection.execute(
                "SELECT s.stage,s.status,s.detail,s.started_at FROM simulation_run_stages s "
                "JOIN simulation_runs r ON r.run_id=s.run_id "
                "WHERE r.started_at>=? AND s.stage IN ('candidate_pool','news','company_intelligence','decision') "
                "ORDER BY s.started_at DESC LIMIT 120",
                (epoch_start,),
            ).fetchall()

        last_candidate_scan_at = None
        last_research_at = None
        last_decision_at = None
        for row in stage_rows:
            stage = str(row["stage"])
            if stage == "candidate_pool" and last_candidate_scan_at is None:
                detail = {}
                try:
                    detail = json.loads(str(row["detail"] or "{}"))
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass
                adaptive = detail.get("adaptive_schedule") if isinstance(detail, dict) else None
                if isinstance(adaptive, dict) and adaptive.get("candidate_scan_due"):
                    last_candidate_scan_at = str(row["started_at"])
            elif stage in {"news", "company_intelligence"} and last_research_at is None:
                if str(row["status"]) != "skipped":
                    last_research_at = str(row["started_at"])
            elif stage == "decision" and last_decision_at is None:
                last_decision_at = str(row["started_at"])
            if last_candidate_scan_at and last_research_at and last_decision_at:
                break

        return {
            "latest_run": dict(latest_run) if latest_run else None,
            "last_execution_poll_at": str(latest_poll["finished_at"] or latest_poll["started_at"]) if latest_poll else None,
            "last_candidate_scan_at": last_candidate_scan_at,
            "last_research_at": last_research_at,
            "last_decision_at": last_decision_at,
        }

    def state(self) -> dict[str, object]:
        epoch = self.simulation_service.current_epoch()
        schedule = dict(self.schedule_state())
        snapshot = dict(self.runtime_snapshot())
        account = self.store.paper_account()
        activity = self._latest_activity(str(epoch["started_at"]))
        paper_state = dict(snapshot.get("paper_state") or {})
        market_state = dict(snapshot.get("market_refresh_state") or {})
        enabled = bool(account.get("enabled"))
        running = bool(paper_state.get("running"))
        pending = [str(item) for item in schedule.get("pending_symbols") or []]
        due_reviews = [str(item) for item in schedule.get("due_review_symbols") or []]
        positions = account.get("positions") or []
        mode = str(schedule.get("mode") or "DISCOVERY")
        latest_run = activity.get("latest_run") if isinstance(activity, dict) else None

        if not enabled:
            runtime_status = "paused"
            headline = "自动模拟已暂停"
            no_trade_reason = "自动执行开关处于关闭状态；行情页面仍可独立刷新。"
        elif running:
            runtime_status = "running"
            headline = "系统正在运行"
            no_trade_reason = str(paper_state.get("last_message") or "正在处理本轮模拟任务。")
        elif pending:
            runtime_status = "waiting_execution"
            headline = "等待已冻结决策的可执行行情"
            no_trade_reason = (
                f"当前有 {len(pending)} 个 BUY/SELL 执行义务；执行轮询只等待新的合格行情，"
                "不会重新调用 AI 改写已经冻结的动作。"
            )
        else:
            runtime_status = "monitoring"
            headline = self._mode_label(mode, bool(positions))
            if isinstance(latest_run, dict) and int(latest_run.get("executed") or 0) == 0 and latest_run.get("message"):
                no_trade_reason = str(latest_run["message"])
            else:
                no_trade_reason = "当前没有待执行 BUY/SELL；HOLD / WAIT / BLOCKED 不会形成成交任务。"

        return {
            "epoch": epoch,
            "runtime_status": runtime_status,
            "headline": headline,
            "mode": mode,
            "mode_label": self._mode_label(mode, bool(positions)),
            "auto_execution_enabled": enabled,
            "running": running,
            "no_trade_reason": no_trade_reason,
            "pending_execution_symbols": pending,
            "due_review_symbols": due_reviews,
            "pending_execution_count": len(pending),
            "due_review_count": len(due_reviews),
            "last_market_refresh_at": market_state.get("last_success_at"),
            "last_cycle_at": paper_state.get("last_finished_at"),
            "last_execution_poll_at": activity.get("last_execution_poll_at"),
            "last_candidate_scan_at": activity.get("last_candidate_scan_at"),
            "last_research_at": activity.get("last_research_at"),
            "last_decision_at": activity.get("last_decision_at"),
            "seconds_until_review": int(snapshot.get("seconds_until_review") or 0),
            "seconds_until_candidate_scan": schedule.get("seconds_until_candidate_scan"),
            "seconds_until_company_research": schedule.get("seconds_until_company_research"),
            "candidate_scan_enabled": bool(schedule.get("candidate_scan_enabled")),
            "latest_run": latest_run,
            "generated_at": beijing_now().isoformat(),
        }
