"""Stable route ownership rules used during the v2 strangler refactor.

The classifier has no FastAPI dependency and does not register routes.  It is a
migration guard: as endpoints leave ``app.application`` their URL determines the
package that owns them, preventing the new API layer from becoming another
monolith.
"""
from __future__ import annotations


_PREFIX_OWNERS: tuple[tuple[str, str], ...] = (
    ("/health", "health"),
    ("/v1/admin/", "admin"),
    ("/v1/app-update", "app_update"),
    ("/v1/paper-trading/", "paper"),
    ("/v1/data-quality/", "data_quality"),
    ("/v1/decision", "decision"),
    ("/v1/research", "research"),
    ("/v1/feed", "research"),
    ("/v1/announcements", "research"),
    ("/v1/ai", "ai"),
    ("/v1/chat", "ai"),
    ("/v1/market", "market"),
    ("/v1/quotes", "market"),
    ("/v1/quote", "market"),
    ("/v1/history", "market"),
    ("/v1/intraday", "market"),
    ("/v1/candidate", "candidate"),
)


def owner_for_path(path: str) -> str:
    """Return the intended v2 API package owner for a public path.

    Unknown routes remain ``portfolio`` during the first migration pass because
    the legacy module contains holdings/watchlist/trade-plan endpoints with
    several historical names.  A2 replaces this fallback with an explicit
    registry after the Android client and OpenAPI path set are audited.
    """
    normalized = str(path or "").strip()
    for prefix, owner in _PREFIX_OWNERS:
        if normalized == prefix or normalized.startswith(prefix):
            return owner
    return "portfolio"
