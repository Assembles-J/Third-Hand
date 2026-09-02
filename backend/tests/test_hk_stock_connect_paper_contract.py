from datetime import datetime, timezone
from decimal import Decimal

from app.api.v1.paper.router import _decorate_manual_order_capability
from app.hk_stock_connect_paper_contract import (
    HKD_CNY_PAIR,
    HKEX_STATUTORY_FEE_SCHEDULE_VERSION,
    HkStockConnectPaperContract,
    calculate_hkex_equity_statutory_fees,
)
from app.market_adapter import adapter_for_market


UTC = timezone.utc


def _metadata(*, lot_size=200, price_tick="0.02"):
    return {
        "symbol": "01810",
        "market": "HK",
        "currency": "HKD",
        "lot_size": lot_size,
        "price_tick": price_tick,
        "source": "test-authority",
        "as_of": "2026-09-02",
    }


def _reference_observation(*, applicable_date="2026-09-02"):
    return {
        "kind": "REFERENCE",
        "applicable_date": applicable_date,
        "pair": "HKD/CNY",
        "currency": "HKD",
        "buy_rate": 0.91,
        "sell_rate": 0.97,
        "settlement_channel": "SH_HK_CONNECT_RMB",
        "provider": "AKShare",
        "provider_version": "test",
        "upstream": "SSE",
        "source_reference": "http://www.sse.com.cn/services/hkexsc/disclo/ratios/",
        "retrieved_at": "2026-09-02T09:00:00+08:00",
        "snapshot_id": "scfx:test",
        "payload_hash": "abc",
    }


def test_hkex_statutory_fee_snapshot_is_versioned_and_rounds_components() -> None:
    fees = calculate_hkex_equity_statutory_fees(Decimal("10000"), side="BUY")

    assert fees["version"] == HKEX_STATUTORY_FEE_SCHEDULE_VERSION
    assert fees["currency"] == "HKD"
    assert fees["sfc_transaction_levy"] == 0.27
    assert fees["afrc_transaction_levy"] == 0.02
    assert fees["trading_fee"] == 0.57
    assert fees["stamp_duty"] == 10.0
    assert fees["statutory_total_hkd"] == 10.86
    assert fees["broker_commission"] is None
    assert fees["participant_clearing_pass_through"] is None


def test_hk_stamp_duty_rounds_up_to_next_hkd() -> None:
    fees = calculate_hkex_equity_statutory_fees(Decimal("10001"), side="SELL")
    assert fees["stamp_duty"] == 11.0


def test_hk_contract_is_fail_closed_when_fx_and_broker_policies_are_missing() -> None:
    contract = HkStockConnectPaperContract().evaluate(
        metadata=_metadata(),
        adapter=adapter_for_market("HK"),
        now=datetime(2026, 9, 2, 10, 0, tzinfo=UTC),
    )

    assert contract["execution_ready"] is False
    assert contract["trading_currency"] == "HKD"
    assert contract["paper_account_currency"] == "CNY"
    assert contract["settlement_currency"] == "CNY"
    assert contract["settlement_channel"] == "SH_HK_CONNECT_RMB"
    assert contract["sellability_rule"] == "HK_T0_SELLABILITY"
    assert contract["fx_required_pair"] == HKD_CNY_PAIR
    assert contract["session_policy"] == "XHKG_CONTINUOUS_ONLY_V1"
    assert contract["statutory_fee_schedule"]["version"] == HKEX_STATUTORY_FEE_SCHEDULE_VERSION
    assert contract["blocking_reason_codes"] == [
        "paper_hk_fx_observation_missing",
        "paper_hk_broker_commission_policy_unconfigured",
        "paper_hk_clearing_fee_policy_unconfigured",
    ]


def test_hk_contract_requires_authoritative_lot_and_tick() -> None:
    contract = HkStockConnectPaperContract().evaluate(
        metadata=_metadata(lot_size=None, price_tick=None),
        adapter=adapter_for_market("HK"),
        now=datetime(2026, 9, 2, 10, 0, tzinfo=UTC),
    )

    assert "paper_instrument_lot_size_required" in contract["blocking_reason_codes"]
    assert "paper_instrument_price_tick_required" in contract["blocking_reason_codes"]


