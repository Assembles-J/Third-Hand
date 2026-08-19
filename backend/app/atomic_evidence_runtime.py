"""Runtime wiring for store-aware Atomic Evidence enrichment."""
from __future__ import annotations

from app.atomic_company_builder import CompanyAwareAtomicEvidenceBuilder
from app.intraday_research_authority import IntradayAuthoritySafeResearchAggregator


def install(m) -> None:
    """Attach persisted company/intraday research without new formal authority.

    The orchestrator still constructs Atomic Evidence only after deterministic
    ActionPolicy candidates are frozen. Intraday facts are visible in the full
    snapshot/AI prompt, while the formal deterministic ResearchAggregator is
    explicitly filtered until the separately versioned #48 policy exists.
    """
    if getattr(m, "_atomic_evidence_runtime_installed", False):
        return
    m._atomic_evidence_runtime_installed = True
    current = m.decision_orchestrator.atomic_evidence_builder
    if not isinstance(current, CompanyAwareAtomicEvidenceBuilder):
        m.decision_orchestrator.atomic_evidence_builder = CompanyAwareAtomicEvidenceBuilder(
            m.store,
            base_builder=current,
        )

    current_aggregator = m.decision_orchestrator.research_aggregator
    if not isinstance(current_aggregator, IntradayAuthoritySafeResearchAggregator):
        m.decision_orchestrator.research_aggregator = IntradayAuthoritySafeResearchAggregator(
            current_aggregator,
        )


__all__ = ["install"]
