"""Paper-trading route ownership for Architecture Refactor v2."""
from __future__ import annotations

from types import ModuleType

from fastapi import APIRouter


def build_router(legacy: ModuleType) -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/v1/paper-trading/account",
        legacy.paper_trading_account,
        methods=["GET"],
        response_model=legacy.PaperTradingAccount,
    )
    router.add_api_route(
        "/v1/paper-trading/account",
        legacy.save_paper_trading_account,
        methods=["PUT"],
        response_model=legacy.PaperTradingAccount,
    )
    router.add_api_route(
        "/v1/paper-trading/net-contributions",
        legacy.reconcile_paper_trading_contributions,
        methods=["PUT"],
        response_model=legacy.PaperTradingAccount,
    )
    router.add_api_route(
        "/v1/paper-trading/logs",
        legacy.paper_trading_logs,
        methods=["GET"],
        response_model=list[legacy.PaperTradingLog],
    )
    router.add_api_route(
        "/v1/paper-trading/equity-snapshots",
        legacy.paper_trading_equity_snapshots,
        methods=["GET"],
        response_model=list[legacy.PaperEquitySnapshot],
    )
    router.add_api_route(
        "/v1/paper-trading/status",
        legacy.paper_trading_status,
        methods=["GET"],
        response_model=legacy.PaperTradingStatus,
    )
    router.add_api_route(
        "/v1/paper-trading/dashboard",
        legacy.paper_trading_dashboard,
        methods=["GET"],
        response_model=legacy.PaperTradingDashboard,
    )
    router.add_api_route(
        "/v1/paper-trading/runs",
        legacy.paper_trading_runs,
        methods=["GET"],
    )
    router.add_api_route(
        "/v1/paper-trading/runs/{run_id}",
        legacy.paper_trading_run_detail,
        methods=["GET"],
    )
    router.add_api_route(
        "/v1/paper-trading/run",
        legacy.run_paper_trading_now,
        methods=["POST"],
    )
    router.add_api_route(
        "/v1/paper-trading/decision-audit/{decision_id}",
        legacy.paper_trading_decision_audit,
        methods=["GET"],
    )
    return router
