"""Deterministic corporate-event acquisition, lifecycle, and pre-event risk policy.

Corporate events are facts about *when* a potentially material disclosure is
scheduled or expected. They are never interpreted as bullish/bearish evidence
by this module.

The built-in remote source remains the secondary Baidu/AKShare earnings
calendar. A source-ranked official-event ingestion contract is also supported:
an injected official fetcher (or a separately persisted official-event cache)
can provide HKEX/company-IR facts without changing DecisionContext, Evidence,
or ActionPolicy authority. Official facts outrank secondary facts; conflicts
remain explicit and auditable.

A known earnings obligation is durable. Once discovered, it survives the
forward calendar window until it is verified, cancelled, or superseded. This
prevents financial-currentness logic from forgetting a due report merely
because its scheduled date moved into the past.
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
OFFICIAL_SOURCE_RANK = 10
SECONDARY_SOURCE_RANK = 30
UNKNOWN_SOURCE_RANK = 90
ACTIVE_LIFECYCLES = frozenset({"SCHEDULED", "DUE", "RELEASE_EXPECTED", "RELEASED_UNVERIFIED"})
TERMINAL_LIFECYCLES = frozenset({"VERIFIED", "CANCELLED", "SUPERSEDED"})
# Remote calendar refresh is a scheduler/maintenance responsibility. Formal
# paper-decision cycles consume the persisted bundle only, preserving Local-First
# behavior and avoiding a new network dependency on the action path.
EVENT_REFRESH_TRIGGERS = frozenset({
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


def _event_key(symbol: str, period: str) -> str:
    normalized_period = " ".join(str(period or "财报").strip().split()).lower()
    payload = f"earnings_report|{symbol}|{normalized_period}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"corp-earnings-key-{digest}"


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


def _source_rank(verification_level: str | None) -> int:
    if verification_level == "official":
        return OFFICIAL_SOURCE_RANK
    if verification_level == "secondary_calendar":
        return SECONDARY_SOURCE_RANK
    return UNKNOWN_SOURCE_RANK


def _lifecycle_for_date(scheduled_at: object, *, today: date, previous: str | None = None) -> str:
    if previous in TERMINAL_LIFECYCLES:
        return str(previous)
    scheduled = _parse_date(scheduled_at)
    if scheduled is None:
        return "RELEASE_EXPECTED" if previous in ACTIVE_LIFECYCLES else "SCHEDULED"
    if scheduled > today:
        return "SCHEDULED"
    if scheduled == today:
        return "DUE"
    return "RELEASE_EXPECTED"


def _event_from_row(
    row: dict[str, object],
    *,
    default_source: str,
    default_reference: str | None,
    default_verification: str,
    today: date,
) -> dict[str, object] | None:
    market = str(row.get("market") or _market_from_exchange(row.get("交易所") or row.get("exchange")) or "").strip().upper()
    symbol = _normalize_provider_symbol(row.get("symbol") or row.get("股票代码"), market)
    scheduled_date = str(row.get("scheduled_date") or row.get("scheduled_at") or "").strip()[:10]
    if not symbol or not market or not _parse_date(scheduled_date):
        return None
    period = str(row.get("period") or row.get("财报期") or row.get("report_period") or "财报").strip() or "财报"
    verification = str(row.get("verification_level") or default_verification).strip() or default_verification
    source = str(row.get("source") or default_source).strip() or default_source
    source_reference = row.get("source_reference") or row.get("url") or default_reference
    lifecycle = str(row.get("lifecycle_status") or "").strip().upper() or _lifecycle_for_date(scheduled_date, today=today)
    if lifecycle not in ACTIVE_LIFECYCLES | TERMINAL_LIFECYCLES:
        lifecycle = _lifecycle_for_date(scheduled_date, today=today)
    event_key = str(row.get("event_key") or _event_key(symbol, period))
    event_id = str(row.get("event_id") or _event_id(symbol, scheduled_date, period))
    name = str(row.get("name") or row.get("股票简称") or symbol)
    return {
        "event_id": event_id,
        "event_key": event_key,
        "symbol": symbol,
        "market": market,
        "event_type": "earnings_report",
        "title": str(row.get("title") or f"{name} {period}计划披露"),
        "scheduled_at": scheduled_date,
        "period": period,
        "impact": "neutral",
        "evidence_polarity": "NEUTRAL_MATERIAL",
        "verification_level": verification,
        "source_rank": int(row.get("source_rank") or _source_rank(verification)),
        "lifecycle_status": lifecycle,
        # An event calendar may conservatively block *new* risk before release.
        # It never authorizes a trade or a directional conclusion.
        "policy_eligible": bool(row.get("policy_eligible", True)),
        "source": source,
        "source_reference": source_reference,
        "announced_at": row.get("announced_at"),
        "verified_at": row.get("verified_at"),
        "document_hash": row.get("document_hash"),
        "parser_version": row.get("parser_version"),
        "summary": str(row.get("summary") or "已知财报披露义务属于方向未知但重要的事件风险，不预判利好或利空。"),
    }


def _merge_event_candidates(candidates: list[dict[str, object]], *, today: date) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Select one active authority per logical event while retaining audit history."""
    # Repeated refreshes can see the same event from today's provider response
    # and from the previous durable bundle. Collapse exact observations before
    # source arbitration so a no-op refresh is byte-for-byte idempotent.
    unique: dict[tuple[object, ...], dict[str, object]] = {}
    for candidate in candidates:
        identity = (
            candidate.get("event_id"),
            candidate.get("source"),
            candidate.get("scheduled_at"),
            candidate.get("verification_level"),
        )
        current = unique.get(identity)
        if current is None:
            unique[identity] = dict(candidate)
            continue
        # Keep the richer persisted record when the observation is identical.
        if len(candidate) > len(current):
            unique[identity] = dict(candidate)

    grouped: dict[str, list[dict[str, object]]] = {}
    for candidate in unique.values():
        grouped.setdefault(str(candidate.get("event_key") or candidate.get("event_id")), []).append(dict(candidate))

    active: list[dict[str, object]] = []
    history: list[dict[str, object]] = []
    for event_key, rows in grouped.items():
        rows.sort(key=lambda item: (
            int(item.get("source_rank") or UNKNOWN_SOURCE_RANK),
            str(item.get("scheduled_at") or ""),
            str(item.get("event_id") or ""),
        ))
        chosen = dict(rows[0])
        chosen["event_key"] = event_key
        chosen["lifecycle_status"] = _lifecycle_for_date(
            chosen.get("scheduled_at"),
            today=today,
            previous=str(chosen.get("lifecycle_status") or "") or None,
        )
        dates = sorted({str(item.get("scheduled_at") or "") for item in rows if item.get("scheduled_at")})
        if len(dates) > 1:
            chosen["conflict_status"] = "CONFLICTED"
            chosen["conflict_dates"] = dates
            chosen["conflict_sources"] = sorted({
                str(item.get("source") or "unknown") for item in rows
            })
        else:
            chosen["conflict_status"] = "NONE"
            chosen["conflict_dates"] = dates
            chosen["conflict_sources"] = []

        for losing in rows[1:]:
            superseded = dict(losing)
            superseded["lifecycle_status"] = "SUPERSEDED"
            superseded["superseded_by"] = chosen.get("event_id")
            history.append(superseded)

        if chosen["lifecycle_status"] in ACTIVE_LIFECYCLES:
            active.append(chosen)
        else:
            history.append(chosen)

    active.sort(key=lambda item: (str(item.get("scheduled_at") or ""), str(item.get("event_id") or "")))
    history.sort(key=lambda item: (str(item.get("scheduled_at") or ""), str(item.get("event_id") or "")))
    return active, history


