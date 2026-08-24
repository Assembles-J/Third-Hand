from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.application_services.personal_universe import PersonalUniverseService
from app.domain.personal_universe import PersonalUniverseMembership, WatchlistEntry, WatchlistPriority


class FakeRepository:
    def __init__(
        self,
        rows: list[WatchlistEntry],
        *,
        markets: dict[str, str] | None = None,
        decisions: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self.rows = rows
        self.markets = markets or {}
        self.decisions = decisions or {}

    def list_watchlist(self, *, include_disabled: bool = False):
        if include_disabled:
            return list(self.rows)
        return [item for item in self.rows if item.enabled]

    def instrument_markets(self, symbols):
        return {symbol: self.markets[symbol] for symbol in symbols if symbol in self.markets}

    def latest_decisions(self, symbols):
        return {symbol: self.decisions[symbol] for symbol in symbols if symbol in self.decisions}


class FakeStore:
    def __init__(self, positions, quotes) -> None:
        self._positions = positions
        self._quotes = quotes

    def paper_account(self):
        return {"positions": list(self._positions)}

    def cached_quotes(self, symbols):
        symbol_set = set(symbols)
        return [item for item in self._quotes if item["symbol"] in symbol_set]


def watch(
    symbol: str,
    priority: WatchlistPriority = WatchlistPriority.NORMAL,
    *,
    updated_at: datetime | None = None,
    enabled: bool = True,
) -> WatchlistEntry:
    now = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)
    return WatchlistEntry(
        symbol=symbol,
        name={"01810": "小米集团-W", "00700": "腾讯控股"}.get(symbol, symbol),
        enabled=enabled,
        priority=priority,
        note="",
        created_at=now,
        updated_at=updated_at or now,
    )


def test_positions_are_always_included_and_overlap_is_deduplicated() -> None:
    service = PersonalUniverseService(
        FakeStore(
            positions=[
                {
                    "symbol": "01810",
                    "name": "小米集团-W",
                    "quantity": 100,
                    "market_value": 2844,
                    "sellable_quantity": 100,
                    "locked_quantity": 0,
                },
                {"symbol": "600000", "name": "浦发银行", "quantity": 200},
            ],
            quotes=[
                {"symbol": "01810", "price": 28.44, "change_percent": 3.64, "is_realtime": True},
            ],
        ),
        FakeRepository(
            [watch("01810", WatchlistPriority.CORE), watch("00700")],
            markets={"01810": "HK", "600000": "CN"},
            decisions={
                "01810": {
                    "decision_id": "decision-xiaomi",
                    "formal_action": "HOLD",
                    "generated_at": "2026-08-20T10:00:00+08:00",
                }
            },
        ),
    )

    rows = service.build()
    by_symbol = {item.symbol: item for item in rows}

    assert set(by_symbol) == {"01810", "600000", "00700"}
    assert by_symbol["01810"].membership is PersonalUniverseMembership.POSITION_AND_WATCHLIST
    assert by_symbol["600000"].membership is PersonalUniverseMembership.POSITION
    assert by_symbol["00700"].membership is PersonalUniverseMembership.WATCHLIST
    assert by_symbol["01810"].watchlist_priority is WatchlistPriority.CORE
    assert by_symbol["01810"].watchlist_enabled is True
    assert by_symbol["01810"].quote_display_state == "live"
    assert by_symbol["01810"].market == "HK"
    assert by_symbol["01810"].formal_action == "HOLD"
    assert by_symbol["01810"].decision_id == "decision-xiaomi"


def test_missing_quote_does_not_drop_watchlist_item() -> None:
    service = PersonalUniverseService(FakeStore([], []), FakeRepository([watch("00700")]))

    rows = service.build()

    assert len(rows) == 1
    assert rows[0].symbol == "00700"
    assert rows[0].quote_display_state == "unavailable"


def test_personal_universe_uses_only_local_store_reads() -> None:
    store = FakeStore([], [{"symbol": "00700", "price": 600.0, "is_realtime": False}])
    service = PersonalUniverseService(store, FakeRepository([watch("00700")]))

    rows = service.build()

    assert rows[0].quote_display_state == "session_close"


def test_watchlist_default_order_uses_priority_then_latest_explicit_update() -> None:
    now = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)
    service = PersonalUniverseService(
        FakeStore([], []),
        FakeRepository(
            [
                watch("00001", WatchlistPriority.NORMAL, updated_at=now + timedelta(hours=3)),
                watch("00700", WatchlistPriority.FOCUS, updated_at=now),
                watch("01810", WatchlistPriority.FOCUS, updated_at=now + timedelta(hours=1)),
                watch("00002", WatchlistPriority.CORE, updated_at=now - timedelta(days=1)),
            ]
        ),
    )

    assert [item.symbol for item in service.build()] == ["00002", "01810", "00700", "00001"]


def test_disabled_watchlist_row_does_not_create_universe_entry_but_position_survives() -> None:
    disabled = watch("01810", WatchlistPriority.CORE, enabled=False)
    watchlist_only_disabled = watch("00700", enabled=False)
    service = PersonalUniverseService(
        FakeStore([{"symbol": "01810", "name": "小米集团-W", "quantity": 100}], []),
        FakeRepository([disabled, watchlist_only_disabled]),
    )

    rows = service.build()

    assert [item.symbol for item in rows] == ["01810"]
    assert rows[0].membership is PersonalUniverseMembership.POSITION
    assert rows[0].watchlist_enabled is False
    assert rows[0].watchlist_priority is WatchlistPriority.CORE
