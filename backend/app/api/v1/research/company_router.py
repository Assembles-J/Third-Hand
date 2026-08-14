"""Company Intelligence research API.

The router exposes research requirements and persisted CompanyContext snapshots.
It does not expose a trade/open endpoint and every assembled context remains
RESEARCH_ONLY.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.research.company_schemas import CompanyContextBuildRequest


def create_company_intelligence_router(service) -> APIRouter:
    router = APIRouter(prefix="/v1/company-intelligence", tags=["company-research"])

    def translate_error(error: Exception) -> None:
        if isinstance(error, KeyError):
            raise HTTPException(status_code=404, detail="company context not found") from error
        if isinstance(error, ValueError):
            raise HTTPException(status_code=422, detail=str(error)) from error
        raise error

    @router.get("/{symbol}/requirements")
    def company_requirements(
        symbol: str,
        research_priority: str | None = Query(default=None),
    ) -> dict[str, object]:
        try:
            return service.requirements(symbol, research_priority=research_priority)
        except Exception as error:
            translate_error(error)
            return {}

    @router.post("/{symbol}/build")
    def build_company_context(symbol: str, payload: CompanyContextBuildRequest) -> dict[str, object]:
        try:
            return service.build_context(symbol, **payload.model_dump())
        except Exception as error:
            translate_error(error)
            return {}

    @router.get("/{symbol}")
    def latest_company_context(symbol: str) -> dict[str, object]:
        try:
            return service.latest_context(symbol)
        except Exception as error:
            translate_error(error)
            return {}

    return router
