"""Data-quality route ownership for Architecture Refactor v2."""
from __future__ import annotations

from types import ModuleType

from fastapi import APIRouter


def build_router(legacy: ModuleType) -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/v1/data-quality/daily-history-attempts",
        legacy.daily_history_provider_attempts,
        methods=["GET"],
    )
    router.add_api_route(
        "/v1/data-quality/provider-health",
        legacy.data_provider_health,
        methods=["GET"],
    )
    return router
