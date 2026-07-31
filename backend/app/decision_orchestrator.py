"""End-to-end auditable decision orchestration; never executes trades."""
from __future__ import annotations

from uuid import uuid4

from app import decision_config as config
from app.decision_models import DecisionReport
from app.time_utils import beijing_now


class DecisionOrchestrator:
    def __init__(self, evidence_engine, policy_engine, sizing_engine, ai_service, guard) -> None:
        self.evidence_engine, self.policy_engine = evidence_engine, policy_engine
        self.sizing_engine, self.ai_service, self.guard = sizing_engine, ai_service, guard

    def generate(self, context) -> DecisionReport:
        evidence = self.evidence_engine.build(context)
        candidates = self.policy_engine.evaluate(context, evidence)
        assessment = self.ai_service.assess(context, evidence, candidates) if config.DECISION_AI_ENABLED else None
        assessment = self.guard.guard(candidates, assessment)
        action = candidates[0].action
        sizing = self.sizing_engine.size(context, action) if config.DECISION_SIZING_ENABLED else None
        status = "BLOCKED" if context.data_quality.status == "blocked" else "DEGRADED" if context.data_quality.status == "degraded" else "READY"
        return DecisionReport(decision_id=str(uuid4()), context_id=context.context_id, symbol=context.symbol, generated_at=beijing_now(), status=status, action=action, summary=self._summary(action, candidates[0].blocked_reasons), evidence=evidence, action_candidates=candidates, ai_assessment=assessment, sizing=sizing, policy_version=self.policy_engine.version, prompt_version=config.DECISION_RESEARCH_PROMPT_VERSION if assessment else None, input_hash=context.input_hash)

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
