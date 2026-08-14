"""Register v2-native routers on the legacy FastAPI shell during migration.

Unlike the rejected route-table rewrite experiment, this module only adds new,
non-conflicting v2 endpoints.  Dependencies are injected from bootstrap so the
new API/domain layers never import the quarantined legacy application module.
"""
from __future__ import annotations

from app.api.v1.candidate.router import create_candidate_router
from app.application_services.candidate.service import CandidateService
from app.infrastructure.database.candidate_repository import CandidateRepository


def register_v2_routes(application) -> None:
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
