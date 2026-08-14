"""Third-Hand ASGI entrypoint.

Runtime governance and legacy-application loading live in ``app.bootstrap`` so
this module remains a stable import alias while the monolithic application is
extracted domain by domain.
"""
from __future__ import annotations

import sys

from app.bootstrap.runtime import load_legacy_application

_application = load_legacy_application()

# Preserve historical monkeypatch/import behavior until the final router
# extraction removes the legacy application module.
sys.modules[__name__] = _application
