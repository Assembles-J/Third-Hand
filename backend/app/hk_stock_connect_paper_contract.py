"""Deterministic prerequisites for Hong Kong Stock Connect paper execution.

This module deliberately does *not* enable HK fills by itself. It freezes the
facts that a future Paper Broker execution must consume so HK cannot silently
inherit A-share assumptions.

SEHK securities trade in HKD while the normal paper account settles through the
Southbound/Stock-Connect RMB channel. The official Stock Connect mechanism uses
directional daily reference exchange rates during trading and separate
settlement exchange ratios after close. A midpoint or generic spot-FX quote is
therefore not an execution input for this contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import math
from typing import Mapping


HKD_CNY_PAIR = "HKD/CNY"
HK_STOCK_CONNECT_SETTLEMENT_CHANNEL = "SH_HK_CONNECT_RMB"
HK_CONTINUOUS_SESSION_POLICY = "XHKG_CONTINUOUS_ONLY_V1"
HKEX_STATUTORY_FEE_SCHEDULE_VERSION = "HKEX_HK_EQUITY_STATUTORY_V1"
HKEX_STATUTORY_FEE_SOURCE_AS_OF = "2026-09-02"

_CENT = Decimal("0.01")
_ONE_HKD = Decimal("1")
_SFC_LEVY_RATE = Decimal("0.000027")       # 0.0027%
_AFRC_LEVY_RATE = Decimal("0.0000015")     # 0.00015%
_TRADING_FEE_RATE = Decimal("0.0000565")   # 0.00565%
_STAMP_DUTY_RATE = Decimal("0.001")        # 0.1%
_BEIJING_TZ = timezone(timedelta(hours=8))


def _money_cent(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _stamp_duty(value: Decimal) -> Decimal:
    return value.quantize(_ONE_HKD, rounding=ROUND_CEILING)


def calculate_hkex_equity_statutory_fees(
    gross_hkd: float | Decimal,
    *,
    side: str,
) -> dict[str, object]:
    """Calculate the versioned HKEX statutory transaction-fee snapshot."""

    gross = Decimal(str(gross_hkd))
    if not gross.is_finite() or gross <= 0:
        raise ValueError("paper_hk_gross_value_invalid")
    normalized_side = str(side or "").strip().upper()
    if normalized_side not in {"BUY", "SELL"}:
        raise ValueError("paper_hk_side_invalid")

    sfc = _money_cent(gross * _SFC_LEVY_RATE)
    afrc = _money_cent(gross * _AFRC_LEVY_RATE)
    trading = _money_cent(gross * _TRADING_FEE_RATE)
    stamp = _stamp_duty(gross * _STAMP_DUTY_RATE)
    total = sfc + afrc + trading + stamp
    return {
        "version": HKEX_STATUTORY_FEE_SCHEDULE_VERSION,
        "source_as_of": HKEX_STATUTORY_FEE_SOURCE_AS_OF,
        "currency": "HKD",
        "gross_hkd": float(gross),
        "side": normalized_side,
        "sfc_transaction_levy": float(sfc),
        "afrc_transaction_levy": float(afrc),
        "trading_fee": float(trading),
        "stamp_duty": float(stamp),
        "broker_commission": None,
        "participant_clearing_pass_through": None,
        "statutory_total_hkd": float(total),
    }


def hkex_statutory_fee_schedule() -> dict[str, object]:
    return {
        "version": HKEX_STATUTORY_FEE_SCHEDULE_VERSION,
        "source_as_of": HKEX_STATUTORY_FEE_SOURCE_AS_OF,
        "currency": "HKD",
        "sfc_transaction_levy_rate": float(_SFC_LEVY_RATE),
        "afrc_transaction_levy_rate": float(_AFRC_LEVY_RATE),
        "trading_fee_rate": float(_TRADING_FEE_RATE),
        "stamp_duty_rate": float(_STAMP_DUTY_RATE),
        "levy_rounding": "NEAREST_HKD_CENT",
        "stamp_duty_rounding": "ROUND_UP_TO_HKD_1",
        "stamp_duty_sides": ["BUY", "SELL"],
        "broker_commission_policy": "SEPARATE_REQUIRED",
        "participant_clearing_pass_through_policy": "SEPARATE_REQUIRED",
    }


def _parse_time(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_BEIJING_TZ)
    return parsed.astimezone(_BEIJING_TZ)


def _positive_rate(value: object) -> float | None:
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return None
    return rate if math.isfinite(rate) and rate > 0 else None


def _normalize_reference_observation(
    raw: Mapping[str, object] | None,
    *,
    now: datetime,
) -> tuple[dict[str, object] | None, list[str]]:
    if raw is None:
        return None, ["paper_hk_fx_observation_missing"]

    if now.tzinfo is None:
        now = now.replace(tzinfo=_BEIJING_TZ)
    else:
        now = now.astimezone(_BEIJING_TZ)

    kind = str(raw.get("kind") or "").strip().upper()
    pair = str(raw.get("pair") or "").strip().upper()
    currency = str(raw.get("currency") or "").strip().upper()
    channel = str(raw.get("settlement_channel") or "").strip()
    applicable_date = str(raw.get("applicable_date") or "").strip()
    provider = str(raw.get("provider") or raw.get("source") or "").strip()
    upstream = str(raw.get("upstream") or "").strip()
    source_reference = str(raw.get("source_reference") or "").strip()
    retrieved_at = _parse_time(raw.get("retrieved_at") or raw.get("observed_at"))
    buy_rate = _positive_rate(raw.get("buy_rate"))
    sell_rate = _positive_rate(raw.get("sell_rate"))

    reasons: list[str] = []
    if (
        kind != "REFERENCE"
        or pair != HKD_CNY_PAIR
        or currency != "HKD"
        or channel != HK_STOCK_CONNECT_SETTLEMENT_CHANNEL
        or buy_rate is None
        or sell_rate is None
        or not provider
        or upstream != "SSE"
        or not source_reference
        or retrieved_at is None
    ):
        reasons.append("paper_hk_fx_observation_invalid")
    elif applicable_date != now.date().isoformat():
        reasons.append("paper_hk_fx_observation_stale")

    normalized = {
        "kind": kind or None,
        "pair": pair or HKD_CNY_PAIR,
        "currency": currency or None,
        "settlement_channel": channel or None,
        "applicable_date": applicable_date or None,
        "buy_rate": buy_rate,
        "sell_rate": sell_rate,
        "provider": provider or None,
        "provider_version": raw.get("provider_version"),
        "upstream": upstream or None,
        "source_reference": source_reference or None,
        "retrieved_at": retrieved_at.isoformat() if retrieved_at else None,
        "snapshot_id": raw.get("snapshot_id"),
        "payload_hash": raw.get("payload_hash"),
    }
    return normalized, reasons


@dataclass(frozen=True, slots=True)
class HkStockConnectPaperContract:
    """Pure evaluator for whether the HK paper-execution contract is complete."""

    def evaluate(
        self,
        *,
        metadata: Mapping[str, object] | None,
        adapter,
        now: datetime,
        fx_observation: Mapping[str, object] | None = None,
        broker_commission_policy: str | None = None,
        participant_clearing_pass_through_policy: str | None = None,
    ) -> dict[str, object]:
        metadata = metadata or {}
        lot_size = int(metadata.get("lot_size") or 0)
        price_tick = metadata.get("price_tick")
        reasons: list[str] = []

        if adapter is None or str(getattr(adapter, "market", "")) != "HK":
            reasons.append("paper_hk_market_identity_invalid")
        else:
            if str(getattr(adapter, "trading_currency", "")) != "HKD":
                reasons.append("paper_hk_trading_currency_invalid")
            if str(getattr(adapter, "settlement_currency", "")) != "CNY":
                reasons.append("paper_hk_settlement_currency_invalid")
            if str(getattr(adapter, "settlement_channel", "")) != HK_STOCK_CONNECT_SETTLEMENT_CHANNEL:
                reasons.append("paper_hk_settlement_channel_invalid")
            if str(getattr(adapter, "settlement_rule", "")) != "HK_T0_SELLABILITY":
                reasons.append("paper_hk_sellability_rule_invalid")

        if lot_size <= 0:
            reasons.append("paper_instrument_lot_size_required")
        if price_tick in (None, "", 0, 0.0):
            reasons.append("paper_instrument_price_tick_required")

        normalized_fx, fx_reasons = _normalize_reference_observation(fx_observation, now=now)
        reasons.extend(fx_reasons)

        broker_policy = str(broker_commission_policy or "").strip() or None
        clearing_policy = str(participant_clearing_pass_through_policy or "").strip() or None
        if broker_policy is None:
            reasons.append("paper_hk_broker_commission_policy_unconfigured")
        if clearing_policy is None:
            reasons.append("paper_hk_clearing_fee_policy_unconfigured")

        reasons = list(dict.fromkeys(reasons))
        return {
            "contract_version": "HK_STOCK_CONNECT_PAPER_V1",
            "market": "HK",
            "exchange_calendar": "XHKG",
            "session_policy": HK_CONTINUOUS_SESSION_POLICY,
            "trading_currency": "HKD",
            "paper_account_currency": "CNY",
            "settlement_currency": "CNY",
            "settlement_channel": HK_STOCK_CONNECT_SETTLEMENT_CHANNEL,
            "sellability_rule": "HK_T0_SELLABILITY",
            "fx_required_pair": HKD_CNY_PAIR,
            # Keep the Phase 2C key for additive/backward compatibility while
            # making its directional daily-reference semantics explicit.
            "fx_observation": normalized_fx,
            "fx_reference_observation": normalized_fx,
            "fx_reference_semantics": {
                "buy_order_reserve_rate": "REFERENCE_SELL_RATE",
                "sell_order_estimate_rate": "REFERENCE_BUY_RATE",
                "midpoint_allowed": False,
                "generic_spot_fx_allowed": False,
            },
            "statutory_fee_schedule": hkex_statutory_fee_schedule(),
            "broker_commission_policy": broker_policy,
            "participant_clearing_pass_through_policy": clearing_policy,
            "lot_size": lot_size or None,
            "price_tick": price_tick,
            "execution_ready": not reasons,
            "blocking_reason_codes": reasons,
        }


__all__ = [
    "HKD_CNY_PAIR",
    "HKEX_STATUTORY_FEE_SCHEDULE_VERSION",
    "HK_STOCK_CONNECT_SETTLEMENT_CHANNEL",
    "HkStockConnectPaperContract",
    "calculate_hkex_equity_statutory_fees",
    "hkex_statutory_fee_schedule",
]
