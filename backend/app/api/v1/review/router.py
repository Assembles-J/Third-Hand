"""PUX2 ReviewPlan read/request routes.

Both routes are local-only. Requesting a full review records research permission;
it does not inject formal candidate membership or execute a paper trade.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.v1.review.schemas import ReviewPlanResponse
from app.domain.personal_universe import ReviewMode, ReviewPlan
from app.time_utils import beijing_now


def create_review_router(service) -> APIRouter:
    router = APIRouter(tags=["review-plan"])

    @router.get("/v1/review-plan/{symbol}", response_model=ReviewPlanResponse)
    def latest_review_plan(symbol: str) -> ReviewPlanResponse:
        plan = service.latest(symbol)
        if plan is None:
            raise HTTPException(status_code=404, detail="尚无可用 ReviewPlan")
        return _response(plan)

    @router.post("/v1/review-plan/{symbol}/request", response_model=ReviewPlanResponse)
    def request_full_review(symbol: str) -> ReviewPlanResponse:
        try:
            plan = service.request_full_review(symbol, evaluated_at=beijing_now())
        except LookupError as error:
            raise HTTPException(status_code=404, detail="标的不在当前 Portfolio / Watchlist") from error
        return _response(plan)

    return router


def _response(plan: ReviewPlan) -> ReviewPlanResponse:
    return ReviewPlanResponse(
        policy_version=plan.policy_version,
        symbol=plan.symbol,
        evaluated_at=plan.evaluated_at,
        review_mode=plan.mode.value,
        analysis_depth=plan.analysis_depth.value,
        reason_codes=plan.reason_codes,
        last_review_at=plan.last_review_at,
        next_review_at=plan.next_review_at,
        routine_full_research_available=plan.routine_full_research_available,
        budget_override=plan.budget_override,
        ai_call_allowed=plan.mode in {ReviewMode.POSITION_REVIEW, ReviewMode.FULL_RESEARCH},
    )
