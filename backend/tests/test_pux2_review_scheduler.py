from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.application_services.personal_universe.review_service import PersonalUniverseReviewService
from app.domain.personal_universe import AnalysisDepth, ReviewMode, ReviewPlan
from app.review_scheduler_runtime import install


TZ = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 8, 28, 10, 0, tzinfo=TZ)


class FakeStore:
    def __init__(self, positions=()) -> None:
        self.positions = list(positions)

    def paper_account(self):
        return {"positions": list(self.positions)}


class FakePersonalRepository:
    def __init__(self, *, watches=None, decisions=None) -> None:
        self.watches = watches or {}
        self.decisions = decisions or {}

    def watchlist_item(self, symbol):
        return self.watches.get(symbol)

    def latest_decisions(self, symbols):
        return {symbol: self.decisions[symbol] for symbol in symbols if symbol in self.decisions}


class FakeReviewPlanRepository:
    def __init__(self) -> None:
        self.saved: list[ReviewPlan] = []

    def save(self, plan: ReviewPlan):
        self.saved.append(plan)
        return f"plan-{len(self.saved)}"

    def latest(self, symbol: str):
        rows = [plan for plan in self.saved if plan.symbol == symbol]
        return rows[-1] if rows else None

    def latest_mode_evaluated_at(self, symbol: str, mode: ReviewMode):
        rows = [
            plan.evaluated_at
            for plan in self.saved
            if plan.symbol == symbol and plan.mode is mode
        ]
        return max(rows) if rows else None


def _decision(*, at=NOW - timedelta(hours=1), review_after=None, material_change=False):
    return {
        "generated_at": at.isoformat(),
        "decision_memory": {
            "review_after": review_after.isoformat() if review_after else None,
            "material_change": material_change,
        },
    }


def test_stable_position_records_one_guard_plan_without_scheduler_tick_spam():
    repository = FakeReviewPlanRepository()
    service = PersonalUniverseReviewService(
        FakeStore([{"symbol": "600519", "quantity": 100}]),
        FakePersonalRepository(
            decisions={"600519": _decision(review_after=NOW + timedelta(days=1))},
        ),
        repository,
    )

    first = service.scheduler_plan("600519", evaluated_at=NOW)
    assert first is not None
    assert first.mode is ReviewMode.GUARD_ONLY
    service.record(first)

    second = service.scheduler_plan("600519", evaluated_at=NOW + timedelta(minutes=5))
    assert second is not None
    recorded = service.record(second)

    assert recorded is first
    assert len(repository.saved) == 1
    assert "no_material_change" in recorded.reason_codes


def test_watchlist_routine_full_research_is_budgeted_once_per_local_day():
    repository = FakeReviewPlanRepository()
    service = PersonalUniverseReviewService(
        FakeStore(),
        FakePersonalRepository(watches={"000001": SimpleNamespace(enabled=True)}),
        repository,
    )

    first = service.scheduler_plan("000001", evaluated_at=NOW)
    assert first is not None and first.mode is ReviewMode.FULL_RESEARCH
    service.record(first)

    second = service.scheduler_plan("000001", evaluated_at=NOW + timedelta(hours=1))
    assert second is not None
    assert second.mode is ReviewMode.NO_REVIEW
    assert second.reason_codes == ("routine_full_research_budget_exhausted",)


def test_explicit_request_stays_pending_until_a_newer_decision_consumes_it():
    repository = FakeReviewPlanRepository()
    personal = FakePersonalRepository(
        decisions={"600519": _decision(review_after=NOW + timedelta(days=1))},
    )
    service = PersonalUniverseReviewService(
        FakeStore([{"symbol": "600519", "quantity": 100}]),
        personal,
        repository,
    )

    requested = service.request_full_review("600519", evaluated_at=NOW)
    assert requested.mode is ReviewMode.FULL_RESEARCH
    assert requested.budget_override is True
    assert "explicit_user_request" in requested.reason_codes

    pending = service.scheduler_plan("600519", evaluated_at=NOW + timedelta(minutes=1))
    assert pending is not None and pending.mode is ReviewMode.FULL_RESEARCH

    personal.decisions["600519"] = _decision(
        at=NOW + timedelta(minutes=2),
        review_after=NOW + timedelta(days=1),
    )
    consumed = service.scheduler_plan("600519", evaluated_at=NOW + timedelta(minutes=3))
    assert consumed is not None and consumed.mode is ReviewMode.GUARD_ONLY


def test_new_material_decision_upgrades_once_to_full_research():
    repository = FakeReviewPlanRepository()
    old = ReviewPlan(
        policy_version="PUX2_REVIEW_V1",
        symbol="600519",
        evaluated_at=NOW - timedelta(hours=2),
        mode=ReviewMode.GUARD_ONLY,
        analysis_depth=AnalysisDepth.GUARDS,
        reason_codes=("position_guard_monitoring", "no_material_change"),
        last_review_at=NOW - timedelta(hours=3),
        next_review_at=NOW + timedelta(days=1),
        routine_full_research_available=True,
        budget_override=False,
    )
    repository.saved.append(old)
    service = PersonalUniverseReviewService(
        FakeStore([{"symbol": "600519", "quantity": 100}]),
        FakePersonalRepository(
            decisions={
                "600519": _decision(
                    at=NOW - timedelta(hours=1),
                    review_after=NOW + timedelta(days=1),
                    material_change=True,
                )
            }
        ),
        repository,
    )

    plan = service.scheduler_plan("600519", evaluated_at=NOW)
    assert plan is not None
    assert plan.mode is ReviewMode.FULL_RESEARCH
    assert "material_change" in plan.reason_codes


