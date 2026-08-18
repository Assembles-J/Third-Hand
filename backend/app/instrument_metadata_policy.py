"""Normalize only the historical synthetic paper-market instrument placeholder.

The legacy paper runtime predates multi-market support and writes
``paper_market_default`` as CN/CNY/100 when metadata is absent.  That row is not
provider authority, so v3 must reinterpret it through the central MarketAdapter
before any formal context consumes it.  Explicit/provider metadata is preserved
unchanged, even when it disagrees with symbol shape.
"""
from __future__ import annotations

from app.market_adapter import adapter_for_symbol


LEGACY_PAPER_DEFAULT_SOURCE = "paper_market_default"
NORMALIZED_PAPER_DEFAULT_SOURCE = "paper_market_default:market_adapter_v1"


def normalize_instrument_metadata(item: dict[str, object] | None) -> dict[str, object] | None:
    if not item:
        return None
    result = dict(item)
    if str(result.get("source") or "") != LEGACY_PAPER_DEFAULT_SOURCE:
        return result

    symbol = str(result.get("symbol") or "").strip().upper()
    adapter = adapter_for_symbol(symbol)
    if adapter is None:
        return result

    result["symbol"] = symbol
    result["market"] = adapter.market
    result["currency"] = adapter.trading_currency
    result["lot_size"] = adapter.default_lot_size or None
    # The legacy placeholder's 0.01 tick was an A-share assumption.  Never
    # promote it across markets; a future instrument provider must supply it.
    if adapter.market != "CN":
        result["price_tick"] = None
    result["source"] = NORMALIZED_PAPER_DEFAULT_SOURCE
    return result


def install() -> None:
    """Patch the persistence boundary before the legacy application constructs its store."""
    from app.storage import PortfolioStore

    if getattr(PortfolioStore, "_instrument_metadata_policy_installed", False):
        return
    PortfolioStore._instrument_metadata_policy_installed = True

    original_save = PortfolioStore.save_instrument_metadata
    original_read = PortfolioStore.instrument_metadata

    def save_instrument_metadata(self, item):
        normalized = normalize_instrument_metadata(item) or dict(item)
        return original_save(self, normalized)

    def instrument_metadata(self, symbol):
        value = original_read(self, symbol)
        normalized = normalize_instrument_metadata(value)
        if normalized and value and normalized != value:
            # Repair existing legacy rows lazily so all future readers, not only
            # DecisionContext, see the same market identity.  This write is
            # deterministic and touches only the known synthetic source.
            original_save(self, normalized)
        return normalized

    PortfolioStore.save_instrument_metadata = save_instrument_metadata
    PortfolioStore.instrument_metadata = instrument_metadata


__all__ = [
    "LEGACY_PAPER_DEFAULT_SOURCE",
    "NORMALIZED_PAPER_DEFAULT_SOURCE",
    "install",
    "normalize_instrument_metadata",
]
