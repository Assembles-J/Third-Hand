"""Read-only Decision Workspace API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException


def create_decision_workspace_router(service) -> APIRouter:
    router = APIRouter(prefix="/v1/decisions", tags=["decision-workspace"])

    @router.get("/{symbol}/workspace")
    def latest_decision_workspace(symbol: str) -> dict[str, object]:
        try:
            return service.latest(symbol)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="decision workspace not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return router


__all__ = ["create_decision_workspace_router"]
