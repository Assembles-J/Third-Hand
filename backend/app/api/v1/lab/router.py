"""N3 Lab HTTP routes.

All endpoints are GET-only projections of persisted Evaluation state. The router
never resolves outcomes, refreshes data, mutates experiment state, or invokes
trading authority.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.lab.schemas import (
    LabBreakdownResponse,
    LabCompareResponse,
    LabExperimentDetailResponse,
    LabExperimentListResponse,
    LabOutcomesResponse,
    LabPerformanceResponse,
    LabSummaryResponse,
)


def create_lab_router(service) -> APIRouter:
    router = APIRouter(prefix="/v1/lab", tags=["strategy-evaluation"])

    def translate_error(error: Exception) -> None:
        if isinstance(error, KeyError):
            raise HTTPException(status_code=404, detail="experiment not found") from error
        if isinstance(error, ValueError):
            raise HTTPException(status_code=422, detail=str(error)) from error
        raise error

    @router.get("/experiments", response_model=LabExperimentListResponse)
    def list_experiments(
        strategy_id: str | None = Query(default=None),
        experiment_type: str | None = Query(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> LabExperimentListResponse:
        try:
            return LabExperimentListResponse.model_validate(service.list_experiments(
                strategy_id=strategy_id,
                experiment_type=experiment_type,
                status=status,
                limit=limit,
            ))
        except Exception as error:
            translate_error(error)
            raise AssertionError("unreachable")

    @router.get("/compare", response_model=LabCompareResponse)
    def compare_experiments(
        ids: list[str] = Query(..., min_length=2, max_length=8),
    ) -> LabCompareResponse:
        try:
            return LabCompareResponse.model_validate(service.compare(tuple(ids)))
        except Exception as error:
            translate_error(error)
            raise AssertionError("unreachable")

    @router.get("/experiments/{experiment_id}", response_model=LabExperimentDetailResponse)
    def experiment_detail(
        experiment_id: str,
        version: str | None = Query(default=None),
    ) -> LabExperimentDetailResponse:
        try:
            return LabExperimentDetailResponse.model_validate(service.detail(experiment_id, version))
        except Exception as error:
            translate_error(error)
            raise AssertionError("unreachable")

    @router.get("/experiments/{experiment_id}/summary", response_model=LabSummaryResponse)
    def experiment_summary(
        experiment_id: str,
        version: str | None = Query(default=None),
    ) -> LabSummaryResponse:
        try:
            return LabSummaryResponse.model_validate(service.summary(experiment_id, version))
        except Exception as error:
            translate_error(error)
            raise AssertionError("unreachable")

    @router.get("/experiments/{experiment_id}/outcomes", response_model=LabOutcomesResponse)
    def experiment_outcomes(
        experiment_id: str,
        version: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> LabOutcomesResponse:
        try:
            return LabOutcomesResponse.model_validate(service.outcomes(
                experiment_id,
                version,
                limit=limit,
            ))
        except Exception as error:
            translate_error(error)
            raise AssertionError("unreachable")

    @router.get("/experiments/{experiment_id}/performance", response_model=LabPerformanceResponse)
    def experiment_performance(
        experiment_id: str,
        version: str | None = Query(default=None),
    ) -> LabPerformanceResponse:
        try:
            return LabPerformanceResponse.model_validate(service.performance(experiment_id, version))
        except Exception as error:
            translate_error(error)
            raise AssertionError("unreachable")

    @router.get("/experiments/{experiment_id}/breakdown", response_model=LabBreakdownResponse)
    def experiment_breakdown(
        experiment_id: str,
        version: str | None = Query(default=None),
    ) -> LabBreakdownResponse:
        try:
            return LabBreakdownResponse.model_validate(service.breakdown(experiment_id, version))
        except Exception as error:
            translate_error(error)
            raise AssertionError("unreachable")

    return router


__all__ = ["create_lab_router"]
