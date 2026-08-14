"""FastAPI entrypoint with runtime governance installed before startup.

The large API assembly lives unchanged in ``app.application``.  Keeping this
entrypoint small prevents candidate/execution governance from being buried in a
monolithic module while preserving ``app.main`` import compatibility.
"""
from __future__ import annotations

import sys

from app.daily_history_policy import install as _install_daily_history_policy

# Tighten the formal daily-price contract before app.application constructs its
# PortfolioStore and PriceHistoryService singletons. This keeps contract cleanup,
# local-first routing, qfq normalization and provider rate limiting active for
# every runtime path without widening trading-policy authority.
_install_daily_history_policy()

# Older dependency surfaces and existing provider test doubles may not expose
# the newer Tencent/Tushare helpers. Capability-based fallback keeps those paths
# backward compatible while current production continues to use the new policy.
from app.daily_history_compat import install as _install_daily_history_compat

_install_daily_history_compat()

from app import application as _application
from app.paper_runtime_integration import install as _install_paper_runtime_governance

_install_paper_runtime_governance(_application)

# Alias app.main to the assembled application module so existing tests and code
# that monkeypatch attributes on app.main continue to affect the function-global
# namespace used by registered FastAPI routes and startup callbacks.
sys.modules[__name__] = _application
