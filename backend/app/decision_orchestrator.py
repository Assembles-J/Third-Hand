"""End-to-end auditable decision orchestration; never executes trades."""
from __future__ import annotations

import logging
from uuid import uuid4

from app import decision_config as config
from app.decision_ai import DecisionAiOutcome
from app.decision_models import DecisionReport, OperationItem
from app.time_utils import beijing_now

logger = logging.getLogger(__name__)


class DecisionOrchestrator:
    def __init__(self, evidence_engine, policy_engine, sizing_engine, ai_service, guard) -> None:
        self.evidence_engine, self.policy_engine = evidence_engine, policy_engine
        self.sizing_engine, self.ai_service, self.guard = sizing_engine, ai_service, guard

    def generate(self, context) -> DecisionReport:
        evidence = self.evidence_engine.build(context)
        candidates = self.policy_engine.evaluate(context, evidence)
        if config.DECISION_AI_ENABLED:
            logger.info(
                "Decision AI dispatch context_id=%s symbol=%s evidence_count=%s candidate_actions=%s",
                context.context_id,
                context.symbol,
                len(evidence),
                ",".join(candidate.action for candidate in candidates),
            )
            ai_outcome = self.ai_service.assess(context, evidence, candidates)
        else:
            logger.warning(
                "Decision AI disabled context_id=%s symbol=%s code=feature_disabled",
                context.context_id,
                context.symbol,
            )
            ai_outcome = DecisionAiOutcome(None, "disabled", "feature_disabled")
        assessment = self.guard.guard(candidates, ai_outcome.assessment)
        action = candidates[0].action
        sizing = self.sizing_engine.size(context, action) if config.DECISION_SIZING_ENABLED else None
        status = "BLOCKED" if context.data_quality.status == "blocked" else "DEGRADED" if context.data_quality.status == "degraded" else "READY"
        return DecisionReport(decision_id=str(uuid4()), context_id=context.context_id, symbol=context.symbol, generated_at=beijing_now(), status=status, action=action, summary=self._summary(action, candidates[0].blocked_reasons), evidence=evidence, action_candidates=candidates, operation_items=self._operation_items(context, action, candidates[0].blocked_reasons, sizing), ai_assessment=assessment, ai_status=ai_outcome.status, ai_error_code=ai_outcome.error_code, market_price=context.quote.price if context.quote else None, market_change_percent=context.quote.change_percent if context.quote else None, market_as_of=context.quote.as_of if context.quote else None, sizing=sizing, policy_version=self.policy_engine.version, prompt_version=config.DECISION_RESEARCH_PROMPT_VERSION if assessment else None, model=ai_outcome.model, input_hash=context.input_hash)

    @staticmethod
    def _operation_items(context, action, candidate_blockers, sizing) -> tuple[OperationItem, ...]:
        plan = context.trade_plan
        quote_price = context.quote.price if context.quote else None
        sizing_blockers = tuple(sizing.blocked_reasons) if sizing else ()
        blockers = tuple(dict.fromkeys((*candidate_blockers, *sizing_blockers)))
        if blockers:
            return (OperationItem(kind="COMPLETE", title="先补全执行条件", trigger="完成下列必填项后重新生成工作台", status="needs_input", blockers=blockers),)
        condition_by_action = {
            "OPEN": getattr(plan, "entry_condition", ""),
            "ADD": getattr(plan, "add_condition", ""),
            "REDUCE": getattr(plan, "reduce_condition", ""),
            "EXIT": getattr(plan, "exit_condition", ""),
        }
        title_by_action = {"OPEN": "建立仓位", "ADD": "满足条件后加仓", "REDUCE": "满足条件后减仓", "EXIT": "满足条件后退出", "HOLD": "继续持有", "WATCH": "继续观察"}
        trigger = condition_by_action.get(action) or "当前无需执行交易；等待下一次规则或行情触发。"
        return (OperationItem(
            kind=action,
            title=title_by_action.get(action, "暂不操作"),
            trigger=trigger,
            reference_price=quote_price,
            invalidation_price=getattr(plan, "invalidation_price", None),
            suggested_quantity=getattr(sizing, "suggested_quantity", None),
            target_quantity=getattr(sizing, "target_quantity", None),
            status="ready",
        ),)

    @staticmethod
    def _summary(action, blocked_reasons) -> str:
        if action == "BLOCKED":
            return "关键输入尚未齐备，暂不生成操作结论。请完成“解除阻断”中的项目后重新分析。"
        labels = {
            "OPEN": "已形成建立仓位候选，仍需核验计划条件和风险约束。",
            "ADD": "已形成加仓候选，仍需遵守仓位和风险约束。",
            "HOLD": "当前规则倾向持有，继续跟踪关键证据和交易计划条件。",
            "WATCH": "当前以观察为主，等待数据或交易计划条件进一步确认。",
            "REDUCE": "风险或仓位证据触发复核，建议结合交易计划审查减仓条件。",
            "EXIT": "退出条件触发复核，建议核验交易计划与最新事实后处理。",
        }
        return labels.get(action, "本次报告已生成，请结合证据和数据状态进行复核。")
