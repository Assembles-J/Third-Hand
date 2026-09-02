"""Register v2-native services/routers on the legacy FastAPI shell during migration.

Unlike the rejected route-table rewrite experiment, this module only adds new,
non-conflicting v2 endpoints and service seams. Dependencies are injected from
bootstrap so the new API/domain layers never import the quarantined legacy
application module.
"""
from __future__ import annotations

from app.api.v1.admin.router import create_admin_diagnostics_router
from app.api.v1.candidate.router import create_candidate_router
from app.api.v1.decision.workspace_router import create_decision_workspace_router
from app.api.v1.lab.router import create_lab_router
from app.api.v1.paper.router import create_paper_schedule_router
from app.api.v1.personal_universe.router import create_personal_universe_router
from app.api.v1.research.company_router import create_company_intelligence_router
from app.application_services.admin.day0_diagnostics import Day0DiagnosticsService
from app.application_services.candidate.service import CandidateService
from app.application_services.company.akshare_provider import CompanyAkshareProvider
from app.application_services.company.provider_registry import CompanyDataProviderRegistry
from app.application_services.company.service import CompanyIntelligenceService
from app.application_services.decision.workspace import DecisionWorkspaceService
from app.application_services.evaluation.lab_query_service import LabQueryService
from app.application_services.market.symbol_search_service import SymbolSearchService
from app.application_services.paper.manual_order import ManualPaperOrderService
from app.application_services.paper.stock_connect_exchange_rates import StockConnectExchangeRateService
from app.application_services.personal_universe.service import PersonalUniverseService
from app.application_services.research.data_gateway import ResearchDataGateway
from app.infrastructure.database.benchmark_evaluation_repository import BenchmarkEvaluationRepository
from app.infrastructure.database.candidate_repository import CandidateRepository
from app.infrastructure.database.company_intelligence_repository import CompanyIntelligenceRepository
from app.infrastructure.database.evaluation_outcome_repository import EvaluationOutcomeRepository
from app.infrastructure.database.experiment_repository import ExperimentDefinitionRepository
from app.infrastructure.database.personal_universe_repository import PersonalUniverseRepository
from app.infrastructure.database.research_data_repository import ResearchDataRepository
from app.infrastructure.database.stock_connect_exchange_rate_repository import StockConnectExchangeRateRepository
from app.infrastructure.database.strategy_evaluation_repository import StrategyEvaluationRepository
from app.infrastructure.database.symbol_search_repository import SymbolSearchRepository


def register_personal_universe_routes(application) -> None:
    """Install the Personal Universe service and routes idempotently.

    FastAPI 0.141 / Starlette 1.6 may wrap included router entries such that
    inspecting ``application.app.routes`` no longer exposes the original path on
    every outer entry. Route-path introspection is therefore not a reliable
    idempotency guard. Keep an explicit bootstrap sentinel instead.
    """
    if not hasattr(application, "personal_universe_service_v2"):
        repository = PersonalUniverseRepository(application.store)
        application.personal_universe_repository_v2 = repository
        application.personal_universe_service_v2 = PersonalUniverseService(
            application.store,
            repository,
        )

    if getattr(application, "_personal_universe_routes_registered_v2", False):
        return

    application.app.include_router(
        create_personal_universe_router(
            application.personal_universe_service_v2,
            application.personal_universe_repository_v2,
        )
    )
    application._personal_universe_routes_registered_v2 = True


