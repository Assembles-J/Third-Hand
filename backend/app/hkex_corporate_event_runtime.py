"""Production wiring for the HKEX Tier-1 CorporateEvent source."""
from __future__ import annotations

from app.hkex_corporate_events import HkexOfficialEventFetcher


def install(m) -> None:
    if getattr(m, "_hkex_corporate_event_runtime_installed", False):
        return
    m._hkex_corporate_event_runtime_installed = True
    service = getattr(m, "corporate_event_service", None)
    if service is None:
        return
    if getattr(service, "_official_fetcher", None) is None:
        service._official_fetcher = HkexOfficialEventFetcher()


__all__ = ["install"]
