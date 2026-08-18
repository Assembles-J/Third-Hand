"""Governed pre-decision acquisition for formal Decision entrypoints.

This module closes the gap between *knowing* that research is missing and
actually attempting a bounded fetch before a new formal Decision freezes its
inputs.  It deliberately sits outside ``DecisionContextBuilder`` and all
policy/AI layers: remote I/O happens here, then those layers consume persisted
state only.
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
    """Translate a local coverage state into the one governed acquisition action."""
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


def _market_requirement_action(status: str | None, provider_registered: bool = True) -> str:
    normalized = str(status or "unknown").strip().lower()
    if normalized == "fresh":
        return "REUSE"
    if normalized == "stale":
        return "REFRESH" if provider_registered else "UNAVAILABLE"
    return "FETCH" if provider_registered else "UNAVAILABLE"


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
        started = self.monotonic()
        deadline = started + _budget_seconds()
        manifests: dict[str, dict[str, object]] = {}
        for symbol in requested:
            if self.monotonic() >= deadline:
                manifests[symbol] = self._budget_exhausted_manifest(
                    symbol,
                    research_priority=research_priority,
                    trigger=trigger,
                )
                continue
            manifests[symbol] = self.acquire(
                symbol,
                research_priority=research_priority,
                trigger=trigger,
                run_id=run_id,
                deadline=deadline,
            ).manifest
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
        items: list[dict[str, object]] = []
        errors: list[dict[str, str]] = []

        try:
            pre_context = self.context_builder.build(symbol)
        except Exception as error:  # preflight diagnosis must never block fail-closed Decision creation
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
            "risk": True,  # deterministic derivative of daily history
            # Current formal regime provider is market-scoped; HK/US deliberately
            # remain unavailable rather than inheriting mainland benchmarks.
            "market_regime": market == "CN",
        }
        market_actions = {
            key: _market_requirement_action(pre_status.get(key), provider_support[key])
            for key in market_keys
        }
        market_attempted = any(value in {"FETCH", "REFRESH"} for value in market_actions.values())
        market_error: Exception | None = None
        if market_attempted and not self._deadline_reached(deadline):
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
        elif market_attempted:
            errors.append({"stage": "market", "error_type": "AcquisitionBudgetExceeded"})

        # Corporate events are mandatory research facts.  The service itself is
        # local-first and daily-cached, so invoking it here does not imply an
        # unconditional network call on every Decision.
        event_pre = self.store.cached_market_intelligence(f"corporate_events:{symbol}") or {}
        event_bundle: dict[str, object] = {}
        event_attempted = not self._deadline_reached(deadline)
        if event_attempted:
            try:
                event_bundle = (
                    self.corporate_event_service.refresh(self.store, [symbol], now=self.now()).get(symbol) or {}
                )
            except Exception as error:
                errors.append({"stage": "corporate_event", "error_type": type(error).__name__})
        else:
            errors.append({"stage": "corporate_event", "error_type": "AcquisitionBudgetExceeded"})
        event_dates = list(event_bundle.get("window_dates") or [])
        event_unavailable = list(event_bundle.get("unavailable_dates") or [])
        event_post_state = (
            "READY" if event_bundle.get("status") == "ready" and event_dates and not event_unavailable
            else "PARTIAL" if event_dates and event_bundle.get("status") in {"ready", "partial", "stale_fallback"}
            else "UNAVAILABLE"
        )
        items.append({
            "requirement_key": "corporate_events",
            "domain": "event",
            "mandatory_for": ["OPEN", "ADD", "research"],
            "pre_state": str(event_pre.get("status") or "LOCAL_MISS"),
            "provider_registered": True,
            "action": "FETCH" if not event_pre else "REFRESH",
            "attempted": event_attempted,
            "provider": str(event_bundle.get("source") or event_pre.get("source") or "corporate_event_calendar"),
            "attempt_status": "ok" if event_post_state == "READY" else "degraded",
            "error_code": None if event_post_state == "READY" else "event_coverage_unavailable",
            "post_state": event_post_state,
            "as_of": event_dates[-1] if event_dates else None,
            "available_at": event_bundle.get("retrieved_at"),
            "freshness_status": "fresh" if event_post_state == "READY" else "unknown",
            "provenance_hash": _manifest_hash(event_bundle) if event_bundle else None,
        })

        company_before: dict[str, object] = {}
        company_after: dict[str, object] = {}
        company_context: dict[str, object] | None = None
        try:
            company_before = self.company_service.requirements(symbol, research_priority=research_priority)
        except Exception as error:
            errors.append({"stage": "company_requirements", "error_type": type(error).__name__})
        required = list(company_before.get("required_datasets") or [])
        actions = {
            str(item.get("dataset_key")): requirement_action(
                str(item.get("local_status") or "LOCAL_MISS"),
                bool(item.get("provider_registered")),
            )
            for item in required
            if isinstance(item, dict)
        }
        company_fetch_needed = any(value in {"FETCH", "REFRESH"} for value in actions.values())
        if company_fetch_needed and not self._deadline_reached(deadline):
            try:
                company_context = self.company_service.build_context(
                    symbol,
                    research_priority=str(company_before.get("research_priority") or research_priority or "L1"),
                    allow_remote=True,
                )
            except Exception as error:
                errors.append({"stage": "company_build", "error_type": type(error).__name__})
        elif company_fetch_needed:
            errors.append({"stage": "company_build", "error_type": "AcquisitionBudgetExceeded"})
        try:
            company_after = self.company_service.requirements(
                symbol,
                research_priority=str(company_before.get("research_priority") or research_priority or "L1"),
            )
        except Exception as error:
            errors.append({"stage": "company_verify", "error_type": type(error).__name__})

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
            if not isinstance(item, dict):
                continue
            key = str(item.get("dataset_key") or "")
            provider_registered = bool(item.get("provider_registered"))
            action = actions.get(key, requirement_action(str(item.get("local_status")), provider_registered))
            after = after_by_key.get(key, {})
            ref = refs_by_key.get(key, {})
            post_status = str(after.get("local_status") or "LOCAL_MISS")
            attempted = action in {"FETCH", "REFRESH"} and company_fetch_needed
            success = post_status == "LOCAL_FRESH_HIT"
            items.append({
                "requirement_key": key,
                "domain": "company_research",
                "mandatory_for": ["research"],
                "pre_state": str(item.get("local_status") or "LOCAL_MISS"),
                "provider_registered": provider_registered,
                "action": action,
                "attempted": attempted,
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
                "post_state": post_status,
                "as_of": ref.get("as_of"),
                "available_at": ref.get("available_at"),
                "freshness_status": after.get("freshness_status") or ref.get("freshness_status") or "missing",
                "provenance_hash": ref.get("payload_hash"),
            })

        try:
            post_context = self.context_builder.build(symbol)
        except Exception as error:
            post_context = None
            errors.append({"stage": "post_context", "error_type": type(error).__name__})
        post_status = _status_map(post_context)
        for key in market_keys:
            action = market_actions[key]
            provider_registered = provider_support[key]
            before = pre_status.get(key, "unknown")
            after = post_status.get(key, "unknown")
            success = after == "fresh"
            items.append({
                "requirement_key": key,
                "domain": "market",
                "mandatory_for": ["OPEN", "ADD", "research"],
                "pre_state": before,
                "provider_registered": provider_registered,
                "action": action,
                "attempted": market_attempted and action in {"FETCH", "REFRESH"},
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

        instrument_present_before = getattr(pre_context, "instrument", None) is not None if pre_context is not None else False
        instrument_present_after = getattr(post_context, "instrument", None) is not None if post_context is not None else False
        items.append({
            "requirement_key": "instrument_metadata",
            "domain": "market_identity",
            "mandatory_for": ["OPEN", "ADD", "sizing", "execution"],
            "pre_state": "READY" if instrument_present_before else "LOCAL_MISS",
            "provider_registered": False,
            "action": "REUSE" if instrument_present_before else "UNAVAILABLE",
            "attempted": False,
            "provider": getattr(getattr(post_context, "instrument", None), "source", None) if post_context is not None else None,
            "attempt_status": "reused" if instrument_present_after else "unavailable",
            "error_code": None if instrument_present_after else "instrument_provider_unregistered",
            "post_state": "READY" if instrument_present_after else "UNAVAILABLE",
            "as_of": getattr(getattr(post_context, "instrument", None), "as_of", None) if post_context is not None else None,
            "available_at": None,
            "freshness_status": "fresh" if instrument_present_after else "missing",
            "provenance_hash": None,
        })

        completed_at = self.now()
        manifest: dict[str, object] = {
            "manifest_id": manifest_id,
            "symbol": symbol,
            "market": market,
            "trigger": trigger,
            "research_priority": str(company_after.get("research_priority") or company_before.get("research_priority") or research_priority or "L1"),
            "requested_at": str(requested_at),
            "completed_at": str(completed_at),
            "requirement_policy_version": config.MANDATORY_ACQUISITION_POLICY_VERSION,
            "budget_policy_version": config.MANDATORY_ACQUISITION_BUDGET_POLICY_VERSION,
            "items": items,
            "errors": errors,
            "status": "ready" if all(self._item_satisfied(item) for item in items if self._is_hard_mandatory(item)) else "degraded",
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

    def _budget_exhausted_manifest(self, symbol: str, *, research_priority: str | None, trigger: str) -> dict[str, object]:
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
            "errors": [{"stage": "preflight", "error_type": "AcquisitionBudgetExceeded"}],
            "status": "degraded",
        }
        manifest["manifest_hash"] = _manifest_hash(manifest)
        self._persist_manifest(manifest)
        return manifest

    def _persist_manifest(self, manifest: dict[str, object]) -> None:
        manifest_id = str(manifest["manifest_id"])
        symbol = str(manifest["symbol"])
        self.store.save_market_intelligence(f"{ACQUISITION_MANIFEST_KEY_PREFIX}{manifest_id}", manifest)
        self.store.save_market_intelligence(f"{ACQUISITION_LATEST_KEY_PREFIX}{symbol}", manifest)

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
    def _is_hard_mandatory(item: dict[str, object]) -> bool:
        return str(item.get("requirement_key")) in {"corporate_events", "quote", "daily_bars", "risk"}

    @staticmethod
    def _item_satisfied(item: dict[str, object]) -> bool:
        return str(item.get("post_state") or "").upper() in {"READY", "LOCAL_FRESH_HIT", "FRESH"}


class AcquisitionAwareContextBuilder:
    """Attach only the manifest identity bound by the surrounding preflight.

    The wrapped builder remains local-only.  A ContextVar binds the exact
    manifest across concurrent API/paper requests without reading a merely
    "latest" global record that could belong to another Decision.
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
        hash_payload = context.model_dump(
            mode="json",
            exclude={"context_id", "generated_at", "input_hash", "timeframe_technicals"},
        )
        hash_payload["source_versions"] = versions
        return context.model_copy(update={
            "source_versions": versions,
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

    # Paper/scheduler formal Decisions resolve this global function at runtime,
    # so replacing the module attribute creates one migration seam without
    # moving remote I/O into the immutable context builder.
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

    # The legacy route is already registered by the time bootstrap installers
    # run.  A narrow HTTP middleware is therefore the safest migration seam for
    # the existing /v1/decisions/generate endpoint.  It does not alter read-only
    # context/evidence endpoints and it leaves invalid request bodies to FastAPI.
    from starlette.middleware.base import BaseHTTPMiddleware

    class MandatoryAcquisitionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.method == "POST" and request.url.path == "/v1/decisions/generate":
                try:
                    raw = await request.body()
                    payload = json.loads(raw.decode("utf-8")) if raw else {}
                    symbols = payload.get("symbols") if isinstance(payload, dict) else None
                    if isinstance(symbols, list):
                        manifests = service.acquire_many(
                            symbols,
                            research_priority="L3",
                            trigger="api-formal-decision",
                        )
                        with bind_acquisition_manifests(manifests):
                            return await call_next(request)
                except (ValueError, UnicodeDecodeError):
                    pass
                except Exception as error:
                    m.logger.warning(
                        "mandatory acquisition middleware degraded error_type=%s",
                        type(error).__name__,
                    )
            return await call_next(request)

    m.app.add_middleware(MandatoryAcquisitionMiddleware)


__all__ = [
    "AcquisitionAwareContextBuilder",
    "AcquisitionResult",
    "ResearchAcquisitionOrchestrator",
    "bind_acquisition_manifests",
    "install",
    "requirement_action",
]
