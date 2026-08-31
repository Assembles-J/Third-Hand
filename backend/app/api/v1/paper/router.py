"""V2-native paper scheduling diagnostics and user manual paper orders."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.application_services.paper.manual_order import ManualPaperOrderRejected


class ManualPaperOrderInput(BaseModel):
    client_order_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=16)
    side: str = Field(min_length=3, max_length=4)
    quantity: float = Field(gt=0)


def create_paper_schedule_router(schedule_state, manual_order_service=None) -> APIRouter:
    router = APIRouter(prefix="/v1/paper-trading", tags=["paper-trading"])

    @router.get("/adaptive-plan")
    def adaptive_plan() -> dict[str, object]:
        return dict(schedule_state())

    if manual_order_service is not None:
        @router.get("/order-capability/{symbol}")
        def manual_order_capability(symbol: str) -> dict[str, object]:
            return manual_order_service.capability(symbol)

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
                        "capability": error.capability,
                    },
                ) from error
            except ValueError as error:
                raise HTTPException(
                    status_code=422,
                    detail={"reason_code": str(error)},
                ) from error

    return router
