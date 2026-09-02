"""Deterministic prerequisites for Hong Kong Stock Connect paper execution.

This module deliberately does *not* enable HK fills by itself.  It freezes the
facts that a future Paper Broker execution must consume so HK cannot silently
inherit A-share assumptions.

Current product direction follows the existing ``MarketAdapter`` contract:
SEHK securities trade in HKD while the normal paper account settles through the
Southbound/Stock-Connect RMB channel.  Therefore an observed HKD->CNY rate,
authoritative instrument lot/tick metadata and explicit paper-broker fee
policies are required before execution can become eligible.

The statutory fee snapshot below models the current ordinary HK securities
transaction levies published by HKEX.  Broker commission and participant-level
clearing pass-through are intentionally separate because they are not universal
investor rates.
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
_UTC = timezone.utc


def _money_cent(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _stamp_duty(value: Decimal) -> Decimal:
    # HKEX states ordinary stock stamp duty is rounded *up* to the nearest HKD.
    return value.quantize(_ONE_HKD, rounding=ROUND_CEILING)


def calculate_hkex_equity_statutory_fees(
    gross_hkd: float | Decimal,
    *,
    side: str,
) -> dict[str, object]:
    """Calculate the versioned HKEX statutory transaction-fee snapshot.

    Brokerage is deliberately excluded: HKEX describes brokerage as freely
    negotiable between brokers and clients.  Participant-level clearing fees are
    also excluded from this statutory snapshot and must be configured explicitly
    by the Paper Broker before a Stock Connect fill can be enabled.
    """

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


def _parse_observed_at(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_UTC)
    return parsed.astimezone(_UTC)


def _normalize_fx_observation(
    raw: Mapping[str, object] | None,
    *,
    now: datetime,
    max_age_seconds: int,
) -> tuple[dict[str, object] | None, list[str]]:
    if raw is None:
        return None, ["paper_hk_fx_observation_missing"]

    pair = str(raw.get("pair") or "").strip().upper()
    source = str(raw.get("source") or "").strip()
    observed_at = _parse_observed_at(raw.get("observed_at"))
    try:
        rate = float(raw.get("rate") or 0)
    except (TypeError, ValueError):
        rate = 0.0

    reasons: list[str] = []
    if pair != HKD_CNY_PAIR or not math.isfinite(rate) or rate <= 0 or not source or observed_at is None:
        reasons.append("paper_hk_fx_observation_invalid")
    elif (now.astimezone(_UTC) - observed_at).total_seconds() > max_age_seconds:
        reasons.append("paper_hk_fx_observation_stale")

    normalized = {
        "pair": pair or HKD_CNY_PAIR,
        "rate": rate if rate > 0 and math.isfinite(rate) else None,
        "observed_at": observed_at.isoformat() if observed_at else None,
        "source": source or None,
        "max_age_seconds": max_age_seconds,
    }
    return normalized, reasons


@dataclass(frozen=True, slots=True)
class HkStockConnectPaperContract:
    """Pure evaluator for whether the HK paper-execution contract is complete."""

    fx_max_age_seconds: int = 300

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

        normalized_fx, fx_reasons = _normalize_fx_observation(
            fx_observation,
            now=now,
            max_age_seconds=max(1, int(self.fx_max_age_seconds)),
        )
        reasons.extend(fx_reasons)

        broker_policy = str(broker_commission_policy or "").strip() or None
        clearing_policy = str(participant_clearing_pass_through_policy or "").strip() or None
        if broker_policy is None:
            reasons.append("paper_hk_broker_commission_policy_unconfigured")
        if clearing_policy is None:
            reasons.append("paper_hk_clearing_fee_policy_unconfigured")

        # Preserve order while preventing duplicate reason codes when the caller
        # also performs generic instrument validation.
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
            "fx_observation": normalized_fx,
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
