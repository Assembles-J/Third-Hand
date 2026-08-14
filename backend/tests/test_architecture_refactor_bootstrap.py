from __future__ import annotations

from pathlib import Path

from fastapi.routing import APIRoute

from app.api.v1.route_ownership import owner_for_path


ROOT = Path(__file__).resolve().parents[1]


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
    assert policy < compat < application_import < paper
    assert "install_migrated_routers" not in source


def test_route_ownership_has_explicit_governance_domains() -> None:
    assert owner_for_path("/health") == "health"
    assert owner_for_path("/v1/admin/overview") == "admin"
    assert owner_for_path("/v1/paper-trading/run") == "paper"
    assert owner_for_path("/v1/data-quality/provider-health") == "data_quality"
    assert owner_for_path("/v1/system/ai-capabilities") == "ai"
    assert owner_for_path("/v1/feed") == "research"
    assert owner_for_path("/v1/announcements") == "research"
    assert owner_for_path("/v1/decisions/latest") == "decision"
    assert owner_for_path("/v1/market/history/600519") == "market"
    assert owner_for_path("/v1/holdings") == "portfolio"


def test_new_domain_package_does_not_depend_on_transport_or_legacy_app() -> None:
    domain_root = ROOT / "app" / "domain"
    for path in domain_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "from fastapi" not in source
        assert "import fastapi" not in source
        assert "app.application" not in source


def test_every_public_api_route_has_a_v2_domain_owner() -> None:
    # The existing route table is still authoritative in PR-A1. This inventory
    # test turns the live OpenAPI surface into the migration ledger: any route
    # added without a v2 domain assignment fails CI instead of disappearing in
    # the legacy application monolith.
    import app.main as runtime

    routes = [route for route in runtime.app.routes if isinstance(route, APIRoute)]
    unclassified = sorted({route.path for route in routes if owner_for_path(route.path) == "unclassified"})
    assert unclassified == [], f"unclassified API routes: {unclassified}"
