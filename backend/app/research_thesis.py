"""Versioned, read-only thesis records derived from validated research reports."""
from __future__ import annotations

from uuid import uuid4

from app.decision_models import ResearchCatalyst, ResearchReport, ThesisVersion
from app.time_utils import beijing_now


class ResearchThesisService:
    """Stores evidence-bound research hypotheses; it never produces a trade action."""

    @staticmethod
    def create(report: ResearchReport, thesis_id: str | None = None, prior: ThesisVersion | None = None) -> ThesisVersion:
        hypotheses = tuple(claim for claim in report.claims if claim.evidence_type in {"INFERENCE", "HYPOTHESIS", "UNKNOWN"})
        catalysts = tuple(
            ResearchCatalyst(
                catalyst_id=f"catalyst.{claim.claim_id}", title=claim.statement,
                source_evidence_ids=claim.supporting_evidence_ids, status="observed",
            )
            for claim in report.claims if claim.evidence_type == "FACT"
        )
        conditions = tuple(dict.fromkeys(condition for claim in report.claims for condition in claim.invalidation_conditions))
        return ThesisVersion(
            thesis_id=thesis_id or str(uuid4()), version=(prior.version + 1) if prior else 1,
            symbol=report.symbol, report_id=report.report_id,
            prior_version_id=f"{prior.thesis_id}:{prior.version}" if prior else None,
            created_at=beijing_now(), hypotheses=hypotheses, catalysts=catalysts,
            invalidation_conditions=conditions,
            review_status="review_required" if hypotheses else "insufficient_evidence",
        )

    @staticmethod
    def review_summary(previous: ThesisVersion, current: ThesisVersion) -> dict[str, object]:
        prior_ids = {item for claim in previous.hypotheses for item in claim.supporting_evidence_ids + claim.counter_evidence_ids}
        current_ids = {item for claim in current.hypotheses for item in claim.supporting_evidence_ids + claim.counter_evidence_ids}
        return {
            "thesis_id": current.thesis_id, "previous_version": previous.version, "current_version": current.version,
            "new_evidence_ids": sorted(current_ids - prior_ids), "removed_evidence_ids": sorted(prior_ids - current_ids),
            "review_status": current.review_status,
            "note": "仅提示需要复核；系统不会自动判定 Thesis 加强、削弱或生成交易动作。",
        }
