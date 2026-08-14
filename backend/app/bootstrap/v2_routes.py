"""Register v2-native services/routers on the legacy FastAPI shell during migration.

Unlike the rejected route-table rewrite experiment, this module only adds new,
non-conflicting v2 endpoints and service seams. Dependencies are injected from
bootstrap so the new API/domain layers never import the quarantined legacy
application module.
"""
from __future__ import annotations

from app.api.v1.candidate.router import create_candidate_router
from app.application_services.candidate.service import CandidateService
from app.application_services.research.data_gateway import ResearchDataGateway
from app.infrastructure.database.candidate_repository import CandidateRepository
from app.infrastructure.database.research_data_repository import ResearchDataRepository


def register_v2_routes(application) -> None:
    # Service seams are idempotently attached regardless of whether a previous
    # test/reload already registered the candidate router.
    if not hasattr(application, "research_data_gateway_v2"):
        research_repository = ResearchDataRepository(application.store)
        application.research_data_repository_v2 = research_repository
        application.research_data_gateway_v2 = ResearchDataGateway(research_repository)

    existing_paths = {getattr(route, "path", None) for route in application.app.routes}
    if "/v1/candidates" in existing_paths:
        return

    repository = CandidateRepository(application.store)
    service = CandidateService(repository)
    application.app.include_router(create_candidate_router(service))
    # Expose these only as bootstrap-owned integration handles for tests/admin
    # diagnostics; v2 modules themselves never import the legacy module.
    application.candidate_repository_v2 = repository
    application.candidate_service_v2 = service
