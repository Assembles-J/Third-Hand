from datetime import datetime, timedelta, timezone

from app.domain.personal_universe import ReviewPolicyInput, plan_review
from app.infrastructure.database.review_plan_repository import ReviewPlanRepository
from app.migrations import run_migrations
from app.storage import PortfolioStore


def test_review_plan_persistence_is_append_only_and_idempotent(tmp_path) -> None:
    database = tmp_path / "review.db"
    store = PortfolioStore(database)
    run_migrations(database)
    repository = ReviewPlanRepository(store)
    now = datetime(2026, 8, 25, 10, 0, tzinfo=timezone(timedelta(hours=8)))
    plan = plan_review(ReviewPolicyInput(
        symbol="01810", evaluated_at=now, has_position=True, watchlist_enabled=True,
    ))

    first = repository.save(plan)
    second = repository.save(plan)
    restored = repository.latest("01810")

    assert first == second
    assert restored == plan
    with store._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM review_plans").fetchone()[0] == 1
