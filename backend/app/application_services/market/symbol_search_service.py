"""Cache-first symbol search with non-blocking remote enrichment."""
from __future__ import annotations

import time
from threading import Lock, Thread

from app.infrastructure.database.symbol_search_repository import normalize_search_text


class SymbolSearchService:
    """Resolve security names/codes without ever blocking HTTP on a live provider."""

    CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
    FAILURE_BACKOFF_SECONDS = 12

    def __init__(self, repository, market_data, logger=None) -> None:
        self.repository = repository
        self.market_data = market_data
        self.logger = logger
        self._lock = Lock()
        self._jobs: dict[str, dict[str, object]] = {}

    def search_many(self, names: list[str]) -> list[dict[str, object]]:
        requested = list(dict.fromkeys(str(name or "").strip() for name in names if str(name or "").strip()))
        return [self.search(name) for name in requested]

    def search(self, query: str) -> dict[str, object]:
        cleaned = str(query or "").strip()
        if not cleaned:
            return {"query": cleaned, "matches": [], "lookup_status": "not_found", "lookup_message": "请输入证券名称或代码。"}

        local = self.repository.local_search(cleaned, limit=20)
        cached = self.repository.cached_lookup(cleaned)
        cached_matches = cached.get("matches", []) if cached else []
        merged = self._merge(cleaned, cached_matches, local)
        cache_age = cached.get("age_seconds") if cached else None
        cache_fresh = cached is not None and isinstance(cache_age, int) and cache_age <= self.CACHE_TTL_SECONDS

        if cache_fresh:
            return {
                "query": cleaned,
                "matches": merged,
                "lookup_status": "matched" if merged else "not_found",
                "lookup_message": "已从本地证券缓存返回。" if merged else "本地证券缓存中没有匹配项。",
            }

        if self._has_definite_local_match(cleaned, local):
            return {
                "query": cleaned,
                "matches": merged,
                "lookup_status": "matched",
                "lookup_message": "已从本地数据库命中，无需等待远程查询。",
            }

        job = self._ensure_remote(cleaned)
        status = str(job.get("status") or "running")
        if status == "failed":
            return {
                "query": cleaned,
                "matches": merged,
                "lookup_status": "partial_failure" if merged else "remote_error",
                "lookup_message": str(job.get("message") or "远程证券目录暂时不可用。"),
            }

        elapsed = max(0.0, time.monotonic() - float(job.get("started_at") or time.monotonic()))
        if status == "completed":
            refreshed = self.repository.cached_lookup(cleaned)
            refreshed_matches = refreshed.get("matches", []) if refreshed else []
            merged = self._merge(cleaned, refreshed_matches, local)
            return {
                "query": cleaned,
                "matches": merged,
                "lookup_status": "matched" if merged else "not_found",
                "lookup_message": "远程证券目录已完成并写入本地缓存。" if merged else "远程证券目录未找到匹配项。",
            }

        if elapsed < 2:
            message = "本地数据库未完整命中，正在连接远程证券目录…"
        elif elapsed < 6:
            message = "远程证券目录响应较慢，仍在后台查询；已有结果会继续保留。"
        else:
            message = "远程查询仍在后台进行，不会阻塞界面；结果返回后会自动写入缓存。"
        return {
            "query": cleaned,
            "matches": merged,
            "lookup_status": "refreshing" if merged else "pending",
            "lookup_message": message,
        }

    def _ensure_remote(self, query: str) -> dict[str, object]:
        now = time.monotonic()
        with self._lock:
            existing = self._jobs.get(query)
            if existing:
                status = str(existing.get("status") or "")
                if status in {"queued", "running"}:
                    return dict(existing)
                if status == "completed":
                    return dict(existing)
                if status == "failed" and now - float(existing.get("finished_at") or now) < self.FAILURE_BACKOFF_SECONDS:
                    return dict(existing)
            state = {
                "status": "queued",
                "started_at": now,
                "finished_at": None,
                "message": "远程证券目录查询已排队。",
            }
            self._jobs[query] = state
            Thread(target=self._refresh_remote, args=(query,), daemon=True, name="symbol-search").start()
            return dict(state)

    def _refresh_remote(self, query: str) -> None:
        with self._lock:
            state = self._jobs.setdefault(query, {})
            state.update({"status": "running", "message": "正在拉取远程证券目录。"})
        try:
            values = self.market_data.lookup_symbols([query])
            result = values[0] if values else {
                "query": query,
                "matches": [],
                "lookup_status": "not_found",
                "lookup_message": "未找到匹配的证券代码。",
            }
            lookup_status = str(result.get("lookup_status") or "not_found")
            matches = result.get("matches") if isinstance(result.get("matches"), list) else []

            # A partial directory failure with zero matches is not evidence that
            # the security does not exist. Do not poison the negative cache; let
            # the UI surface a retryable remote error instead.
            if lookup_status == "partial_failure" and not matches:
                with self._lock:
                    self._jobs[query] = {
                        "status": "failed",
                        "started_at": state.get("started_at", time.monotonic()),
                        "finished_at": time.monotonic(),
                        "message": str(result.get("lookup_message") or "部分证券目录暂不可用，请稍后重试。"),
                    }
                return

            self.repository.save_remote_lookup(result)
            with self._lock:
                self._jobs[query] = {
                    "status": "completed",
                    "started_at": state.get("started_at", time.monotonic()),
                    "finished_at": time.monotonic(),
                    "message": "远程证券目录已写入缓存。",
                }
        except Exception as error:
            if self.logger is not None:
                self.logger.warning("symbol search remote refresh failed query=%s error_type=%s", query, type(error).__name__)
            with self._lock:
                self._jobs[query] = {
                    "status": "failed",
                    "started_at": state.get("started_at", time.monotonic()),
                    "finished_at": time.monotonic(),
                    "message": "远程证券目录查询失败，请稍后重试。",
                }

    @staticmethod
    def _score(candidate: dict[str, object], query: str) -> int:
        cleaned = str(query or "").strip().upper()
        normalized = normalize_search_text(cleaned)
        symbol = str(candidate.get("symbol") or "").strip().upper()
        name = normalize_search_text(candidate.get("name") or "")
        padded_hk = cleaned.zfill(5) if cleaned.isdigit() and len(cleaned) < 5 else cleaned
        if symbol in {cleaned, padded_hk}:
            return 100
        if name == normalized:
            return 95
        if symbol.startswith(cleaned):
            return 90
        if name.startswith(normalized):
            return 80
        if normalized and normalized in name:
            return 70
        return 0

    def _merge(self, query: str, *groups: object) -> list[dict[str, object]]:
        by_key: dict[str, dict[str, object]] = {}
        for group in groups:
            if not isinstance(group, list):
                continue
            for item in group:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("symbol") or "").strip().upper()
                market = str(item.get("market") or "CN").strip().upper()
                if not symbol:
                    continue
                key = f"{market}:{symbol}"
                existing = by_key.get(key)
                if existing is None or self._score(item, query) > self._score(existing, query):
                    by_key[key] = dict(item)
        return sorted(by_key.values(), key=lambda item: (-self._score(item, query), str(item.get("symbol") or "")))[:20]

    def _has_definite_local_match(self, query: str, local: list[dict[str, str]]) -> bool:
        """Return true only when local identity data is enough to skip providers.

        Exact symbol/name hits are always definite. A sufficiently specific name
        may also omit a market suffix from the canonical security name, for
        example ``小米集团`` versus ``小米集团-W``. Treat that as definite only
        when the local directory resolves the prefix to one unique security.
        Numeric prefixes deliberately do not use this shortcut because a code
        prefix can legitimately match many securities outside the local cache.
        """
        if any(self._score(item, query) >= 95 for item in local):
            return True

        cleaned = str(query or "").strip().upper()
        normalized = normalize_search_text(cleaned)
        if cleaned.isdigit() or len(normalized) < 4:
            return False

        prefix_identities = {
            f"{str(item.get('market') or 'CN').strip().upper()}:{str(item.get('symbol') or '').strip().upper()}"
            for item in local
            if str(item.get("symbol") or "").strip()
            and normalize_search_text(item.get("name") or "").startswith(normalized)
        }
        return len(prefix_identities) == 1
