"""Install adaptive scheduling around the governed paper runtime.

This module deliberately reuses the already-installed paper runtime primitives.
It only controls cadence and scope.  Candidate authorization, ActionPolicy,
PositionSizing and execution remain owned by their existing deterministic layers.
"""
from __future__ import annotations

from app.domain.trading.adaptive_schedule import adaptive_paper_schedule
from app.paper_runtime import (
    candidate_pool_audit,
    excluded_requested_symbols,
    pending_current_version_decision_symbols,
    runtime_scope,
)


def install(m) -> None:
    if getattr(m, "_adaptive_paper_runtime_installed", False):
        return
    m._adaptive_paper_runtime_installed = True

    original_paper_trading_symbols = m.paper_trading_symbols
    original_refresh_universe_opportunity_inputs = m.refresh_universe_opportunity_inputs
    m.last_paper_candidate_scan_at = 0.0

    def _plan(pending_symbols=()):
        settings = m.store.system_settings()
        return adaptive_paper_schedule(
            m.store.paper_account(),
            configured_interval_seconds=int(settings["paper_trading_interval_seconds"]),
            pending_symbols=pending_symbols,
        )

    def adaptive_paper_schedule_state() -> dict[str, object]:
        pending = pending_current_version_decision_symbols(
            m.store,
            policy_version=m.action_policy_engine.version,
        )
        plan = _plan(pending)
        now = m.time.monotonic()
        scan_interval = plan.candidate_scan_interval_seconds
        seconds_until_candidate_scan = None
        candidate_scan_due = False
        if plan.candidate_scan_enabled and scan_interval is not None:
            elapsed = max(0.0, now - m.last_paper_candidate_scan_at)
            candidate_scan_due = m.last_paper_candidate_scan_at <= 0 or elapsed >= scan_interval
            seconds_until_candidate_scan = 0 if candidate_scan_due else max(0, round(scan_interval - elapsed))
        return {
            **plan.as_dict(),
            "pending_symbols": list(pending),
            "candidate_scan_due": candidate_scan_due,
            "seconds_until_candidate_scan": seconds_until_candidate_scan,
            "usage_scope": "SCHEDULING_ONLY",
            "formal_trade_authority": False,
        }

    def refresh_universe_opportunity_inputs(trigger: str) -> list[str]:
        """Suppress automatic broad-market research when capital is fully deployed.

        Manual/explicit maintenance calls retain their historical behavior. The
        scheduler-only suppression is important because the legacy market loop
        performs the whole-market refresh *before* asking ``paper_trading_symbols``.
        Without this guard a FULL_FOCUS account would still download thousands
        of unrelated quotes every 30 minutes even though formal paper work had
        already narrowed itself to holdings.
        """
        if str(trigger) == "scheduler-whole-market":
            state = adaptive_paper_schedule_state()
            if state["mode"] == "FULL_FOCUS":
                m.logger.info(
                    "whole-market candidate refresh skipped adaptive_mode=FULL_FOCUS "
                    "cash_ratio=%s focus_symbols=%s",
                    state["cash_ratio"],
                    ",".join(str(item) for item in state["focus_symbols"]) or "none",
                )
                return []
        return original_refresh_universe_opportunity_inputs(trigger)

    def paper_trading_symbols() -> list[str]:
        """Return only work that is actually due under the adaptive cadence."""
        state = adaptive_paper_schedule_state()
        focus = [str(item) for item in state["focus_symbols"]]
        if not state["candidate_scan_enabled"] or not state["candidate_scan_due"]:
            return focus
        return original_paper_trading_symbols()

    def run_paper_trading_cycle(
        requested_symbols: list[str],
        force: bool = False,
        allow_when_disabled: bool = False,
    ) -> dict[str, object]:
        """Run governed work with holdings-first cadence and bounded discovery."""
        if not allow_when_disabled and not m.store.system_settings()["paper_trading_enabled"]:
            with m.paper_trading_state_lock:
                m.paper_trading_state.update({
                    "running": False,
                    "last_status": "disabled",
                    "last_message": "自动执行已关闭；可在系统管理中开启。",
                })
            return {"executed": 0, "skipped": 0, "run_id": None}

        pending = pending_current_version_decision_symbols(
            m.store,
            policy_version=m.action_policy_engine.version,
        )
        plan = _plan(pending)
        now_mono = m.time.monotonic()
        if not force and now_mono - m.last_paper_trading_run_at < plan.review_interval_seconds:
            with m.paper_trading_state_lock:
                m.paper_trading_state.update({
                    "running": False,
                    "last_status": "waiting_interval",
                    "last_message": f"自适应分析模式 {plan.mode}：等待本模式的复核间隔。",
                })
            return {"executed": 0, "skipped": 0, "run_id": None}

        rotation_key = m.beijing_now().date().isoformat()
        selection = m.paper_candidate_selection(rotation_key)
        candidate_scan_due = False
        if plan.candidate_scan_enabled and plan.candidate_scan_interval_seconds is not None:
            scan_elapsed = max(0.0, now_mono - m.last_paper_candidate_scan_at)
            candidate_scan_due = (
                force
                or m.last_paper_candidate_scan_at <= 0
                or scan_elapsed >= plan.candidate_scan_interval_seconds
            )

        if force:
            effective_requested = tuple(dict.fromkeys(
                str(item).strip().upper() for item in requested_symbols if str(item).strip()
            ))
        elif candidate_scan_due:
            # The scheduler-provided list is already deterministic. Fall back to
            # the selector if an older caller supplied an empty list.
            effective_requested = tuple(dict.fromkeys(
                str(item).strip().upper() for item in requested_symbols if str(item).strip()
            )) or tuple(dict.fromkeys((*selection.symbols, *pending)))
        else:
            # Full / holding-focus cycles do not refresh unrelated candidates.
            effective_requested = plan.focus_symbols

        decision_symbols, due_symbols, symbols = runtime_scope(
            selection,
            requested_symbols=effective_requested,
            pending_symbols=pending,
        )
        excluded = excluded_requested_symbols(
            selection,
            requested_symbols=effective_requested,
            pending_symbols=pending,
        )
        data_refresh_symbols = tuple(dict.fromkeys((*symbols, *excluded)))

        with m.paper_trading_state_lock:
            m.paper_trading_state.update({
                "running": True,
                "last_started_at": m.beijing_now(),
                "last_status": "running",
                "last_message": (
                    f"自适应模式 {plan.mode}："
                    f"持仓研究 {plan.holding_research_priority}，"
                    f"{'本轮含确定性候选扫描' if candidate_scan_due else '本轮仅聚焦持仓/到期决策'}。"
                ),
                "last_symbols": list(symbols),
            })
        m.last_paper_trading_run_at = now_mono
        if candidate_scan_due and not force:
            m.last_paper_candidate_scan_at = now_mono

        names = m.paper_trading_names(list(data_refresh_symbols))
        run_id = m._create_simulation_run("manual" if force else "scheduler", list(symbols), "交易运行开始")
        pool_detail = candidate_pool_audit(
            selection,
            requested_symbols=effective_requested,
            decision_symbols=decision_symbols,
            due_symbols=due_symbols,
        )
        pool_detail.update({
            "runtime_symbols": list(symbols),
            "data_refresh_symbols": list(data_refresh_symbols),
            "excluded_requested_symbols": list(excluded),
            "symbol_names": {symbol: names.get(symbol, symbol) for symbol in selection.symbols},
            "adaptive_schedule": {
                **plan.as_dict(),
                "candidate_scan_due": candidate_scan_due,
            },
        })
        for item in pool_detail.get("selected_items", []):
            if isinstance(item, dict):
                item["name"] = names.get(str(item.get("symbol") or ""), str(item.get("symbol") or ""))
        m._record_simulation_stage(run_id, "candidate_pool", "ok", detail=pool_detail)

        for symbol in excluded:
            symbol_name = names.get(symbol.strip().upper(), symbol)
            bar_count = len(m.store.daily_prices(symbol, 60))
            terminal_state = "skipped_data_unavailable" if bar_count < 60 else "not_due"
            reason = "insufficient_daily_bars" if bar_count < 60 else "not_selected_by_deterministic_scheduler"
            detail = {
                "name": symbol_name,
                "reason": reason,
                "daily_bar_count": bar_count,
                "candidate_selection_version": selection.selection_version,
                "candidate_pool_hash": selection.candidate_pool_hash,
            }
            m._record_simulation_symbol_state(run_id, symbol, terminal_state, detail, name=symbol_name)
            m._record_simulation_stage(
                run_id,
                "decision",
                "skipped",
                symbol=symbol,
                detail={"terminal_state": terminal_state, **detail},
            )

        executed = 0
        skipped = 0
        no_action_reasons: list[str] = []
        try:
            m.refresh_paper_candidate_data(list(data_refresh_symbols), force_refresh=force, run_id=run_id)
            names = m.paper_trading_names(list(data_refresh_symbols))
            with m.paper_trading_state_lock:
                m.paper_trading_state.update({
                    "last_status": "researching",
                    "last_message": "行情已同步；自动研究优先级按资金占用自适应，正式动作仍由确定性策略生成。",
                })
            m.refresh_paper_market_intelligence(list(symbols), names)
            m._record_simulation_stage(
                run_id,
                "news",
                "ok",
                detail={"symbol_count": len(symbols), "usage_scope": "RESEARCH_ONLY"},
            )

            # Company Intelligence is research-only.  When installed, held names
            # receive the deeper L3/L4 context chosen by the adaptive plan.  Its
            # own gateway remains local-first and TTL-controlled.
            company_focus = [symbol for symbol in plan.focus_symbols if symbol in set(symbols)]
            refresh_company = getattr(m, "refresh_company_intelligence_focus", None)
            if callable(refresh_company) and company_focus:
                refresh_company(
                    company_focus,
                    research_priority=plan.holding_research_priority,
                    run_id=run_id,
                )

            due_executed, due_skipped = m.execute_due_paper_decisions(list(due_symbols), names, run_id=run_id)
            executed += due_executed
            skipped += due_skipped
            generated_reports = m.prepare_paper_decisions(
                list(decision_symbols),
                run_id=run_id,
                names=names,
                selection=selection,
            )
            if not due_executed:
                no_action_reasons.append("本交易时段没有到期且可执行的当前版本历史决策")
            if excluded:
                no_action_reasons.append(f"{len(excluded)} 个显式请求不属于当前 formal cohort，仅完成数据预热与审计")
            if not candidate_scan_due and not force:
                no_action_reasons.append("自适应模式本轮不扫描新标的，资源集中到持仓与到期决策")

            m.store.record_paper_equity_snapshot()
            m._record_simulation_stage(run_id, "equity_snapshot", "ok", detail={})
            result = {"executed": executed, "skipped": skipped, "run_id": run_id}
            with m.paper_trading_state_lock:
                summary = (
                    f"自适应 {plan.mode}：本轮正式候选 {len(decision_symbols)} 只，"
                    f"到期历史决策 {len(due_symbols)} 只，生成或复用 {generated_reports} 份统一决策，"
                    f"执行 {executed} 笔。"
                )
                if not executed and no_action_reasons:
                    summary += " 暂不交易：" + "；".join(no_action_reasons[:2]) + "。"
                m.paper_trading_state.update({
                    "running": False,
                    "last_finished_at": m.beijing_now(),
                    "last_status": "completed",
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
                generated=generated_reports,
            )
            return result
        except Exception as error:
            with m.paper_trading_state_lock:
                m.paper_trading_state.update({
                    "running": False,
                    "last_finished_at": m.beijing_now(),
                    "last_status": "failed",
                    "last_message": f"交易判断异常：{type(error).__name__}: {error}",
                    "last_run_id": run_id,
                })
            m._finish_simulation_run(
                run_id,
                "failed",
                f"交易判断异常：{type(error).__name__}: {error}",
                executed=executed,
                skipped=skipped,
            )
            raise

    m.adaptive_paper_schedule_state = adaptive_paper_schedule_state
    m.refresh_universe_opportunity_inputs = refresh_universe_opportunity_inputs
    m.paper_trading_symbols = paper_trading_symbols
    m.run_paper_trading_cycle = run_paper_trading_cycle
