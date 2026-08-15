"""Register v2-native services/routers on the legacy FastAPI shell during migration.

Unlike the rejected route-table rewrite experiment, this module only adds new,
non-conflicting v2 endpoints and service seams. Dependencies are injected from
bootstrap so the new API/domain layers never import the quarantined legacy
application module.
"""
from __future__ import annotations

from app.api.v1.admin.router import create_admin_diagnostics_router
from app.api.v1.candidate.router import create_candidate_router
from app.application_services.admin.day0_diagnostics import Day0DiagnosticsService
from app.application_services.candidate.service import CandidateService
from app.application_services.research.data_gateway import ResearchDataGateway
from app.infrastructure.database.candidate_repository import CandidateRepository
from app.infrastructure.database.research_data_repository import ResearchDataRepository


def register_v2_routes(application) -> None:
    if not hasattr(application, "research_data_gateway_v2"):
        research_repository = ResearchDataRepository(application.store)
        application.research_data_repository_v2 = research_repository
        application.research_data_gateway_v2 = ResearchDataGateway(research_repository)

    if not hasattr(application, "candidate_service_v2"):
        repository = CandidateRepository(application.store)
        application.candidate_repository_v2 = repository
        application.candidate_service_v2 = CandidateService(repository)

    if not hasattr(application, "day0_diagnostics_service_v2"):
        application.day0_diagnostics_service_v2 = Day0DiagnosticsService(application.store)

    existing_paths = {getattr(route, "path", None) for route in application.app.routes}
    if "/v1/candidates" not in existing_paths:
        application.app.include_router(create_candidate_router(application.candidate_service_v2))
    if "/v1/admin/day0-diagnostics" not in existing_paths:
        application.app.include_router(create_admin_diagnostics_router(application.day0_diagnostics_service_v2))
