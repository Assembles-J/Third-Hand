"""Paper-runtime adapters for explicit order quantity and entry provenance."""
from __future__ import annotations

import sqlite3
from collections.abc import Mapping


def explicit_order_quantity(sizing: Mapping[str, object] | None) -> float:
    """Return the current order quantity without target-position fallback.

    `suggested_quantity` is the current compatibility field for executable order
    size. Numeric zero is meaningful and must stay zero. `target_quantity`
    describes the resulting position and is never an order-size fallback.
    """
    if not isinstance(sizing, Mapping):
        return 0.0
    raw = sizing.get("suggested_quantity")
    if raw is None:
        return 0.0
    try:
        quantity = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, quantity)


def project_paper_holdings(store, paper_account: Mapping[str, object]) -> list[dict[str, object]]:
    """Preserve the frozen paper-position entry episode into DecisionContext.

    `paper_account()` already exposes the entry contract. The authoritative
    original open time lives in `paper_position_episodes.opened_at`; read it here
    so an ADD cannot reset `PositionSnapshot.opened_at` through the mutable
    aggregate-position `updated_at` field.
    """
    episode_opened_at: dict[str, str] = {}
    connect = getattr(store, "_connect", None)
    if callable(connect):
        try:
            with connect() as connection:
                rows = connection.execute(
                    "SELECT symbol,opened_at FROM paper_position_episodes WHERE closed_at IS NULL"
                ).fetchall()
            episode_opened_at = {
                str(row["symbol"]).strip().upper(): str(row["opened_at"])
                for row in rows
                if row["symbol"] is not None and row["opened_at"] is not None
            }
        except sqlite3.Error:
            # Projection remains compatible with databases created before the
            # episode migration; current migrations/tests exercise this table.
            episode_opened_at = {}

    results: list[dict[str, object]] = []
    positions = paper_account.get("positions", [])
    for raw in positions if isinstance(positions, list) else []:
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        symbol = str(item.get("symbol") or "").strip().upper()
        results.append({
            "symbol": item.get("symbol"),
            "name": item.get("name"),
            "quantity": item.get("quantity"),
            "average_cost": item.get("average_cost"),
            "sellable_quantity": item.get("sellable_quantity"),
            "locked_quantity": item.get("locked_quantity"),
            "next_eligible_sell_at": item.get("next_eligible_sell_at"),
            "created_at": episode_opened_at.get(symbol) or item.get("updated_at"),
            "entry_episode_id": item.get("entry_episode_id"),
            "entry_decision_id": item.get("entry_decision_id"),
            "entry_evidence_snapshot_hash": item.get("entry_evidence_snapshot_hash"),
            "entry_research_assessment_hash": item.get("entry_research_assessment_hash"),
            "entry_risk_state": item.get("entry_risk_state"),
            "entry_technical_state": item.get("entry_technical_state"),
            "entry_market_regime": item.get("entry_market_regime"),
            "entry_event_state": item.get("entry_event_state"),
            "entry_price": item.get("entry_price"),
        })
    return results


__all__ = ["explicit_order_quantity", "project_paper_holdings"]
