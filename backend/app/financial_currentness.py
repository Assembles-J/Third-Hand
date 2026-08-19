"""Deterministic financial report-period currentness for frozen Atomic Evidence.

Retrieval freshness answers whether a snapshot was fetched/validated recently.
Financial currentness answers whether the underlying report observation is the
latest period we can treat as current confirmation.  The two must never be
collapsed: a historical report fetched today is still historical evidence.
"""
from __future__ import annotations

from datetime import date, datetime

from app import decision_config as config
from app.atomic_models import AtomicFactRecord, FinancialCurrentnessSnapshot


class FinancialCurrentnessPolicy:
    """Annotate financial facts without changing their historical polarity."""

    version = config.FINANCIAL_CURRENTNESS_POLICY_VERSION

    @staticmethod
    def _date(value: object) -> date | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text[:10]).date()
        except ValueError:
            return None

    @staticmethod
    def _is_financial_fact(fact: AtomicFactRecord) -> bool:
        return fact.domain == "fundamental" and fact.dimension == "fundamental_company"

    @staticmethod
    def _is_upcoming_earnings(fact: AtomicFactRecord) -> bool:
        return (
            fact.dimension == "corporate_event"
            and fact.metric.startswith("event.upcoming.earnings_report.")
            and fact.polarity == "NEUTRAL_MATERIAL"
        )

    def evaluate(
        self,
        facts: tuple[AtomicFactRecord, ...],
        *,
        has_financial_conflict: bool = False,
    ) -> tuple[tuple[AtomicFactRecord, ...], FinancialCurrentnessSnapshot]:
        financial = tuple(fact for fact in facts if self._is_financial_fact(fact))
        report_dates = tuple(
            parsed
            for fact in financial
            if (parsed := self._date(fact.period_end)) is not None
        )
        latest_observed_date = max(report_dates) if report_dates else None
        latest_observed = latest_observed_date.isoformat() if latest_observed_date else None

        earnings_dates = tuple(
            parsed
            for fact in facts
            if self._is_upcoming_earnings(fact)
            if (parsed := self._date(fact.value or fact.period_end)) is not None
        )
        expected_report_at = min(earnings_dates).isoformat() if earnings_dates else None
        expected_date = self._date(expected_report_at)

        def _verified_current_fact(fact: AtomicFactRecord) -> bool:
            announced = self._date(fact.announced_at)
            period = self._date(fact.period_end)
            return (
                expected_date is not None
                and announced is not None
                and announced >= expected_date
                and period is not None
                and period == latest_observed_date
            )

        verified_after_event = any(_verified_current_fact(fact) for fact in financial)

        if has_financial_conflict:
            current_confirmation = "CONFLICTED"
            latest_period_status = "UNKNOWN"
            reasons = ("financial_source_conflict",)
        elif expected_date is not None and verified_after_event:
            current_confirmation = "CONFIRMED"
            latest_period_status = "CURRENT"
            reasons = (f"verified_report_available_for_event:{expected_report_at}",)
        elif expected_date is not None:
            current_confirmation = "PENDING"
            latest_period_status = "PENDING_EXPECTED_REPORT"
            reasons = (f"earnings_report_pending:{expected_report_at}",)
        elif report_dates:
            # Without an authoritative reporting-calendar signal we preserve the
            # period as valid history but do not fabricate current confirmation.
            current_confirmation = "UNKNOWN"
            latest_period_status = "HISTORICAL_VALID"
            reasons = ("no_authoritative_expected_report_signal",)
        else:
            current_confirmation = "UNKNOWN"
            latest_period_status = "UNKNOWN"
            reasons = ("financial_report_period_unknown",)

        annotated: list[AtomicFactRecord] = []
        for fact in facts:
            if not self._is_financial_fact(fact):
                annotated.append(fact)
                continue
            if self._date(fact.period_end) is None:
                observation_currentness = "UNKNOWN"
            elif latest_period_status == "CURRENT" and _verified_current_fact(fact):
                observation_currentness = "CURRENT"
            elif latest_period_status == "PENDING_EXPECTED_REPORT":
                observation_currentness = "PENDING_EXPECTED_REPORT"
            elif latest_period_status == "HISTORICAL_VALID":
                observation_currentness = "HISTORICAL_VALID"
            else:
                observation_currentness = "UNKNOWN"
            annotated.append(fact.model_copy(update={
                "retrieval_freshness": fact.retrieval_freshness or fact.freshness_status,
                "observation_currentness": observation_currentness,
                "expected_report_at": expected_report_at,
            }))

        return tuple(annotated), FinancialCurrentnessSnapshot(
            policy_version=self.version,
            latest_observed_period=latest_observed,
            expected_report_at=expected_report_at,
            latest_period_status=latest_period_status,
            current_confirmation=current_confirmation,
            reason_codes=reasons,
        )


__all__ = ["FinancialCurrentnessPolicy"]
