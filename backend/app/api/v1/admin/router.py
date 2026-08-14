"""Admin route ownership for Architecture Refactor v2."""
from __future__ import annotations

from types import ModuleType

from fastapi import APIRouter


def build_router(legacy: ModuleType) -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/v1/admin/overview",
        legacy.admin_overview,
        methods=["GET"],
        response_model=legacy.AdminOverview,
    )
    router.add_api_route(
        "/v1/admin/config",
        legacy.admin_config,
        methods=["GET"],
        response_model=legacy.SystemConfig,
    )
    router.add_api_route(
        "/v1/admin/config",
        legacy.save_admin_config,
        methods=["PUT"],
        response_model=legacy.SystemConfig,
    )
    return router