class CorporateEventService:
    """Refresh source-ranked corporate events into a durable local lifecycle."""

    def __init__(self, fetcher=None, calendar=None, official_fetcher=None) -> None:
        self._fetcher = fetcher or self._akshare_fetch
        self._calendar = calendar or TradingCalendarService()
        self._official_fetcher = official_fetcher

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

    def _official_payload(self, store, symbol: str, market: str | None, now: datetime) -> dict[str, object]:
        """Read/fill the Tier-1 ingestion cache without hiding remote I/O in DecisionContext.

        The injected fetcher is intentionally provider-agnostic. An HKEX or issuer-IR
        adapter can return normalized rows, while formal decisions consume only the
        persisted result. When no fetcher is registered, an existing official cache
        is still honored; absence remains explicit rather than fabricated.
        """
        key = f"corporate_event_official:{symbol}"
        cached = store.cached_market_intelligence(key) or {}
        if self._official_fetcher is None:
            return cached
        retrieved_on = str(cached.get("retrieved_on") or "")
        if cached.get("status") == "ready" and retrieved_on == now.date().isoformat():
            return cached
        try:
            raw = self._official_fetcher(symbol=symbol, market=market, now=now)
            rows = _records(raw)
            payload = {
                "status": "ready",
                "symbol": symbol,
                "market": market,
                "rows": rows,
                "retrieved_at": now.isoformat(),
                "retrieved_on": now.date().isoformat(),
                "source_rank": OFFICIAL_SOURCE_RANK,
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
                "symbol": symbol,
                "market": market,
                "rows": [],
                "retrieved_at": now.isoformat(),
                "retrieved_on": now.date().isoformat(),
                "source_rank": OFFICIAL_SOURCE_RANK,
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
        today = now.date()

        results: dict[str, dict[str, object]] = {}
        for symbol in requested:
            market = markets.get(symbol)
            candidates: list[dict[str, object]] = []
            unavailable_dates = []

            for scheduled_date, payload in payloads.items():
                if payload.get("status") not in {"ready", "stale_fallback"}:
                    unavailable_dates.append(scheduled_date)
                for row in payload.get("rows", []):
                    if not isinstance(row, dict):
                        continue
                    row_symbol = str(row.get("symbol") or "").strip().upper()
                    row_market = str(row.get("market") or "").strip().upper()
                    if row_symbol != symbol or row_market != market:
                        continue
                    event = _event_from_row(
                        row,
                        default_source=CALENDAR_SOURCE,
                        default_reference=CALENDAR_SOURCE_REFERENCE,
                        default_verification="secondary_calendar",
                        today=today,
                    )
                    if event is not None:
                        candidates.append(event)

            official_payload = self._official_payload(store, symbol, market, now)
            official_status = str(official_payload.get("status") or "unavailable")
            for row in official_payload.get("rows", []):
                if not isinstance(row, dict):
                    continue
                official_row = dict(row)
                official_row.setdefault("symbol", symbol)
                official_row.setdefault("market", market)
                official_row.setdefault("verification_level", "official")
                official_row.setdefault("source_rank", OFFICIAL_SOURCE_RANK)
                event = _event_from_row(
                    official_row,
                    default_source=str(official_row.get("source") or "official_corporate_event_source"),
                    default_reference=official_row.get("source_reference"),
                    default_verification="official",
                    today=today,
                )
                if event is not None and event.get("symbol") == symbol and event.get("market") == market:
                    candidates.append(event)

            previous = store.cached_market_intelligence(f"corporate_events:{symbol}") or {}
            previous_history = [dict(item) for item in previous.get("event_history", []) if isinstance(item, dict)]
            current_ids = {str(item.get("event_id") or "") for item in candidates if item.get("event_id")}
            # A previously known unresolved event is a durable obligation. Do not
            # erase it when its scheduled date falls out of the forward window.
            # If the same exact event is present in this refresh, do not add it a
            # second time merely because it also exists in the durable bundle.
            for item in previous.get("events", []):
                if not isinstance(item, dict):
                    continue
                previous_event = dict(item)
                if str(previous_event.get("event_id") or "") in current_ids:
                    continue
                previous_event["lifecycle_status"] = _lifecycle_for_date(
                    previous_event.get("scheduled_at"),
                    today=today,
                    previous=str(previous_event.get("lifecycle_status") or "") or None,
                )
                if previous_event["lifecycle_status"] in ACTIVE_LIFECYCLES:
                    candidates.append(previous_event)
                else:
                    previous_history.append(previous_event)

            events, superseded_history = _merge_event_candidates(candidates, today=today)
            history_by_identity = {
                (str(item.get("event_id") or ""), str(item.get("lifecycle_status") or "")): dict(item)
                for item in [*previous_history, *superseded_history]
                if item.get("event_id")
            }
            event_history = list(history_by_identity.values())
            event_history.sort(key=lambda item: (str(item.get("scheduled_at") or ""), str(item.get("event_id") or "")))

            status = "partial" if unavailable_dates or official_status == "stale_fallback" else "ready"
            bundle = {
                "status": status,
                "symbol": symbol,
                "market": market,
                "window_dates": dates,
                "events": events,
                "event_history": event_history,
                "source": CALENDAR_SOURCE,
                "source_reference": CALENDAR_SOURCE_REFERENCE,
                "source_hierarchy": {
                    "official": OFFICIAL_SOURCE_RANK,
                    "secondary_calendar": SECONDARY_SOURCE_RANK,
                    "unknown": UNKNOWN_SOURCE_RANK,
                },
                "official_source_status": official_status,
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
    """Refresh scheduled-event cache on scheduler/maintenance inputs only."""
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
                "corporate event lifecycle refreshed symbols=%s event_count=%s policy_version=%s",
                ",".join(requested),
                event_count,
                config.CORPORATE_EVENT_POLICY_VERSION,
            )
        except Exception as error:
            m.logger.warning(
                "corporate event lifecycle refresh unavailable error_type=%s",
                type(error).__name__,
            )
        return result

    m.refresh_derived_cache = refresh_derived_cache


__all__ = [
    "ACTIVE_LIFECYCLES",
    "CALENDAR_SOURCE",
    "CALENDAR_SOURCE_REFERENCE",
    "CorporateEventService",
    "OFFICIAL_SOURCE_RANK",
    "SECONDARY_SOURCE_RANK",
    "TERMINAL_LIFECYCLES",
    "install",
    "pre_event_policy_blockers",
    "sessions_until_event",
]
