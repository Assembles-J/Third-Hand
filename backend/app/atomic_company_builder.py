"""Store-aware Atomic Evidence builder for persisted Company Intelligence facts."""
from __future__ import annotations

from app import decision_config as config
from app.atomic_evidence import AtomicEvidenceSnapshotBuilder
from app.atomic_models import AtomicEvidenceSnapshot
from app.atomic_company_research import CompanyResearchAtomicSource
from app.domain.research.data_gateway import canonical_hash


class CompanyAwareAtomicEvidenceBuilder:
    """Enrich the base shadow snapshot without changing formal decision inputs."""

    version = config.ATOMIC_EVIDENCE_VERSION

    def __init__(self, store, base_builder=None, company_source=None) -> None:
        self.base_builder = base_builder or AtomicEvidenceSnapshotBuilder()
        self.company_source = company_source or CompanyResearchAtomicSource(store)

    def build(self, context, evidence) -> AtomicEvidenceSnapshot:
        base = self.base_builder.build(context, evidence)
        company = self.company_source.build(context)
        facts = tuple(sorted((*base.facts, *company.facts), key=lambda item: item.fact_id))
        availability = tuple(sorted((*base.availability, *company.availability), key=lambda item: item.capability))
        conflicts = tuple(sorted((*base.conflicts, *company.conflicts), key=lambda item: item.conflict_id))

        if len({item.fact_id for item in facts}) != len(facts):
            raise ValueError("combined atomic fact IDs must be unique")
        if len({item.capability for item in availability}) != len(availability):
            raise ValueError("combined atomic availability capabilities must be unique")
        if len({item.conflict_id for item in conflicts}) != len(conflicts):
            raise ValueError("combined atomic conflict IDs must be unique")

        snapshot_hash = canonical_hash({
            "version": self.version,
            "context_input_hash": context.input_hash,
            "symbol": context.symbol,
            "market": base.market,
            "facts": [item.model_dump(mode="json", exclude={"observed_at"}) for item in facts],
            "availability": [item.model_dump(mode="json") for item in availability],
            "conflicts": [item.model_dump(mode="json") for item in conflicts],
        })
        return AtomicEvidenceSnapshot(
            version=self.version,
            context_id=context.context_id,
            context_input_hash=context.input_hash,
            symbol=context.symbol,
            market=base.market,
            generated_at=context.generated_at,
            facts=facts,
            availability=availability,
            conflicts=conflicts,
            snapshot_hash=snapshot_hash,
        )


__all__ = ["CompanyAwareAtomicEvidenceBuilder"]
