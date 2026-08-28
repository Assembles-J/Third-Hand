"""Install PUX2 ReviewPlan consumption around the existing paper scheduler.

The wrapper intentionally leaves candidate selection, Formal Action, Risk,
Sizing, ExecutionPrecheck and Paper Broker untouched. It only decides whether a
scheduler-owned Personal Universe symbol may enter expensive research work.
"""
from __future__ import annotations

from contextvars import ContextVar

from app.api.v1.review.router import create_review_router
from app.application_services.personal_universe.review_service import PersonalUniverseReviewService
from app.domain.personal_universe import ReviewMode
from app.infrastructure.database.personal_universe_repository import PersonalUniverseRepository
from app.infrastructure.database.review_plan_repository import ReviewPlanRepository


_explicit_cycle: ContextVar[bool] = ContextVar("pux2_explicit_review_cycle", default=False)


def install(m) -> None:
    if getattr(m, "_pux2_review_scheduler_installed", False):
        return
    m._pux2_review_scheduler_installed = True

    service = getattr(m, "personal_universe_review_service_v2", None)
    if service is None:
        personal_repository = getattr(m, "personal_universe_repository_v2", None)
        if personal_repository is None:
            personal_repository = PersonalUniverseRepository(m.store)
            m.personal_universe_repository_v2 = personal_repository
        review_repository = ReviewPlanRepository(m.store)
        service = PersonalUniverseReviewService(m.store, personal_repository, review_repository)
        m.review_plan_repository_v2 = review_repository
        m.personal_universe_review_service_v2 = service

    existing_paths = {getattr(route, "path", None) for route in m.app.routes}
    if "/v1/review-plan/{symbol}" not in existing_paths:
        m.app.include_router(create_review_router(service))

    original_run_cycle = m.run_paper_trading_cycle
    original_refresh_market_intelligence = m.refresh_paper_market_intelligence
    original_prepare_decisions = m.prepare_paper_decisions
    original_refresh_company = getattr(m, "refresh_company_intelligence_focus", None)

    def review_plan(symbol: str):
        return service.scheduler_plan(
            symbol,
            evaluated_at=m.beijing_now(),
            explicit_user_request=_explicit_cycle.get(),
        )

    def run_paper_trading_cycle(
        requested_symbols: list[str],
        force: bool = False,
        allow_when_disabled: bool = False,
    ) -> dict[str, object]:
        # Existing force=true is already an explicit operator/manual request.
        # Treat it as a full-review override for Personal Universe symbols while
        # leaving formal candidate membership and execution gates unchanged.
        token = _explicit_cycle.set(bool(force))
        try:
            return original_run_cycle(
                requested_symbols,
                force=force,
                allow_when_disabled=allow_when_disabled,
            )
        finally:
            _explicit_cycle.reset(token)

    def refresh_paper_market_intelligence(symbols: list[str], names: dict[str, str]) -> None:
        permitted: list[str] = []
        for symbol in symbols:
            plan = review_plan(symbol)
            if plan is None or plan.mode in {ReviewMode.POSITION_REVIEW, ReviewMode.FULL_RESEARCH}:
                permitted.append(symbol)
        if permitted:
            original_refresh_market_intelligence(permitted, names)

    def refresh_company_intelligence_focus(
        symbols: list[str],
        *,
        research_priority: str,
        run_id=None,
    ) -> int:
        if not callable(original_refresh_company):
            return 0
        permitted: list[str] = []
        for symbol in symbols:
            plan = review_plan(symbol)
            if plan is None or plan.mode is ReviewMode.FULL_RESEARCH:
                permitted.append(symbol)
            else:
                m._record_simulation_stage(
                    run_id,
                    "company_intelligence",
                    "skipped",
                    symbol=symbol,
                    detail={
                        "reason": f"review_policy_{plan.mode.value.lower()}",
                        "review_policy_version": plan.policy_version,
                        "review_mode": plan.mode.value,
                        "analysis_depth": plan.analysis_depth.value,
                        "usage_scope": "RESEARCH_ONLY",
                        "formal_trade_authority": False,
                    },
                )
        if not permitted:
            return 0
        return int(original_refresh_company(
            permitted,
            research_priority=research_priority,
            run_id=run_id,
        ) or 0)

    def prepare_paper_decisions(
        symbols: list[str],
        run_id: str | None = None,
        names: dict[str, str] | None = None,
    ) -> int:
        permitted: list[str] = []
        for symbol in symbols:
            plan = review_plan(symbol)
            if plan is None:
                # PUX3 owns future Discovery/candidate demotion. Do not silently
                # change that separate formal-candidate behavior in PUX2.
                permitted.append(symbol)
                continue

            recorded = service.record(plan)
            m._record_simulation_stage(
                run_id,
                "review_plan",
                "ok",
                symbol=symbol,
                detail={
                    "review_policy_version": recorded.policy_version,
                    "review_mode": recorded.mode.value,
                    "analysis_depth": recorded.analysis_depth.value,
                    "reason_codes": list(recorded.reason_codes),
                    "last_review_at": recorded.last_review_at.isoformat() if recorded.last_review_at else None,
                    "next_review_at": recorded.next_review_at.isoformat() if recorded.next_review_at else None,
                    "routine_full_research_available": recorded.routine_full_research_available,
                    "budget_override": recorded.budget_override,
                    "full_research_permitted": recorded.mode is ReviewMode.FULL_RESEARCH,
                    "formal_trade_authority": False,
                },
            )
            if recorded.mode in {ReviewMode.POSITION_REVIEW, ReviewMode.FULL_RESEARCH}:
                permitted.append(symbol)
            else:
                m._record_simulation_stage(
                    run_id,
                    "decision",
                    "skipped",
                    symbol=symbol,
                    detail={
                        "terminal_state": "review_not_due",
                        "reason": f"review_policy_{recorded.mode.value.lower()}",
                        "review_mode": recorded.mode.value,
                        "analysis_depth": recorded.analysis_depth.value,
                    },
                )

        if not permitted:
            return 0
        return int(original_prepare_decisions(permitted, run_id=run_id, names=names) or 0)

    m.run_paper_trading_cycle = run_paper_trading_cycle
    m.refresh_paper_market_intelligence = refresh_paper_market_intelligence
    if callable(original_refresh_company):
        m.refresh_company_intelligence_focus = refresh_company_intelligence_focus
    m.prepare_paper_decisions = prepare_paper_decisions
