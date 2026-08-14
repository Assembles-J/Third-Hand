"""Compatibility alias for the quarantined legacy application assembly.

Architecture Refactor v2 moves the historical monolith to
``app.legacy.application_legacy``.  Keep this import path as an alias during the
migration so existing tests, Uvicorn imports and monkeypatches continue to touch
the function-global namespace used by legacy routes.

New production endpoints and services must not be added here or to the legacy
module; they belong to the v2 domain packages.
"""
from __future__ import annotations

import sys

from app.legacy import application_legacy as _legacy

sys.modules[__name__] = _legacy
