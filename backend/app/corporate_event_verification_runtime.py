"""Reconcile official CorporateEvent lifecycle with normalized financial reports.

A published HKEX results announcement is first stored as RELEASED_UNVERIFIED.
Once Company Intelligence has persisted a normalized financial dataset matching
that official report period, the event becomes VERIFIED with explicit snapshot
provenance.  Verified lifecycle is durable across later calendar refreshes.

This module never changes trade direction.  It only reconciles fact lifecycle
at the acquisition/research boundary; DecisionContext/Evidence/AI/Arbiter stay
free of hidden remote I/O and persistence writes.
"""
from __future__ import annotations

from datetime import datetime
from functools import wraps
from typing import Mapping

from app.time_utils import beijing_now


CORPORATE_EVENT_VERIFICATION_VERSION = "corporate-event-verification-v1-financial-snapshot"
_FINANCIAL_KEYS = ("financial_summary", "profit_cashflow_drivers", "margin_structure")


def _report_type(value: object) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if any(token in text for token in ("中报", "中期", "interim", "half")):
        return "interim"
    if any(token in text for token in ("一季", "first quarter", "q1")):
        return "q1"
    if any(token in text for token in ("三季", "third quarter", "q3")):
        return "q3"
    if any(token in text for token in ("年报", "年度", "annual", "final")):
        return "annual"
    return None


def _year(value: object) -> int | None:
    text = str(value or "").strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _rows_for_dataset(key: str, payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, Mapping):
        return []
    candidate_keys = {
        "financial_summary": ("report_period_indicators", "annual_indicators", "indicators"),
        "profit_cashflow_drivers": ("report_period_driver_history", "annual_driver_history", "indicator_history"),
        "margin_structure": ("company_margin_history", "segment_margins"),
    }.get(key, ())
    for candidate in candidate_keys:
        value = payload.get(candidate)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _row_period(row: Mapping[str, object]) -> tuple[int | None, str | None, str | None]:
    period = (
        row.get("report_date")
        or row.get("REPORT_DATE")
        or row.get("START_DATE")
        or row.get("日期")
    )
    period_text = str(period or "").strip()[:10] or None
    report_type = _report_type(row.get("report_type") or row.get("DATE_TYPE") or row.get("REPORT_TYPE"))
    if report_type is None and period_text:
        suffix = period_text[5:10]
        report_type = {
            "03-31": "q1",
            "06-30": "interim",
            "09-30": "q3",
            "12-31": "annual",
        }.get(suffix)
    return _year(period_text), report_type, period_text


def _matching_financial_snapshot(company_context: Mapping[str, object], event: Mapping[str, object]) -> dict[str, object] | None:
    event_type = _report_type(event.get("period"))
    event_year = _year(event.get("period")) or _year(event.get("scheduled_at"))
    if event_type is None:
        return None

    datasets = company_context.get("datasets")
    datasets = datasets if isinstance(datasets, Mapping) else {}
    refs_raw = company_context.get("dataset_refs") or ()
    refs: dict[str, Mapping[str, object]] = {}
    for ref in refs_raw:
        if isinstance(ref, Mapping) and ref.get("dataset_key"):
            refs[str(ref["dataset_key"])] = ref

    for key in _FINANCIAL_KEYS:
        payload = datasets.get(key)
        for row in _rows_for_dataset(key, payload):
            row_year, row_type, period_end = _row_period(row)
            if row_type != event_type:
                continue
            if event_year is not None and row_year is not None and row_year != event_year:
                continue
            ref = refs.get(key, {})
            return {
                "dataset_key": key,
                "snapshot_id": ref.get("snapshot_id"),
                "payload_hash": ref.get("payload_hash"),
                "provider": ref.get("provider"),
                "as_of": ref.get("as_of") or period_end,
                "available_at": ref.get("available_at"),
                "report_period": period_end,
                "report_type": row_type,
            }
    return None


