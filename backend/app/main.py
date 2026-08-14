"""FastAPI entrypoint with runtime governance installed before startup.

The large API assembly lives unchanged in ``app.application``.  Keeping this
entrypoint small prevents candidate/execution governance from being buried in a
monolithic module while preserving ``app.main`` import compatibility.
"""
from __future__ import annotations

import sys

from app import application as _application
from app.paper_runtime_integration import install as _install_paper_runtime_governance

_install_paper_runtime_governance(_application)

# Alias app.main to the assembled application module so existing tests and code
# that monkeypatch attributes on app.main continue to affect the function-global
# namespace used by registered FastAPI routes and startup callbacks.
sys.modules[__name__] = _application
