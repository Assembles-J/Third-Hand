"""Incremental transport migration from the legacy FastAPI assembly.

Architecture Refactor v2 moves route ownership without changing endpoint
implementations. Legacy decorators are removed from the live router table, then
the same endpoint callables are registered by domain packages, avoiding duplicate
paths while keeping URL/signature/business behavior stable.
"""
from __future__ import annotations

from types import ModuleType

from app.api.v1.admin.router import build_router as build_admin_router
from app.api.v1.ai.router import build_router as build_ai_router
from app.api.v1.app_update.router import build_router as build_app_update_router
from app.api.v1.data_quality.router import build_router as build_data_quality_router
from app.api.v1.decision.router import build_router as build_decision_router
from app.api.v1.health.router import build_router as build_health_router
from app.api.v1.paper.router import build_router as build_paper_router


_MIGRATED_PATHS = {
    "/health",
    "/v1/system/ai-capabilities",
    "/v1/app-update",
    "/v1/app-update/apk",
    "/v1/admin/overview",
    "/v1/admin/config",
    "/v1/data-quality/daily-history-attempts",
    "/v1/data-quality/provider-health",
    "/v1/data-quality/events",
    "/v1/paper-trading/account",
    "/v1/paper-trading/net-contributions",
    "/v1/paper-trading/logs",
    "/v1/paper-trading/equity-snapshots",
    "/v1/paper-trading/status",
    "/v1/paper-trading/dashboard",
    "/v1/paper-trading/runs",
    "/v1/paper-trading/runs/{run_id}",
    "/v1/paper-trading/run",
    "/v1/paper-trading/decision-audit/{decision_id}",
    "/v1/decisions/context/{symbol}",
    "/v1/decisions/generate",
    "/v1/decisions/latest",
    "/v1/decisions/jobs/{job_id}",
    "/v1/decisions",
    "/v1/decisions/{decision_id}",
    "/v1/decisions/{decision_id}/lineage",
    "/v1/decisions/evidence/{symbol}",
    "/v1/decisions/shadow/{symbol}",
}


def _remove_legacy_routes(legacy: ModuleType) -> None:
    routes = legacy.app.router.routes
    routes[:] = [route for route in routes if getattr(route, "path", None) not in _MIGRATED_PATHS]


def install_migrated_routers(legacy: ModuleType) -> None:
    """Replace selected legacy routes with domain-owned registrations once."""
    if getattr(legacy, "_V2_API_MIGRATION_INSTALLED", False):
        return

    _remove_legacy_routes(legacy)
    legacy.app.include_router(build_health_router(legacy))
    legacy.app.include_router(build_ai_router(legacy))
    legacy.app.include_router(build_app_update_router(legacy))
    legacy.app.include_router(build_admin_router(legacy))
    legacy.app.include_router(build_data_quality_router(legacy))
    legacy.app.include_router(build_paper_router(legacy))
    legacy.app.include_router(build_decision_router(legacy))
    legacy._V2_API_MIGRATION_INSTALLED = True
