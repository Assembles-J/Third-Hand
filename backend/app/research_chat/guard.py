from __future__ import annotations
from app.decision_models import AiResearchAssessment
from app.decision_guard import DecisionGuard
from .models import ResearchModelOutput
def validate_output(output, evidence_ids, candidates):
 if not set(output.supporting_evidence_ids+output.contradicting_evidence_ids).issubset(evidence_ids):return None
 assessment=AiResearchAssessment(thesis_status=output.thesis_status if output.thesis_status in {"strengthened","unchanged","weakened","invalidated","unknown"} else "unknown",preferred_action=output.candidate_action, supporting_evidence_ids=output.supporting_evidence_ids,opposing_evidence_ids=output.contradicting_evidence_ids,missing_evidence=output.missing_evidence,uncertainty=output.model_uncertainty if output.model_uncertainty in {"low","medium","high"} else "high",summary=output.answer_summary)
 return DecisionGuard().guard(candidates,assessment)
