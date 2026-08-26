from datetime import datetime, timedelta, timezone

import pytest

from app.domain.personal_universe import AnalysisDepth, ReviewMode, ReviewPolicyInput, plan_review


NOW = datetime(2026, 8, 25, 10, 0, tzinfo=timezone(timedelta(hours=8)))


def policy(**changes):
    values = dict(symbol="01810", evaluated_at=NOW, has_position=False, watchlist_enabled=True)
    values.update(changes)
    return plan_review(ReviewPolicyInput(**values))


def test_stable_position_is_guard_only_without_full_research() -> None:
    plan = policy(has_position=True, material_change=False)
    assert plan.mode is ReviewMode.GUARD_ONLY
    assert plan.analysis_depth is AnalysisDepth.GUARDS
    assert "no_material_change" in plan.reason_codes


def test_due_position_review_does_not_grant_full_research() -> None:
    plan = policy(has_position=True, review_after=NOW - timedelta(minutes=1))
    assert plan.mode is ReviewMode.POSITION_REVIEW
    assert plan.analysis_depth is AnalysisDepth.POSITION


def test_routine_full_research_budget_is_once_per_symbol_local_day() -> None:
    plan = policy(last_full_research_at=NOW - timedelta(hours=1))
    assert plan.mode is ReviewMode.NO_REVIEW
    assert plan.routine_full_research_available is False
    assert plan.reason_codes == ("routine_full_research_budget_exhausted",)


def test_material_change_and_user_request_are_audited_overrides() -> None:
    material = policy(material_change=True, last_full_research_at=NOW)
    requested = policy(explicit_user_request=True, last_full_research_at=NOW)
    assert material.mode is ReviewMode.FULL_RESEARCH
    assert requested.mode is ReviewMode.FULL_RESEARCH
    assert material.budget_override and requested.budget_override


def test_hard_guard_remains_active_when_routine_budget_is_exhausted() -> None:
    plan = policy(has_position=True, hard_guard_due=True, last_full_research_at=NOW)
    assert plan.mode is ReviewMode.GUARD_ONLY
    assert plan.reason_codes == ("hard_guard_obligation",)


def test_naive_policy_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        policy(evaluated_at=NOW.replace(tzinfo=None))
