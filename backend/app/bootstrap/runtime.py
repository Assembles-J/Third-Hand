"""Runtime bootstrap for Third-Hand.

This module centralizes startup governance that historically lived in
``app.main``.  It deliberately returns the existing ``app.application`` module
unchanged so PR-A1 is behavior-preserving; later PRs can replace that module with
an app factory domain by domain.
"""
from __future__ import annotations

from types import ModuleType


def load_legacy_application() -> ModuleType:
    """Install runtime governance, then return the current application module.

    Import ordering is part of the production contract: the daily-history policy
    must wrap ``PortfolioStore`` before ``app.application`` constructs its
    singletons, and paper runtime governance must be installed after the module
    exists.
    """
    from app.daily_history_policy import install as install_daily_history_policy
    from app.daily_history_compat import install as install_daily_history_compat

    install_daily_history_policy()
    install_daily_history_compat()

    from app import application
    from app.paper_runtime_integration import install as install_paper_runtime_governance

    install_paper_runtime_governance(application)
    return application
