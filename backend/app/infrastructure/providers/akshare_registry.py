"""AKShare interface discovery and guarded read-only execution.

Registry metadata discovery is separate from execution.  AI may search metadata,
but an interface can execute only when code explicitly adds it to the allowlist.
No arbitrary Python/eval path exists.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import date, datetime
import math
import re
from typing import Any, Mapping


_INTERFACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _normalize(value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        raise ValueError("provider payload nesting too deep")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _normalize(item, depth=depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item, depth=depth + 1) for item in value]
    # pandas DataFrame / Series support without making pandas an architecture
    # dependency of the domain/application layers.
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            converted = to_dict(orient="records")
        except TypeError:
            converted = to_dict()
        return _normalize(converted, depth=depth + 1)
    # numpy scalar-like values expose item().
    item = getattr(value, "item", None)
    if callable(item):
        converted = item()
        if converted is value:
            raise TypeError(f"unsupported provider value: {type(value).__name__}")
        return _normalize(converted, depth=depth + 1)
    raise TypeError(f"unsupported provider value: {type(value).__name__}")


def _validate_json_args(value: Any, *, depth: int = 0) -> Any:
    if depth > 6:
        raise ValueError("tool arguments nesting too deep")
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, list):
        if len(value) > 200:
            raise ValueError("tool argument list too large")
        return [_validate_json_args(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        if len(value) > 100:
            raise ValueError("too many tool arguments")
        return {str(key): _validate_json_args(item, depth=depth + 1) for key, item in value.items()}
    raise TypeError(f"tool argument must be JSON compatible: {type(value).__name__}")


class AkshareRegistryService:
    """Offline-ish interface metadata discovery wrapper.

    AKShare currently exposes ``search``, ``interface_info`` and
    ``list_categories`` from its local interface registry.  This service never
    interprets returned names as executable authority.
    """

    def __init__(self, ak_module=None) -> None:
        self._ak_module = ak_module

    def _ak(self):
        if self._ak_module is None:
            import akshare as ak
            self._ak_module = ak
        return self._ak_module

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        text = str(query or "").strip()
        if not text:
            raise ValueError("registry query must not be blank")
        result = _normalize(self._ak().search(text))
        if isinstance(result, dict):
            rows = [result]
        elif isinstance(result, list):
            rows = [row if isinstance(row, dict) else {"value": row} for row in result]
        else:
            rows = [{"value": result}]
        return rows[: max(1, min(int(limit), 100))]

    def interface_info(self, interface_name: str) -> Any:
        name = self._validate_name(interface_name)
        return _normalize(self._ak().interface_info(name))

    def list_categories(self) -> Any:
        return _normalize(self._ak().list_categories())

    @staticmethod
    def _validate_name(interface_name: str) -> str:
        name = str(interface_name or "").strip()
        if not _INTERFACE_RE.fullmatch(name) or name.startswith("_"):
            raise ValueError("invalid AKShare interface name")
        return name


class AkshareExecutionPolicy:
    """Explicit allowlist; discovery never mutates this set."""

    def __init__(self, allowed_interfaces=()) -> None:
        self._allowed = frozenset(AkshareRegistryService._validate_name(name) for name in allowed_interfaces)

    def is_allowed(self, interface_name: str) -> bool:
        try:
            name = AkshareRegistryService._validate_name(interface_name)
        except ValueError:
            return False
        return name in self._allowed

    def require_allowed(self, interface_name: str) -> str:
        name = AkshareRegistryService._validate_name(interface_name)
        if name not in self._allowed:
            raise PermissionError(f"AKShare interface not allowlisted: {name}")
        return name

    @property
    def allowed_interfaces(self) -> tuple[str, ...]:
        return tuple(sorted(self._allowed))


class AkshareResearchExecutor:
    """Execute one explicitly allowlisted read-only AKShare function."""

    def __init__(
        self,
        *,
        policy: AkshareExecutionPolicy,
        ak_module=None,
        timeout_seconds: float = 15.0,
        max_rows: int = 500,
    ) -> None:
        self.policy = policy
        self._ak_module = ak_module
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self.max_rows = max(1, min(int(max_rows), 5_000))

    def _ak(self):
        if self._ak_module is None:
            import akshare as ak
            self._ak_module = ak
        return self._ak_module

    def execute(self, interface_name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        name = self.policy.require_allowed(interface_name)
        args = _validate_json_args(dict(arguments or {}))
        function = getattr(self._ak(), name, None)
        if not callable(function):
            raise AttributeError(f"AKShare interface unavailable: {name}")

        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="akshare-research")
        future = pool.submit(function, **args)
        try:
            raw = future.result(timeout=self.timeout_seconds)
        except FutureTimeoutError as error:
            future.cancel()
            raise TimeoutError(f"AKShare interface timeout: {name}") from error
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        normalized = _normalize(raw)
        truncated = False
        if isinstance(normalized, list) and len(normalized) > self.max_rows:
            normalized = normalized[: self.max_rows]
            truncated = True
        return {
            "interface_name": name,
            "arguments": args,
            "rows": normalized,
            "truncated": truncated,
            "max_rows": self.max_rows,
            "usage_scope": "RESEARCH_ONLY",
        }
