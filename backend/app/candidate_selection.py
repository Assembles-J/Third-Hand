"""Deterministic, auditable candidate scheduling for frozen observations.

Selection is intentionally independent from watchlists, hot sectors, price
change rankings, fund flow and LLM output. Existing paper positions are always
included for risk monitoring; remaining slots rotate deterministically across
the eligible universe.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app import decision_config as config


@dataclass(frozen=True)
class CandidateSelection:
    symbols: tuple[str, ...]
    position_symbols: tuple[str, ...]
    rotated_symbols: tuple[str, ...]
    candidate_pool_hash: str
    selection_version: str
    rotation_key: str

    def audit_for(self, symbol: str) -> dict[str, object]:
        """Return immutable per-symbol selection lineage for DecisionReport."""
        normalized = str(symbol).strip().upper()
        if normalized not in self.symbols:
            raise ValueError("symbol is not in candidate selection")
        return {
            "candidate_selection_version": self.selection_version,
            "candidate_pool_hash": self.candidate_pool_hash,
            "candidate_rotation_key": self.rotation_key,
            "candidate_rank": self.symbols.index(normalized) + 1,
            "candidate_selection_reason": (
                "paper_position_risk_monitor"
                if normalized in self.position_symbols
                else "deterministic_rotation"
            ),
        }


def _normalized(values) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip().upper() for value in values if str(value).strip()}))


def _pool_hash(symbols: tuple[str, ...]) -> str:
    payload = "\n".join(symbols).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def select_candidates(
    eligible_symbols,
    *,
    position_symbols=(),
    limit: int,
    rotation_key: str,
) -> CandidateSelection:
    """Select an auditable cohort without directional market preferences.

    ``rotation_key`` should be a stable observation key such as trading date.
    Changing watchlist membership, sector heat or same-day returns must not
    change this result when the eligible universe and positions are unchanged.

    Paper positions are a safety exception to the nominal candidate limit: all
    positions remain in the cohort even when their quote/history is incomplete,
    and even when the account holds more names than the configured open-candidate
    budget. Missing data may block their action later, but must never hide them
    from risk monitoring.
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")
    if not rotation_key.strip():
        raise ValueError("rotation_key must not be blank")

    eligible = _normalized(eligible_symbols)
    positions = _normalized(position_symbols)
    position_set = set(positions)
    effective_limit = max(limit, len(positions))
    remaining_slots = max(0, effective_limit - len(positions))
    non_positions = tuple(symbol for symbol in eligible if symbol not in position_set)

    def rotation_rank(symbol: str) -> str:
        material = f"{config.CANDIDATE_SELECTION_VERSION}|{rotation_key}|{symbol}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    rotated = tuple(sorted(non_positions, key=lambda symbol: (rotation_rank(symbol), symbol))[:remaining_slots])
    selected = (*positions, *rotated)
    return CandidateSelection(
        symbols=selected,
        position_symbols=positions,
        rotated_symbols=rotated,
        candidate_pool_hash=_pool_hash(eligible),
        selection_version=config.CANDIDATE_SELECTION_VERSION,
        rotation_key=rotation_key,
    )
