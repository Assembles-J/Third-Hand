"""Local-only Personal Universe read model composition.

Opening the Watchlist screen must not trigger provider I/O, Company Research,
Decision AI, Mandatory Acquisition, or paper execution.
"""
from __future__ import annotations

from app.domain.personal_universe import (
    PersonalUniverseItem,
    PersonalUniverseMembership,
    WatchlistEntry,
    WatchlistPriority,
)


class PersonalUniverseService:
    def __init__(self, store, repository) -> None:
        self.store = store
        self.repository = repository

    def build(self) -> list[PersonalUniverseItem]:
        all_watchlist = {
            item.symbol: item
            for item in self.repository.list_watchlist(include_disabled=True)
        }
        active_watchlist = {
            symbol: item
            for symbol, item in all_watchlist.items()
            if item.enabled
        }
        positions = {
            str(item.get("symbol") or "").strip().upper(): item
            for item in (self.store.paper_account().get("positions") or [])
            if str(item.get("symbol") or "").strip()
        }
        symbols = list(dict.fromkeys([*positions.keys(), *active_watchlist.keys()]))
        quote_rows = self.store.cached_quotes(symbols) if symbols else []
        quotes = {str(item.get("symbol") or "").strip().upper(): item for item in quote_rows}
        markets = self.repository.instrument_markets(symbols)
        decisions = self.repository.latest_decisions(symbols)

        rows: list[PersonalUniverseItem] = []
        for symbol in symbols:
            position = positions.get(symbol)
            watch = all_watchlist.get(symbol)
            active_watch = active_watchlist.get(symbol)
            quote = quotes.get(symbol) or {}
            decision = decisions.get(symbol) or {}
            if position is not None and active_watch is not None:
                membership = PersonalUniverseMembership.POSITION_AND_WATCHLIST
            elif position is not None:
                membership = PersonalUniverseMembership.POSITION
            else:
                membership = PersonalUniverseMembership.WATCHLIST

            name = str(
                (position or {}).get("name")
                or (watch.name if watch is not None else "")
                or quote.get("name")
                or symbol
            ).strip()
            last_price = _optional_float(quote.get("price"))
            change_percent = _optional_float(quote.get("change_percent"))
            quote_as_of = _optional_text(quote.get("as_of") or quote.get("retrieved_at"))
            quote_state = _quote_display_state(quote)
            market = _optional_text(
                markets.get(symbol)
                or (position or {}).get("market")
                or quote.get("market")
            )
            formal_action = _optional_text(decision.get("formal_action") or decision.get("action"))
            decision_id = _optional_text(decision.get("decision_id"))
            decision_updated_at = _optional_text(
                decision.get("generated_at")
                or decision.get("created_at")
                or decision.get("_persisted_created_at")
            )

            rows.append(
                PersonalUniverseItem(
                    symbol=symbol,
                    name=name,
                    membership=membership,
                    market=market,
                    watchlist_priority=watch.priority if watch is not None else None,
                    watchlist_note=watch.note if watch is not None else None,
                    watchlist_enabled=watch.enabled if watch is not None else None,
                    position_quantity=_optional_float((position or {}).get("quantity")),
                    position_market_value=_optional_float((position or {}).get("market_value")),
                    sellable_quantity=_optional_float((position or {}).get("sellable_quantity")),
                    locked_quantity=_optional_float((position or {}).get("locked_quantity")),
                    last_price=last_price,
                    change_percent=change_percent,
                    quote_display_state=quote_state,
                    quote_as_of=quote_as_of,
                    formal_action=formal_action,
                    decision_id=decision_id,
                    decision_updated_at=decision_updated_at,
                )
            )

        return sorted(
            rows,
            key=lambda item: _sort_key(item, active_watchlist.get(item.symbol)),
        )


def _quote_display_state(quote: dict[str, object]) -> str:
    if not quote or quote.get("price") is None:
        return "unavailable"
    explicit = str(quote.get("display_freshness") or quote.get("display_state") or "").strip().lower()
    if explicit in {"live", "refreshing", "session_close", "stale", "unavailable"}:
        return explicit
    refresh_status = str(quote.get("refresh_status") or "").strip().lower()
    if refresh_status in {"refreshing", "stale"}:
        return refresh_status
    return "live" if bool(quote.get("is_realtime")) else "session_close"


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _sort_key(item: PersonalUniverseItem, watch: WatchlistEntry | None) -> tuple[int, int, float, str]:
    membership_rank = {
        PersonalUniverseMembership.POSITION_AND_WATCHLIST: 0,
        PersonalUniverseMembership.POSITION: 1,
        PersonalUniverseMembership.WATCHLIST: 2,
    }[item.membership]
    priority_rank = {
        WatchlistPriority.CORE: 0,
        WatchlistPriority.FOCUS: 1,
        WatchlistPriority.NORMAL: 2,
        None: 3,
    }[item.watchlist_priority if watch is not None else None]
    updated_rank = -watch.updated_at.timestamp() if watch is not None else 0.0
    return membership_rank, priority_rank, updated_rank, item.symbol
