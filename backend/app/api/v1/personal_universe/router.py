"""FastAPI routes for Personal Universe.

The read route is local-only and never triggers remote acquisition or model
execution. Watchlist mutation remains user-attention metadata only.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from app.api.v1.personal_universe.schemas import (
    PersonalUniverseCounts,
    PersonalUniverseItemResponse,
    PersonalUniverseResponse,
    WatchlistItemResponse,
    WatchlistUpdateRequest,
)
from app.domain.personal_universe import WatchlistPriority
from app.time_utils import beijing_now


def create_personal_universe_router(service, repository) -> APIRouter:
    router = APIRouter(tags=["personal-universe"])

    @router.get("/v1/personal-universe", response_model=PersonalUniverseResponse)
    def personal_universe() -> PersonalUniverseResponse:
        items = service.build()
        position_count = sum(1 for item in items if "POSITION" in item.membership.value)
        watchlist_count = sum(1 for item in items if "WATCHLIST" in item.membership.value)
        warnings: list[str] = []
        unavailable_quotes = sum(1 for item in items if item.quote_display_state == "unavailable")
        if unavailable_quotes:
            warnings.append(f"{unavailable_quotes} 个标的缺少可展示行情")
        data_state = "partial" if warnings else "ready"
        return PersonalUniverseResponse(
            generated_at=beijing_now(),
            items=[PersonalUniverseItemResponse.model_validate(asdict(item)) for item in items],
            counts=PersonalUniverseCounts(
                positions=position_count,
                watchlist=watchlist_count,
                combined=len(items),
            ),
            data_state=data_state,
            warnings=warnings,
        )

    @router.put("/v1/watchlist/{symbol}", response_model=WatchlistItemResponse)
    def update_watchlist(symbol: str, payload: WatchlistUpdateRequest) -> WatchlistItemResponse:
        priority = WatchlistPriority(payload.priority) if payload.priority is not None else None
        try:
            item = repository.update_watchlist_item(
                symbol,
                name=payload.name,
                enabled=payload.enabled,
                priority=priority,
                note=payload.note,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if item is None:
            raise HTTPException(status_code=404, detail="未找到自选股")
        return WatchlistItemResponse(
            symbol=item.symbol,
            name=item.name,
            enabled=item.enabled,
            priority=item.priority.value,
            note=item.note,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    return router