def test_hk_contract_can_become_ready_only_with_explicit_directional_daily_facts() -> None:
    contract = HkStockConnectPaperContract().evaluate(
        metadata=_metadata(),
        adapter=adapter_for_market("HK"),
        now=datetime(2026, 9, 2, 10, 0, tzinfo=UTC),
        fx_observation=_reference_observation(),
        broker_commission_policy="PAPER_BROKER_ZERO_COMMISSION_V1",
        participant_clearing_pass_through_policy="PAPER_CLEARING_EXPLICIT_V1",
    )

    assert contract["execution_ready"] is True
    assert contract["blocking_reason_codes"] == []
    assert contract["fx_reference_observation"]["buy_rate"] == 0.91
    assert contract["fx_reference_observation"]["sell_rate"] == 0.97
    assert contract["fx_reference_semantics"]["buy_order_reserve_rate"] == "REFERENCE_SELL_RATE"
    assert contract["fx_reference_semantics"]["sell_order_estimate_rate"] == "REFERENCE_BUY_RATE"
    assert contract["fx_reference_semantics"]["midpoint_allowed"] is False


def test_hk_contract_rejects_reference_rate_for_another_applicable_date() -> None:
    contract = HkStockConnectPaperContract().evaluate(
        metadata=_metadata(),
        adapter=adapter_for_market("HK"),
        now=datetime(2026, 9, 2, 10, 0, tzinfo=UTC),
        fx_observation=_reference_observation(applicable_date="2026-09-01"),
        broker_commission_policy="PAPER_BROKER_ZERO_COMMISSION_V1",
        participant_clearing_pass_through_policy="PAPER_CLEARING_EXPLICIT_V1",
    )

    assert contract["execution_ready"] is False
    assert contract["blocking_reason_codes"] == ["paper_hk_fx_observation_stale"]


class _FakeStore:
    def instrument_metadata(self, symbol: str):
        assert symbol == "01810"
        return _metadata()


class _FakeManualOrderService:
    store = _FakeStore()

    @staticmethod
    def now_provider():
        return datetime(2026, 9, 2, 10, 0, tzinfo=UTC)


class _FakeRateService:
    @staticmethod
    def status():
        return {"reference": _reference_observation()}


def test_hk_order_capability_keeps_compatibility_blocker_and_adds_diagnostics() -> None:
    capability = _decorate_manual_order_capability(
        _FakeManualOrderService(),
        {
            "symbol": "01810",
            "market": "HK",
            "currency": "HKD",
            "executable": False,
            "reason_codes": ["paper_hk_execution_not_configured"],
        },
    )

    assert capability["executable"] is False
    assert capability["reason_codes"][0] == "paper_hk_execution_not_configured"
    assert "paper_hk_fx_observation_missing" in capability["reason_codes"]
    assert "paper_hk_broker_commission_policy_unconfigured" in capability["reason_codes"]
    assert "paper_hk_clearing_fee_policy_unconfigured" in capability["reason_codes"]
    assert capability["execution_contract"]["settlement_channel"] == "SH_HK_CONNECT_RMB"
    assert capability["execution_contract"]["lot_size"] == 200
    assert capability["execution_contract"]["price_tick"] == "0.02"


def test_hk_capability_consumes_local_reference_snapshot_but_stays_fee_blocked() -> None:
    capability = _decorate_manual_order_capability(
        _FakeManualOrderService(),
        {
            "symbol": "01810",
            "market": "HK",
            "currency": "HKD",
            "executable": False,
            "reason_codes": ["paper_hk_execution_not_configured"],
        },
        _FakeRateService(),
    )

    assert capability["executable"] is False
    assert "paper_hk_fx_observation_missing" not in capability["reason_codes"]
    assert "paper_hk_fx_observation_stale" not in capability["reason_codes"]
    assert "paper_hk_broker_commission_policy_unconfigured" in capability["reason_codes"]
    assert capability["execution_contract"]["fx_reference_observation"]["snapshot_id"] == "scfx:test"
