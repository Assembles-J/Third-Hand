"""Wire schemas for governed PUX2 ReviewPlan observability."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


ReviewModeValue = Literal["NO_REVIEW", "GUARD_ONLY", "POSITION_REVIEW", "FULL_RESEARCH"]
AnalysisDepthValue = Literal["NONE", "GUARDS", "POSITION", "FULL"]


class ReviewPlanResponse(BaseModel):
    policy_version: str
    symbol: str
    evaluated_at: datetime
    review_mode: ReviewModeValue
    analysis_depth: AnalysisDepthValue
    reason_codes: tuple[str, ...]
    last_review_at: datetime | None = None
    next_review_at: datetime | None = None
    routine_full_research_available: bool
    budget_override: bool
    ai_call_allowed: bool
