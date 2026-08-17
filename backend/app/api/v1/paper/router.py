"""V2-native paper scheduling diagnostics."""
from __future__ import annotations

from fastapi import APIRouter


def create_paper_schedule_router(schedule_state) -> APIRouter:
    router = APIRouter(prefix="/v1/paper-trading", tags=["paper-trading"])

    @router.get("/adaptive-plan")
    def adaptive_plan() -> dict[str, object]:
        return dict(schedule_state())

    return router
