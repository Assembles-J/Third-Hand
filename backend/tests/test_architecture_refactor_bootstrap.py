from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from fastapi.routing import APIRoute

from app.api.v1.route_ownership import owner_for_path


ROOT = Path(__file__).resolve().parents[1]


EXPECTED_MIGRATED_ROUTES = {
    ("/health", "GET"),
    ("/v1/system/ai-capabilities", "GET"),
    ("/v1/app-update", "GET"),
    ("/v1/app-update/apk", "GET"),
    ("/v1/admin/overview", "GET"),
    ("/v1/admin/config", "GET"),
    ("/v1/admin/config", "PUT"),
    ("/v1/data-quality/daily-history-attempts", "GET"),
    ("/v1/data-quality/provider-health", "GET"),
    ("/v1/data-quality/events", "GET"),
    ("/v1/paper-trading/account", "GET"),
    ("/v1/paper-trading/account", "PUT"),
    ("/v1/paper-trading/net-contributions", "PUT"),
    ("/v1/paper-trading/logs", "GET"),
    ("/v1/paper-trading/equity-snapshots", "GET"),
    ("/v1/paper-trading/status", "GET"),
    ("/v1/paper-trading/dashboard", "GET"),
    ("/v1/paper-trading/runs", "GET"),
    ("/v1/paper-trading/runs/{run_id}", "GET"),
    ("/v1/paper-trading/run", "POST"),
    ("/v1/paper-trading/decision-audit/{decision_id}", "GET"),
    ("/v1/decisions/context/{symbol}", "GET"),
    ("/v1/decisions/generate", "POST"),
    ("/v1/decisions/latest", "GET"),
    ("/v1/decisions/jobs/{job_id}", "GET"),
    ("/v1/decisions", "GET"),
    ("/v1/decisions/{decision_id}", "GET"),
    ("/v1/decisions/{decision_id}/lineage", "GET"),
    ("/v1/decisions/evidence/{symbol}", "GET"),
    ("/v1/decisions/shadow/{symbol}", "GET"),
}


def _route_pairs(runtime) -> list[tuple[str, str]]:
    return [
        (route.path, method)
        for route in runtime.app.routes
        if isinstance(route, APIRoute)
        for method in sorted(route.methods or set())
    ]


def test_main_is_only_a_small_bootstrap_alias() -> None:
    source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert len(source.splitlines()) <= 30
    assert "load_legacy_application" in source
    assert "daily_history_policy" not in source
    assert "paper_runtime_integration" not in source


def test_bootstrap_runtime_preserves_governance_import_order() -> None:
    source = (ROOT / "app" / "bootstrap" / "runtime.py").read_text(encoding="utf-8")
    policy = source.index("install_daily_history_policy()")
    compat = source.index("install_daily_history_compat()")
    application_import = source.index("from app import application")
    paper = source.index("install_paper_runtime_governance(application)")
    api_migration = source.index("install_migrated_routers(application)")
    assert policy < compat < application_import < paper < api_migration


def test_route_ownership_has_explicit_governance_domains() -> None:
    assert owner_for_path("/health") == "health"
    assert owner_for_path("/v1/admin/overview") == "admin"
    assert owner_for_path("/v1/paper-trading/run") == "paper"
    assert owner_for_path("/v1/data-quality/provider-health") == "data_quality"
    assert owner_for_path("/v1/system/ai-capabilities") == "ai"
    assert owner_for_path("/v1/feed") == "research"
    assert owner_for_path("/v1/announcements") == "research"
    assert owner_for_path("/v1/decisions/latest") == "decision"


def test_new_domain_package_does_not_depend_on_transport_or_legacy_app() -> None:
    domain_root = ROOT / "app" / "domain"
    for path in domain_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "from fastapi" not in source
        assert "import fastapi" not in source
        assert "app.application" not in source


def test_first_migrated_routes_are_registered_once_per_method() -> None:
    # Other legacy tests may reload app.application in-process. Reconcile the
    # migrated transport boundary before asserting the shared process route set.
    import app.main as runtime
    from app.api.v1.migration import install_migrated_routers

    install_migrated_routers(runtime)
    route_pairs = _route_pairs(runtime)
    for expected in EXPECTED_MIGRATED_ROUTES:
        assert route_pairs.count(expected) == 1, (expected, route_pairs)


def test_fresh_process_bootstrap_registers_migrated_routes() -> None:
    # Production Uvicorn starts from a fresh interpreter. Verify that path
    # independently from pytest's shared module/reload state.
    code = """
import json
from fastapi.routing import APIRoute
import app.main as runtime
pairs = sorted((r.path, m) for r in runtime.app.routes if isinstance(r, APIRoute) for m in (r.methods or set()))
print(json.dumps(pairs))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    pairs = {tuple(item) for item in json.loads(completed.stdout.strip().splitlines()[-1])}
    assert EXPECTED_MIGRATED_ROUTES.issubset(pairs)


def test_every_public_api_route_has_a_v2_domain_owner() -> None:
    import app.main as runtime
    from app.api.v1.migration import install_migrated_routers

    install_migrated_routers(runtime)
    routes = [route for route in runtime.app.routes if isinstance(route, APIRoute)]
    unclassified = sorted({route.path for route in routes if owner_for_path(route.path) == "unclassified"})
    assert unclassified == [], f"unclassified API routes: {unclassified}"
