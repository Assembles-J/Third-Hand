"""AI-system route ownership for Architecture Refactor v2."""
from __future__ import annotations

from types import ModuleType

from fastapi import APIRouter


def build_router(legacy: ModuleType) -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/v1/system/ai-capabilities",
        legacy.ai_capabilities,
        methods=["GET"],
    )
    return router
