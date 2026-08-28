"""Execution-only polling for frozen paper decisions between analysis reviews.

The adaptive paper runtime intentionally throttles research and decision generation
to multi-minute intervals. Market quotes refresh more frequently, so an already
frozen BUY/ADD/REDUCE/EXIT decision should be allowed to consume a strictly later
eligible quote without rerunning research or changing policy authority.
"""
from __future__ import annotations

from app.paper_runtime import pending_current_version_decision_symbols


MIN_EXECUTION_POLL_INTERVAL_SECONDS = 30
MAX_EXECUTION_POLL_INTERVAL_SECONDS = 60


def install(m) -> None:
    if getattr(m, "_paper_execution_poll_runtime_installed", False):
        return
    m._paper_execution_poll_runtime_installed = True

    original_run_paper_trading_cycle = m.run_paper_trading_cycle
    m.last_paper_execution_poll_at = 0.0

    def _poll_interval_seconds() -> int:
        market_interval = int(getattr(m, "MARKET_REFRESH_INTERVAL_SECONDS", MAX_EXECUTION_POLL_INTERVAL_SECONDS))
        return min(MAX_EXECUTION_POLL_INTERVAL_SECONDS, max(MIN_EXECUTION_POLL_INTERVAL_SECONDS, market_interval))

    def _requested_execution_symbols(requested_symbols, pending_symbols) -> tuple[str, ...]:
        requested = {
            str(item).strip().upper()
            for item in requested_symbols
            if str(item).strip()
        }
        return tuple(
            symbol for symbol in pending_symbols
            if not requested or symbol in requested
        )

    def run_paper_trading_cycle(
        requested_symbols: list[str],
        force: bool = False,
        allow_when_disabled: bool = False,
    ) -> dict[str, object]:
        """Poll execution obligations while leaving full analysis cadence intact."""
        settings = m.store.system_settings()
        if force or allow_when_disabled or not settings["paper_trading_enabled"]:
            return original_run_paper_trading_cycle(
                requested_symbols,
                force=force,
                allow_when_disabled=allow_when_disabled,
            )

        pending = pending_current_version_decision_symbols(
            m.store,
            policy_version=m.action_policy_engine.version,
        )
        if not pending or m.last_paper_trading_run_at <= 0:
            return original_run_paper_trading_cycle(requested_symbols)

        schedule = m.adaptive_paper_schedule_state()
        now_mono = m.time.monotonic()
        review_interval = int(schedule["review_interval_seconds"])
        if now_mono - m.last_paper_trading_run_at >= review_interval:
            return original_run_paper_trading_cycle(requested_symbols)

        execution_symbols = _requested_execution_symbols(requested_symbols, pending)
        poll_interval = _poll_interval_seconds()
        if (
            not execution_symbols
            or now_mono - m.last_paper_execution_poll_at < poll_interval
        ):
            return original_run_paper_trading_cycle(requested_symbols)

        # The market worker refreshes quotes immediately before this call. We use
        # only that local cache here: no provider/research/LLM work is introduced.
        # execute_due_paper_decisions still owns market-hours, quote freshness,
        # later-than-decision, action-gate, sizing, T+1 and idempotency checks.
        m.last_paper_execution_poll_at = now_mono
        names = m.paper_trading_names(list(execution_symbols))
        run_id = m._create_simulation_run(
            "scheduler-execution",
            list(execution_symbols),
            "到期历史决策执行轮询",
        )
        executed = skipped = 0
        try:
            with m.paper_trading_state_lock:
                m.paper_trading_state.update({
                    "running": True,
                    "last_started_at": m.beijing_now(),
                    "last_status": "execution_poll",
                    "last_message": "分析复核间隔内，仅检查已冻结决策是否出现可执行的新行情。",
                    "last_symbols": list(execution_symbols),
                })
            executed, skipped = m.execute_due_paper_decisions(
                list(execution_symbols),
                names,
                run_id=run_id,
            )
            if executed:
                m.store.record_paper_equity_snapshot()
            summary = (
                f"执行轮询检查 {len(execution_symbols)} 个已冻结决策，"
                f"执行 {executed} 笔；完整研究/决策仍按自适应复核间隔运行。"
            )
            with m.paper_trading_state_lock:
                m.paper_trading_state.update({
                    "running": False,
                    "last_finished_at": m.beijing_now(),
                    "last_status": "execution_poll_completed",
                    "last_message": summary,
                    "last_executed": executed,
                    "last_skipped": skipped,
                    "last_run_id": run_id,
                })
            m._finish_simulation_run(
                run_id,
                "completed",
                summary,
                executed=executed,
                skipped=skipped,
                generated=0,
            )
            return {"executed": executed, "skipped": skipped, "run_id": run_id}
        except Exception as error:
            with m.paper_trading_state_lock:
                m.paper_trading_state.update({
                    "running": False,
                    "last_finished_at": m.beijing_now(),
                    "last_status": "execution_poll_failed",
                    "last_message": f"执行轮询异常：{type(error).__name__}: {error}",
                    "last_run_id": run_id,
                })
            m._finish_simulation_run(
                run_id,
                "failed",
                f"执行轮询异常：{type(error).__name__}: {error}",
                executed=executed,
                skipped=skipped,
                generated=0,
            )
            raise

    m.run_paper_trading_cycle = run_paper_trading_cycle
