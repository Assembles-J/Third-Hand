"""Runtime wiring for Phase-2 store-aware Atomic Evidence enrichment."""
from __future__ import annotations

from app.atomic_company_builder import CompanyAwareAtomicEvidenceBuilder


def install(m) -> None:
    """Attach persisted company research to the already-shadow-only builder.

    The orchestrator still constructs Atomic Evidence only after deterministic
    policy candidates are frozen.  This installer therefore adds observability
    and persistence, not formal trade authority or a new remote-data dependency.
    """
    if getattr(m, "_atomic_evidence_runtime_installed", False):
        return
    m._atomic_evidence_runtime_installed = True
    current = m.decision_orchestrator.atomic_evidence_builder
    if isinstance(current, CompanyAwareAtomicEvidenceBuilder):
        return
    m.decision_orchestrator.atomic_evidence_builder = CompanyAwareAtomicEvidenceBuilder(
        m.store,
        base_builder=current,
    )


__all__ = ["install"]