class FakeReviewService:
    def __init__(self, plans):
        self.plans = plans
        self.recorded = []
        self.explicit_flags = []

    def scheduler_plan(self, symbol, *, evaluated_at, explicit_user_request=False):
        self.explicit_flags.append(explicit_user_request)
        return self.plans.get(symbol)

    def record(self, plan):
        self.recorded.append(plan.symbol)
        return plan

    def latest(self, _symbol):
        return None

    def request_full_review(self, _symbol, *, evaluated_at):
        raise LookupError


def _plan(symbol: str, mode: ReviewMode) -> ReviewPlan:
    depth = {
        ReviewMode.NO_REVIEW: AnalysisDepth.NONE,
        ReviewMode.GUARD_ONLY: AnalysisDepth.GUARDS,
        ReviewMode.POSITION_REVIEW: AnalysisDepth.POSITION,
        ReviewMode.FULL_RESEARCH: AnalysisDepth.FULL,
    }[mode]
    return ReviewPlan(
        policy_version="PUX2_REVIEW_V1",
        symbol=symbol,
        evaluated_at=NOW,
        mode=mode,
        analysis_depth=depth,
        reason_codes=(f"test_{mode.value.lower()}",),
        last_review_at=None,
        next_review_at=None,
        routine_full_research_available=True,
        budget_override=False,
    )


def test_runtime_filters_guard_only_from_news_company_and_decision_research():
    service = FakeReviewService({
        "600519": _plan("600519", ReviewMode.GUARD_ONLY),
        "000001": _plan("000001", ReviewMode.POSITION_REVIEW),
        "000002": _plan("000002", ReviewMode.FULL_RESEARCH),
    })
    calls = {"news": [], "company": [], "decision": [], "stages": []}
    module = SimpleNamespace()
    module.store = object()
    module.beijing_now = lambda: NOW
    module.personal_universe_review_service_v2 = service
    module.app = SimpleNamespace(routes=[], include_router=lambda _router: None)
    module._record_simulation_stage = lambda *args, **kwargs: calls["stages"].append((args, kwargs))
    module.refresh_paper_market_intelligence = lambda symbols, _names: calls["news"].append(list(symbols))
    module.refresh_company_intelligence_focus = (
        lambda symbols, *, research_priority, run_id=None: calls["company"].append(list(symbols)) or len(symbols)
    )
    module.prepare_paper_decisions = (
        lambda symbols, run_id=None, names=None: calls["decision"].append(list(symbols)) or len(symbols)
    )

    def original_cycle(requested_symbols, force=False, allow_when_disabled=False):
        symbols = ["600519", "000001", "000002", "999999"]
        module.refresh_paper_market_intelligence(symbols, {})
        module.refresh_company_intelligence_focus(symbols, research_priority="L4", run_id="run-1")
        generated = module.prepare_paper_decisions(symbols, run_id="run-1", names={})
        return {"executed": 0, "skipped": 0, "run_id": "run-1", "generated": generated}

    module.run_paper_trading_cycle = original_cycle
    install(module)

    result = module.run_paper_trading_cycle(["600519"])

    assert result["generated"] == 3
    assert calls["news"] == [["000001", "000002", "999999"]]
    assert calls["company"] == [["000002", "999999"]]
    assert calls["decision"] == [["000001", "000002", "999999"]]
    assert service.recorded == ["600519", "000001", "000002"]
    assert not any(service.explicit_flags)


def test_force_cycle_is_seen_as_explicit_review_permission():
    service = FakeReviewService({"600519": _plan("600519", ReviewMode.FULL_RESEARCH)})
    module = SimpleNamespace(
        store=object(),
        beijing_now=lambda: NOW,
        personal_universe_review_service_v2=service,
        app=SimpleNamespace(routes=[], include_router=lambda _router: None),
        _record_simulation_stage=lambda *args, **kwargs: None,
        refresh_paper_market_intelligence=lambda _symbols, _names: None,
        refresh_company_intelligence_focus=lambda _symbols, *, research_priority, run_id=None: 0,
        prepare_paper_decisions=lambda _symbols, run_id=None, names=None: 1,
    )

    def original_cycle(requested_symbols, force=False, allow_when_disabled=False):
        module.prepare_paper_decisions(["600519"], run_id="run-force", names={})
        return {"executed": 0, "skipped": 0, "run_id": "run-force"}

    module.run_paper_trading_cycle = original_cycle
    install(module)
    module.run_paper_trading_cycle(["600519"], force=True)

    assert any(service.explicit_flags)