def register_v2_routes(application) -> None:
    if not hasattr(application, "research_data_gateway_v2"):
        research_repository = ResearchDataRepository(application.store)
        application.research_data_repository_v2 = research_repository
        application.research_data_gateway_v2 = ResearchDataGateway(research_repository)

    if not hasattr(application, "candidate_service_v2"):
        repository = CandidateRepository(application.store)
        application.candidate_repository_v2 = repository
        application.candidate_service_v2 = CandidateService(repository)

    register_personal_universe_routes(application)

    if not hasattr(application, "symbol_search_service_v2"):
        symbol_repository = SymbolSearchRepository(application.store)
        symbol_service = SymbolSearchService(
            repository=symbol_repository,
            market_data=application.market_data,
            logger=application.logger,
        )
        application.symbol_search_repository_v2 = symbol_repository
        application.symbol_search_service_v2 = symbol_service

        # Keep the existing GET/POST symbol lookup routes and DTOs stable while
        # replacing their blocking module-global implementation. The legacy
        # route resolves this function at request time, so no duplicate route is
        # needed and Android/OCR callers remain backward compatible.
        def resolve_market_symbols_cached(names):
            return [
                application.SymbolLookupResult.model_validate(item)
                for item in symbol_service.search_many(names)
            ]

        application.resolve_market_symbols = resolve_market_symbols_cached

    if not hasattr(application, "company_intelligence_service_v2"):
        company_repository = CompanyIntelligenceRepository(application.store)
        provider_registry = CompanyDataProviderRegistry()
        CompanyAkshareProvider().register(provider_registry)
        application.company_intelligence_repository_v2 = company_repository
        application.company_provider_registry_v2 = provider_registry
        application.company_intelligence_service_v2 = CompanyIntelligenceService(
            gateway=application.research_data_gateway_v2,
            repository=company_repository,
            candidate_repository=application.candidate_repository_v2,
            provider_registry=provider_registry,
        )

        def refresh_company_intelligence_focus(symbols, *, research_priority: str, run_id=None):
            """Best-effort local-first deep research for currently focused holdings."""
            built = 0
            for symbol in dict.fromkeys(str(item).strip().upper() for item in symbols if str(item).strip()):
                try:
                    context = application.company_intelligence_service_v2.build_context(
                        symbol,
                        research_priority=research_priority,
                        allow_remote=True,
                    )
                    application._record_simulation_stage(
                        run_id,
                        "company_intelligence",
                        "ok",
                        symbol=symbol,
                        detail={
                            "research_priority": research_priority,
                            "analysis_depth": context.get("analysis_depth"),
                            "research_ready": context.get("research_ready"),
                            "missing_datasets": context.get("missing_datasets") or [],
                            "usage_scope": "RESEARCH_ONLY",
                            "formal_trade_authority": False,
                        },
                    )
                    built += 1
                except Exception as error:
                    application.logger.warning(
                        "company intelligence focus refresh unavailable symbol=%s error_type=%s",
                        symbol,
                        type(error).__name__,
                    )
                    application._record_simulation_stage(
                        run_id,
                        "company_intelligence",
                        "degraded",
                        symbol=symbol,
                        detail={
                            "research_priority": research_priority,
                            "error_type": type(error).__name__,
                            "usage_scope": "RESEARCH_ONLY",
                            "formal_trade_authority": False,
                        },
                    )
            return built

        application.refresh_company_intelligence_focus = refresh_company_intelligence_focus

    if not hasattr(application, "day0_diagnostics_service_v2"):
        application.day0_diagnostics_service_v2 = Day0DiagnosticsService(application.store)

    if not hasattr(application, "decision_workspace_service_v2"):
        application.decision_workspace_service_v2 = DecisionWorkspaceService(application.store)

    if not hasattr(application, "stock_connect_exchange_rate_service_v2"):
        stock_connect_repository = StockConnectExchangeRateRepository(application.store)
        application.stock_connect_exchange_rate_repository_v2 = stock_connect_repository
        application.stock_connect_exchange_rate_service_v2 = StockConnectExchangeRateService(
            stock_connect_repository,
        )

    if not hasattr(application, "manual_paper_order_service_v2"):
        application.manual_paper_order_service_v2 = ManualPaperOrderService(
            application.store,
            calendar=application.trading_calendar,
        )

    if not hasattr(application, "lab_query_service_v2"):
        experiment_repository = ExperimentDefinitionRepository(application.store)
        outcome_repository = EvaluationOutcomeRepository(application.store)
        strategy_evaluation_repository = StrategyEvaluationRepository(application.store)
        benchmark_evaluation_repository = BenchmarkEvaluationRepository(application.store)
        application.experiment_definition_repository_v3 = experiment_repository
        application.evaluation_outcome_repository_v3 = outcome_repository
        application.strategy_evaluation_repository_v3 = strategy_evaluation_repository
        application.benchmark_evaluation_repository_v3 = benchmark_evaluation_repository
        application.lab_query_service_v2 = LabQueryService(
            experiment_repository,
            outcome_repository,
            strategy_evaluation_repository,
            benchmark_evaluation_repository,
        )

    existing_paths = {getattr(route, "path", None) for route in application.app.routes}
    if "/v1/candidates" not in existing_paths:
        application.app.include_router(create_candidate_router(application.candidate_service_v2))
    if "/v1/admin/day0-diagnostics" not in existing_paths:
        application.app.include_router(create_admin_diagnostics_router(application.day0_diagnostics_service_v2))
    if "/v1/paper-trading/adaptive-plan" not in existing_paths:
        application.app.include_router(
            create_paper_schedule_router(
                application.adaptive_paper_schedule_state,
                application.manual_paper_order_service_v2,
                application.stock_connect_exchange_rate_service_v2,
            )
        )
    if "/v1/company-intelligence/{symbol}/requirements" not in existing_paths:
        application.app.include_router(create_company_intelligence_router(application.company_intelligence_service_v2))
    if "/v1/decisions/{symbol}/workspace" not in existing_paths:
        application.app.include_router(create_decision_workspace_router(application.decision_workspace_service_v2))
    if "/v1/lab/experiments" not in existing_paths:
        application.app.include_router(create_lab_router(application.lab_query_service_v2))
