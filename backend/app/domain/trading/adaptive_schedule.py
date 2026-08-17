"""Adaptive scheduling policy for paper analysis.

The policy changes *when* already-governed work is evaluated, never ActionPolicy,
candidate authorization, PositionSizing, or execution semantics. Low-cash
portfolios spend their automatic budget on held positions and due execution
obligations instead of repeatedly refreshing unrelated candidates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


MIN_REVIEW_INTERVAL_SECONDS = 5 * 60
HOLDING_CANDIDATE_SCAN_INTERVAL_SECONDS = 30 * 60
HOLDING_COMPANY_RESEARCH_INTERVAL_SECONDS = 30 * 60
DISCOVERY_COMPANY_RESEARCH_INTERVAL_SECONDS = 60 * 60
DISCOVERY_MIN_INTERVAL_SECONDS = 10 * 60
FULL_FOCUS_CASH_RATIO = 0.05
HOLDING_FOCUS_CASH_RATIO = 0.20


@dataclass(frozen=True)
class AdaptivePaperSchedule:
    mode: str
    review_interval_seconds: int
    candidate_scan_interval_seconds: int | None
    candidate_scan_enabled: bool
    company_research_interval_seconds: int
    holding_research_priority: str
    holding_symbols: tuple[str, ...]
    focus_symbols: tuple[str, ...]
    cash_ratio: float
    invested_ratio: float
    reason: str
    version: str = "adaptive-paper-schedule-v1"

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["holding_symbols"] = list(self.holding_symbols)
        payload["focus_symbols"] = list(self.focus_symbols)
        return payload


def _symbols(account: dict[str, object]) -> tuple[str, ...]:
    positions = account.get("positions") or []
    return tuple(dict.fromkeys(
        str(item.get("symbol") or "").strip().upper()
        for item in positions
        if isinstance(item, dict) and str(item.get("symbol") or "").strip()
    ))


def adaptive_paper_schedule(
    account: dict[str, object],
    *,
    configured_interval_seconds: int,
    pending_symbols=(),
) -> AdaptivePaperSchedule:
    """Resolve automatic analysis cadence from the current paper account.

    ``FULL_FOCUS`` means cash is <=5% of equity and at least one position exists.
    Automatic discovery is disabled in that state; held symbols and already-due
    execution obligations remain in scope. Fast market/risk review and slow
    company-fundamental research have separate cadences so a 5-minute holding
    review never becomes a 5-minute financial-statement provider retry loop.
    """
    configured = max(MIN_REVIEW_INTERVAL_SECONDS, int(configured_interval_seconds))
    held = _symbols(account)
    pending = tuple(dict.fromkeys(
        str(symbol).strip().upper() for symbol in pending_symbols if str(symbol).strip()
    ))
    focus = tuple(dict.fromkeys((*held, *pending)))

    cash = max(0.0, float(account.get("available_cash") or 0.0))
    total_equity = max(0.0, float(account.get("total_equity") or 0.0))
    market_value = max(0.0, float(account.get("market_value") or 0.0))
    denominator = total_equity if total_equity > 0 else cash + market_value
    cash_ratio = 1.0 if denominator <= 0 else min(1.0, max(0.0, cash / denominator))
    invested_ratio = 1.0 - cash_ratio

    if held and cash_ratio <= FULL_FOCUS_CASH_RATIO:
        return AdaptivePaperSchedule(
            mode="FULL_FOCUS",
            review_interval_seconds=MIN_REVIEW_INTERVAL_SECONDS,
            candidate_scan_interval_seconds=None,
            candidate_scan_enabled=False,
            company_research_interval_seconds=HOLDING_COMPANY_RESEARCH_INTERVAL_SECONDS,
            holding_research_priority="L4",
            holding_symbols=held,
            focus_symbols=focus,
            cash_ratio=round(cash_ratio, 6),
            invested_ratio=round(invested_ratio, 6),
            reason="cash_ratio_at_or_below_5_percent_focus_on_holdings_and_due_execution",
        )

    if held and cash_ratio <= HOLDING_FOCUS_CASH_RATIO:
        return AdaptivePaperSchedule(
            mode="HOLDING_FOCUS",
            review_interval_seconds=MIN_REVIEW_INTERVAL_SECONDS,
            candidate_scan_interval_seconds=max(HOLDING_CANDIDATE_SCAN_INTERVAL_SECONDS, configured),
            candidate_scan_enabled=True,
            company_research_interval_seconds=HOLDING_COMPANY_RESEARCH_INTERVAL_SECONDS,
            holding_research_priority="L3",
            holding_symbols=held,
            focus_symbols=focus,
            cash_ratio=round(cash_ratio, 6),
            invested_ratio=round(invested_ratio, 6),
            reason="cash_ratio_at_or_below_20_percent_prioritize_holdings_reduce_discovery_frequency",
        )

    return AdaptivePaperSchedule(
        mode="DISCOVERY",
        review_interval_seconds=max(DISCOVERY_MIN_INTERVAL_SECONDS, configured),
        candidate_scan_interval_seconds=max(DISCOVERY_MIN_INTERVAL_SECONDS, configured),
        candidate_scan_enabled=True,
        company_research_interval_seconds=DISCOVERY_COMPANY_RESEARCH_INTERVAL_SECONDS,
        holding_research_priority="L2" if held else "L1",
        holding_symbols=held,
        focus_symbols=focus,
        cash_ratio=round(cash_ratio, 6),
        invested_ratio=round(invested_ratio, 6),
        reason="cash_available_keep_deterministic_candidate_discovery_enabled",
    )
