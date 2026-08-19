"""Persisted intraday timeframe snapshots as research-only Atomic Evidence."""
from __future__ import annotations

from app.atomic_company_research import AtomicResearchSourceResult
from app.atomic_models import AtomicFactRecord, EvidenceAvailabilityRecord
from app.domain.research.data_gateway import canonical_hash
from app.intraday_timeframes import (
    INTRADAY_TIMEFRAME_POLICY_VERSION,
    IntradayTimeframeSnapshot,
    build_intraday_timeframe_snapshots,
)
from app.trading_calendar import TradingCalendarService


_AVAILABILITY = {
    "AVAILABLE": "available",
    "MISSING": "missing",
    "STALE": "stale",
    "CONFLICTED": "conflicted",
}


class IntradayTimeframeAtomicSource:
    """Read only local one-minute bars and emit action-free timeframe facts."""

    def __init__(self, store, *, calendar=None, limit: int = 5000) -> None:
        self.store = store
        self.calendar = calendar or TradingCalendarService()
        self.limit = max(500, min(int(limit), 20_000))

    def build(self, context) -> AtomicResearchSourceResult:
        market = context.instrument.market if context.instrument else TradingCalendarService.market_for_symbol(context.symbol)
        rows = self.store.intraday_prices(context.symbol, limit=self.limit)
        snapshots = build_intraday_timeframe_snapshots(
            rows,
            market=market,
            analysis_at=context.generated_at,
            calendar=self.calendar,
        )
        if not snapshots:
            return AtomicResearchSourceResult()

        facts: list[AtomicFactRecord] = []
        availability: list[EvidenceAvailabilityRecord] = []
        for snapshot in snapshots:
            capability = f"intraday.{snapshot.timeframe}"
            availability.append(EvidenceAvailabilityRecord(
                capability=capability,
                status=_AVAILABILITY[snapshot.availability],  # type: ignore[arg-type]
                reason_codes=snapshot.reason_codes,
                source_keys=("intraday_price_cache",),
            ))
            if snapshot.close is None:
                continue
            facts.extend(self._facts(context, market, snapshot))

        return AtomicResearchSourceResult(
            facts=tuple(sorted(facts, key=lambda item: item.fact_id)),
            availability=tuple(sorted(availability, key=lambda item: item.capability)),
        )

    @staticmethod
    def _facts(context, market: str | None, snapshot: IntradayTimeframeSnapshot) -> list[AtomicFactRecord]:
        metrics = (
            ("close", snapshot.close, "high"),
            ("trend_structure", snapshot.trend_structure, "high"),
            ("price_location", snapshot.price_location, "medium"),
            ("momentum", snapshot.momentum, "medium"),
            ("volatility", snapshot.volatility, "medium"),
            ("volatility_percent", snapshot.volatility_percent, "medium"),
        )
        freshness = snapshot.freshness_status if snapshot.freshness_status in {"fresh", "stale", "unknown"} else "unknown"
        confidence = .85 if snapshot.availability == "AVAILABLE" else .45 if snapshot.availability == "STALE" else .35
        facts = []
        for metric_name, value, materiality in metrics:
            if value is None:
                continue
            metric = f"intraday.{snapshot.timeframe}.{metric_name}"
            provenance = canonical_hash({
                "policy_version": INTRADAY_TIMEFRAME_POLICY_VERSION,
                "context_input_hash": context.input_hash,
                "symbol": context.symbol,
                "market": market,
                "timeframe": snapshot.timeframe,
                "metric": metric_name,
                "value": value,
                "source_hash": snapshot.source_hash,
                "as_of": snapshot.as_of,
            })
            facts.append(AtomicFactRecord(
                fact_id=f"atomic.{metric}",
                symbol=context.symbol,
                market=market,
                domain="intraday_research",
                # Deliberately does not start with `technical_`: the current
                # deterministic ResearchAggregator therefore cannot treat these
                # facts as formal technical authority before #48.
                dimension=f"intraday_research_{snapshot.timeframe}",
                metric=metric,
                value=value,
                unit="percent" if metric_name == "volatility_percent" else None,
                period_end=snapshot.as_of,
                comparison_type="completed_timeframe_observation",
                source_name=snapshot.source,
                source_timestamp=snapshot.as_of,
                available_at=snapshot.retrieved_at,
                retrieved_at=snapshot.retrieved_at,
                observed_at=context.generated_at,
                freshness_status=freshness,
                retrieval_freshness=freshness,
                polarity="NEUTRAL_MATERIAL",
                materiality=materiality,  # type: ignore[arg-type]
                # Intraday facts describe a completed timeframe state but do not
                # carry a calibrated directional comparison yet. `partial` is
                # the existing AtomicFactRecord contract for that situation.
                comparison_adequacy="partial",
                confidence=confidence,
                provenance_hash=provenance,
            ))
        return facts


__all__ = ["IntradayTimeframeAtomicSource"]
