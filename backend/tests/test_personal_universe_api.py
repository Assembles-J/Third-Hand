from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI

from app.api.v1.personal_universe.router import create_personal_universe_router
from app.api.v1.route_ownership import owner_for_path
from app.bootstrap.v2_routes import register_personal_universe_routes


ROOT = Path(__file__).resolve().parents[1]


class _Service:
    def build(self):
        return []


class _Repository:
    pass


def test_personal_universe_routes_are_registered_with_explicit_ownership() -> None:
    """Verify production startup wiring, route factory contract and idempotency."""
    runtime_source = (ROOT / "app" / "bootstrap" / "runtime.py").read_text(encoding="utf-8")
    assert "from app.bootstrap.v2_routes import register_v2_routes" in runtime_source
    assert "register_v2_routes(application)" in runtime_source
    assert owner_for_path("/v1/personal-universe") == "personal_universe"
    assert owner_for_path("/v1/watchlist/01810") == "portfolio"

    router = create_personal_universe_router(_Service(), _Repository())
    methods_by_path: dict[str, set[str]] = {}
    for route in router.routes:
        path = getattr(route, "path", None)
        if path is None:
            continue
        methods_by_path.setdefault(path, set()).update(getattr(route, "methods", set()) or set())

    assert "GET" in methods_by_path["/v1/personal-universe"]
    assert "PUT" in methods_by_path["/v1/watchlist/{symbol}"]

    application = SimpleNamespace(app=FastAPI(), store=object())
    initial_count = len(application.app.routes)
    register_personal_universe_routes(application)
    first_count = len(application.app.routes)
    first_repository = application.personal_universe_repository_v2
    first_service = application.personal_universe_service_v2

    register_personal_universe_routes(application)

    assert first_count > initial_count
    assert len(application.app.routes) == first_count
    assert application._personal_universe_routes_registered_v2 is True
    assert application.personal_universe_repository_v2 is first_repository
    assert application.personal_universe_service_v2 is first_service