def _all_event_rows(bundle: Mapping[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for key in ("events", "event_history"):
        for item in bundle.get(key, ()) or ():
            if isinstance(item, Mapping):
                rows.append(dict(item))
    return rows


def reconcile_company_context(store, symbol: str, company_context: Mapping[str, object], *, now: datetime | None = None) -> int:
    """Mark matching official earnings obligations VERIFIED.

    The event remains in ``events`` rather than being hidden in history so the
    deterministic financial-currentness layer keeps the expected-report anchor.
    Because the scheduled date is already past, the existing pre-event gate
    cannot block new risk from this verified historical event.
    """
    normalized = str(symbol or "").strip().upper()
    bundle = store.cached_market_intelligence(f"corporate_events:{normalized}") or {}
    if not bundle:
        return 0
    verified_at = (now or beijing_now()).isoformat()
    events = [dict(item) for item in bundle.get("events", ()) if isinstance(item, Mapping)]
    history = [dict(item) for item in bundle.get("event_history", ()) if isinstance(item, Mapping)]
    changed = 0

    # Official active events own the expected-report anchor.  If a prior refresh
    # already moved RELEASED_UNVERIFIED into history, consider it as well.
    candidates = [*events, *history]
    for event in candidates:
        if str(event.get("event_type") or "") != "earnings_report":
            continue
        if str(event.get("verification_level") or "") != "official":
            continue
        if str(event.get("lifecycle_status") or "") == "VERIFIED":
            continue
        match = _matching_financial_snapshot(company_context, event)
        if match is None:
            continue
        event_id = str(event.get("event_id") or "")
        verified = {
            **event,
            "lifecycle_status": "VERIFIED",
            "verified_at": verified_at,
            "verification_reason": "matching_normalized_financial_report",
            "verification_policy_version": CORPORATE_EVENT_VERIFICATION_VERSION,
            "verification_dataset_key": match.get("dataset_key"),
            "verification_snapshot_id": match.get("snapshot_id"),
            "verification_payload_hash": match.get("payload_hash"),
            "verification_provider": match.get("provider"),
            "verification_report_period": match.get("report_period"),
            "verification_report_type": match.get("report_type"),
        }
        events = [item for item in events if str(item.get("event_id") or "") != event_id]
        history = [item for item in history if str(item.get("event_id") or "") != event_id]
        events.append(verified)
        changed += 1

    if not changed:
        return 0
    events.sort(key=lambda item: (str(item.get("scheduled_at") or ""), str(item.get("event_id") or "")))
    history.sort(key=lambda item: (str(item.get("scheduled_at") or ""), str(item.get("event_id") or "")))
    updated = dict(bundle)
    updated["events"] = events
    updated["event_history"] = history
    updated["verification_policy_version"] = CORPORATE_EVENT_VERIFICATION_VERSION
    updated["verified_at"] = verified_at
    store.save_market_intelligence(f"corporate_events:{normalized}", updated)
    return changed


def _restore_verified(previous: Mapping[str, object], refreshed: Mapping[str, object]) -> dict[str, object]:
    """Prevent a later provider refresh from regressing VERIFIED to pending."""
    verified = {
        str(item.get("event_id") or ""): dict(item)
        for item in _all_event_rows(previous)
        if str(item.get("lifecycle_status") or "") == "VERIFIED" and item.get("event_id")
    }
    if not verified:
        return dict(refreshed)
    events = [dict(item) for item in refreshed.get("events", ()) if isinstance(item, Mapping)]
    history = [dict(item) for item in refreshed.get("event_history", ()) if isinstance(item, Mapping)]
    for event_id, terminal in verified.items():
        events = [item for item in events if str(item.get("event_id") or "") != event_id]
        history = [item for item in history if str(item.get("event_id") or "") != event_id]
        events.append(terminal)
    events.sort(key=lambda item: (str(item.get("scheduled_at") or ""), str(item.get("event_id") or "")))
    history.sort(key=lambda item: (str(item.get("scheduled_at") or ""), str(item.get("event_id") or "")))
    result = dict(refreshed)
    result["events"] = events
    result["event_history"] = history
    result["verification_policy_version"] = CORPORATE_EVENT_VERIFICATION_VERSION
    return result


def install(m) -> None:
    """Make VERIFIED lifecycle durable around the existing refresh service."""
    if getattr(m, "_corporate_event_verification_runtime_installed", False):
        return
    m._corporate_event_verification_runtime_installed = True
    service = getattr(m, "corporate_event_service", None)
    store = getattr(m, "store", None)
    if service is None or store is None:
        return
    original_refresh = service.refresh

    @wraps(original_refresh)
    def refresh(store_arg, symbols, *, now):
        requested = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
        previous = {
            symbol: store_arg.cached_market_intelligence(f"corporate_events:{symbol}") or {}
            for symbol in requested
        }
        result = original_refresh(store_arg, symbols, now=now)
        for symbol in requested:
            bundle = result.get(symbol)
            if not isinstance(bundle, Mapping):
                continue
            restored = _restore_verified(previous.get(symbol, {}), bundle)
            if restored != bundle:
                store_arg.save_market_intelligence(f"corporate_events:{symbol}", restored)
                result[symbol] = restored
        return result

    service.refresh = refresh


__all__ = [
    "CORPORATE_EVENT_VERIFICATION_VERSION",
    "install",
    "reconcile_company_context",
]
