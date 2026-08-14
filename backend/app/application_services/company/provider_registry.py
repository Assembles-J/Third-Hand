"""Explicit provider registry for Company Intelligence datasets.

Adapters are injected by bootstrap.  A missing adapter is an explicit
"local-only / unavailable" state, never a reason for the service to import a
remote SDK directly.
"""
from __future__ import annotations


class CompanyDataProviderRegistry:
    def __init__(self) -> None:
        self._fetchers: dict[str, object] = {}

    def register(self, data_type: str, fetcher) -> None:
        key = str(data_type or "").strip().lower()
        if not key:
            raise ValueError("data_type must not be blank")
        if not callable(fetcher):
            raise ValueError("fetcher must be callable")
        self._fetchers[key] = fetcher

    def get(self, data_type: str):
        return self._fetchers.get(str(data_type or "").strip().lower())

    def registered_data_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._fetchers))
