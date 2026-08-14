"""Formal decision route ownership for Architecture Refactor v2."""
from __future__ import annotations

from types import ModuleType

from fastapi import APIRouter


def build_router(legacy: ModuleType) -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/v1/decisions/context/{symbol}",
        legacy.decision_context,
        methods=["GET"],
        response_model=legacy.DecisionContext,
    )
    router.add_api_route(
        "/v1/decisions/generate",
        legacy.generate_decisions,
        methods=["POST"],
    )
    router.add_api_route(
        "/v1/decisions/latest",
        legacy.latest_decision,
        methods=["GET"],
    )
    router.add_api_route(
        "/v1/decisions/jobs/{job_id}",
        legacy.decision_job_status,
        methods=["GET"],
    )
    router.add_api_route(
        "/v1/decisions",
        legacy.decision_history,
        methods=["GET"],
    )
    router.add_api_route(
        "/v1/decisions/{decision_id}",
        legacy.decision_detail,
        methods=["GET"],
    )
    router.add_api_route(
        "/v1/decisions/{decision_id}/lineage",
        legacy.decision_lineage,
        methods=["GET"],
    )
    router.add_api_route(
        "/v1/decisions/evidence/{symbol}",
        legacy.decision_evidence,
        methods=["GET"],
    )
    router.add_api_route(
        "/v1/decisions/shadow/{symbol}",
        legacy.decision_shadow_report,
        methods=["GET"],
        response_model=legacy.ShadowDecisionReport,
    )
    return router
