"""Deterministic, read-only research report built from canonical evidence."""
from __future__ import annotations

from uuid import uuid4

from app.decision_models import ResearchClaim, ResearchReport
from app.time_utils import beijing_now


class ResearchReportBuilder:
    """Creates claims but never emits a trade action, price, or quantity."""

    def __init__(self, evidence_engine) -> None:
        self.evidence_engine = evidence_engine

    def build(self, context) -> ResearchReport:
        evidence = self.evidence_engine.build(context)
        ids = {item.evidence_id for item in evidence}
        positive = tuple(item.evidence_id for item in evidence if item.direction == "positive")
        negative = tuple(item.evidence_id for item in evidence if item.direction == "negative")
        claims: list[ResearchClaim] = []
        if positive or negative:
            claims.append(ResearchClaim(
                claim_id="research.market_observation", evidence_type="INFERENCE",
                statement="当前可用证据同时包含支持与风险信号，应结合后续事实持续复核。",
                supporting_evidence_ids=positive, counter_evidence_ids=negative,
                missing_evidence=tuple(context.data_quality.missing_fields),
                invalidation_conditions=("出现更新的正式公告、行情或风险数据后重新生成研究报告。",),
                confidence_band="medium" if context.data_quality.status == "ready" else "low",
            ))
        for item in evidence:
            if item.category == "event":
                claims.append(ResearchClaim(
                    claim_id=f"research.event.{item.evidence_id}", evidence_type="FACT",
                    statement=item.description, supporting_evidence_ids=(item.evidence_id,),
                    missing_evidence=(), counter_evidence_ids=(),
                    invalidation_conditions=("以正式公告或来源更新为准。",),
                    confidence_band="medium" if item.fresh else "low",
                ))
        if not claims:
            claims.append(ResearchClaim(
                claim_id="research.insufficient_evidence", evidence_type="UNKNOWN",
                statement="当前没有足够的结构化支持或反对证据形成研究判断。",
                missing_evidence=tuple(context.data_quality.missing_fields or context.data_quality.warnings),
                invalidation_conditions=("补齐新的可追溯数据后重新生成研究报告。",), confidence_band="low",
            ))
        self._validate(claims, ids)
        status = "blocked" if context.data_quality.status == "blocked" else "degraded" if context.data_quality.status == "degraded" else "ready"
        return ResearchReport(report_id=str(uuid4()), context_id=context.context_id, symbol=context.symbol,
                              generated_at=beijing_now(), evidence=evidence, claims=tuple(claims),
                              data_quality=context.data_quality, report_status=status, input_hash=context.input_hash)

    @staticmethod
    def _validate(claims, known_ids: set[str]) -> None:
        for claim in claims:
            referenced = set(claim.supporting_evidence_ids) | set(claim.counter_evidence_ids)
            if not referenced.issubset(known_ids):
                raise ValueError("research_claim_unknown_evidence")
            if claim.evidence_type == "FACT" and not claim.supporting_evidence_ids:
                raise ValueError("research_fact_requires_evidence")
            if claim.evidence_type in {"INFERENCE", "HYPOTHESIS"} and not (claim.counter_evidence_ids or claim.missing_evidence):
                raise ValueError("research_inference_requires_counter_or_missing")
