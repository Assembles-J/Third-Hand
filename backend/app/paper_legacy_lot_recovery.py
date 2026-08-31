"""Recover provable legacy paper PositionLots before account projections.

Older Third-Hand databases may contain an aggregate ``paper_trading_positions``
row and immutable executed BUY/SELL ledger entries but no corresponding
``paper_position_lots`` rows.  Sellability is lot-derived, so reading such an
account otherwise presents the entire holding as locked forever.

This compatibility hook reuses the existing FIFO reconciliation authority in
``PortfolioStore``.  It never invents inventory: a repair is committed only when
the immutable executed ledger replays to the exact aggregate position quantity.
Market/currency identity comes from persisted instrument metadata when present,
falling back to the central MarketAdapter only for legacy rows.
"""
from __future__ import annotations

from app.market_adapter import adapter_for_market, adapter_for_symbol
from app.time_utils import beijing_now


def _market_identity(connection, symbol: str) -> tuple[str, str] | None:
    metadata = connection.execute(
        "SELECT market,currency FROM instrument_metadata WHERE symbol=?",
        (symbol,),
    ).fetchone()

    adapter = None
    currency = None
    if metadata:
        adapter = adapter_for_market(str(metadata["market"] or ""))
        currency = str(metadata["currency"] or "").strip().upper() or None
    if adapter is None:
        adapter = adapter_for_symbol(symbol)
    if adapter is None:
        return None
    return adapter.market, currency or adapter.trading_currency


def reconcile_missing_position_lots(store) -> dict[str, tuple[str, ...]]:
    """Rebuild only missing, ledger-provable lots and report the outcome.

    Existing lot inventory is never rewritten.  A failed replay remains
    fail-closed so the normal account projection continues to expose zero
    sellability rather than guessing inventory provenance.
    """

    recovered: list[str] = []
    failed: list[str] = []
    now = beijing_now().isoformat()

    with store._connect() as connection:
        positions = connection.execute(
            "SELECT symbol,quantity FROM paper_trading_positions WHERE quantity > 0"
        ).fetchall()
        for position in positions:
            symbol = str(position["symbol"]).strip().upper()
            existing = connection.execute(
                "SELECT COUNT(*) AS count FROM paper_position_lots WHERE symbol=?",
                (symbol,),
            ).fetchone()
            if int(existing["count"]):
                continue

            identity = _market_identity(connection, symbol)
            if identity is None:
                failed.append(symbol)
                continue
            market, currency = identity

            # The normal paper ledger is currently implemented only for CN.
            # HK legacy inventory may still be reconstructed as read-only lot
            # evidence so it is not mislabeled with a CN T+1 lock; execution
            # remains fail-closed behind the HK fee/currency contract.
            if market not in {"CN", "HK"}:
                failed.append(symbol)
                continue

            if store._reconcile_legacy_position_lots(
                connection,
                symbol=symbol,
                market=market,
                currency=currency,
                now=now,
            ):
                recovered.append(symbol)
            else:
                failed.append(symbol)

    return {
        "recovered": tuple(recovered),
        "failed": tuple(failed),
    }


def install() -> None:
    """Install idempotent read-time recovery before legacy stores are created."""

    from app.storage import PortfolioStore

    if getattr(PortfolioStore, "_paper_legacy_lot_recovery_installed", False):
        return
    PortfolioStore._paper_legacy_lot_recovery_installed = True

    original_paper_account = PortfolioStore.paper_account

    def paper_account(self):
        reconcile_missing_position_lots(self)
        return original_paper_account(self)

    PortfolioStore.paper_account = paper_account


__all__ = ["install", "reconcile_missing_position_lots"]
