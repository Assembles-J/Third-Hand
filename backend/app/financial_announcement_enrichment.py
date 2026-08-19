"""Deterministic cross-source enrichment for financial announcement timing.

Financial values remain owned by the persisted financial provider snapshot. The
official CorporateEvent source owns the publication timestamp. This join fills
only missing `announced_at` metadata when report period/year match; it never
changes a financial value, polarity, or trading authority.
"""
from __future__ import annotations

from app.domain.research.data_gateway import canonical_hash


FINANCIAL_DOMAINS = frozenset({"fundamental"})
FINANCIAL_DIMENSIONS = frozenset({"fundamental_company"})


def _report_type_from_event_period(value: object) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if any(token in text for token in ("中报", "中期", "interim", "half")):
        return "interim"
    if any(token in text for token in ("一季", "first quarter", "q1")):
        return "q1"
    if any(token in text for token in ("三季", "third quarter", "q3")):
        return "q3"
    if any(token in text for token in ("年报", "年度", "annual", "final")):
        return "annual"
    return None


def _year(value: object) -> int | None:
    text = str(value or "").strip()
    if len(text) < 4 or not text[:4].isdigit():
        return None
    return int(text[:4])


class FinancialAnnouncementEnricher:
    version = "financial-announcement-enrichment-v1-official-event-join"

    def __init__(self, store) -> None:
        self.store = store

    def enrich(self, context, facts):
        events = self._official_events(context.symbol)
        if not events:
            return tuple(facts)
        result = []
        for fact in facts:
            if (
                fact.domain not in FINANCIAL_DOMAINS
                or fact.dimension not in FINANCIAL_DIMENSIONS
                or fact.announced_at
                or not fact.period_end
            ):
                result.append(fact)
                continue
            event = self._match_event(fact, events)
            if event is None:
                result.append(fact)
                continue
            announced_at = str(event.get("announced_at") or "").strip()
            if not announced_at:
                result.append(fact)
                continue
            provenance_hash = canonical_hash({
                "version": self.version,
                "financial_fact_provenance": fact.provenance_hash,
                "event_id": event.get("event_id"),
                "event_source": event.get("source"),
                "event_source_reference": event.get("source_reference"),
                "announced_at": announced_at,
            })
            result.append(fact.model_copy(update={
                "announced_at": announced_at,
                "provenance_hash": provenance_hash,
            }))
        return tuple(result)

    def _official_events(self, symbol: str) -> list[dict[str, object]]:
        bundle = self.store.cached_market_intelligence(f"corporate_events:{symbol}") or {}
        candidates = [
            dict(item)
            for item in (*tuple(bundle.get("events", []) or ()), *tuple(bundle.get("event_history", []) or ()))
            if isinstance(item, dict)
            and str(item.get("event_type") or "") == "earnings_report"
            and str(item.get("verification_level") or "") == "official"
            and item.get("announced_at")
        ]
        candidates.sort(key=lambda item: str(item.get("announced_at") or ""), reverse=True)
        return candidates

    @staticmethod
    def _match_event(fact, events: list[dict[str, object]]) -> dict[str, object] | None:
        fact_year = _year(fact.period_end)
        fact_type = str(fact.report_type or "").strip().lower() or None
        for event in events:
            event_type = _report_type_from_event_period(event.get("period"))
            event_year = _year(event.get("period")) or _year(event.get("scheduled_at"))
            if fact_year is not None and event_year is not None and fact_year != event_year:
                continue
            if fact_type and event_type and fact_type != event_type:
                continue
            # Require an explicit report-type match. A merely matching calendar
            # year must not stamp an unrelated annual/interim observation.
            if fact_type and event_type and fact_type == event_type:
                return event
        return None


__all__ = ["FinancialAnnouncementEnricher"]
