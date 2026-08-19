"""Local-First governed 60m/15m/5m technical evidence.

This module consumes only persisted one-minute bars.  It never calls a market
provider and it owns no formal action authority.  Until the separately
versioned Multi-Timeframe ActionPolicy is enabled, its output is research/audit
Evidence only.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from statistics import mean
from zoneinfo import ZoneInfo

from app.decision_models import TimeframeTechnicalSnapshot
from app.market_adapter import adapter_for_market
from app.trading_calendar import TradingCalendarService


INTRADAY_TIMEFRAME_POLICY_VERSION = "intraday-timeframe-evidence-v1-completed-bars"
TIMEFRAME_MINUTES = (60, 15, 5)
MIN_TECHNICAL_BUCKETS = 12

# Exchange lunch breaks are structural boundaries. A 60m bucket never bridges
# 11:30 -> 13:00 in CN or 12:00 -> 13:00 in HK.
_SESSION_WINDOWS: dict[str, tuple[tuple[time, time], ...]] = {
    "CN": ((time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))),
    "HK": ((time(9, 30), time(12, 0)), (time(13, 0), time(16, 0))),
    "US": ((time(9, 30), time(16, 0)),),
}


def _hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _parse_bar_time(value: object, timezone_name: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    timezone = ZoneInfo(timezone_name)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def _session_window(market: str, moment: datetime) -> tuple[datetime, datetime] | None:
    for start_time, end_time in _SESSION_WINDOWS.get(market, ()):
        start = moment.replace(hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0)
        end = moment.replace(hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0)
        # Provider one-minute bars are conventionally labelled by minute start.
        # The exact session-end label is not a new bucket start.
        if start <= moment < end:
            return start, end
    return None


def _bucket_bounds(market: str, moment: datetime, minutes: int) -> tuple[datetime, datetime] | None:
    session = _session_window(market, moment)
    if session is None:
        return None
    session_start, session_end = session
    offset_minutes = int((moment - session_start).total_seconds() // 60)
    bucket_offset = (offset_minutes // minutes) * minutes
    bucket_start = session_start + timedelta(minutes=bucket_offset)
    bucket_end = min(bucket_start + timedelta(minutes=minutes), session_end)
    return bucket_start, bucket_end


def _completed_buckets(
    rows: list[dict[str, object]],
    *,
    market: str,
    timezone_name: str,
    minutes: int,
    analysis_at: datetime,
) -> list[dict[str, object]]:
    timezone = ZoneInfo(timezone_name)
    reference = analysis_at.astimezone(timezone)
    grouped: dict[tuple[str, str], list[tuple[datetime, dict[str, object]]]] = defaultdict(list)
    for row in rows:
        moment = _parse_bar_time(row.get("bar_time"), timezone_name)
        if moment is None or moment > reference:
            continue
        bounds = _bucket_bounds(market, moment, minutes)
        if bounds is None:
            continue
        bucket_start, bucket_end = bounds
        # Never promote the currently forming candle to completed evidence.
        if bucket_end > reference:
            continue
        grouped[(bucket_start.isoformat(), bucket_end.isoformat())].append((moment, row))

    buckets: list[dict[str, object]] = []
    for (start_text, end_text), items in grouped.items():
        items.sort(key=lambda pair: pair[0])
        values = [item[1] for item in items]
        try:
            opens = [float(item["open"]) for item in values]
            closes = [float(item["close"]) for item in values]
            highs = [float(item["high"]) for item in values]
            lows = [float(item["low"]) for item in values]
        except (KeyError, TypeError, ValueError):
            continue
        source_names = sorted({str(item.get("source") or "intraday_price_cache") for item in values})
        retrieved = sorted(str(item.get("updated_at") or "") for item in values if item.get("updated_at"))
        buckets.append({
            "start": start_text,
            "end": end_text,
            "open": opens[0],
            "close": closes[-1],
            "high": max(highs),
            "low": min(lows),
            "volume": sum(float(item.get("volume") or 0) for item in values),
            "amount": sum(float(item.get("amount") or 0) for item in values),
            "source": ",".join(source_names),
            "retrieved_at": retrieved[-1] if retrieved else None,
            "raw_count": len(values),
        })
    buckets.sort(key=lambda item: str(item["end"]))
    return buckets


def _latest_expected_bucket_end(
    *,
    market: str,
    timezone_name: str,
    minutes: int,
    analysis_at: datetime,
    latest_completed_date: str | None,
    latest_observed_date: date | None,
) -> datetime | None:
    timezone = ZoneInfo(timezone_name)
    reference = analysis_at.astimezone(timezone)
    completed_date = None
    try:
        completed_date = date.fromisoformat(str(latest_completed_date)) if latest_completed_date else None
    except ValueError:
        completed_date = None
    target_date = max(item for item in (completed_date, latest_observed_date) if item is not None) if any(
        item is not None for item in (completed_date, latest_observed_date)
    ) else None
    if target_date is None:
        return None

    windows = _SESSION_WINDOWS.get(market, ())
    candidates: list[datetime] = []
    for start_time, end_time in windows:
        session_start = datetime.combine(target_date, start_time, tzinfo=timezone)
        session_end = datetime.combine(target_date, end_time, tzinfo=timezone)
        cap = min(reference, session_end) if target_date == reference.date() else session_end
        if cap <= session_start:
            continue
        elapsed = int((cap - session_start).total_seconds() // 60)
        completed_minutes = (elapsed // minutes) * minutes
        if cap >= session_end:
            completed_minutes = int((session_end - session_start).total_seconds() // 60)
        if completed_minutes <= 0:
            continue
        candidates.append(min(session_start + timedelta(minutes=completed_minutes), session_end))
    return max(candidates) if candidates else None


def _technical_snapshot(
    buckets: list[dict[str, object]],
    *,
    timeframe: str,
    minutes: int,
    expected_end: datetime | None,
) -> TimeframeTechnicalSnapshot:
    if not buckets:
        return TimeframeTechnicalSnapshot(
            timeframe=timeframe,
            as_of=None,
            sample_count=0,
            source="intraday_price_cache",
            source_hash=_hash([]),
            freshness_status="unknown",
            availability="MISSING",
            last_completed_bar=None,
            reason_codes=("intraday.no_completed_bars",),
        )

    closes = [float(item["close"]) for item in buckets]
    latest = buckets[-1]
    latest_end = datetime.fromisoformat(str(latest["end"]))
    stale = bool(expected_end is not None and latest_end < expected_end)
    enough = len(buckets) >= MIN_TECHNICAL_BUCKETS
    if stale:
        availability = "STALE"
        reasons = ("intraday.latest_completed_bucket_missing",)
    elif not enough:
        availability = "MISSING"
        reasons = ("intraday.insufficient_completed_buckets",)
    else:
        availability = "AVAILABLE"
        reasons = ()

    fast_sma = mean(closes[-4:]) if len(closes) >= 4 else None
    slow_sma = mean(closes[-12:]) if len(closes) >= 12 else None
    trend = None
    if fast_sma is not None and slow_sma is not None:
        trend = "up" if fast_sma > slow_sma else "down" if fast_sma < slow_sma else "flat"

    price_location = "UNKNOWN"
    if fast_sma is not None and slow_sma is not None:
        if closes[-1] > fast_sma and closes[-1] > slow_sma:
            price_location = "ABOVE_FAST_SLOW"
        elif closes[-1] < fast_sma and closes[-1] < slow_sma:
            price_location = "BELOW_FAST_SLOW"
        else:
            price_location = "BETWEEN_FAST_SLOW"

    momentum = "UNKNOWN"
    if len(closes) >= 2:
        momentum = "UP" if closes[-1] > closes[-2] else "DOWN" if closes[-1] < closes[-2] else "FLAT"

    ranges = [
        (float(item["high"]) - float(item["low"])) / float(item["close"]) * 100
        for item in buckets[-12:]
        if float(item["close"]) != 0
    ]
    volatility_percent = mean(ranges) if ranges else None
    volatility = "UNKNOWN"
    if volatility_percent is not None:
        volatility = "HIGH" if volatility_percent >= 2.0 else "MEDIUM" if volatility_percent >= 0.8 else "LOW"

    source_material = [{
        key: item.get(key)
        for key in ("start", "end", "open", "close", "high", "low", "volume", "amount", "source", "retrieved_at", "raw_count")
    } for item in buckets]
    sources = sorted({str(item.get("source") or "intraday_price_cache") for item in buckets})
    retrieved_values = sorted(str(item.get("retrieved_at") or "") for item in buckets if item.get("retrieved_at"))
    return TimeframeTechnicalSnapshot(
        timeframe=timeframe,
        as_of=str(latest["end"]),
        sample_count=len(buckets),
        close=closes[-1],
        fast_sma=round(fast_sma, 6) if fast_sma is not None else None,
        slow_sma=round(slow_sma, 6) if slow_sma is not None else None,
        trend=trend,
        trend_structure=trend.upper() if trend else "UNKNOWN",
        price_location=price_location,
        momentum=momentum,
        volatility=volatility,
        volatility_percent=round(volatility_percent, 6) if volatility_percent is not None else None,
        source=",".join(sources) or "intraday_price_cache",
        source_hash=_hash(source_material),
        retrieved_at=retrieved_values[-1] if retrieved_values else None,
        freshness_status="stale" if stale else "fresh" if enough else "unknown",
        availability=availability,
        last_completed_bar=str(latest["end"]),
        reason_codes=reasons,
        policy_authority="RESEARCH_ONLY",
    )


def build_intraday_timeframe_snapshots(
    rows: list[dict[str, object]],
    *,
    market: str | None,
    analysis_at: datetime,
    calendar: TradingCalendarService | None = None,
) -> tuple[TimeframeTechnicalSnapshot, ...]:
    adapter = adapter_for_market(market)
    normalized_market = str(market or "").strip().upper()
    if adapter is None or normalized_market not in _SESSION_WINDOWS:
        return ()
    timezone = ZoneInfo(adapter.timezone)
    parsed_times = [
        parsed for parsed in (_parse_bar_time(row.get("bar_time"), adapter.timezone) for row in rows)
        if parsed is not None
    ]
    latest_observed_date = max((item.date() for item in parsed_times), default=None)
    service = calendar or TradingCalendarService()
    try:
        latest_completed_date = service.latest_completed_session_date(normalized_market, analysis_at)
    except Exception:
        latest_completed_date = None

    snapshots = []
    for minutes in TIMEFRAME_MINUTES:
        timeframe = f"{minutes}m"
        buckets = _completed_buckets(
            rows,
            market=normalized_market,
            timezone_name=adapter.timezone,
            minutes=minutes,
            analysis_at=analysis_at,
        )
        expected_end = _latest_expected_bucket_end(
            market=normalized_market,
            timezone_name=adapter.timezone,
            minutes=minutes,
            analysis_at=analysis_at,
            latest_completed_date=latest_completed_date,
            latest_observed_date=latest_observed_date,
        )
        snapshots.append(_technical_snapshot(
            buckets,
            timeframe=timeframe,
            minutes=minutes,
            expected_end=expected_end,
        ))
    return tuple(snapshots)


__all__ = [
    "INTRADAY_TIMEFRAME_POLICY_VERSION",
    "MIN_TECHNICAL_BUCKETS",
    "TIMEFRAME_MINUTES",
    "build_intraday_timeframe_snapshots",
]
