"""Stable route ownership rules used during the v2 strangler refactor.

The classifier has no FastAPI dependency and does not register routes. It is a
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

    ("/v1/decisions", "decision"),

    ("/v1/system/ai-capabilities", "ai"),
    ("/v1/ai-jobs", "ai"),
    ("/v1/research-chat", "ai"),
    ("/v1/chat", "ai"),

    ("/v1/news", "research"),
    ("/v1/feed", "research"),
    ("/v1/announcements", "research"),
    ("/v1/research/", "research"),
    ("/v1/research-recommendations", "research"),
    ("/v1/research-reports", "research"),
    ("/v1/research-theses", "research"),
    ("/v1/opportunity-scan", "research"),
    ("/v1/daily-reviews", "research"),
    ("/v1/learning-cases", "research"),
    ("/v1/research-rules", "research"),
    ("/v1/glossary", "research"),

    ("/v1/market", "market"),
    ("/v1/instruments", "market"),

    ("/v1/holdings", "portfolio"),
    ("/v1/holding-drafts", "portfolio"),
    ("/v1/sales", "portfolio"),
    ("/v1/watchlist", "portfolio"),
    ("/v1/risk", "portfolio"),
    ("/v1/portfolio", "portfolio"),
    ("/v1/account", "portfolio"),
    ("/v1/trade-plans", "portfolio"),
    ("/v1/personal-rules", "portfolio"),

    ("/v1/candidate", "candidate"),
)


def owner_for_path(path: str) -> str:
    """Return the intended v2 API package owner for a public path.

    ``unclassified`` is deliberate: a newly discovered route must be assigned a
    domain instead of silently becoming portfolio-owned.
    """
    normalized = str(path or "").strip()
    for prefix, owner in _PREFIX_OWNERS:
        if normalized == prefix or normalized.startswith(prefix):
            return owner
    return "unclassified"
