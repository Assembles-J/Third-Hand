"""Public-news adapter for the portfolio feed."""
from __future__ import annotations

import time
from datetime import datetime
from threading import Lock

from app.time_utils import BEIJING_TIMEZONE, beijing_now


class NewsDataUnavailable(RuntimeError):
    pass


GLOSSARY_HINTS = {
    "回购": "出现“回购”：区分计划与已完成金额，并核对公告原文。",
    "减持": "出现“减持”：核对主体、比例、期限与完整公告，单则消息不能说明基本面变化。",
    "业绩": "出现“业绩”：关注同比口径、一次性损益与公告披露的风险因素。",
    "分红": "出现“分红”：核对除权除息日、股权登记日与方案是否已实施。",
    "风险": "出现“风险”：优先阅读原文中的风险提示及其适用范围。",
}


class NewsService:
    CACHE_SECONDS = 300
    MAX_ITEMS_PER_SYMBOL = 8

    def __init__(self) -> None:
        self._cache: dict[tuple[str, ...], tuple[float, list[dict[str, object]]]] = {}
        self._lock = Lock()

    def fetch(self, symbols: list[str], names_by_symbol: dict[str, str]) -> list[dict[str, object]]:
        key = tuple(sorted(set(symbols)))
        with self._lock:
            cached = self._cache.get(key)
            if cached and time.monotonic() - cached[0] < self.CACHE_SECONDS:
                return cached[1]
        try:
            import akshare as ak
            records: list[dict[str, object]] = []
            for symbol in key:
                frame = ak.stock_news_em(symbol=symbol)
                for row in frame.head(self.MAX_ITEMS_PER_SYMBOL).to_dict("records"):
                    title = str(row.get("新闻标题", "")).strip()
                    url = str(row.get("新闻链接", "")).strip()
                    if not title or not url:
                        continue
                    text = f"{title} {row.get('新闻内容', '')}"
                    records.append({
                        "id": f"news-{symbol}-{url}", "title": title,
                        "source_name": str(row.get("文章来源", "东方财富资讯")), "source_url": url,
                        "published_at": self._parse_time(row.get("发布时间")), "related_symbols": [symbol],
                        "explanation": self._explanation(symbol, names_by_symbol.get(symbol, symbol), text),
                        "confidence": 0.75,
                    })
        except Exception as error:
            raise NewsDataUnavailable("公开新闻源暂时不可用，请稍后刷新。") from error
        deduplicated = {str(item["source_url"]): item for item in records}
        result = sorted(deduplicated.values(), key=lambda item: item["published_at"], reverse=True)
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
    def _explanation(symbol: str, name: str, text: str) -> str:
        hint = next((message for term, message in GLOSSARY_HINTS.items() if term in text), "打开原文确认事实、发布时间和适用范围。")
        return f"为什么与你有关：内容匹配持仓 {name}（{symbol}）。{hint}"
