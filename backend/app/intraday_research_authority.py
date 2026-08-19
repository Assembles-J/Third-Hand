"""Authority firewall for pre-ActionPolicy intraday Evidence.

#47 intentionally makes 60m/15m/5m available to audit/AI before #48 grants any
formal multi-timeframe authority. The deterministic ResearchAggregator already
has a bounded adverse-new-risk veto, so feeding intraday facts into its confidence
or directional buckets would be an indirect policy change. This adapter filters
intraday-only facts/availability for formal aggregation while leaving the full
Atomic Evidence snapshot available to the AI research path and report audit.
"""
from __future__ import annotations

from app.research_assessment import ResearchAggregator


INTRADAY_RESEARCH_AUTHORITY_VERSION = "intraday-research-authority-v1-no-formal-effect"


class IntradayAuthoritySafeResearchAggregator:
    def __init__(self, base=None) -> None:
        self.base = base or ResearchAggregator()
        self.version = getattr(self.base, "version", "research-aggregation")

    def build(self, snapshot):
        formal_snapshot = snapshot.model_copy(update={
            "facts": tuple(
                fact for fact in snapshot.facts
                if fact.domain != "intraday_research"
            ),
            "availability": tuple(
                item for item in snapshot.availability
                if not item.capability.startswith("intraday.")
            ),
        })
        assessment = self.base.build(formal_snapshot)
        versions = dict(assessment.aggregation_policy_versions)
        versions["intraday_authority"] = INTRADAY_RESEARCH_AUTHORITY_VERSION
        # The assessment was derived from the formal-authority subset, but it is
        # attached to the full frozen snapshot. Keep that full snapshot identity
        # so SemanticInvariantValidator can still verify report lineage.
        return assessment.model_copy(update={
            "evidence_snapshot_hash": snapshot.snapshot_hash,
            "aggregation_policy_versions": versions,
        })


__all__ = ["INTRADAY_RESEARCH_AUTHORITY_VERSION", "IntradayAuthoritySafeResearchAggregator"]
