"""Build compact, deterministic Atomic Evidence beside the current engine.

Phase 2 is intentionally shadow-only.  This module may read DecisionContext and
existing EvidenceItems, but no ActionPolicy, sizing, execution or AI component
may read its output yet.  Availability and conflicts mirror the existing
DecisionQualitySummary rather than creating a second data-quality truth system.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from app import decision_config as config
from app.atomic_models import (
    AtomicEvidenceSnapshot,
    AtomicFactRecord,
    EvidenceAvailabilityRecord,
    EvidenceConflictRecord,
)
from app.decision_models import DecisionContext, EvidenceItem
from app.trading_calendar import TradingCalendarService


_DIMENSION_BY_CATEGORY = {
    "position": "position_exposure",
    "price": "market_price",
    "trend": "technical_trend",
    "momentum": "technical_momentum",
    "volatility": "technical_volatility",
    "volume": "market_liquidity",
    "event": "corporate_event",
    "fundamental": "fundamental",
    "market": "market_context",
    "relative": "relative_strength",
    "liquidity": "liquidity",
    "plan": "trade_plan",
    "risk": "risk",
    "data_quality": "data_quality",
}


_CONFLICT_SOURCES = {
    "consistency.quote_older_than_daily_bar": ("quote", "daily_bars"),
    "consistency.risk_older_than_daily_bar": ("risk", "daily_bars"),
}


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _freshness_by_source(context: DecisionContext) -> dict[str, str]:
    return {
        item.source_key: item.status
        for item in context.data_quality.source_freshness
    }


def _polarity(direction: str) -> str:
    if direction == "positive":
        return "SUPPORTIVE"
    if direction == "negative":
        return "ADVERSE"
    return "NEUTRAL_MATERIAL"


def _materiality(strength: float) -> str:
    if strength >= .70:
        return "high"
    if strength >= .40:
        return "medium"
    return "low"


def _comparison_adequacy(item: EvidenceItem) -> str:
    if item.threshold is not None:
        return "adequate"
    if item.category in {"event", "data_quality"}:
        return "not_applicable"
    return "partial"


def _event_confidence(context: DecisionContext, evidence_id: str) -> float | None:
    for event in context.events:
        if not evidence_id.endswith(event.event_id):
            continue
        if event.verification_level == "official":
            return .95
        if event.verification_level == "secondary_calendar":
            return .75
        return .60
    return None


def _evidence_confidence(context: DecisionContext, item: EvidenceItem) -> float:
    event_confidence = _event_confidence(context, item.evidence_id) if item.category == "event" else None
    if event_confidence is not None:
        return event_confidence if item.fresh else min(event_confidence, .50)
    if not item.fresh:
        return .45
    if item.usage_scope == "POLICY":
        return .90
    if item.usage_scope == "RESEARCH_ONLY":
        return .65
    return .80


def _fact_provenance(
    *,
    context: DecisionContext,
    domain: str,
    metric: str,
    value: object,
    source_evidence_id: str | None,
    source_name: str | None,
    source_reference: str | None,
    source_timestamp: str | None,
    threshold: object = None,
) -> str:
    return _hash({
        "context_input_hash": context.input_hash,
        "symbol": context.symbol,
        "domain": domain,
        "metric": metric,
        "value": value,
        "threshold": threshold,
        "source_evidence_id": source_evidence_id,
        "source_name": source_name,
        "source_reference": source_reference,
        "source_timestamp": source_timestamp,
    })


class FactExtractor:
    """Translate current deterministic evidence into source-level atomic facts."""

    def build(
        self,
        context: DecisionContext,
        evidence: tuple[EvidenceItem, ...],
    ) -> tuple[AtomicFactRecord, ...]:
        market = (
            context.instrument.market
            if context.instrument
            else TradingCalendarService.market_for_symbol(context.symbol)
        )
        facts = [*self._identity_facts(context, market), *self._price_facts(context, market)]
        facts.extend(self._evidence_facts(context, evidence, market))
        facts.sort(key=lambda item: item.fact_id)
        if len({item.fact_id for item in facts}) != len(facts):
            raise ValueError("atomic fact IDs must be unique")
        return tuple(facts)

    @staticmethod
    def _identity_facts(context: DecisionContext, market: str | None) -> list[AtomicFactRecord]:
        instrument = context.instrument
        if instrument is None:
            return []
        confidence = .75 if instrument.source.startswith("paper_market_default") else .90
        values = [
            ("market", instrument.market, "high"),
            ("currency", instrument.currency, "high"),
            ("lot_size", instrument.lot_size, "high"),
            ("price_tick", instrument.price_tick, "medium"),
        ]
        facts = []
        for metric, value, materiality in values:
            if value is None:
                continue
            source_timestamp = _text(instrument.as_of)
            facts.append(AtomicFactRecord(
                fact_id=f"atomic.instrument.{metric}",
                symbol=context.symbol,
                market=market,
                domain="instrument",
                dimension="instrument_identity",
                metric=f"instrument.{metric}",
                value=value,
                source_name=instrument.source,
                source_timestamp=source_timestamp,
                observed_at=context.generated_at,
                freshness_status="unknown",
                polarity="NEUTRAL_MATERIAL",
                materiality=materiality,
                comparison_adequacy="not_applicable",
                confidence=confidence,
                provenance_hash=_fact_provenance(
                    context=context,
                    domain="instrument",
                    metric=f"instrument.{metric}",
                    value=value,
                    source_evidence_id=None,
                    source_name=instrument.source,
                    source_reference=None,
                    source_timestamp=source_timestamp,
                ),
            ))
        return facts

    @staticmethod
    def _price_facts(context: DecisionContext, market: str | None) -> list[AtomicFactRecord]:
        quality = context.data_quality
        freshness = _freshness_by_source(context)
        warnings = set(quality.warnings)
        facts: list[AtomicFactRecord] = []
        if context.quote is not None:
            conflicted = "consistency.quote_older_than_daily_bar" in warnings
            status = freshness.get("quote", "unknown")
            source_timestamp = _text(context.quote.as_of or context.quote.retrieved_at)
            value = context.quote.price
            facts.append(AtomicFactRecord(
                fact_id="atomic.raw.quote.price",
                symbol=context.symbol,
                market=market,
                domain="price",
                dimension="market_price",
                metric="quote.price",
                value=value,
                source_evidence_id="quote.price",
                source_name=context.quote.source,
                source_timestamp=source_timestamp,
                observed_at=context.generated_at,
                freshness_status=status if status in {"fresh", "stale", "unknown", "unavailable"} else "unknown",
                polarity="CONFLICT" if conflicted else "NEUTRAL_MATERIAL",
                materiality="high",
                comparison_adequacy="not_applicable",
                confidence=.40 if conflicted else .90 if status == "fresh" else .50,
                provenance_hash=_fact_provenance(
                    context=context,
                    domain="price",
                    metric="quote.price",
                    value=value,
                    source_evidence_id="quote.price",
                    source_name=context.quote.source,
                    source_reference=None,
                    source_timestamp=source_timestamp,
                ),
            ))
        if context.daily_bars.last_close is not None:
            status = freshness.get("daily_bars", "unknown")
            source_timestamp = _text(context.daily_bars.last_trading_date)
            value = context.daily_bars.last_close
            facts.append(AtomicFactRecord(
                fact_id="atomic.raw.daily_bars.last_close",
                symbol=context.symbol,
                market=market,
                domain="price",
                dimension="market_price",
                metric="daily_bars.last_close",
                value=value,
                source_evidence_id="daily_bars.last_close",
                source_name=context.daily_bars.source,
                source_timestamp=source_timestamp,
                observed_at=context.generated_at,
                freshness_status=status if status in {"fresh", "stale", "unknown", "unavailable"} else "unknown",
                polarity="NEUTRAL_MATERIAL",
                materiality="high",
                comparison_adequacy="not_applicable",
                confidence=.90 if status == "fresh" else .50,
                provenance_hash=_fact_provenance(
                    context=context,
                    domain="price",
                    metric="daily_bars.last_close",
                    value=value,
                    source_evidence_id="daily_bars.last_close",
                    source_name=context.daily_bars.source,
                    source_reference=None,
                    source_timestamp=source_timestamp,
                ),
            ))
        return facts

    @staticmethod
    def _evidence_facts(
        context: DecisionContext,
        evidence: tuple[EvidenceItem, ...],
        market: str | None,
    ) -> list[AtomicFactRecord]:
        facts = []
        for item in evidence:
            source_timestamp = _text(item.as_of)
            freshness = "fresh" if item.fresh else "unknown" if item.category == "data_quality" else "stale"
            metric = item.evidence_id
            facts.append(AtomicFactRecord(
                fact_id=f"atomic.evidence.{item.evidence_id}",
                symbol=context.symbol,
                market=market,
                domain=item.category,
                dimension=_DIMENSION_BY_CATEGORY.get(item.category, item.category),
                metric=metric,
                value=item.value,
                comparison_type="threshold" if item.threshold is not None else "observation",
                source_evidence_id=item.evidence_id,
                source_name=item.source,
                source_reference=item.source_reference,
                source_timestamp=source_timestamp,
                period_end=source_timestamp,
                observed_at=context.generated_at,
                freshness_status=freshness,
                polarity=_polarity(item.direction),
                materiality=_materiality(item.strength),
                comparison_adequacy=_comparison_adequacy(item),
                confidence=_evidence_confidence(context, item),
                provenance_hash=_fact_provenance(
                    context=context,
                    domain=item.category,
                    metric=metric,
                    value=item.value,
                    source_evidence_id=item.evidence_id,
                    source_name=item.source,
                    source_reference=item.source_reference,
                    source_timestamp=source_timestamp,
                    threshold=item.threshold,
                ),
            ))
        return facts


class AtomicEvidenceSnapshotBuilder:
    version = config.ATOMIC_EVIDENCE_VERSION

    def __init__(self, fact_extractor: FactExtractor | None = None) -> None:
        self.fact_extractor = fact_extractor or FactExtractor()

    def build(
        self,
        context: DecisionContext,
        evidence: tuple[EvidenceItem, ...],
    ) -> AtomicEvidenceSnapshot:
        market = (
            context.instrument.market
            if context.instrument
            else TradingCalendarService.market_for_symbol(context.symbol)
        )
        facts = self.fact_extractor.build(context, evidence)
        availability = self._availability(context)
        conflicts = self._conflicts(context)
        content_hash = _hash({
            "version": self.version,
            "context_input_hash": context.input_hash,
            "symbol": context.symbol,
            "market": market,
            # observed_at/generated_at identify the run, not the evidence
            # content. Exclude them so the same frozen input has the same hash.
            "facts": [item.model_dump(mode="json", exclude={"observed_at"}) for item in facts],
            "availability": [item.model_dump(mode="json") for item in availability],
            "conflicts": [item.model_dump(mode="json") for item in conflicts],
        })
        return AtomicEvidenceSnapshot(
            version=self.version,
            context_id=context.context_id,
            context_input_hash=context.input_hash,
            symbol=context.symbol,
            market=market,
            generated_at=context.generated_at,
            facts=facts,
            availability=availability,
            conflicts=conflicts,
            snapshot_hash=content_hash,
        )

    @staticmethod
    def _availability(context: DecisionContext) -> tuple[EvidenceAvailabilityRecord, ...]:
        quality = context.data_quality
        warnings = set(quality.warnings)
        missing = set(quality.missing_fields)
        stale = set(quality.stale_fields)
        open_gate = next((item for item in quality.action_gates if item.action == "OPEN"), None)
        open_unavailable = set(open_gate.unavailable_fields if open_gate else ())

        conflict_by_capability = {
            "quote": tuple(sorted(code for code in warnings if code == "consistency.quote_older_than_daily_bar")),
            "risk": tuple(sorted(code for code in warnings if code == "consistency.risk_older_than_daily_bar")),
        }
        definitions = (
            ("quote", context.quote is not None, ("quote",), ("quote.price",)),
            ("daily_bars", context.daily_bars.count > 0, ("daily_bars",), ("daily_bars.minimum_60",)),
            ("technical", context.technical is not None, ("daily_bars",), ("daily_bars.minimum_60",)),
            ("risk", context.risk is not None, ("risk",), ("risk",)),
            ("market_regime", context.market_regime is not None, ("market_regime",), ("market_regime",)),
            ("instrument", context.instrument is not None, ("instrument",), ("instrument",)),
            ("events", bool(context.events), ("events",), ("events",)),
            ("relative_strength", context.relative_strength is not None, ("relative_strength",), ("relative_strength",)),
            ("trade_plan", bool(context.trade_plan and context.trade_plan.enabled), ("trade_plan",), ("trade_plan.auto_draft",)),
            ("account.total_assets", context.account.total_assets is not None, ("account",), ("account.total_assets",)),
        )
        records = []
        for capability, present, source_keys, reason_prefixes in definitions:
            reasons: list[str] = []
            conflicts = conflict_by_capability.get(capability, ())
            if conflicts:
                status = "conflicted"
                reasons.extend(conflicts)
            elif any(key in stale for key in source_keys):
                status = "stale"
                reasons.extend(f"stale:{key}" for key in source_keys if key in stale)
            elif any(code in missing for code in reason_prefixes):
                status = "missing"
                reasons.extend(code for code in reason_prefixes if code in missing)
            else:
                matched_warnings = tuple(sorted(
                    warning
                    for warning in warnings
                    if any(warning.startswith(f"{prefix} unavailable") for prefix in reason_prefixes)
                ))
                matched_open = tuple(sorted(
                    field
                    for field in open_unavailable
                    if any(field.startswith(prefix) for prefix in reason_prefixes)
                ))
                if matched_warnings or matched_open or not present:
                    status = "degraded"
                    reasons.extend(matched_warnings)
                    reasons.extend(f"open_unavailable:{field}" for field in matched_open)
                    if not present and not reasons:
                        reasons.append("context_absent")
                else:
                    status = "available"
            records.append(EvidenceAvailabilityRecord(
                capability=capability,
                status=status,
                reason_codes=tuple(dict.fromkeys(reasons)),
                source_keys=tuple(source_keys),
            ))
        return tuple(sorted(records, key=lambda item: item.capability))

    @staticmethod
    def _conflicts(context: DecisionContext) -> tuple[EvidenceConflictRecord, ...]:
        records = []
        for warning in sorted(context.data_quality.warnings):
            if not warning.startswith("consistency."):
                continue
            sources = _CONFLICT_SOURCES.get(warning, ())
            records.append(EvidenceConflictRecord(
                conflict_id=f"atomic.conflict.{warning.removeprefix('consistency.')}",
                code=warning,
                affected_sources=tuple(sources),
                severity="high",
                policy_effect="mirrors_existing_data_quality_gates",
            ))
        return tuple(records)


__all__ = ["AtomicEvidenceSnapshotBuilder", "FactExtractor"]
