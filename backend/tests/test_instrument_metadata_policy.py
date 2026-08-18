from app.instrument_metadata_policy import (
    LEGACY_PAPER_DEFAULT_SOURCE,
    NORMALIZED_PAPER_DEFAULT_SOURCE,
    install,
    normalize_instrument_metadata,
)
from app.storage import PortfolioStore


def _legacy(symbol: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "market": "CN",
        "currency": "CNY",
        "lot_size": 100,
        "price_tick": 0.01,
        "source": LEGACY_PAPER_DEFAULT_SOURCE,
        "as_of": "2026-08-18",
    }


def test_legacy_paper_default_uses_market_adapter_for_hk_and_us():
    hk = normalize_instrument_metadata(_legacy("01810"))
    us = normalize_instrument_metadata(_legacy("AAPL"))

    assert hk is not None
    assert hk["market"] == "HK"
    assert hk["currency"] == "HKD"
    assert hk["lot_size"] is None
    assert hk["price_tick"] is None
    assert hk["source"] == NORMALIZED_PAPER_DEFAULT_SOURCE

    assert us is not None
    assert us["market"] == "US"
    assert us["currency"] == "USD"
    assert us["lot_size"] == 1
    assert us["price_tick"] is None


def test_legacy_cn_default_keeps_cn_adapter_semantics():
    cn = normalize_instrument_metadata(_legacy("600519"))

    assert cn is not None
    assert cn["market"] == "CN"
    assert cn["currency"] == "CNY"
    assert cn["lot_size"] == 100
    assert cn["price_tick"] == 0.01


def test_explicit_provider_metadata_is_never_overridden_by_symbol_shape():
    explicit = {
        "symbol": "600519",
        "market": "HK",
        "currency": "HKD",
        "lot_size": 200,
        "price_tick": "0.02",
        "source": "provider-fixture",
        "as_of": "2026-08-18",
    }

    assert normalize_instrument_metadata(explicit) == explicit


def test_installed_policy_repairs_existing_legacy_row_on_read(tmp_path):
    original_save = PortfolioStore.save_instrument_metadata
    original_read = PortfolioStore.instrument_metadata
    had_flag = hasattr(PortfolioStore, "_instrument_metadata_policy_installed")
    previous_flag = getattr(PortfolioStore, "_instrument_metadata_policy_installed", None)
    try:
        if had_flag:
            delattr(PortfolioStore, "_instrument_metadata_policy_installed")
        PortfolioStore.save_instrument_metadata = original_save
        PortfolioStore.instrument_metadata = original_read

        store = PortfolioStore(tmp_path / "instrument-policy.db")
        original_save(store, _legacy("01810"))
        assert original_read(store, "01810")["market"] == "CN"

        install()
        repaired = store.instrument_metadata("01810")

        assert repaired is not None
        assert repaired["market"] == "HK"
        assert repaired["currency"] == "HKD"
        assert repaired["lot_size"] is None
        assert repaired["source"] == NORMALIZED_PAPER_DEFAULT_SOURCE
        persisted = original_read(store, "01810")
        assert persisted["market"] == "HK"
        assert persisted["source"] == NORMALIZED_PAPER_DEFAULT_SOURCE
    finally:
        PortfolioStore.save_instrument_metadata = original_save
        PortfolioStore.instrument_metadata = original_read
        if hasattr(PortfolioStore, "_instrument_metadata_policy_installed"):
            delattr(PortfolioStore, "_instrument_metadata_policy_installed")
        if had_flag:
            PortfolioStore._instrument_metadata_policy_installed = previous_flag
