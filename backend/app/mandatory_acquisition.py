"""Governed pre-decision acquisition for formal Decision entrypoints.

This module closes the gap between *knowing* that research is missing and
actually attempting a bounded fetch before a new formal Decision freezes its
inputs. Remote I/O happens here, then DecisionContext/Evidence/AI/Arbiter consume
persisted state only.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
import logging
import os
import time
from typing import Callable, Iterable
from uuid import uuid4

from app import decision_config as config
from app.decision_context import _canonical_hash
from app.market_adapter import market_for_symbol


logger = logging.getLogger(__name__)

ACQUISITION_LATEST_KEY_PREFIX = "mandatory_acquisition_latest:"
ACQUISITION_MANIFEST_KEY_PREFIX = "mandatory_acquisition_manifest:"
FORMAL_DECISION_TRIGGER = "formal-decision-preflight"

_BOUND_MANIFESTS: ContextVar[dict[str, dict[str, object]]] = ContextVar(
    "thirdhand_mandatory_acquisition_manifests",
    default={},
)


def _budget_seconds() -> float:
    try:
        return max(1.0, min(float(os.getenv("MANDATORY_ACQUISITION_BUDGET_SECONDS", "30")), 120.0))
    except ValueError:
        return 30.0


def requirement_action(local_status: str | None, provider_registered: bool) -> str:
    """Translate a local coverage state into a governed acquisition action."""
    state = str(local_status or "LOCAL_MISS").strip().upper()
    if state == "LOCAL_FRESH_HIT":
        return "REUSE"
    if state == "LOCAL_STALE_HIT":
        return "REFRESH" if provider_registered else "UNAVAILABLE"
    if state == "LOCAL_MISS":
        return "FETCH" if provider_registered else "UNAVAILABLE"
    return "FETCH" if provider_registered else "UNAVAILABLE"


def _manifest_hash(payload: dict[str, object]) -> str:
    material = {key: value for key, value in payload.items() if key != "manifest_hash"}
    encoded = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _status_map(context) -> dict[str, str]:
    if context is None:
        return {}
    return {
        str(item.source_key): str(item.status)
        for item in tuple(getattr(context.data_quality, "source_freshness", ()) or ())
    }


def _market_requirement_action(status: str | None, provider_registered: bool) -> str:
    normalized = str(status or "unknown").strip().lower()
    if normalized == "fresh":
        return "REUSE"
    if normalized == "stale":
        return "REFRESH" if provider_registered else "UNAVAILABLE"
    return "FETCH" if provider_registered else "UNAVAILABLE"


def _iso_date(value: object) -> str | None:
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else None


@dataclass(frozen=True)
class AcquisitionResult:
    symbol: str
    manifest: dict[str, object]


class ResearchAcquisitionOrchestrator:
    """Run bounded, auditable acquisition before a formal Decision context is built."""

    def __init__(
        self,
        *,
        store,
        context_builder,
        company_service,
        corporate_event_service,
        fetch_quotes: Callable[..., object],
        refresh_derived: Callable[..., object],
        now: Callable[[], object],
        log=None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.store = store
        self.context_builder = context_builder
        self.company_service = company_service
        self.corporate_event_service = corporate_event_service
        self.fetch_quotes = fetch_quotes
        self.refresh_derived = refresh_derived
        self.now = now
        self.log = log or logger
        self.monotonic = monotonic

    def acquire_many(
        self,
        symbols: Iterable[str],
        *,
        research_priority: str | None,
        trigger: str,
        run_id: str | None = None,
    ) -> dict[str, dict[str, object]]:
        requested = list(dict.fromkeys(str(item).strip().upper() for item in symbols if str(item).strip()))
        deadline = self.monotonic() + _budget_seconds()
        manifests: dict[str, dict[str, object]] = {}
        for symbol in requested:
            if self.monotonic() >= deadline:
                manifests[symbol] = self._failed_manifest(
                    symbol,
                    research_priority=research_priority,
                    trigger=trigger,
                    error_type="AcquisitionBudgetExceeded",
                )
                continue
            try:
                manifests[symbol] = self.acquire(
                    symbol,
                    research_priority=research_priority,
                    trigger=trigger,
                    run_id=run_id,
                    deadline=deadline,
                ).manifest
            except Exception as error:
                self.log.exception(
                    "mandatory acquisition failed closed symbol=%s error_type=%s",
                    symbol,
                    type(error).__name__,
                )
                manifests[symbol] = self._failed_manifest(
                    symbol,
                    research_priority=research_priority,
                    trigger=trigger,
                    error_type=type(error).__name__,
                )
        return manifests

    def acquire(
        self,
        symbol: str,
        *,
        research_priority: str | None,
        trigger: str,
        run_id: str | None = None,
        deadline: float | None = None,
    ) -> AcquisitionResult:
        symbol = str(symbol).strip().upper()
        requested_at = self.now()
        manifest_id = str(uuid4())
        errors: list[dict[str, str]] = []

        try:
            pre_context = self.context_builder.build(symbol)
        except Exception as error:
            pre_context = None
            errors.append({"stage": "pre_context", "error_type": type(error).__name__})
        pre_status = _status_map(pre_context)
        market = (
            str(getattr(getattr(pre_context, "instrument", None), "market", "") or "").strip().upper()
            or market_for_symbol(symbol)
        )

        market_keys = ("quote", "daily_bars", "risk", "market_regime")
        provider_support = {
            "quote": True,
            "daily_bars": True,
            "risk": True,
            # HK/US regime providers are intentionally not synthesized from CN.
            "market_regime": market == "CN",
        }
        market_actions = {
            key: _market_requirement_action(pre_status.get(key), provider_support[key])
            for key in market_keys
        }
        market_call_needed = any(action in {"FETCH", "REFRESH"} for action in market_actions.values())
        market_call_attempted = False
        market_error: Exception | None = None
        if market_call_needed and not self._deadline_reached(deadline):
            market_call_attempted = True
            try:
                self.fetch_quotes(
                    [symbol],
                    force_refresh=True,
                    trigger=FORMAL_DECISION_TRIGGER,
                    run_id=run_id,
                )
            except Exception as error:
                market_error = error
                errors.append({"stage": "quote", "error_type": type(error).__name__})
            try:
                self.refresh_derived(
                    [symbol],
                    FORMAL_DECISION_TRIGGER,
                    force_history=True,
                    run_id=run_id,
                )
            except Exception as error:
                market_error = market_error or error
                errors.append({"stage": "derived", "error_type": type(error).__name__})
        elif market_call_needed:
            errors.append({"stage": "market", "error_type": "AcquisitionBudgetExceeded"})

        event_pre = self.store.cached_market_intelligence(f"corporate_events:{symbol}") or {}
        today = _iso_date(self.now())
        event_pre_fresh = (
            event_pre.get("status") == "ready"
            and bool(event_pre.get("window_dates"))
            and _iso_date(event_pre.get("retrieved_at")) == today
        )
        event_action = "REUSE" if event_pre_fresh else "REFRESH" if event_pre else "FETCH"
        event_attempted = False
        event_bundle: dict[str, object] = dict(event_pre) if event_pre_fresh else {}
        if event_action != "REUSE" and not self._deadline_reached(deadline):
            event_attempted = True
            try:
                event_bundle = (
                    self.corporate_event_service.refresh(self.store, [symbol], now=self.now()).get(symbol) or {}
                )
            except Exception as error:
                errors.append({"stage": "corporate_event", "error_type": type(error).__name__})
        elif event_action != "REUSE":
            errors.append({"stage": "corporate_event", "error_type": "AcquisitionBudgetExceeded"})
        event_dates = list(event_bundle.get("window_dates") or [])
        event_unavailable = list(event_bundle.get("unavailable_dates") or [])
        event_post_state = (
            "READY" if event_bundle.get("status") == "ready" and event_dates and not event_unavailable
            else "PARTIAL" if event_dates and event_bundle.get("status") in {"ready", "partial", "stale_fallback"}
            else "UNAVAILABLE"
        )

        company_before: dict[str, object] = {}
        company_after: dict[str, object] = {}
        company_context: dict[str, object] | None = None
        try:
            company_before = self.company_service.requirements(symbol, research_priority=research_priority)
        except Exception as error:
            errors.append({"stage": "company_requirements", "error_type": type(error).__name__})
        required = [item for item in list(company_before.get("required_datasets") or []) if isinstance(item, dict)]
        company_actions = {
            str(item.get("dataset_key")): requirement_action(
                str(item.get("local_status") or "LOCAL_MISS"),
                bool(item.get("provider_registered")),
            )
            for item in required
        }
        company_fetch_needed = any(action in {"FETCH", "REFRESH"} for action in company_actions.values())
        company_build_attempted = False
        resolved_priority = str(company_before.get("research_priority") or research_priority or "L1")
        if company_fetch_needed and not self._deadline_reached(deadline):
            company_build_attempted = True
            try:
                company_context = self.company_service.build_context(
                    symbol,
                    research_priority=resolved_priority,
                    allow_remote=True,
                )
            except Exception as error:
                errors.append({"stage": "company_build", "error_type": type(error).__name__})
        elif company_fetch_needed:
            errors.append({"stage": "company_build", "error_type": "AcquisitionBudgetExceeded"})
        try:
            company_after = self.company_service.requirements(symbol, research_priority=resolved_priority)
        except Exception as error:
            errors.append({"stage": "company_verify", "error_type": type(error).__name__})
        if company_context is None and hasattr(self.company_service, "latest_context"):
            try:
                company_context = self.company_service.latest_context(symbol)
            except Exception:
                company_context = None

        try:
            post_context = self.context_builder.build(symbol)
        except Exception as error:
            post_context = None
            errors.append({"stage": "post_context", "error_type": type(error).__name__})
        post_status = _status_map(post_context)

        items: list[dict[str, object]] = []
        items.append({
            "requirement_key": "corporate_events",
            "domain": "event",
            "mandatory_for": ["OPEN", "ADD", "research"],
            "pre_state": "LOCAL_FRESH_HIT" if event_pre_fresh else str(event_pre.get("status") or "LOCAL_MISS"),
            "provider_registered": True,
            "action": event_action,
            "attempted": event_attempted,
            "provider": str(event_bundle.get("source") or event_pre.get("source") or "corporate_event_calendar"),
            "attempt_status": (
                "reused" if event_action == "REUSE"
                else "ok" if event_post_state == "READY"
                else "degraded"
            ),
            "error_code": None if event_post_state == "READY" else "event_coverage_unavailable",
            "post_state": event_post_state,
            "as_of": event_dates[-1] if event_dates else None,
            "available_at": event_bundle.get("retrieved_at"),
            "freshness_status": "fresh" if event_post_state == "READY" else "unknown",
            "provenance_hash": _manifest_hash(event_bundle) if event_bundle else None,
        })

        after_by_key = {
            str(item.get("dataset_key")): item
            for item in list(company_after.get("required_datasets") or [])
            if isinstance(item, dict)
        }
        refs_by_key = {
            str(item.get("dataset_key")): item
            for item in list((company_context or {}).get("dataset_refs") or [])
            if isinstance(item, dict)
        }
        for item in required:
            key = str(item.get("dataset_key") or "")
            provider_registered = bool(item.get("provider_registered"))
            action = company_actions.get(key, requirement_action(str(item.get("local_status")), provider_registered))
            after = after_by_key.get(key, {})
            ref = refs_by_key.get(key, {})
            post_state = str(after.get("local_status") or "LOCAL_MISS")
            success = post_state == "LOCAL_FRESH_HIT"
            items.append({
                "requirement_key": key,
                "domain": "company_research",
                # Company Intelligence remains RESEARCH_ONLY. Missing coverage
                # degrades research but does not create a second ActionPolicy gate.
                "mandatory_for": ["research"],
                "pre_state": str(item.get("local_status") or "LOCAL_MISS"),
                "provider_registered": provider_registered,
                "action": action,
                "attempted": company_build_attempted and action in {"FETCH", "REFRESH"},
                "provider": ref.get("provider"),
                "attempt_status": (
                    "reused" if action == "REUSE"
                    else "unavailable" if action == "UNAVAILABLE"
                    else "ok" if success
                    else "degraded"
                ),
                "error_code": (
                    None if success or action == "REUSE"
                    else "provider_unregistered" if action == "UNAVAILABLE"
                    else "post_fetch_coverage_missing"
                ),
                "post_state": post_state,
                "as_of": ref.get("as_of"),
                "available_at": ref.get("available_at"),
                "freshness_status": after.get("freshness_status") or ref.get("freshness_status") or "missing",
                "provenance_hash": ref.get("payload_hash"),
            })

        for key in market_keys:
            action = market_actions[key]
            after = post_status.get(key, "unknown")
            success = after == "fresh"
            items.append({
                "requirement_key": key,
                "domain": "market",
                "mandatory_for": ["OPEN", "ADD", "research"],
                "pre_state": pre_status.get(key, "unknown"),
                "provider_registered": provider_support[key],
                "action": action,
                "attempted": market_call_attempted and action in {"FETCH", "REFRESH"},
                "provider": None,
                "attempt_status": (
                    "reused" if action == "REUSE"
                    else "unavailable" if action == "UNAVAILABLE"
                    else "ok" if success
                    else "degraded"
                ),
                "error_code": (
                    None if success or action == "REUSE"
                    else "provider_unregistered" if action == "UNAVAILABLE"
                    else type(market_error).__name__ if market_error is not None
                    else "post_fetch_not_fresh"
                ),
                "post_state": after,
                "as_of": self._context_as_of(post_context, key),
                "available_at": None,
                "freshness_status": after,
                "provenance_hash": None,
            })

        instrument_before = getattr(pre_context, "instrument", None) if pre_context is not None else None
        instrument_after = getattr(post_context, "instrument", None) if post_context is not None else None
        items.append({
            "requirement_key": "instrument_metadata",
            "domain": "market_identity",
            "mandatory_for": ["OPEN", "ADD", "sizing", "execution"],
            "pre_state": "READY" if instrument_before is not None else "LOCAL_MISS",
            "provider_registered": False,
            "action": "REUSE" if instrument_before is not None else "UNAVAILABLE",
            "attempted": False,
            "provider": getattr(instrument_after, "source", None),
            "attempt_status": "reused" if instrument_after is not None else "unavailable",
            "error_code": None if instrument_after is not None else "instrument_provider_unregistered",
            "post_state": "READY" if instrument_after is not None else "UNAVAILABLE",
            "as_of": getattr(instrument_after, "as_of", None),
            "available_at": None,
            "freshness_status": "fresh" if instrument_after is not None else "missing",
            "provenance_hash": None,
        })

        completed_at = self.now()
        manifest: dict[str, object] = {
            "manifest_id": manifest_id,
            "symbol": symbol,
            "market": market,
            "trigger": trigger,
            "research_priority": str(company_after.get("research_priority") or resolved_priority),
            "requested_at": str(requested_at),
            "completed_at": str(completed_at),
            "requirement_policy_version": config.MANDATORY_ACQUISITION_POLICY_VERSION,
            "budget_policy_version": config.MANDATORY_ACQUISITION_BUDGET_POLICY_VERSION,
            "items": items,
            "errors": errors,
            "status": "ready" if all(self._item_satisfied(item) for item in items) else "degraded",
        }
        manifest["manifest_hash"] = _manifest_hash(manifest)
        self._persist_manifest(manifest)
        self.log.info(
            "mandatory acquisition completed symbol=%s manifest_id=%s status=%s errors=%s",
            symbol,
            manifest_id,
            manifest["status"],
            len(errors),
        )
        return AcquisitionResult(symbol=symbol, manifest=manifest)

    def _failed_manifest(
        self,
        symbol: str,
        *,
        research_priority: str | None,
        trigger: str,
        error_type: str,
    ) -> dict[str, object]:
        now = self.now()
        manifest: dict[str, object] = {
            "manifest_id": str(uuid4()),
            "symbol": symbol,
            "market": market_for_symbol(symbol),
            "trigger": trigger,
            "research_priority": research_priority or "L1",
            "requested_at": str(now),
            "completed_at": str(now),
            "requirement_policy_version": config.MANDATORY_ACQUISITION_POLICY_VERSION,
            "budget_policy_version": config.MANDATORY_ACQUISITION_BUDGET_POLICY_VERSION,
            "items": [],
            "errors": [{"stage": "preflight", "error_type": error_type}],
            "status": "degraded",
        }
        manifest["manifest_hash"] = _manifest_hash(manifest)
        self._persist_manifest(manifest)
        return manifest

    def _persist_manifest(self, manifest: dict[str, object]) -> None:
        try:
            manifest_id = str(manifest["manifest_id"])
            symbol = str(manifest["symbol"])
            self.store.save_market_intelligence(f"{ACQUISITION_MANIFEST_KEY_PREFIX}{manifest_id}", manifest)
            self.store.save_market_intelligence(f"{ACQUISITION_LATEST_KEY_PREFIX}{symbol}", manifest)
        except Exception as error:
            # The in-request manifest remains bound to the DecisionContext even
            # if audit persistence itself is temporarily unavailable.
            self.log.error(
                "mandatory acquisition manifest persistence failed symbol=%s error_type=%s",
                manifest.get("symbol"),
                type(error).__name__,
            )

    def _deadline_reached(self, deadline: float | None) -> bool:
        return deadline is not None and self.monotonic() >= deadline

    @staticmethod
    def _context_as_of(context, key: str):
        if context is None:
            return None
        if key == "quote":
            return getattr(getattr(context, "quote", None), "as_of", None)
        if key == "daily_bars":
            return getattr(getattr(context, "daily_bars", None), "last_trading_date", None)
        if key == "risk":
            return getattr(getattr(context, "risk", None), "as_of", None)
        if key == "market_regime":
            return getattr(getattr(context, "market_regime", None), "as_of", None)
        return None

    @staticmethod
    def _item_satisfied(item: dict[str, object]) -> bool:
        return str(item.get("post_state") or "").upper() in {"READY", "LOCAL_FRESH_HIT", "FRESH"}


class AcquisitionAwareContextBuilder:
    """Attach only the exact manifest bound by the surrounding preflight.

    The wrapped builder remains local-only. ContextVar binding keeps concurrent
    API/paper decisions from accidentally linking a different symbol's latest
    manifest.
    """

    def __init__(self, delegate) -> None:
        self.delegate = delegate

    def build(self, symbol: str, **kwargs):
        context = self.delegate.build(symbol, **kwargs)
        manifest = _BOUND_MANIFESTS.get().get(str(symbol).strip().upper())
        if not manifest:
            return context

        versions = dict(context.source_versions)
        versions.update({
            "mandatory_acquisition_policy": config.MANDATORY_ACQUISITION_POLICY_VERSION,
            "acquisition_manifest_id": str(manifest.get("manifest_id") or ""),
            "acquisition_manifest_hash": str(manifest.get("manifest_hash") or ""),
        })

        # Only unsatisfied requirements that explicitly govern OPEN/ADD become
        # hard action blockers. RESEARCH_ONLY Company Intelligence gaps remain
        # visible to Atomic Evidence/ResearchAssessment without becoming a
        # second ActionPolicy authority.
        blocking = []
        for item in list(manifest.get("items") or []):
            if not isinstance(item, dict):
                continue
            if ResearchAcquisitionOrchestrator._item_satisfied(item):
                continue
            mandatory_for = {str(value).upper() for value in list(item.get("mandatory_for") or [])}
            if {"OPEN", "ADD"} & mandatory_for:
                blocking.append(str(item.get("requirement_key") or "unknown"))
        if manifest.get("status") == "degraded" and not list(manifest.get("items") or []):
            blocking.append("preflight")

        quality = context.data_quality
        if blocking:
            gates = []
            unavailable = tuple(f"mandatory_acquisition.{key}" for key in dict.fromkeys(blocking))
            for gate in quality.action_gates:
                if gate.action in {"OPEN", "ADD"}:
                    gates.append(gate.model_copy(update={
                        "permission": "blocked",
                        "reasons": tuple(dict.fromkeys((*gate.reasons, "mandatory_acquisition.degraded"))),
                        "unavailable_fields": tuple(dict.fromkeys((*gate.unavailable_fields, *unavailable))),
                    }))
                else:
                    gates.append(gate)
            quality = quality.model_copy(update={
                "status": "degraded" if quality.status == "ready" else quality.status,
                "warnings": tuple(dict.fromkeys((*quality.warnings, "mandatory acquisition incomplete"))),
                "action_gates": tuple(gates),
            })

        hash_payload = context.model_dump(
            mode="json",
            exclude={"context_id", "generated_at", "input_hash", "timeframe_technicals"},
        )
        hash_payload["source_versions"] = versions
        hash_payload["data_quality"] = quality.model_dump(mode="json")
        return context.model_copy(update={
            "source_versions": versions,
            "data_quality": quality,
            "input_hash": _canonical_hash(hash_payload),
        })

    def __getattr__(self, name: str):
        return getattr(self.delegate, name)


@contextmanager
def bind_acquisition_manifests(manifests: dict[str, dict[str, object]]):
    normalized = {str(key).strip().upper(): value for key, value in manifests.items()}
    token = _BOUND_MANIFESTS.set(normalized)
    try:
        yield
    finally:
        _BOUND_MANIFESTS.reset(token)


def install(m) -> None:
    """Wire one acquisition service to formal API and paper Decision entrypoints."""
    if getattr(m, "_mandatory_acquisition_installed", False):
        return
    if not hasattr(m, "company_intelligence_service_v2"):
        raise RuntimeError("company intelligence service must be registered before mandatory acquisition")
    if not hasattr(m, "corporate_event_service"):
        raise RuntimeError("corporate event service must be installed before mandatory acquisition")

    m._mandatory_acquisition_installed = True
    original_builder = m.decision_context_builder
    service = ResearchAcquisitionOrchestrator(
        store=m.store,
        context_builder=original_builder,
        company_service=m.company_intelligence_service_v2,
        corporate_event_service=m.corporate_event_service,
        fetch_quotes=m.fetch_and_store_quotes,
        refresh_derived=m.refresh_derived_cache,
        now=m.beijing_now,
        log=m.logger,
    )
    m.mandatory_acquisition_service_v3 = service
    m.decision_context_builder = AcquisitionAwareContextBuilder(original_builder)

    original_prepare_paper_decisions = m.prepare_paper_decisions

    def prepare_paper_decisions(symbols, run_id=None, names=None):
        manifests = service.acquire_many(
            symbols,
            research_priority=None,
            trigger="paper-formal-decision",
            run_id=run_id,
        )
        with bind_acquisition_manifests(manifests):
            return original_prepare_paper_decisions(symbols, run_id=run_id, names=names)

    m.prepare_paper_decisions = prepare_paper_decisions

    # The legacy route was already registered during module import. A narrow
    # middleware adds preflight to that one formal-write endpoint while leaving
    # read-only context/evidence routes local-only. Provider work runs off the
    # event loop; call_next is invoked exactly once so route errors are not
    # accidentally swallowed/replayed.
    from anyio import to_thread
    from starlette.middleware.base import BaseHTTPMiddleware

    class MandatoryAcquisitionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.method != "POST" or request.url.path != "/v1/decisions/generate":
                return await call_next(request)
            try:
                raw = await request.body()
                payload = json.loads(raw.decode("utf-8")) if raw else {}
            except (ValueError, UnicodeDecodeError):
                return await call_next(request)
            symbols = payload.get("symbols") if isinstance(payload, dict) else None
            if not isinstance(symbols, list):
                return await call_next(request)

            manifests = await to_thread.run_sync(
                lambda: service.acquire_many(
                    symbols,
                    research_priority="L3",
                    trigger="api-formal-decision",
                )
            )
            with bind_acquisition_manifests(manifests):
                return await call_next(request)

    m.app.add_middleware(MandatoryAcquisitionMiddleware)


__all__ = [
    "ACQUISITION_LATEST_KEY_PREFIX",
    "ACQUISITION_MANIFEST_KEY_PREFIX",
    "AcquisitionAwareContextBuilder",
    "AcquisitionResult",
    "ResearchAcquisitionOrchestrator",
    "bind_acquisition_manifests",
    "install",
    "requirement_action",
]
