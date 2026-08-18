"""Explicit market/instrument identity boundary for decision and execution services.

The resolver keeps legacy symbol-shape compatibility in one place.  Callers
should consume :class:`MarketAdapter` / instrument metadata instead of
re-inferring market, currency, lot or benchmark semantics independently.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


MarketCode = Literal["CN", "HK", "US"]


@dataclass(frozen=True, slots=True)
class MarketAdapter:
    market: MarketCode
    exchange_calendar: str
    timezone: str
    trading_currency: str
    settlement_currency: str
    settlement_channel: str
    default_lot_size: int
    settlement_rule: str
    paper_fee_schedule: str
    benchmark_symbols: tuple[str, ...]


MARKET_ADAPTERS: dict[MarketCode, MarketAdapter] = {
    "CN": MarketAdapter(
        market="CN",
        exchange_calendar="XSHG",
        timezone="Asia/Shanghai",
        trading_currency="CNY",
        settlement_currency="CNY",
        settlement_channel="CN_A_CASH",
        default_lot_size=100,
        settlement_rule="CN_A_T1_SELLABILITY",
        paper_fee_schedule="CN_A_STANDARD",
        benchmark_symbols=("sh000001", "sh000300", "sz399006"),
    ),
    "HK": MarketAdapter(
        market="HK",
        exchange_calendar="XHKG",
        timezone="Asia/Hong_Kong",
        trading_currency="HKD",
        # Mainland brokers settle Stock Connect cash in RMB while the security
        # itself is quoted/traded in HKD. An observed HKD->CNY rate is therefore
        # required at the execution boundary; it must never be inferred.
        settlement_currency="CNY",
        settlement_channel="SH_HK_CONNECT_RMB",
        # HK board lots are instrument-specific.  Zero means callers must
        # obtain explicit instrument metadata before sizing/execution.
        default_lot_size=0,
        settlement_rule="HK_INSTRUMENT_SPECIFIC",
        # Do not silently apply CN fees to HK trades. A configured HK paper
        # schedule is required before the simulated ledger may execute them.
        paper_fee_schedule="UNCONFIGURED",
        benchmark_symbols=("HSI", "HSTECH"),
    ),
    "US": MarketAdapter(
        market="US",
        exchange_calendar="XNYS",
        timezone="America/New_York",
        trading_currency="USD",
        settlement_currency="USD",
        settlement_channel="US_LOCAL_CASH",
        default_lot_size=1,
        settlement_rule="US_T1_SETTLEMENT",
        # The single-CNY paper ledger has no FX/US fee model yet.
        paper_fee_schedule="UNCONFIGURED",
        benchmark_symbols=("SPX", "NDX"),
    ),
}


_US_TICKER = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")


def market_for_symbol(symbol: str) -> MarketCode | None:
    """Resolve the compatibility market for a normalized public symbol.

    This deliberately centralizes the current symbol-shape heuristic.  It is a
    compatibility resolver, not permanent instrument authority: persisted
    instrument metadata should override inference once available.
    """

    normalized = str(symbol or "").strip().upper()
    if not normalized:
        return None

    # Hong Kong stock codes such as 01810.
    if len(normalized) == 5 and normalized.isdigit():
        return "HK"

    # Mainland A-shares / ETFs such as 600519 and 510300.
    if len(normalized) == 6 and normalized.isdigit():
        return "CN"

    # Common US ticker representation.  Exchange-qualified/provider-specific
    # symbols should be normalized by their provider before reaching here.
    if _US_TICKER.fullmatch(normalized):
        return "US"

    return None


def adapter_for_market(market: str | None) -> MarketAdapter | None:
    normalized = str(market or "").strip().upper()
    return MARKET_ADAPTERS.get(normalized)  # type: ignore[arg-type]


def adapter_for_symbol(symbol: str) -> MarketAdapter | None:
    return adapter_for_market(market_for_symbol(symbol))


__all__ = [
    "MARKET_ADAPTERS",
    "MarketAdapter",
    "MarketCode",
    "adapter_for_market",
    "adapter_for_symbol",
    "market_for_symbol",
]
