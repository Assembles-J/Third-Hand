"""PUX2 scheduler-facing ReviewPlan orchestration.

This service decides research permission for the Personal Universe only. It does
not select formal candidates, generate actions, size orders or execute trades.
The paper/runtime layers remain responsible for those authorities.
"""
from __future__ import annotations

from datetime import datetime

from app.domain.personal_universe import ReviewMode, ReviewPlan, ReviewPolicyInput, plan_review
from app.time_utils import BEIJING_TIMEZONE


class PersonalUniverseReviewService:
    def __init__(self, store, personal_repository, review_plan_repository) -> None:
        self.store = store
        self.personal_repository = personal_repository
        self.review_plan_repository = review_plan_repository

    def latest(self, symbol: str) -> ReviewPlan | None:
        return self.review_plan_repository.latest(symbol)

    def scheduler_plan(
        self,
        symbol: str,
        *,
        evaluated_at: datetime,
        explicit_user_request: bool = False,
    ) -> ReviewPlan | None:
        """Compute a local-only review permission for one Personal Universe symbol.

        Symbols outside the active Personal Universe return ``None`` so the
        existing deterministic candidate runtime remains unchanged until PUX3
        explicitly demotes that separate Discovery workflow.
        """
        canonical = str(symbol or "").strip().upper()
        if not canonical:
            return None
        evaluated_at = _aware(evaluated_at)

        positions = {
            str(item.get("symbol") or "").strip().upper()
            for item in (self.store.paper_account().get("positions") or [])
            if str(item.get("symbol") or "").strip()
        }
        watch = self.personal_repository.watchlist_item(canonical)
        has_position = canonical in positions
        watchlist_enabled = bool(watch is not None and watch.enabled)
        if not has_position and not watchlist_enabled:
            return None

        decision = self.personal_repository.latest_decisions([canonical]).get(canonical) or {}
        decision_at = _decision_time(decision)
        memory = decision.get("decision_memory") if isinstance(decision, dict) else None
        memory = memory if isinstance(memory, dict) else {}
        review_after = _optional_datetime(memory.get("review_after"))

        latest_plan = self.review_plan_repository.latest(canonical)
        latest_plan_at = latest_plan.evaluated_at if latest_plan is not None else None
        pending_explicit_request = bool(
            latest_plan is not None
            and "explicit_user_request" in latest_plan.reason_codes
            and (decision_at is None or latest_plan.evaluated_at >= decision_at)
        )
        new_material_change = bool(
            memory.get("material_change")
            and decision_at is not None
            and (latest_plan_at is None or decision_at > latest_plan_at)
        )

        last_full_research_at = self.review_plan_repository.latest_mode_evaluated_at(
            canonical,
            ReviewMode.FULL_RESEARCH,
        )
        return plan_review(
            ReviewPolicyInput(
                symbol=canonical,
                evaluated_at=evaluated_at,
                has_position=has_position,
                watchlist_enabled=watchlist_enabled,
                material_change=new_material_change,
                # PUX2.3 keeps cheap risk/quote/T+1 acquisition alive in the
                # runtime even when no formal review is generated. A later
                # dedicated guard-event adapter may promote this flag from a
                # typed persisted hard-guard transition.
                hard_guard_due=False,
                explicit_user_request=explicit_user_request or pending_explicit_request,
                review_after=review_after,
                last_review_at=decision_at,
                last_full_research_at=last_full_research_at,
                next_routine_review_at=review_after,
            )
        )

    def record(self, plan: ReviewPlan) -> ReviewPlan:
        """Persist only a semantic ReviewPlan transition, not every scheduler tick."""
        latest = self.review_plan_repository.latest(plan.symbol)
        if latest is not None and _same_semantics(latest, plan):
            return latest
        self.review_plan_repository.save(plan)
        return plan

    def request_full_review(self, symbol: str, *, evaluated_at: datetime) -> ReviewPlan:
        """Persist an explicit full-review request without bypassing formal scope.

        The request is research permission only. It neither injects the symbol
        into the formal candidate cohort nor executes a paper trade.
        """
        plan = self.scheduler_plan(
            symbol,
            evaluated_at=evaluated_at,
            explicit_user_request=True,
        )
        if plan is None:
            raise LookupError("symbol is outside the active Personal Universe")
        return self.record(plan)


def _decision_time(decision: dict[str, object]) -> datetime | None:
    return _optional_datetime(
        decision.get("generated_at")
        or decision.get("created_at")
        or decision.get("_persisted_created_at")
    )


def _optional_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return _aware(value)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return _aware(parsed)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=BEIJING_TIMEZONE)
    return value.astimezone(BEIJING_TIMEZONE)


def _same_semantics(left: ReviewPlan, right: ReviewPlan) -> bool:
    return bool(
        left.policy_version == right.policy_version
        and left.symbol == right.symbol
        and left.mode == right.mode
        and left.analysis_depth == right.analysis_depth
        and left.reason_codes == right.reason_codes
        and left.last_review_at == right.last_review_at
        and left.next_review_at == right.next_review_at
        and left.routine_full_research_available == right.routine_full_research_available
        and left.budget_override == right.budget_override
    )
