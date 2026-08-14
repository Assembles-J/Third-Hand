"""Application-update route ownership for Architecture Refactor v2."""
from __future__ import annotations

from types import ModuleType

from fastapi import APIRouter
from fastapi.responses import FileResponse


def build_router(legacy: ModuleType) -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/v1/app-update/apk",
        legacy.download_app_update,
        methods=["GET"],
        response_class=FileResponse,
        responses={404: {"description": "Release APK not found"}},
    )
    router.add_api_route(
        "/v1/app-update",
        legacy.app_update,
        methods=["GET"],
        response_model=legacy.AppUpdate,
        responses={204: {"description": "No update configured"}},
    )
    return router
