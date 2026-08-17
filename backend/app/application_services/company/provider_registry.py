"""Explicit provider registry for Company Intelligence datasets."""
from __future__ import annotations


class CompanyDataProviderRegistry:
    def __init__(self) -> None:
        self._fetchers: dict[str, object] = {}
        self._supports: dict[str, object] = {}

    def register(self, data_type: str, fetcher, *, supports=None) -> None:
        key = str(data_type or "").strip().lower()
        if not key:
            raise ValueError("data_type must not be blank")
        if not callable(fetcher):
            raise ValueError("fetcher must be callable")
        if supports is not None and not callable(supports):
            raise ValueError("supports must be callable")
        self._fetchers[key] = fetcher
        if supports is not None:
            self._supports[key] = supports

    def get(self, data_type: str):
        return self._fetchers.get(str(data_type or "").strip().lower())

    def supports(self, data_type: str, symbol: str) -> bool:
        key = str(data_type or "").strip().lower()
        if key not in self._fetchers:
            return False
        checker = self._supports.get(key)
        if checker is None:
            return True
        return bool(checker(key, str(symbol or "").strip().upper()))

    def registered_data_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._fetchers))
