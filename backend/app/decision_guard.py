"""Prevent AI research output from bypassing deterministic policy candidates."""
from __future__ import annotations

from app.decision_models import ActionCandidate, AiResearchAssessment


class DecisionGuard:
    def guard(self, candidates: tuple[ActionCandidate, ...], assessment: AiResearchAssessment | None) -> AiResearchAssessment | None:
        if assessment is None:
            return None
        allowed = {candidate.action for candidate in candidates}
        if assessment.preferred_action not in allowed:
            return None
        if candidates and candidates[0].action == "BLOCKED" and assessment.preferred_action != "BLOCKED":
            return None
        return assessment
