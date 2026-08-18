from datetime import datetime, timezone

from app.market_adapter import adapter_for_market, adapter_for_symbol, market_for_symbol
from app.trading_calendar import TradingCalendarService


def test_market_adapter_resolves_cn_hk_and_us_symbols():
    assert market_for_symbol("600519") == "CN"
    assert market_for_symbol("510300") == "CN"
    assert market_for_symbol("01810") == "HK"
    assert market_for_symbol("AAPL") == "US"
    assert market_for_symbol("BRK.B") == "US"
    assert market_for_symbol("") is None
    assert market_for_symbol("12") is None


def test_market_adapter_exposes_explicit_market_rules():
    cn = adapter_for_market("cn")
    hk = adapter_for_symbol("01810")
    us = adapter_for_symbol("AAPL")

    assert cn is not None
    assert cn.trading_currency == "CNY"
    assert cn.default_lot_size == 100
    assert cn.exchange_calendar == "XSHG"

    assert hk is not None
    assert hk.trading_currency == "HKD"
    assert hk.settlement_currency == "CNY"
    assert hk.settlement_channel == "SH_HK_CONNECT_RMB"
    assert hk.default_lot_size == 0
    assert hk.paper_fee_schedule == "UNCONFIGURED"
    assert hk.exchange_calendar == "XHKG"
    assert hk.benchmark_symbols == ("HSI", "HSTECH")

    assert us is not None
    assert us.trading_currency == "USD"
    assert us.default_lot_size == 1
    assert us.paper_fee_schedule == "UNCONFIGURED"
    assert us.exchange_calendar == "XNYS"


def test_trading_calendar_delegates_symbol_identity_to_market_adapter():
    service = TradingCalendarService()

    assert service.market_for_symbol("600519") == "CN"
    assert service.market_for_symbol("01810") == "HK"
    assert service.market_for_symbol("AAPL") == "US"


def test_us_calendar_is_available_for_completed_session_queries():
    service = TradingCalendarService()
    # 2026-08-18 22:00 UTC is after the NYSE regular close on that session.
    moment = datetime(2026, 8, 18, 22, 0, tzinfo=timezone.utc)

    assert service.latest_completed_session_date("US", moment) == "2026-08-18"
    assert service.latest_completed_symbol_session_date("AAPL", moment) == "2026-08-18"
