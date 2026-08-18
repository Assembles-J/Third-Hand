"""Runtime bootstrap for Third-Hand.

Architecture Refactor v2 keeps startup governance outside the historical API
monolith. The monolith is quarantined under ``app.legacy`` and may only shrink;
new v2-native endpoints are registered from domain packages by dependency
injection rather than added back to the legacy assembly.
"""
from __future__ import annotations

from types import ModuleType


def load_legacy_application() -> ModuleType:
    """Install governance, load legacy shell, then attach v2-native routers.

    Import ordering is part of the production contract: daily-history policy,
    compatibility hooks, and legacy synthetic instrument normalization must wrap
    PortfolioStore/provider classes before the legacy module constructs its
    singletons. Paper runtime governance then patches that exact module object.
    Adaptive scheduling narrows cadence/scope without changing policy authority.
    Session-aware data scheduling narrows when provider-backed refreshes may run.
    Corporate-event policy then wraps the already-local-first derived refresh so
    a bounded cached event calendar is available before formal paper decisions.
    Finally, additive non-conflicting v2 routes receive dependencies from
    bootstrap.
    """
    from app.daily_history_policy import install as install_daily_history_policy
    from app.daily_history_compat import install as install_daily_history_compat
    from app.instrument_metadata_policy import install as install_instrument_metadata_policy

    install_daily_history_policy()
    install_daily_history_compat()
    install_instrument_metadata_policy()

    from app.legacy import application_legacy as application
    from app.paper_runtime_integration import install as install_paper_runtime_governance
    from app.adaptive_paper_runtime import install as install_adaptive_paper_runtime
    from app.data_scheduling_policy import install as install_data_scheduling_policy
    from app.corporate_events import install as install_corporate_event_policy
    from app.bootstrap.v2_routes import register_v2_routes

    install_paper_runtime_governance(application)
    install_adaptive_paper_runtime(application)
    install_data_scheduling_policy(application)
    install_corporate_event_policy(application)
    register_v2_routes(application)
    return application
