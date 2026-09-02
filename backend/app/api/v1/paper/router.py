"""V2-native paper scheduling diagnostics and user-owned paper actions."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.application_services.paper.manual_order import ManualPaperOrderRejected
from app.application_services.paper.simulation_session import PaperSimulationRestartRejected
from app.hk_stock_connect_paper_contract import HkStockConnectPaperContract
from app.market_adapter import adapter_for_market


class ManualPaperOrderInput(BaseModel):
    client_order_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=16)
    side: str = Field(min_length=3, max_length=4)
    quantity: float = Field(gt=0)


class PaperSimulationRestartInput(BaseModel):
    client_restart_id: str = Field(min_length=1, max_length=128)
    initial_cash: float = Field(gt=0, le=1_000_000_000)


def _decorate_manual_order_capability(manual_order_service, capability: dict[str, object]) -> dict[str, object]:
    """Attach machine-readable HK prerequisites without changing fill authority.

    The existing summary rejection code stays first for backward-compatible
    clients. Detailed blockers are additive facts for Android/operations and
    future Phase 2D execution work.
    """

    result = dict(capability)
    if str(result.get("market") or "").strip().upper() != "HK":
        return result

    symbol = str(result.get("symbol") or "").strip().upper()
    metadata = manual_order_service.store.instrument_metadata(symbol)
    contract = HkStockConnectPaperContract().evaluate(
        metadata=metadata,
        adapter=adapter_for_market("HK"),
        now=manual_order_service.now_provider(),
        # Phase 2C intentionally has no trusted FX ingestion source and no
        # broker/participant pass-through policy yet. Missing facts remain
        # explicit blockers instead of being guessed from an internet quote.
        fx_observation=None,
        broker_commission_policy=None,
        participant_clearing_pass_through_policy=None,
    )
    result["execution_contract"] = contract
    reasons = list(result.get("reason_codes") or [])
    reasons.extend(contract["blocking_reason_codes"])
    result["reason_codes"] = list(dict.fromkeys(str(reason) for reason in reasons if reason))
    result["executable"] = bool(result.get("executable")) and bool(contract["execution_ready"])
    return result


def create_paper_schedule_router(
    schedule_state,
    manual_order_service=None,
    simulation_service=None,
    runtime_state_service=None,
    ledger_mutation_lock=None,
) -> APIRouter:
    router = APIRouter(prefix="/v1/paper-trading", tags=["paper-trading"])

    @router.get("/adaptive-plan")
    def adaptive_plan() -> dict[str, object]:
        return dict(schedule_state())

    if runtime_state_service is not None:
        @router.get("/runtime-state")
        def runtime_state() -> dict[str, object]:
            return runtime_state_service.state()

    if simulation_service is not None:
        @router.get("/epochs")
        def paper_simulation_epochs(limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, object]]:
            return simulation_service.epochs(limit=limit)

        @router.post("/restart")
        def restart_paper_simulation(payload: PaperSimulationRestartInput) -> dict[str, object]:
            acquired = False
            try:
                if ledger_mutation_lock is not None:
                    acquired = bool(ledger_mutation_lock.acquire(blocking=False))
                    if not acquired:
                        raise PaperSimulationRestartRejected("paper_restart_runtime_busy")
                return simulation_service.restart(
                    initial_cash=payload.initial_cash,
                    client_restart_id=payload.client_restart_id,
                )
            except PaperSimulationRestartRejected as error:
                raise HTTPException(
                    status_code=409,
                    detail={"reason_code": str(error)},
                ) from error
            finally:
                if acquired:
                    ledger_mutation_lock.release()

    if manual_order_service is not None:
        @router.get("/order-capability/{symbol}")
        def manual_order_capability(symbol: str) -> dict[str, object]:
            return _decorate_manual_order_capability(
                manual_order_service,
                manual_order_service.capability(symbol),
            )

        @router.post("/orders")
        def submit_manual_order(payload: ManualPaperOrderInput) -> dict[str, object]:
            try:
                if ledger_mutation_lock is None:
                    return manual_order_service.submit(
                        client_order_id=payload.client_order_id,
                        symbol=payload.symbol,
                        side=payload.side,
                        quantity=payload.quantity,
                    )
                with ledger_mutation_lock:
                    return manual_order_service.submit(
                        client_order_id=payload.client_order_id,
                        symbol=payload.symbol,
                        side=payload.side,
                        quantity=payload.quantity,
                    )
            except ManualPaperOrderRejected as error:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "reason_code": error.reason_code,
                        "capability": _decorate_manual_order_capability(
                            manual_order_service,
                            error.capability,
                        ),
                    },
                ) from error
            except ValueError as error:
                raise HTTPException(
                    status_code=422,
                    detail={"reason_code": str(error)},
                ) from error

    return router
