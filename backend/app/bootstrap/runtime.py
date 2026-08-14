"""Runtime bootstrap for Third-Hand.

This module centralizes startup governance that historically lived in
``app.main``.  Architecture Refactor v2 then replaces selected legacy FastAPI
route registrations with domain-owned routers while keeping the same endpoint
callables and public behavior.
"""
from __future__ import annotations

from types import ModuleType


def load_legacy_application() -> ModuleType:
    """Install data/execution governance, migrate transport ownership, return app."""
    from app.daily_history_policy import install as install_daily_history_policy
    from app.daily_history_compat import install as install_daily_history_compat

    # Must run before app.application constructs PortfolioStore and providers.
    install_daily_history_policy()
    install_daily_history_compat()

    from app import application
    from app.paper_runtime_integration import install as install_paper_runtime_governance
    from app.api.v1.migration import install_migrated_routers

    # Paper governance patches application-level runtime functions after the
    # legacy module exists. Route extraction then re-registers the resulting
    # endpoint callables by domain without changing their implementations.
    install_paper_runtime_governance(application)
    install_migrated_routers(application)
    return application
