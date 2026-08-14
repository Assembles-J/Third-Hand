"""Runtime bootstrap for Third-Hand.

Architecture Refactor v2 keeps startup governance outside the historical API
monolith.  The monolith is now quarantined under ``app.legacy`` and may only
shrink while replacement domains are built and verified.
"""
from __future__ import annotations

from types import ModuleType


def load_legacy_application() -> ModuleType:
    """Install runtime governance, then load the quarantined legacy assembly.

    Import ordering is part of the production contract: daily-history policy and
    compatibility hooks must wrap PortfolioStore/provider classes before the
    legacy module constructs its singletons. Paper runtime governance then
    patches that exact module object so route-function globals see the governed
    implementations.
    """
    from app.daily_history_policy import install as install_daily_history_policy
    from app.daily_history_compat import install as install_daily_history_compat

    install_daily_history_policy()
    install_daily_history_compat()

    from app.legacy import application_legacy as application
    from app.paper_runtime_integration import install as install_paper_runtime_governance

    install_paper_runtime_governance(application)
    return application
