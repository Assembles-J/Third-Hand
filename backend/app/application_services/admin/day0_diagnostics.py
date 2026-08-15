"""Read-only Day-0 production diagnostics.

The service summarizes already-persisted simulation audit data.  It must never
re-run policy, mutate paper accounts, expose secrets, or provide a trading write
path.  Its only purpose is to make production governance and OPEN-gate failures
inspectable without SSH access.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from app import decision_config as config


CHECK_MEANINGS_CN: dict[str, str] = {
    "action_gate.open": "OPEN 基础数据门是否放行",
    "position.absent": "当前是否没有该股票持仓",
    "quote.available": "有效行情报价是否存在",
    "risk.available": "风险数据是否存在",
    "cash.positive": "可用现金是否大于 0",
    "positive_policy_evidence.present": "是否至少存在一项正式正向策略证据",
    "market.not_defensive": "市场环境是否不处于防守状态",
}

ACTION_MEANINGS_CN: dict[str, str] = {
    "OPEN": "建立新仓位",
    "ADD": "已有持仓基础上加仓",
    "HOLD": "继续持有当前仓位",
    "WATCH": "继续观察，当前不产生交易动作",
    "REDUCE": "降低已有仓位",
    "EXIT": "退出已有仓位",
    "BLOCKED": "关键输入或动作门阻断",
}

EXECUTION_REASON_MEANINGS_CN: dict[str, str] = {
    "execution_not_due_next_market_session": "决策尚未到下一可成交市场日期",
    "execution_action_gate_blocked": "原决策的动作数据门没有放行",
    "execution_quote_missing": "缺少可用于成交的后续行情",
    "execution_time_unknown": "无法确认决策日期或成交行情日期",
    "invalid_side_or_sizing": "动作方向、数量或价格不满足执行要求",
    "paper_sell_blocked_no_position": "没有可卖出的纸面持仓",
    "decision_governance_version_not_current": "决策治理版本已不是当前版本",
    "no_current_formal_decision_report": "没有当前治理版本的正式决策报告",
    "decision_already_executed": "该正式决策已经执行过",
}


class Day0DiagnosticsService:
    """Summarize latest persisted paper-run audit data without side effects."""

    def __init__(self, store) -> None:
        self.store = store

    @staticmethod
    def _elapsed_ms(started_at: object, finished_at: object) -> int | None:
        if not started_at or not finished_at:
            return None
        try:
            start = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(finished_at).replace("Z", "+00:00"))
        except ValueError:
            return None
        return max(0, round((end - start).total_seconds() * 1000))

    @staticmethod
    def _provider_summary(items: list[dict[str, object]]) -> list[dict[str, object]]:
        allowed = (
            "provider",
            "circuit_state",
            "consecutive_failures",
            "total_attempts",
            "total_success",
            "total_failures",
            "last_attempt_at",
            "last_success_at",
            "last_failure_at",
            "cooldown_until",
            "error_type",
            "updated_at",
        )
        return [{key: item.get(key) for key in allowed} for item in items]

    @staticmethod
    def _candidate_audit(run: dict[str, object] | None) -> dict[str, object]:
        if not run:
            return {}
        for stage in run.get("stages", []):
            if stage.get("stage") != "candidate_pool":
                continue
            detail = dict(stage.get("detail") or {})
            return {
                "candidate_selection_version": detail.get("candidate_selection_version"),
                "candidate_pool_hash": detail.get("candidate_pool_hash"),
                "rotation_key": detail.get("rotation_key"),
                "eligible_count": detail.get("eligible_count"),
                "requested_limit": detail.get("requested_limit"),
                "selected_count": detail.get("selected_count"),
                "selection_algorithm": detail.get("selection_algorithm"),
                "selection_independent_of": list(detail.get("selection_independent_of") or []),
                "selected_items": list(detail.get("selected_items") or []),
                "decision_symbols": list(detail.get("decision_symbols") or []),
                "due_execution_symbols": list(detail.get("due_execution_symbols") or []),
            }
        return {}

    @staticmethod
    def _decision_rows(run: dict[str, object] | None) -> list[dict[str, object]]:
        if not run:
            return []
        rows: list[dict[str, object]] = []
        for stage in run.get("stages", []):
            if stage.get("stage") != "decision":
                continue
            detail = dict(stage.get("detail") or {})
            audit = dict(detail.get("open_gate_audit") or {})
            failed_checks = [
                str(item.get("check_id") or "")
                for item in audit.get("checks", [])
                if not bool(item.get("passed")) and str(item.get("check_id") or "")
            ]
            action = str(detail.get("action") or "").upper() or None
            rows.append({
                "symbol": stage.get("symbol"),
                "name": detail.get("name"),
                "decision_id": detail.get("decision_id"),
                "terminal_state": detail.get("terminal_state"),
                "stage_status": stage.get("status"),
                "action": action,
                "action_meaning_cn": ACTION_MEANINGS_CN.get(action or "", ""),
                "data_quality_status": detail.get("data_quality_status"),
                "open_gate_permission": audit.get("permission") if audit else None,
                "open_gate_failed_checks": failed_checks,
                "open_gate_blockers": list(audit.get("blockers") or []),
                "positive_evidence_ids": list(audit.get("positive_evidence_ids") or []),
                "candidate_rank": detail.get("candidate_rank"),
                "candidate_selection_reason": detail.get("candidate_selection_reason"),
                "ai_shadow_action": detail.get("ai_shadow_action"),
                "ai_shadow_agreement": detail.get("ai_shadow_agreement"),
                "elapsed_ms": stage.get("elapsed_ms"),
            })
        return rows

    @staticmethod
    def _execution_rows(run: dict[str, object] | None) -> list[dict[str, object]]:
        if not run:
            return []
        rows: list[dict[str, object]] = []
        for stage in run.get("stages", []):
            if stage.get("stage") != "execution":
                continue
            detail = dict(stage.get("detail") or {})
            reason = str(detail.get("reason") or "") or None
            rows.append({
                "symbol": stage.get("symbol"),
                "name": detail.get("name"),
                "decision_id": detail.get("decision_id"),
                "terminal_state": detail.get("terminal_state"),
                "stage_status": stage.get("status"),
                "action": detail.get("action"),
                "side": detail.get("side"),
                "reason": reason,
                "reason_meaning_cn": EXECUTION_REASON_MEANINGS_CN.get(reason or "", ""),
                "elapsed_ms": stage.get("elapsed_ms"),
            })
        return rows

    def snapshot(self) -> dict[str, object]:
        versions = config.audit_version_snapshot()
        latest_summary = (self.store.simulation_runs(1) or [None])[0]
        run = self.store.simulation_run(str(latest_summary["run_id"])) if latest_summary else None
        decisions = self._decision_rows(run)
        executions = self._execution_rows(run)

        action_counts = Counter(str(item.get("action") or "UNKNOWN") for item in decisions)
        failed_check_counts = Counter(
            check_id
            for item in decisions
            for check_id in item.get("open_gate_failed_checks", [])
        )
        open_gate_allowed = sum(1 for item in decisions if item.get("open_gate_permission") == "allowed")
        open_gate_blocked = sum(1 for item in decisions if item.get("open_gate_permission") == "blocked")
        open_gate_missing = sum(1 for item in decisions if not item.get("open_gate_permission"))
        execution_reason_counts = Counter(
            str(item.get("reason") or "none")
            for item in executions
            if item.get("stage_status") != "ok"
        )

        day0_blockers: list[str] = []
        day0_warnings: list[str] = []
        git_commit = str(versions.get("git_commit") or "")
        if not git_commit or git_commit == "unknown":
            day0_blockers.append("git_commit_unknown")
        if not run:
            day0_warnings.append("no_simulation_run")
        elif decisions and open_gate_missing:
            day0_warnings.append("latest_run_has_decision_without_open_gate_audit")

        return {
            "read_only": True,
            "generated_from_persisted_audit": True,
            "deployment": {
                "git_commit": git_commit or "unknown",
                "identity_ok": bool(git_commit and git_commit != "unknown"),
                "audit_versions": versions,
            },
            "day0": {
                "blockers": day0_blockers,
                "warnings": day0_warnings,
            },
            "latest_run": None if not run else {
                "run_id": run.get("run_id"),
                "trigger": run.get("trigger"),
                "started_at": run.get("started_at"),
                "finished_at": run.get("finished_at"),
                "elapsed_ms": self._elapsed_ms(run.get("started_at"), run.get("finished_at")),
                "status": run.get("status"),
                "symbol_count": run.get("symbol_count"),
                "generated": run.get("generated"),
                "executed": run.get("executed"),
                "skipped": run.get("skipped"),
                "message": run.get("message"),
            },
            "candidate_pool": self._candidate_audit(run),
            "decision_summary": {
                "action_counts": dict(sorted(action_counts.items())),
                "decision_count": len(decisions),
                "items": decisions,
            },
            "open_gate_summary": {
                "allowed": open_gate_allowed,
                "blocked": open_gate_blocked,
                "missing_audit": open_gate_missing,
                "failed_check_counts": dict(sorted(failed_check_counts.items())),
                "check_meanings_cn": CHECK_MEANINGS_CN,
            },
            "execution_summary": {
                "items": executions,
                "reason_counts": dict(sorted(execution_reason_counts.items())),
                "reason_meanings_cn": EXECUTION_REASON_MEANINGS_CN,
            },
            "provider_health": self._provider_summary(self.store.provider_health_summary()),
            "parameter_guide": {
                "actions": ACTION_MEANINGS_CN,
                "open_gate_checks": CHECK_MEANINGS_CN,
                "execution_reasons": EXECUTION_REASON_MEANINGS_CN,
                "notes": {
                    "score_percent": "数据完整度评分，不是胜率或上涨概率",
                    "policy_score": "确定性动作规则的内部优先级归一化值，不是收益概率",
                    "ai_shadow_action": "AI 研究层影子动作，仅用于比较，不参与正式执行",
                    "positive_evidence_ids": "实际命中的正式正向 POLICY 证据编号",
                    "NEXT_ELIGIBLE_OBSERVED_QUOTE": "决策日期之后下一次满足执行条件的已观察行情，不等同于下一交易日开盘价",
                },
            },
        }
