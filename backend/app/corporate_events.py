"""Deterministic scheduled corporate-event adapter and pre-event risk policy.

Corporate events are facts about *when* a potentially material disclosure is
scheduled. They are never interpreted as bullish/bearish evidence by this
module. The current provider is a secondary earnings calendar exposed by
AKShare; source tier and provenance remain visible so a future official adapter
can replace or cross-check it without changing policy semantics.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app import decision_config as config
from app.decision_models import EventSnapshot
from app.market_adapter import adapter_for_market
from app.trading_calendar import TradingCalendarService


CALENDAR_SOURCE = "Baidu 股市通财报日历 via AKShare"
CALENDAR_SOURCE_REFERENCE = "https://gushitong.baidu.com/calendar"
EVENT_LOOKAHEAD_SESSIONS = 3
EVENT_REFRESH_TRIGGERS = frozenset({
    "paper-trading-decision",
    "scheduler-trading-session",
    "scheduler-close-snapshot",
})


def _records(value) -> list[dict[str, object]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return [dict(item) for item in to_dict("records")]
        except (TypeError, ValueError):
            return []
    return []


def _market_from_exchange(value: object) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    if text in {"HK", "HKG"} or "香港" in text or "港股" in text:
        return "HK"
    if text in {"US", "USA"} or "美股" in text or any(key in text for key in ("NASDAQ", "NYSE", "AMEX")):
        return "US"
    if text in {"SH", "SZ", "BJ", "CN", "A股"} or any(key in text for key in ("沪", "深", "京", "上交所", "深交所", "北交所")):
        return "CN"
    return None


def _normalize_provider_symbol(value: object, market: str | None) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if market in {"HK", "CN"}:
        digits = "".join(character for character in text if character.isdigit())
        if not digits:
            return ""
        return digits.zfill(5 if market == "HK" else 6)
    return text


def _event_id(symbol: str, scheduled_date: str, period: str) -> str:
    payload = f"earnings_report|{symbol}|{scheduled_date}|{period}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"corp-earnings-{digest}"


def _parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


class CorporateEventService:
    """Refresh a bounded, daily-cached earnings calendar into local storage."""

    def __init__(self, fetcher=None, calendar=None) -> None:
        self._fetcher = fetcher or self._akshare_fetch
        self._calendar = calendar or TradingCalendarService()

    @staticmethod
    def _akshare_fetch(date_text: str):
        import akshare as ak

        return ak.news_report_time_baidu(date=date_text)

    @staticmethod
    def _instrument_market(store, symbol: str) -> str | None:
        try:
            metadata = store.instrument_metadata(symbol)
        except Exception:
            metadata = None
        if metadata and metadata.get("market"):
            return str(metadata["market"]).strip().upper()
        return TradingCalendarService.market_for_symbol(symbol)

    def _session_dates(self, market: str, now: datetime) -> list[str]:
        adapter = adapter_for_market(market)
        if adapter is None:
            return []
        local_date = now.astimezone(ZoneInfo(adapter.timezone)).date()
        end = local_date + timedelta(days=14)
        sessions = self._calendar.session_dates(market, local_date.isoformat(), end.isoformat())
        return list(sessions[:EVENT_LOOKAHEAD_SESSIONS])

    def _calendar_payload(self, store, scheduled_date: str, now: datetime) -> dict[str, object]:
        key = f"corporate_event_calendar:{scheduled_date}"
        cached = store.cached_market_intelligence(key) or {}
        retrieved_on = str(cached.get("retrieved_on") or "")
        if cached.get("status") == "ready" and retrieved_on == now.date().isoformat():
            return cached

        try:
            raw = self._fetcher(scheduled_date.replace("-", ""))
            normalized_rows = []
            for row in _records(raw):
                market = _market_from_exchange(row.get("交易所") or row.get("exchange"))
                symbol = _normalize_provider_symbol(row.get("股票代码") or row.get("symbol"), market)
                if not symbol or not market:
                    continue
                normalized_rows.append({
                    "symbol": symbol,
                    "market": market,
                    "name": str(row.get("股票简称") or row.get("name") or symbol),
                    "period": str(row.get("财报期") or row.get("period") or "财报"),
                    "scheduled_date": scheduled_date,
                })
            payload = {
                "status": "ready",
                "scheduled_date": scheduled_date,
                "rows": normalized_rows,
                "source": CALENDAR_SOURCE,
                "source_reference": CALENDAR_SOURCE_REFERENCE,
                "retrieved_at": now.isoformat(),
                "retrieved_on": now.date().isoformat(),
            }
            store.save_market_intelligence(key, payload)
            return payload
        except Exception as error:
            if cached:
                fallback = dict(cached)
                fallback["status"] = "stale_fallback"
                fallback["error_type"] = type(error).__name__
                return fallback
            return {
                "status": "unavailable",
                "scheduled_date": scheduled_date,
                "rows": [],
                "source": CALENDAR_SOURCE,
                "source_reference": CALENDAR_SOURCE_REFERENCE,
                "retrieved_at": now.isoformat(),
                "retrieved_on": now.date().isoformat(),
                "error_type": type(error).__name__,
            }

    def refresh(self, store, symbols, *, now: datetime) -> dict[str, dict[str, object]]:
        requested = list(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
        markets = {symbol: self._instrument_market(store, symbol) for symbol in requested}
        dates = sorted({
            scheduled_date
            for market in set(value for value in markets.values() if value)
            for scheduled_date in self._session_dates(str(market), now)
        })
        payloads = {scheduled_date: self._calendar_payload(store, scheduled_date, now) for scheduled_date in dates}

        events_by_symbol: dict[str, list[dict[str, object]]] = {symbol: [] for symbol in requested}
        unavailable_dates = []
        for scheduled_date, payload in payloads.items():
            if payload.get("status") not in {"ready", "stale_fallback"}:
                unavailable_dates.append(scheduled_date)
            for row in payload.get("rows", []):
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("symbol") or "").strip().upper()
                market = str(row.get("market") or "").strip().upper()
                if symbol not in events_by_symbol or market != markets.get(symbol):
                    continue
                period = str(row.get("period") or "财报")
                event_id = _event_id(symbol, scheduled_date, period)
                events_by_symbol[symbol].append({
                    "event_id": event_id,
                    "symbol": symbol,
                    "market": market,
                    "event_type": "earnings_report",
                    "title": f"{row.get('name') or symbol} {period}计划披露",
                    "scheduled_at": scheduled_date,
                    "impact": "neutral",
                    "evidence_polarity": "NEUTRAL_MATERIAL",
                    "verification_level": "secondary_calendar",
                    # A secondary calendar may conservatively block *new* risk.
                    # It never authorizes a trade or a directional conclusion.
                    "policy_eligible": True,
                    "source": CALENDAR_SOURCE,
                    "source_reference": CALENDAR_SOURCE_REFERENCE,
                    "summary": "已知财报披露日属于方向未知但重要的事件风险，不预判利好或利空。",
                })

        results: dict[str, dict[str, object]] = {}
        for symbol in requested:
            events = events_by_symbol[symbol]
            previous = store.cached_market_intelligence(f"corporate_events:{symbol}") or {}
            if unavailable_dates and previous.get("events"):
                by_id = {str(item.get("event_id")): dict(item) for item in events if isinstance(item, dict)}
                for item in previous.get("events", []):
                    if not isinstance(item, dict):
                        continue
                    scheduled = str(item.get("scheduled_at") or "")[:10]
                    if scheduled in dates and str(item.get("event_id") or "") not in by_id:
                        by_id[str(item.get("event_id") or "")] = dict(item)
                events = list(by_id.values())
            events.sort(key=lambda item: (str(item.get("scheduled_at") or ""), str(item.get("event_id") or "")))
            status = "partial" if unavailable_dates else "ready"
            bundle = {
                "status": status,
                "symbol": symbol,
                "market": markets.get(symbol),
                "window_dates": dates,
                "events": events,
                "source": CALENDAR_SOURCE,
                "source_reference": CALENDAR_SOURCE_REFERENCE,
                "retrieved_at": now.isoformat(),
                "unavailable_dates": unavailable_dates,
            }
            store.save_market_intelligence(f"corporate_events:{symbol}", bundle)
            results[symbol] = bundle
        return results


def sessions_until_event(
    event: EventSnapshot,
    *,
    market: str,
    analysis_at: datetime,
    calendar: TradingCalendarService | None = None,
) -> int | None:
    scheduled = _parse_date(event.scheduled_at)
    adapter = adapter_for_market(market)
    if scheduled is None or adapter is None:
        return None
    local_date = analysis_at.astimezone(ZoneInfo(adapter.timezone)).date()
    if scheduled < local_date:
        return None
    if scheduled == local_date:
        return 0
    service = calendar or TradingCalendarService()
    sessions = service.session_dates(market, local_date.isoformat(), scheduled.isoformat())
    return sum(1 for item in sessions if local_date < date.fromisoformat(item) <= scheduled)


def pre_event_policy_blockers(
    events: tuple[EventSnapshot, ...],
    *,
    market: str | None,
    analysis_at: datetime,
    calendar: TradingCalendarService | None = None,
) -> tuple[str, ...]:
    """Block new risk near scheduled earnings without manufacturing direction."""
    if not market:
        return ()
    blockers = []
    for event in events:
        if (
            event.lifecycle != "upcoming"
            or event.event_type != "earnings_report"
            or not event.policy_eligible
        ):
            continue
        distance = sessions_until_event(
            event,
            market=market,
            analysis_at=analysis_at,
            calendar=calendar,
        )
        if distance is not None and distance <= config.PRE_EVENT_BLOCK_SESSIONS:
            blockers.append(f"event_risk.upcoming_earnings:{event.event_id}")
    return tuple(dict.fromkeys(blockers))


def install(m) -> None:
    """Refresh scheduled-event cache before formal paper decisions use context."""
    if getattr(m, "_corporate_event_policy_installed", False):
        return
    m._corporate_event_policy_installed = True
    service = CorporateEventService()
    m.corporate_event_service = service
    original_refresh_derived_cache = m.refresh_derived_cache

    def refresh_derived_cache(symbols, trigger, force_history=False, run_id=None):
        result = original_refresh_derived_cache(
            symbols,
            trigger,
            force_history=force_history,
            run_id=run_id,
        )
        if str(trigger) not in EVENT_REFRESH_TRIGGERS:
            return result
        requested = list(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
        if not requested:
            return result
        try:
            bundles = service.refresh(m.store, requested, now=m.beijing_now())
            event_count = sum(len(bundle.get("events", [])) for bundle in bundles.values())
            m.logger.info(
                "corporate event calendar refreshed symbols=%s event_count=%s policy_version=%s",
                ",".join(requested),
                event_count,
                config.CORPORATE_EVENT_POLICY_VERSION,
            )
        except Exception as error:
            m.logger.warning(
                "corporate event calendar refresh unavailable error_type=%s",
                type(error).__name__,
            )
        return result

    m.refresh_derived_cache = refresh_derived_cache


__all__ = [
    "CALENDAR_SOURCE",
    "CALENDAR_SOURCE_REFERENCE",
    "CorporateEventService",
    "install",
    "pre_event_policy_blockers",
    "sessions_until_event",
]
