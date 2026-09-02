"""V2-native paper scheduling diagnostics and user manual paper orders."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.application_services.paper.manual_order import ManualPaperOrderRejected
from app.hk_stock_connect_paper_contract import HkStockConnectPaperContract
from app.market_adapter import adapter_for_market


class ManualPaperOrderInput(BaseModel):
    client_order_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=16)
    side: str = Field(min_length=3, max_length=4)
    quantity: float = Field(gt=0)


def _decorate_manual_order_capability(
    manual_order_service,
    capability: dict[str, object],
    stock_connect_exchange_rate_service=None,
) -> dict[str, object]:
    """Attach machine-readable HK prerequisites without changing fill authority."""

    result = dict(capability)
    if str(result.get("market") or "").strip().upper() != "HK":
        return result

    symbol = str(result.get("symbol") or "").strip().upper()
    metadata = manual_order_service.store.instrument_metadata(symbol)
    fx_reference = None
    if stock_connect_exchange_rate_service is not None:
        fx_reference = stock_connect_exchange_rate_service.status().get("reference")

    contract = HkStockConnectPaperContract().evaluate(
        metadata=metadata,
        adapter=adapter_for_market("HK"),
        now=manual_order_service.now_provider(),
        fx_observation=fx_reference,
        # Phase 2D1 supplies official directional exchange-rate observations but
        # intentionally does not select broker/participant fee policies yet.
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
    stock_connect_exchange_rate_service=None,
) -> APIRouter:
    router = APIRouter(prefix="/v1/paper-trading", tags=["paper-trading"])

    @router.get("/adaptive-plan")
    def adaptive_plan() -> dict[str, object]:
        return dict(schedule_state())

    if stock_connect_exchange_rate_service is not None:
        @router.get("/stock-connect-rates")
        def stock_connect_rates() -> dict[str, object]:
            """Read only the latest locally persisted Stock Connect FX facts."""
            return dict(stock_connect_exchange_rate_service.status())

        @router.post("/stock-connect-rates/refresh")
        def refresh_stock_connect_rates() -> dict[str, object]:
            """Explicit bounded refresh of the two documented SSE rate tables."""
            return dict(stock_connect_exchange_rate_service.refresh())

    if manual_order_service is not None:
        @router.get("/order-capability/{symbol}")
        def manual_order_capability(symbol: str) -> dict[str, object]:
            return _decorate_manual_order_capability(
                manual_order_service,
                manual_order_service.capability(symbol),
                stock_connect_exchange_rate_service,
            )

        @router.post("/orders")
        def submit_manual_order(payload: ManualPaperOrderInput) -> dict[str, object]:
            try:
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
                            stock_connect_exchange_rate_service,
                        ),
                    },
                ) from error
            except ValueError as error:
                raise HTTPException(
                    status_code=422,
                    detail={"reason_code": str(error)},
                ) from error

    return router
