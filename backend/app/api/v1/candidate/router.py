"""Candidate Management HTTP API.

These endpoints control research scheduling only. No endpoint in this router can
submit a formal trade, alter ActionPolicy or invoke PositionSizing.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.candidate.schemas import (
    CandidateActivationRuleEnabledRequest,
    CandidateActivationRuleRequest,
    CandidateAnalysisResultRequest,
    CandidateAnalysisStartRequest,
    CandidateCreateRequest,
    CandidatePriorityRequest,
    CandidateTransitionRequest,
)


def create_candidate_router(service) -> APIRouter:
    router = APIRouter(prefix="/v1/candidates", tags=["candidate-research"])

    def translate_error(error: Exception) -> None:
        if isinstance(error, KeyError):
            raise HTTPException(status_code=404, detail="candidate or rule not found") from error
        if isinstance(error, ValueError):
            raise HTTPException(status_code=422, detail=str(error)) from error
        raise error

    @router.get("")
    def list_candidates(
        lifecycle_status: str | None = Query(default=None),
        research_priority: str | None = Query(default=None),
        include_archived: bool = Query(default=False),
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> list[dict[str, object]]:
        try:
            return service.list(
                lifecycle_status=lifecycle_status,
                research_priority=research_priority,
                include_archived=include_archived,
                limit=limit,
            )
        except Exception as error:
            translate_error(error)
            return []

    @router.post("")
    def add_manual_candidate(payload: CandidateCreateRequest) -> dict[str, object]:
        try:
            return service.add_manual_candidate(**payload.model_dump())
        except Exception as error:
            translate_error(error)
            return {}

    @router.get("/{symbol}")
    def candidate_detail(symbol: str) -> dict[str, object]:
        try:
            return service.get(symbol)
        except Exception as error:
            translate_error(error)
            return {}

    @router.put("/{symbol}/lifecycle")
    def transition_candidate(symbol: str, payload: CandidateTransitionRequest) -> dict[str, object]:
        try:
            return service.transition(symbol, **payload.model_dump())
        except Exception as error:
            translate_error(error)
            return {}

    @router.put("/{symbol}/priority")
    def change_candidate_priority(symbol: str, payload: CandidatePriorityRequest) -> dict[str, object]:
        try:
            return service.change_priority(symbol, **payload.model_dump())
        except Exception as error:
            translate_error(error)
            return {}

    @router.post("/{symbol}/activation-rules")
    def add_activation_rule(symbol: str, payload: CandidateActivationRuleRequest) -> dict[str, object]:
        try:
            return service.add_activation_rule(symbol, **payload.model_dump())
        except Exception as error:
            translate_error(error)
            return {}

    @router.put("/{symbol}/activation-rules/{rule_id}")
    def set_activation_rule_enabled(
        symbol: str,
        rule_id: str,
        payload: CandidateActivationRuleEnabledRequest,
    ) -> dict[str, object]:
        try:
            return service.set_activation_rule_enabled(symbol, rule_id, enabled=payload.enabled)
        except Exception as error:
            translate_error(error)
            return {}

    @router.get("/{symbol}/analysis-readiness")
    def analysis_readiness(symbol: str) -> dict[str, object]:
        try:
            return service.analysis_readiness(symbol)
        except Exception as error:
            translate_error(error)
            return {}

    @router.post("/{symbol}/analysis/start")
    def start_analysis(symbol: str, payload: CandidateAnalysisStartRequest) -> dict[str, object]:
        """Enter ANALYZING only after lifecycle/cooldown readiness passes."""
        try:
            return service.start_analysis(symbol, reason=payload.reason)
        except Exception as error:
            translate_error(error)
            return {}

    @router.post("/{symbol}/analysis-result")
    def record_analysis_result(symbol: str, payload: CandidateAnalysisResultRequest) -> dict[str, object]:
        """Persist a completed deep-research result/cooldown contract.

        This is an integration seam for the later Research AI worker. It stores
        research lifecycle state only and cannot emit/override a formal action.
        """
        try:
            return service.record_analysis_result(symbol, **payload.model_dump())
        except Exception as error:
            translate_error(error)
            return {}

    return router
