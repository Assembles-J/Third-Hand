"""Point-in-time Company Intelligence enrichment for Atomic Evidence.

This source reads only persisted Research Local-First snapshots. It never calls
providers and is invoked only after formal ActionPolicy candidates are frozen.
The first schema-aware extraction intentionally targets normalized HK company
margin/profit-driver datasets; other datasets still contribute deterministic
availability/provenance but are not guessed into metrics.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from app.atomic_models import AtomicFactRecord, EvidenceAvailabilityRecord, EvidenceConflictRecord
from app.decision_models import DecisionContext
from app.domain.research.data_gateway import canonical_hash
from app.infrastructure.database.company_intelligence_repository import CompanyIntelligenceRepository
from app.infrastructure.database.research_data_repository import ResearchDataRepository


@dataclass(frozen=True)
class AtomicResearchSourceResult:
    facts: tuple[AtomicFactRecord, ...] = ()
    availability: tuple[EvidenceAvailabilityRecord, ...] = ()
    conflicts: tuple[EvidenceConflictRecord, ...] = ()


def _parse_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text.endswith("%"):
        text = text[:-1].strip()
    if not text or text.lower() in {"nan", "none", "null", "--"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _latest_row(rows: object, date_key: str = "report_date") -> dict[str, object] | None:
    if not isinstance(rows, list):
        return None
    candidates = [dict(item) for item in rows if isinstance(item, dict)]
    if not candidates:
        return None
    return max(candidates, key=lambda item: str(item.get(date_key) or ""))


def _polarity(metric: str, value: float) -> str:
    if metric.endswith("_yoy_percent"):
        if value > 0:
            return "SUPPORTIVE"
        if value < 0:
            return "ADVERSE"
    return "NEUTRAL_MATERIAL"


def _fact_spec(metric: str) -> tuple[str | None, str, str, str]:
    """Return unit, comparison type, adequacy and materiality."""
    if metric.endswith("_yoy_percent"):
        return "percent", "year_over_year", "adequate", "high"
    if metric.endswith("_percent"):
        return "percent", "reported_level", "partial", "medium"
    if metric in {"revenue", "gross_profit", "holder_profit"}:
        # Provider payloads do not carry a reliable normalized currency/unit yet.
        return None, "reported_level", "partial", "high"
    return None, "reported_level", "partial", "medium"


def _fact_id(dataset_key: str, report_date: str, metric: str) -> str:
    period = report_date.replace("-", "") or "unknown"
    return f"atomic.company.{dataset_key}.{period}.{metric}"


class CompanyResearchAtomicSource:
    """Read persisted company contexts and emit action-free fundamental facts."""

    def __init__(self, store) -> None:
        self.store = store
        self.company_repository = CompanyIntelligenceRepository(store)
        self.research_repository = ResearchDataRepository(store)

    def build(self, context: DecisionContext) -> AtomicResearchSourceResult:
        company = self.company_repository.latest_context_at_or_before(
            context.symbol,
            context.generated_at.isoformat(),
        )
        if company is None:
            return AtomicResearchSourceResult(availability=(
                EvidenceAvailabilityRecord(
                    capability="company_research",
                    status="missing",
                    reason_codes=("no_point_in_time_context",),
                    source_keys=("company_research_snapshots",),
                ),
            ))

        context_id = str(company.get("context_id") or "")
        missing_datasets = tuple(str(item) for item in company.get("missing_datasets", []) if str(item))
        stale_datasets = set(str(item) for item in company.get("stale_datasets", []) if str(item))
        refs = [dict(item) for item in company.get("dataset_refs", []) if isinstance(item, dict)]
        datasets = company.get("datasets") if isinstance(company.get("datasets"), dict) else {}

        availability: list[EvidenceAvailabilityRecord] = []
        facts: list[AtomicFactRecord] = []
        conflicts: list[EvidenceConflictRecord] = []
        overall_reasons = [*(f"missing:{item}" for item in missing_datasets), *(f"stale:{item}" for item in sorted(stale_datasets))]
        availability.append(EvidenceAvailabilityRecord(
            capability="company_research",
            status="degraded" if overall_reasons else "available",
            reason_codes=tuple(overall_reasons),
            source_keys=(f"company_context:{context_id}",),
        ))

        ref_by_key = {str(item.get("dataset_key") or ""): item for item in refs if item.get("dataset_key")}
        for dataset_key in sorted(set((*ref_by_key.keys(), *missing_datasets))):
            ref = ref_by_key.get(dataset_key)
            if ref is None:
                availability.append(EvidenceAvailabilityRecord(
                    capability=f"company_dataset.{dataset_key}",
                    status="missing",
                    reason_codes=("dataset_missing_from_company_context",),
                    source_keys=(f"company_context:{context_id}",),
                ))
                continue
            self._consume_dataset(
                context=context,
                company_context_id=context_id,
                dataset_key=dataset_key,
                ref=ref,
                payload=datasets.get(dataset_key),
                stale=dataset_key in stale_datasets or str(ref.get("freshness_status") or "") != "fresh",
                facts=facts,
                availability=availability,
                conflicts=conflicts,
            )

        facts.sort(key=lambda item: item.fact_id)
        availability.sort(key=lambda item: item.capability)
        conflicts.sort(key=lambda item: item.conflict_id)
        if len({item.fact_id for item in facts}) != len(facts):
            raise ValueError("company atomic fact IDs must be unique")
        return AtomicResearchSourceResult(tuple(facts), tuple(availability), tuple(conflicts))

    def _consume_dataset(
        self,
        *,
        context: DecisionContext,
        company_context_id: str,
        dataset_key: str,
        ref: dict[str, object],
        payload: object,
        stale: bool,
        facts: list[AtomicFactRecord],
        availability: list[EvidenceAvailabilityRecord],
        conflicts: list[EvidenceConflictRecord],
    ) -> None:
        snapshot_id = str(ref.get("snapshot_id") or "")
        ref_available_at = _parse_datetime(ref.get("available_at"))
        source_keys = (f"company_context:{company_context_id}", f"research_snapshot:{snapshot_id}")
        if ref_available_at is None:
            availability.append(EvidenceAvailabilityRecord(
                capability=f"company_dataset.{dataset_key}",
                status="degraded",
                reason_codes=("available_at_invalid",),
                source_keys=source_keys,
            ))
            return
        if ref_available_at > context.generated_at:
            availability.append(EvidenceAvailabilityRecord(
                capability=f"company_dataset.{dataset_key}",
                status="missing",
                reason_codes=("not_available_at_decision_time",),
                source_keys=source_keys,
            ))
            return

        raw_snapshot = self.research_repository.get_snapshot(snapshot_id) if snapshot_id else None
        if raw_snapshot is None:
            availability.append(EvidenceAvailabilityRecord(
                capability=f"company_dataset.{dataset_key}",
                status="degraded",
                reason_codes=("research_snapshot_reference_missing",),
                source_keys=source_keys,
            ))
            return

        raw_available_at = _parse_datetime(raw_snapshot.available_at)
        if raw_available_at is None:
            availability.append(EvidenceAvailabilityRecord(
                capability=f"company_dataset.{dataset_key}",
                status="degraded",
                reason_codes=("research_snapshot_available_at_invalid",),
                source_keys=source_keys,
            ))
            return
        if raw_available_at > context.generated_at:
            # The persisted ResearchDataSnapshot is the source-of-truth boundary.
            # A stale/corrupt CompanyContext ref must never make future data
            # visible to an earlier decision, even if the ref claims an older
            # available_at value.
            availability.append(EvidenceAvailabilityRecord(
                capability=f"company_dataset.{dataset_key}",
                status="missing",
                reason_codes=("research_snapshot_not_available_at_decision_time",),
                source_keys=source_keys,
            ))
            return
        if raw_available_at != ref_available_at:
            code = f"company_dataset_available_at_mismatch:{dataset_key}"
            availability.append(EvidenceAvailabilityRecord(
                capability=f"company_dataset.{dataset_key}",
                status="conflicted",
                reason_codes=(code,),
                source_keys=source_keys,
            ))
            conflicts.append(EvidenceConflictRecord(
                conflict_id=f"atomic.conflict.company.{dataset_key}.available_at",
                code=code,
                affected_sources=source_keys,
                severity="high",
                policy_effect="shadow_only_no_formal_authority",
            ))
            return

        expected_hash = str(ref.get("payload_hash") or "")
        context_payload_hash = canonical_hash(payload) if payload is not None else ""
        snapshot_hash = str(raw_snapshot.payload_hash)
        if not expected_hash or expected_hash != context_payload_hash or expected_hash != snapshot_hash:
            code = f"company_dataset_payload_hash_mismatch:{dataset_key}"
            availability.append(EvidenceAvailabilityRecord(
                capability=f"company_dataset.{dataset_key}",
                status="conflicted",
                reason_codes=(code,),
                source_keys=source_keys,
            ))
            conflicts.append(EvidenceConflictRecord(
                conflict_id=f"atomic.conflict.company.{dataset_key}.payload_hash",
                code=code,
                affected_sources=source_keys,
                severity="high",
                policy_effect="shadow_only_no_formal_authority",
            ))
            return

        availability.append(EvidenceAvailabilityRecord(
            capability=f"company_dataset.{dataset_key}",
            status="stale" if stale else "available",
            reason_codes=("dataset_stale",) if stale else (),
            source_keys=source_keys,
        ))
        if context.instrument and context.instrument.market != "HK":
            return
        if dataset_key == "profit_cashflow_drivers":
            row = _latest_row(payload.get("annual_driver_history") if isinstance(payload, dict) else None)
            if row:
                facts.extend(self._facts_from_row(context, dataset_key, ref, raw_snapshot, row, stale))
        elif dataset_key == "margin_structure":
            row = _latest_row(payload.get("company_margin_history") if isinstance(payload, dict) else None)
            if row:
                facts.extend(self._facts_from_row(context, dataset_key, ref, raw_snapshot, row, stale))

    @staticmethod
    def _facts_from_row(context, dataset_key, ref, raw_snapshot, row, stale) -> Iterable[AtomicFactRecord]:
        report_date = str(row.get("report_date") or "")[:10]
        announced_at = str(row.get("announced_at") or "").strip() or None
        report_type = str(row.get("report_type") or "annual").strip() or None
        metrics = (
            "revenue",
            "revenue_yoy_percent",
            "gross_profit",
            "gross_profit_yoy_percent",
            "holder_profit",
            "holder_profit_yoy_percent",
            "operating_cashflow_to_sales_percent",
            "roe_percent",
            "roic_percent",
            "gross_margin_percent",
            "net_margin_percent",
        )
        results = []
        for metric in metrics:
            value = _number(row.get(metric))
            if value is None:
                continue
            unit, comparison_type, adequacy, materiality = _fact_spec(metric)
            provenance = canonical_hash({
                "context_input_hash": context.input_hash,
                "research_snapshot_id": raw_snapshot.snapshot_id,
                "payload_hash": raw_snapshot.payload_hash,
                "dataset_key": dataset_key,
                "metric": metric,
                "period_end": report_date,
                "report_type": report_type,
                "announced_at": announced_at,
                "value": value,
                "available_at": raw_snapshot.available_at,
                "retrieved_at": raw_snapshot.fetched_at,
            })
            results.append(AtomicFactRecord(
                fact_id=_fact_id(dataset_key, report_date, metric),
                symbol=context.symbol,
                market=context.instrument.market if context.instrument else None,
                domain="fundamental",
                dimension="fundamental_company",
                metric=metric,
                value=value,
                unit=unit,
                period_end=report_date or None,
                report_type=report_type,
                announced_at=announced_at,
                comparison_type=comparison_type,
                source_evidence_id=f"research_snapshot:{raw_snapshot.snapshot_id}",
                source_name=str(ref.get("provider") or raw_snapshot.provider),
                source_reference=raw_snapshot.source_reference,
                source_timestamp=str(ref.get("as_of") or raw_snapshot.as_of),
                available_at=raw_snapshot.available_at,
                retrieved_at=raw_snapshot.fetched_at,
                observed_at=context.generated_at,
                freshness_status="stale" if stale else "fresh",
                retrieval_freshness="stale" if stale else "fresh",
                polarity=_polarity(metric, value),
                materiality=materiality,
                comparison_adequacy=adequacy,
                confidence=.50 if stale else .75,
                provenance_hash=provenance,
            ))
        return results


__all__ = ["AtomicResearchSourceResult", "CompanyResearchAtomicSource"]
