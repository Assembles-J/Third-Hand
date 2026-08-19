"""Tier-1 HKEX corporate-event adapter.

The adapter is intentionally narrow: it reads official HKEX listed-company title
search results and promotes only published result announcements to the existing
CorporateEvent lifecycle. Pre-event scheduling remains eligible to use the
secondary calendar as a conservative fallback until an official board-meeting
*meeting date* can be verified from a first-party document/IR source.

No remote call occurs inside DecisionContext/Evidence/AI/Arbiter. The adapter is
used only by CorporateEventService during bounded acquisition/maintenance and
its normalized rows are persisted before formal decision consumption.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta
from typing import Any

import httpx


HKEX_ACTIVE_STOCKS_URL = "https://www1.hkexnews.hk/ncms/script/eds/activestock_sehk_e.json"
HKEX_TITLE_SEARCH_URL = "https://www1.hkexnews.hk/search/titlesearch.xhtml"
HKEX_SOURCE = "HKEXnews"
HKEX_SOURCE_REFERENCE = "https://www.hkexnews.hk/search/titlesearch.xhtml"
HKEX_EVENT_ADAPTER_VERSION = "hkex-corporate-event-v1-results-announcement"

_RESULT_TOKENS = (
    "INTERIM RESULTS",
    "ANNUAL RESULTS",
    "FINAL RESULTS",
    "QUARTERLY RESULTS",
    "FIRST QUARTER RESULTS",
    "THIRD QUARTER RESULTS",
    "中期業績",
    "中期业绩",
    "全年業績",
    "全年业绩",
    "年度業績",
    "年度业绩",
    "季度業績",
    "季度业绩",
)


def _normalize_hk_symbol(value: object) -> str:
    digits = "".join(character for character in str(value or "") if character.isdigit())
    return digits.zfill(5) if digits else ""


def _clean_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(html.unescape(text).split())


def _parse_release_time(value: str) -> datetime | None:
    cleaned = value.replace("Release Time:", "").strip()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def _infer_period(title: str, published: datetime) -> str:
    upper = title.upper()
    year = published.year
    if "INTERIM" in upper or "中期" in title:
        return f"{year}年中报"
    if "FIRST QUARTER" in upper or "第一季度" in title or "一季度" in title:
        return f"{year}年一季报"
    if "THIRD QUARTER" in upper or "第三季度" in title or "三季度" in title:
        return f"{year}年三季报"
    if "QUARTERLY" in upper or "季度" in title:
        return f"{year}年季度报告"
    return f"{year}年报"


def _is_results_announcement(category: str, title: str) -> bool:
    haystack = f"{category} {title}".upper()
    return any(token.upper() in haystack for token in _RESULT_TOKENS)


def _parse_title_search_rows(page: str, symbol: str) -> list[dict[str, object]]:
    """Extract result-announcement facts from the official HKEX result table."""
    rows: list[dict[str, object]] = []
    for row in re.findall(r"<tr\b[^>]*>.*?</tr>", page or "", flags=re.IGNORECASE | re.DOTALL):
        code_match = re.search(
            r"stock-short-code[^>]*>.*?(?:Stock Code:\s*</span>)?\s*(\d{1,5})",
            row,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if code_match and _normalize_hk_symbol(code_match.group(1)) != symbol:
            continue
        release_match = re.search(
            r"release-time[^>]*>(.*?)</td>",
            row,
            flags=re.IGNORECASE | re.DOTALL,
        )
        published = _parse_release_time(_clean_html(release_match.group(1))) if release_match else None
        if published is None:
            continue
        category_match = re.search(
            r'class=["\'][^"\']*headline[^"\']*["\'][^>]*>(.*?)</div>',
            row,
            flags=re.IGNORECASE | re.DOTALL,
        )
        category = _clean_html(category_match.group(1)) if category_match else ""
        link_match = re.search(
            r'class=["\'][^"\']*doc-link[^"\']*["\'][^>]*>\s*<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            row,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if link_match is None:
            continue
        href = html.unescape(link_match.group(1)).strip()
        title = _clean_html(link_match.group(2))
        if not _is_results_announcement(category, title):
            continue
        if href.startswith("http"):
            document_url = href
        else:
            document_url = f"https://www1.hkexnews.hk/{href.lstrip('/')}"
        rows.append({
            "symbol": symbol,
            "market": "HK",
            "period": _infer_period(title, published),
            "scheduled_date": published.date().isoformat(),
            "title": title or "HKEX Results Announcement",
            "source": HKEX_SOURCE,
            "source_reference": document_url,
            "verification_level": "official",
            "source_rank": 10,
            # Publishing a results announcement proves the disclosure occurred,
            # but the normalized financial dataset may not yet be ingested.
            "lifecycle_status": "RELEASED_UNVERIFIED",
            "announced_at": published.isoformat(),
            "parser_version": HKEX_EVENT_ADAPTER_VERSION,
            "summary": "HKEX 已发布业绩公告；在结构化财务数据完成验证前保持 RELEASED_UNVERIFIED。",
        })
    rows.sort(key=lambda item: (str(item["scheduled_date"]), str(item["title"])))
    return rows


class HkexOfficialEventFetcher:
    """Bounded official-source fetcher compatible with CorporateEventService."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
        lookback_days: int = 120,
    ) -> None:
        self._client = client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            trust_env=False,
            headers={
                "User-Agent": "Mozilla/5.0 Third-Hand/1.0",
                "Accept": "application/json,text/html,application/xhtml+xml,*/*",
                "Accept-Language": "en,zh-HK;q=0.9,zh;q=0.8",
            },
        )
        self._timeout_seconds = max(1.0, float(timeout_seconds))
        self._lookback_days = max(7, min(int(lookback_days), 366))
        self._stock_ids: dict[str, str] = {}

    def __call__(self, *, symbol: str, market: str | None, now: datetime) -> list[dict[str, object]]:
        if str(market or "").upper() != "HK":
            return []
        normalized = _normalize_hk_symbol(symbol)
        if not normalized:
            return []
        stock_id = self._resolve_stock_id(normalized)
        if stock_id is None:
            return []
        page = self._fetch_title_page(stock_id, now)
        return _parse_title_search_rows(page, normalized)

    def _resolve_stock_id(self, symbol: str) -> str | None:
        if symbol in self._stock_ids:
            return self._stock_ids[symbol]
        response = self._client.get(HKEX_ACTIVE_STOCKS_URL, timeout=self._timeout_seconds)
        response.raise_for_status()
        payload: Any = response.json()
        if not isinstance(payload, list):
            return None
        for item in payload:
            if not isinstance(item, dict):
                continue
            if _normalize_hk_symbol(item.get("c")) != symbol:
                continue
            stock_id = str(item.get("i") or "").strip()
            if stock_id:
                self._stock_ids[symbol] = stock_id
                return stock_id
        return None

    def _fetch_title_page(self, stock_id: str, now: datetime) -> str:
        end = now.date()
        start = end - timedelta(days=self._lookback_days)
        response = self._client.get(
            HKEX_TITLE_SEARCH_URL,
            params={
                "lang": "EN",
                "market": "SEHK",
                "category": "0",
                "stockId": stock_id,
                "from": start.strftime("%Y%m%d"),
                "to": end.strftime("%Y%m%d"),
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return response.text


__all__ = [
    "HKEX_ACTIVE_STOCKS_URL",
    "HKEX_EVENT_ADAPTER_VERSION",
    "HKEX_SOURCE",
    "HKEX_TITLE_SEARCH_URL",
    "HkexOfficialEventFetcher",
    "_parse_title_search_rows",
]
