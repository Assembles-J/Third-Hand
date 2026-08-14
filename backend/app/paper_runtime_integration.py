"""Install governed paper-runtime behavior into the FastAPI application module.

The existing application assembly is intentionally kept unchanged in
``app.application``. This integration layer owns only the candidate/data-prewarm,
paper-decision and historical-execution boundaries introduced by the frozen
observation governance spec.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app import decision_config as config
from app.candidate_selection import CandidateSelection, select_candidates
from app.paper_runtime import (
    candidate_pool_audit,
    current_candidate_selection,
    excluded_requested_symbols,
    latest_current_version_decision_report,
    pending_current_version_decision_symbols,
    report_matches_current_selection,
    runtime_scope,
)


def install(m) -> None:
    """Patch the application module before FastAPI startup callbacks run."""

    def paper_candidate_selection(rotation_key: str | None = None) -> CandidateSelection:
        return current_candidate_selection(
            m.store,
            limit=m.PAPER_TRADING_CANDIDATE_LIMIT,
            rotation_key=rotation_key or m.beijing_now().date().isoformat(),
        )

    def paper_trading_symbols() -> list[str]:
        """Formal candidate cohort plus due current-version execution obligations."""
        selection = paper_candidate_selection()
        pending = pending_current_version_decision_symbols(
            m.store,
            policy_version=m.action_policy_engine.version,
        )
        return list(dict.fromkeys((*selection.symbols, *pending)))

    def refresh_universe_opportunity_inputs(trigger: str) -> list[str]:
        """Refresh market research metadata and a neutral history-prewarm cohort.

        Hot sectors/top movers remain UI/research metadata only. The 24 symbols
        whose histories are prewarmed are selected from the full quoted A-share
        snapshot by the deterministic scheduler, so research popularity cannot
        indirectly decide which names become formal paper candidates.
        """
        with m.universe_scan_state_lock:
            m.universe_scan_state["last_attempt_at"] = m.beijing_now()
        try:
            with m.market_collection_lock:
                snapshot = m.market_data.a_share_universe_snapshot(force_refresh=True)
                m.store.save_quotes(snapshot)
                hot_sectors = m.market_data.hot_a_share_sectors(limit=3)
                members = [
                    member
                    for sector in hot_sectors
                    for member in m.market_data.a_share_sector_members(str(sector["name"]), limit=12)
                ]
            quote_by_symbol = {str(item["symbol"]): item for item in snapshot}
            metadata: dict[str, dict[str, str]] = {}
            for member in members:
                symbol = str(member["symbol"])
                if symbol in quote_by_symbol:
                    metadata[symbol] = {
                        "name": str(quote_by_symbol[symbol].get("name") or member["name"] or symbol),
                        "sector": str(member["sector"]),
                    }
            if not metadata:
                ranked = sorted(
                    (item for item in snapshot if item.get("price") is not None),
                    key=lambda item: float(item.get("change_percent") or -999),
                    reverse=True,
                )[:24]
                metadata = {
                    str(item["symbol"]): {
                        "name": str(item.get("name") or item["symbol"]),
                        "sector": "市场活跃股",
                    }
                    for item in ranked
                }

            snapshot_symbols = [
                str(item["symbol"])
                for item in snapshot
                if item.get("price") is not None
            ]
            snapshot_set = set(snapshot_symbols)
            position_symbols = [
                str(item["symbol"])
                for item in m.store.paper_account().get("positions", [])
                if str(item["symbol"]) in snapshot_set
            ]
            prewarm = select_candidates(
                snapshot_symbols,
                position_symbols=position_symbols,
                limit=24,
                rotation_key=f"{m.beijing_now().date().isoformat()}:history-prewarm",
            )
            selected = list(prewarm.symbols)
            with m.universe_scan_state_lock:
                m.universe_scan_state.update({
                    "last_success_at": m.beijing_now(),
                    "last_error": None,
                    "hot_sectors": hot_sectors,
                    "candidates": metadata,
                })
            m.logger.info(
                "全市场研究输入刷新 trigger=%s quotes=%s research_sectors=%s history_queue=%s candidate_selection_version=%s candidate_pool_hash=%s",
                trigger,
                len(snapshot),
                ",".join(str(item["name"]) for item in hot_sectors) or "fallback",
                ",".join(selected),
                prewarm.selection_version,
                prewarm.candidate_pool_hash,
            )
            m.queue_background(m.refresh_derived_cache, selected, f"{trigger}-deterministic-history-prewarm")
            return selected
        except m.MarketDataUnavailable as error:
            with m.universe_scan_state_lock:
                m.universe_scan_state["last_error"] = f"{error.code}: {error}"
            m.logger.warning("全市场研究输入不可用 trigger=%s code=%s", trigger, error.code)
            raise

    def refresh_paper_candidate_data(symbols: list[str], *, force_refresh: bool, run_id: str | None = None) -> None:
        """Make governed runtime/data-prewarm symbols decision-ready."""
        if not symbols:
            return
        with m.paper_trading_state_lock:
            m.paper_trading_state.update({
                "last_status": "preparing_data",
                "last_message": f"正在补齐 {len(symbols)} 只持仓、确定性候选、到期决策或显式预热请求的数据。",
                "last_symbols": symbols,
            })
        try:
            m.fetch_and_store_quotes(symbols, force_refresh=force_refresh, trigger="paper-trading-decision", run_id=run_id)
        except m.MarketDataUnavailable as error:
            m.logger.info("paper candidate quote refresh unavailable: %s", error)
        m.refresh_derived_cache(symbols, "paper-trading-decision", force_history=force_refresh, run_id=run_id)

    def prepare_paper_decisions(
        symbols: list[str],
        run_id: str | None = None,
        names: dict[str, str] | None = None,
        selection: CandidateSelection | None = None,
    ) -> int:
        """Create/reuse formal decisions only for deterministic candidate symbols."""
        generated = 0
        paper_account = m.store.paper_account()
        paper_holdings = [
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "quantity": item["quantity"],
                "average_cost": item["average_cost"],
                "created_at": item.get("updated_at"),
            }
            for item in paper_account.get("positions", [])
        ]
        names = names or {
            str(item["symbol"]).strip().upper(): str(item.get("name") or item["symbol"])
            for item in paper_holdings
        }
        reuse_seconds = int(
            m.store.system_settings().get("paper_trading_interval_seconds", m.PAPER_TRADING_INTERVAL_SECONDS)
        )
        for symbol in symbols:
            stage_started_at = m.beijing_now().isoformat()
            symbol_key = symbol.strip().upper()
            symbol_name = names.get(symbol_key, symbol)
            quote = next(iter(m.store.cached_quotes([symbol])), None)
            daily_bars = m.store.daily_prices(symbol, 60)
            if not quote or quote.get("price") is None or len(daily_bars) < 60:
                reason = "missing_quote" if (not quote or quote.get("price") is None) else "insufficient_daily_bars"
                detail = {
                    "name": symbol_name,
                    "reason": reason,
                    "quote_price": quote.get("price") if quote else None,
                    "daily_bar_count": len(daily_bars),
                }
                m._record_simulation_symbol_state(run_id, symbol, "skipped_data_unavailable", detail, name=symbol_name)
                m._record_simulation_stage(run_id, "decision", "skipped", symbol=symbol, detail={"terminal_state": "skipped_data_unavailable", **detail}, started_at=stage_started_at)
                continue

            latest = latest_current_version_decision_report(m.store, symbol, policy_version=m.action_policy_engine.version)
            if latest and selection is not None:
                try:
                    recent = (m.beijing_now() - datetime.fromisoformat(str(latest["generated_at"]))).total_seconds() < reuse_seconds
                    lineage_matches = report_matches_current_selection(latest, selection, policy_version=m.action_policy_engine.version)
                    if recent and lineage_matches:
                        reused_detail = {
                            "name": symbol_name,
                            "decision_id": str(latest.get("decision_id") or ""),
                            "generated_at": str(latest.get("generated_at") or ""),
                            "reason": "within_interval_same_governance_version",
                            "action": latest.get("action"),
                            "open_gate_audit": latest.get("open_gate_audit") or {},
                            "candidate_selection_version": latest.get("candidate_selection_version"),
                            "candidate_pool_hash": latest.get("candidate_pool_hash"),
                            "candidate_rotation_key": latest.get("candidate_rotation_key"),
                            "candidate_rank": latest.get("candidate_rank"),
                            "candidate_selection_reason": latest.get("candidate_selection_reason"),
                        }
                        m._record_simulation_symbol_state(run_id, symbol, "decision_reused", reused_detail, name=symbol_name)
                        m._record_simulation_stage(run_id, "decision", "ok", symbol=symbol, detail={"terminal_state": "decision_reused", **reused_detail}, started_at=stage_started_at)
                        generated += 1
                        continue
                except ValueError:
                    pass

            if not m.store.instrument_metadata(symbol):
                m.store.save_instrument_metadata({
                    "symbol": symbol,
                    "market": "CN",
                    "currency": "CNY",
                    "lot_size": 100,
                    "price_tick": 0.01,
                    "source": "paper_market_default",
                    "as_of": str(quote.get("as_of") or m.beijing_now().isoformat()),
                })
            context = m.decision_context_builder.build(symbol, holdings_override=paper_holdings, available_cash_override=float(paper_account.get("available_cash") or 0))
            m.store.save_decision_context(context.model_dump(mode="json"))
            candidate_audit = selection.audit_for(symbol) if selection and symbol in selection.symbols else None
            report = m.decision_orchestrator.generate(context, candidate_audit=candidate_audit).model_dump(mode="json")
            # Keep explainability deterministic and sidecar-compatible with the
            # existing DecisionReport schema.  The extra JSON field is persisted
            # for paper audit/UI without granting a new policy input.
            open_gate_audit = m.action_policy_engine.open_gate_audit(context, m.evidence_engine.build(context))
            report["open_gate_audit"] = open_gate_audit
            m.store.save_decision_report(report)
            terminal_state = "blocked_by_gate" if str(report.get("status") or "").upper() == "BLOCKED" else "decision_generated"
            decision_detail = {
                "name": symbol_name,
                "decision_id": str(report.get("decision_id") or ""),
                "action": report.get("action"),
                "status": report.get("status"),
                "data_quality_status": str((report.get("data_quality") or {}).get("status") or ""),
                "open_gate_audit": open_gate_audit,
                "candidate_selection_version": report.get("candidate_selection_version"),
                "candidate_pool_hash": report.get("candidate_pool_hash"),
                "candidate_rotation_key": report.get("candidate_rotation_key"),
                "candidate_rank": report.get("candidate_rank"),
                "candidate_selection_reason": report.get("candidate_selection_reason"),
                "ai_shadow_action": report.get("ai_shadow_action"),
                "ai_shadow_agreement": report.get("ai_shadow_agreement"),
            }
            m._record_simulation_symbol_state(run_id, symbol, terminal_state, decision_detail, name=symbol_name)
            m._record_simulation_stage(run_id, "decision", "ok", symbol=symbol, detail={"terminal_state": terminal_state, **decision_detail}, started_at=stage_started_at)
            generated += 1
        return generated

    def execute_due_paper_decisions(symbols: list[str], names: dict[str, str], run_id: str | None = None) -> tuple[int, int]:
        """Fill current-version historical decisions at a later eligible quote."""
        positions = {str(item["symbol"]).strip().upper(): float(item["quantity"]) for item in m.store.paper_account().get("positions", [])}
        executed = skipped = 0
        for symbol in symbols:
            stage_started_at = m.beijing_now().isoformat()
            symbol_name = names.get(symbol.strip().upper(), symbol)
            report = latest_current_version_decision_report(m.store, symbol, policy_version=m.action_policy_engine.version)
            quote = next(iter(m.store.cached_quotes([symbol])), None)
            if not report:
                detail = {"name": symbol_name, "reason": "no_current_formal_decision_report"}
                m._record_simulation_symbol_state(run_id, symbol, "not_due", detail, name=symbol_name)
                m._record_simulation_stage(run_id, "execution", "skipped", symbol=symbol, detail={"terminal_state": "not_due", **detail}, started_at=stage_started_at)
                continue
            if report.get("policy_version") != m.action_policy_engine.version or report.get("candidate_selection_version") != config.CANDIDATE_SELECTION_VERSION:
                reason = "decision_governance_version_not_current"
                detail = {"name": symbol_name, "decision_id": str(report.get("decision_id") or ""), "reason": reason}
                m._record_simulation_symbol_state(run_id, symbol, "skipped_execution", detail, name=symbol_name)
                m._record_simulation_stage(run_id, "execution", "skipped", symbol=symbol, detail={"terminal_state": "skipped_execution", **detail}, started_at=stage_started_at)
                skipped += 1
                continue
            check = m.validate_daily_execution(report, quote)
            if not check.allowed:
                terminal_state = "not_due" if check.reason == "execution_not_due_next_market_session" else "blocked_by_gate" if check.reason == "execution_action_gate_blocked" else "skipped_execution"
                detail = {"name": symbol_name, "decision_id": str(report.get("decision_id") or ""), "reason": check.reason, "action": report.get("action")}
                m._record_simulation_symbol_state(run_id, symbol, terminal_state, detail, name=symbol_name)
                m._record_simulation_stage(run_id, "execution", "skipped", symbol=symbol, detail={"terminal_state": terminal_state, **detail}, started_at=stage_started_at)
                continue
            action = str(report.get("action") or "").upper()
            sizing = report.get("sizing") or {}
            quantity = float(sizing.get("suggested_quantity") or sizing.get("target_quantity") or 0)
            price = float((quote or {}).get("price") or 0)
            side = "BUY" if action in {"OPEN", "ADD"} else "SELL" if action in {"REDUCE", "EXIT"} else None
            if not side or quantity <= 0 or price <= 0:
                detail = {"name": symbol_name, "decision_id": str(report.get("decision_id") or ""), "reason": "invalid_side_or_sizing", "action": action, "quantity": quantity, "price": price}
                m._record_simulation_symbol_state(run_id, symbol, "skipped_execution", detail, name=symbol_name)
                m._record_simulation_stage(run_id, "execution", "skipped", symbol=symbol, detail={"terminal_state": "skipped_execution", **detail}, started_at=stage_started_at)
                continue
            if side == "SELL" and positions.get(symbol, 0.0) <= 0:
                m.store.record_paper_skip(symbol=symbol, name=symbol_name, decision_id=str(report.get("decision_id") or "") or None, reason="paper_sell_blocked_no_position", price=price)
                detail = {"name": symbol_name, "decision_id": str(report.get("decision_id") or ""), "reason": "paper_sell_blocked_no_position", "action": action}
                m._record_simulation_symbol_state(run_id, symbol, "skipped_execution", detail, name=symbol_name)
                m._record_simulation_stage(run_id, "execution", "skipped", symbol=symbol, detail={"terminal_state": "skipped_execution", **detail}, started_at=stage_started_at)
                skipped += 1
                continue
            if side == "SELL":
                quantity = min(quantity, positions.get(symbol, 0.0))
            try:
                m.store.execute_paper_trade(
                    trade_id=str(uuid4()), symbol=symbol, name=symbol_name, side=side,
                    quantity=quantity, price=price, decision_id=str(report.get("decision_id") or "") or None,
                    reason=f"next_market_session:{action}; {str(report.get('summary') or '')[:180]}",
                    execution_quote_at=str((quote or {}).get("as_of") or (quote or {}).get("retrieved_at") or "") or None,
                    execution_quote_source=str((quote or {}).get("source") or "") or None,
                    fill_price_mode="NEXT_ELIGIBLE_OBSERVED_QUOTE",
                )
                detail = {"name": symbol_name, "decision_id": str(report.get("decision_id") or ""), "side": side, "quantity": quantity, "price": price, "action": action}
                m._record_simulation_symbol_state(run_id, symbol, "executed", detail, name=symbol_name)
                m._record_simulation_stage(run_id, "execution", "ok", symbol=symbol, detail={"terminal_state": "executed", **detail}, started_at=stage_started_at)
                executed += 1
                positions[symbol] = positions.get(symbol, 0.0) + (quantity if side == "BUY" else -quantity)
            except ValueError as error:
                if str(error) != "paper_decision_already_executed":
                    m.store.record_paper_skip(symbol=symbol, name=symbol_name, decision_id=str(report.get("decision_id") or "") or None, reason=str(error), price=price)
                    detail = {"name": symbol_name, "decision_id": str(report.get("decision_id") or ""), "reason": str(error), "action": action}
                    m._record_simulation_symbol_state(run_id, symbol, "skipped_execution", detail, name=symbol_name)
                    m._record_simulation_stage(run_id, "execution", "skipped", symbol=symbol, detail={"terminal_state": "skipped_execution", **detail}, started_at=stage_started_at)
                    skipped += 1
                else:
                    detail = {"name": symbol_name, "decision_id": str(report.get("decision_id") or ""), "reason": "decision_already_executed", "action": action}
                    m._record_simulation_symbol_state(run_id, symbol, "not_due", detail, name=symbol_name)
                    m._record_simulation_stage(run_id, "execution", "skipped", symbol=symbol, detail={"terminal_state": "not_due", **detail}, started_at=stage_started_at)
        return executed, skipped

    def run_paper_trading_cycle(requested_symbols: list[str], force: bool = False, allow_when_disabled: bool = False) -> dict[str, object]:
        """Run deterministic new decisions plus separately tracked due executions."""
        if not allow_when_disabled and not m.store.system_settings()["paper_trading_enabled"]:
            with m.paper_trading_state_lock:
                m.paper_trading_state.update({"running": False, "last_status": "disabled", "last_message": "自动执行已关闭；可在系统管理中开启。"})
            return {"executed": 0, "skipped": 0, "run_id": None}
        configured_interval = int(m.store.system_settings().get("paper_trading_interval_seconds", m.PAPER_TRADING_INTERVAL_SECONDS))
        if not force and m.time.monotonic() - m.last_paper_trading_run_at < configured_interval:
            with m.paper_trading_state_lock:
                m.paper_trading_state.update({"running": False, "last_status": "waiting_interval", "last_message": "等待已配置的执行间隔；到期后会读取最新统一决策。"})
            return {"executed": 0, "skipped": 0, "run_id": None}

        rotation_key = m.beijing_now().date().isoformat()
        selection = paper_candidate_selection(rotation_key)
        pending = pending_current_version_decision_symbols(m.store, policy_version=m.action_policy_engine.version)
        decision_symbols, due_symbols, symbols = runtime_scope(selection, requested_symbols=requested_symbols, pending_symbols=pending)
        excluded = excluded_requested_symbols(selection, requested_symbols=requested_symbols, pending_symbols=pending)
        data_refresh_symbols = tuple(dict.fromkeys((*symbols, *excluded)))
        with m.paper_trading_state_lock:
            m.paper_trading_state.update({
                "running": True,
                "last_started_at": m.beijing_now(),
                "last_status": "running",
                "last_message": "正在读取确定性候选、历史到期决策与模拟账本。",
                "last_symbols": list(symbols),
            })
        m.last_paper_trading_run_at = m.time.monotonic()
        names = m.paper_trading_names(list(data_refresh_symbols))
        run_id = m._create_simulation_run("manual" if force else "scheduler", list(symbols), "交易运行开始")
        pool_detail = candidate_pool_audit(selection, requested_symbols=requested_symbols, decision_symbols=decision_symbols, due_symbols=due_symbols)
        pool_detail["runtime_symbols"] = list(symbols)
        pool_detail["data_refresh_symbols"] = list(data_refresh_symbols)
        pool_detail["excluded_requested_symbols"] = list(excluded)
        pool_detail["symbol_names"] = {symbol: names.get(symbol, symbol) for symbol in selection.symbols}
        for item in pool_detail.get("selected_items", []):
            if isinstance(item, dict):
                item["name"] = names.get(str(item.get("symbol") or ""), str(item.get("symbol") or ""))
        m._record_simulation_stage(run_id, "candidate_pool", "ok", detail=pool_detail)
        for symbol in excluded:
            symbol_name = names.get(symbol.strip().upper(), symbol)
            bar_count = len(m.store.daily_prices(symbol, 60))
            terminal_state = "skipped_data_unavailable" if bar_count < 60 else "not_due"
            reason = "insufficient_daily_bars" if bar_count < 60 else "not_selected_by_deterministic_scheduler"
            detail = {"name": symbol_name, "reason": reason, "daily_bar_count": bar_count, "candidate_selection_version": selection.selection_version, "candidate_pool_hash": selection.candidate_pool_hash}
            m._record_simulation_symbol_state(run_id, symbol, terminal_state, detail, name=symbol_name)
            m._record_simulation_stage(run_id, "decision", "skipped", symbol=symbol, detail={"terminal_state": terminal_state, **detail})
        executed = 0
        skipped = 0
        no_action_reasons: list[str] = []
        try:
            # Explicit requests that are outside the formal cohort may prewarm
            # data, but they remain absent from decision_symbols for this run.
            refresh_paper_candidate_data(list(data_refresh_symbols), force_refresh=force, run_id=run_id)
            names = m.paper_trading_names(list(data_refresh_symbols))
            with m.paper_trading_state_lock:
                m.paper_trading_state.update({"last_status": "researching", "last_message": "行情已同步；新闻仅做研究补充，正式动作继续由确定性策略生成。"})
            m.refresh_paper_market_intelligence(list(symbols), names)
            m._record_simulation_stage(run_id, "news", "ok", detail={"symbol_count": len(symbols), "usage_scope": "RESEARCH_ONLY"})
            due_executed, due_skipped = execute_due_paper_decisions(list(due_symbols), names, run_id=run_id)
            executed += due_executed
            skipped += due_skipped
            generated_reports = prepare_paper_decisions(list(decision_symbols), run_id=run_id, names=names, selection=selection)
            if not due_executed:
                no_action_reasons.append("本交易时段没有到期且可执行的当前版本历史决策")
            if excluded:
                no_action_reasons.append(f"{len(excluded)} 个显式请求不属于当前 formal cohort，仅完成数据预热与审计")
            m.store.record_paper_equity_snapshot()
            m._record_simulation_stage(run_id, "equity_snapshot", "ok", detail={})
            result = {"executed": executed, "skipped": skipped, "run_id": run_id}
            with m.paper_trading_state_lock:
                summary = f"本轮确定性候选 {len(decision_symbols)} 只，到期历史决策 {len(due_symbols)} 只，生成或复用 {generated_reports} 份统一决策，执行 {executed} 笔。"
                if not executed and no_action_reasons:
                    summary += " 暂不交易：" + "；".join(no_action_reasons[:2]) + "。"
                m.paper_trading_state.update({"running": False, "last_finished_at": m.beijing_now(), "last_status": "completed", "last_message": summary, "last_executed": executed, "last_skipped": skipped, "last_run_id": run_id})
            m._finish_simulation_run(run_id, "completed", summary, executed=executed, skipped=skipped, generated=generated_reports)
            return result
        except Exception as error:
            with m.paper_trading_state_lock:
                m.paper_trading_state.update({"running": False, "last_finished_at": m.beijing_now(), "last_status": "failed", "last_message": f"交易判断异常：{type(error).__name__}: {error}", "last_run_id": run_id})
            m._finish_simulation_run(run_id, "failed", f"交易判断异常：{type(error).__name__}: {error}", executed=executed, skipped=skipped)
            raise

    m.paper_candidate_selection = paper_candidate_selection
    m.paper_trading_symbols = paper_trading_symbols
    m.refresh_universe_opportunity_inputs = refresh_universe_opportunity_inputs
    m.refresh_paper_candidate_data = refresh_paper_candidate_data
    m.prepare_paper_decisions = prepare_paper_decisions
    m.execute_due_paper_decisions = execute_due_paper_decisions
    m.run_paper_trading_cycle = run_paper_trading_cycle
