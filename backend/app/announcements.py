"""A-share disclosure-announcement adapter backed by CNInfo through AKShare."""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from threading import Lock

from app.news import GLOSSARY_HINTS
from app.time_utils import BEIJING_TIMEZONE, beijing_now


class AnnouncementDataUnavailable(RuntimeError):
    pass


class AnnouncementService:
    CACHE_SECONDS = 900
    MAX_ITEMS_PER_SYMBOL = 10

    def __init__(self) -> None:
        self._cache: dict[tuple[str, ...], tuple[float, list[dict[str, object]]]] = {}
        self._lock = Lock()

    def fetch(self, symbols: list[str], names_by_symbol: dict[str, str], days: int = 30) -> list[dict[str, object]]:
        a_share_symbols = sorted({symbol for symbol in symbols if len(symbol) == 6 and symbol.isdigit()})
        if not a_share_symbols:
            return []
        key = tuple(a_share_symbols)
        with self._lock:
            cached = self._cache.get(key)
            if cached and time.monotonic() - cached[0] < self.CACHE_SECONDS:
                return cached[1]
        start = (date.today() - timedelta(days=days)).strftime("%Y%m%d")
        end = date.today().strftime("%Y%m%d")
        try:
            import akshare as ak
            records: list[dict[str, object]] = []
            successful_requests = 0
            for symbol in a_share_symbols:
                try:
                    frame = ak.stock_zh_a_disclosure_report_cninfo(
                        symbol=symbol, market="沪深京", category="", start_date=start, end_date=end,
                    )
                    successful_requests += 1
                except Exception:
                    continue
                for row in frame.head(self.MAX_ITEMS_PER_SYMBOL).to_dict("records"):
                    title = str(row.get("公告标题", "")).strip()
                    url = str(row.get("公告链接", "")).strip()
                    if not title or not url:
                        continue
                    records.append({
                        "id": f"announcement-{symbol}-{url}", "title": title,
                        "source_name": "巨潮资讯（正式公告）", "source_url": url,
                        "published_at": self._parse_time(row.get("公告时间")), "related_symbols": [symbol],
                        "explanation": self._explanation(symbol, names_by_symbol.get(symbol, symbol), title),
                        "confidence": 0.95,
                    })
            if not successful_requests:
                raise AnnouncementDataUnavailable("公开公告源暂时不可用，请稍后刷新。")
        except ImportError as error:
            raise AnnouncementDataUnavailable("未安装 AKShare，无法获取公告。") from error
        result = sorted({str(item["source_url"]): item for item in records}.values(), key=lambda item: item["published_at"], reverse=True)
        with self._lock:
            self._cache[key] = (time.monotonic(), result)
        return result

    @staticmethod
    def _parse_time(value: object) -> datetime:
        if isinstance(value, datetime):
            return value.replace(tzinfo=BEIJING_TIMEZONE) if value.tzinfo is None else value.astimezone(BEIJING_TIMEZONE)
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.replace(tzinfo=BEIJING_TIMEZONE) if parsed.tzinfo is None else parsed.astimezone(BEIJING_TIMEZONE)
        except ValueError:
            return beijing_now()

    @staticmethod
    def _explanation(symbol: str, name: str, title: str) -> str:
        hint = next((message for term, message in GLOSSARY_HINTS.items() if term in title), "这是正式披露公告，请优先阅读原文并确认公告类别与适用期间。")
        return f"为什么与你有关：公告属于持仓 {name}（{symbol}）。{hint}"
