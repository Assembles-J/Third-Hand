"""Event-aware Company Intelligence refresh at the research boundary.

A provider TTL answers whether cached bytes were fetched recently. An official
results announcement answers a different question: whether a newer financial
observation should now exist. This runtime adapter keeps those semantics
separate by forcing only registered financial datasets after an official release
has been observed, while leaving all other company datasets on normal TTLs.
"""
from __future__ import annotations

from functools import wraps


FINANCIAL_DATA_TYPES = (
    "company_financial_summary",
    "company_margin_structure",
    "company_profit_cashflow_drivers",
)
FINANCIAL_DATASET_KEYS = frozenset({
    "financial_summary",
    "margin_structure",
    "profit_cashflow_drivers",
})
REFRESH_REASON = "official_earnings_release_observed"


def _official_release_pending(store, symbol: str) -> bool:
    bundle = store.cached_market_intelligence(f"corporate_events:{symbol}") or {}
    for item in bundle.get("events", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("event_type") or "") != "earnings_report":
            continue
        if str(item.get("verification_level") or "") != "official":
            continue
        # CorporateEvent date-state projection may classify a same-day official
        # release as DUE/RELEASE_EXPECTED for compatibility. `announced_at` is
        # the first-party fact that a newer report has actually been published.
        if item.get("announced_at"):
            return True
    return False


def install(m) -> None:
    if getattr(m, "_financial_release_refresh_runtime_installed", False):
        return
    m._financial_release_refresh_runtime_installed = True
    service = getattr(m, "company_intelligence_service", None)
    store = getattr(m, "store", None)
    if service is None or store is None:
        return

    original_requirements = service.requirements
    original_build_context = service.build_context

    @wraps(original_requirements)
    def requirements(symbol: str, *, research_priority: str | None = None):
        result = original_requirements(symbol, research_priority=research_priority)
        if not _official_release_pending(store, str(symbol).strip().upper()):
            return result
        updated = dict(result)
        items = []
        for raw in result.get("required_datasets", []):
            item = dict(raw)
            if (
                item.get("dataset_key") in FINANCIAL_DATASET_KEYS
                and bool(item.get("provider_registered"))
                and item.get("local_status") == "LOCAL_FRESH_HIT"
            ):
                # Mandatory Acquisition already understands LOCAL_STALE_HIT as
                # one bounded REFRESH action. No new action authority is added.
                item["local_status"] = "LOCAL_STALE_HIT"
                item["refresh_reason"] = REFRESH_REASON
            items.append(item)
        updated["required_datasets"] = items
        updated["event_driven_refresh"] = REFRESH_REASON
        return updated

    @wraps(original_build_context)
    def build_context(
        symbol: str,
        *,
        research_priority: str | None = None,
        allow_remote: bool = True,
        force_refresh_data_types: tuple[str, ...] = (),
        refresh_reason: str | None = None,
    ):
        normalized = str(symbol).strip().upper()
        forced = tuple(force_refresh_data_types)
        reason = refresh_reason
        if allow_remote and _official_release_pending(store, normalized):
            forced = tuple(dict.fromkeys((*forced, *FINANCIAL_DATA_TYPES)))
            reason = reason or REFRESH_REASON
        return original_build_context(
            normalized,
            research_priority=research_priority,
            allow_remote=allow_remote,
            force_refresh_data_types=forced,
            refresh_reason=reason,
        )

    service.requirements = requirements
    service.build_context = build_context


__all__ = [
    "FINANCIAL_DATASET_KEYS",
    "FINANCIAL_DATA_TYPES",
    "REFRESH_REASON",
    "install",
]
