"""Read-only admin diagnostics HTTP endpoints."""
from __future__ import annotations

from fastapi import APIRouter


def create_admin_diagnostics_router(service) -> APIRouter:
    router = APIRouter(prefix="/v1/admin", tags=["admin-diagnostics"])

    @router.get("/day0-diagnostics")
    def day0_diagnostics() -> dict[str, object]:
        """Return redacted production Day-0 diagnostics from persisted audit data."""
        return service.snapshot()

    return router
