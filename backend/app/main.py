"""Third-Hand MVP API.

The application intentionally keeps portfolio data in process for the MVP.  Swap
``PortfolioStore`` for a database repository after authentication is added.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Annotated
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from app.market import MarketDataService, MarketDataUnavailable
from app.news import NewsDataUnavailable, NewsService
from app.announcements import AnnouncementDataUnavailable, AnnouncementService
from app.storage import PortfolioStore
from app.time_utils import beijing_now
from app.risk import RiskDataUnavailable, RiskService

app = FastAPI(title="Third-Hand API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

DISCLAIMER = "信息仅供学习与核查，不构成投资建议；请以原始公告和合规行情源为准。"


class GlossaryCard(BaseModel):
    term: str
    plain_explanation: str
    watch_for: str


class NewsItem(BaseModel):
    id: str
    title: str
    source_name: str
    source_url: str
    published_at: datetime
    related_symbols: list[str]
    explanation: str
    confidence: float = Field(ge=0, le=1)
    disclaimer: str = DISCLAIMER


class HoldingInput(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=100)
    quantity: float = Field(gt=0)
    average_cost: float = Field(ge=0)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class Holding(HoldingInput):
    id: str
    created_at: datetime


class HoldingDraftInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    quantity: float = Field(gt=0)
    average_cost: float = Field(ge=0)


class HoldingDraft(HoldingDraftInput):
    id: str
    created_at: datetime


class HoldingDraftBatchInput(BaseModel):
    items: list[HoldingDraftInput] = Field(min_length=1, max_length=100)


class ImportResult(BaseModel):
    accepted: int
    rejected_rows: list[int]
    message: str


class SecurityCandidate(BaseModel):
    symbol: str
    name: str
    market: str
    currency: str
    match_type: str


class SymbolLookupResult(BaseModel):
    query: str
    matches: list[SecurityCandidate]


class MarketQuote(BaseModel):
    symbol: str
    name: str = ""
    price: float | None = None
    change: float | None = None
    change_percent: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    previous_close: float | None = None
    volume: float | None = None
    amount: float | None = None
    currency: str
    source: str = ""
    retrieved_at: datetime | None = None
    as_of: str | None = None
    is_realtime: bool = False
    delay_seconds: int | None = None
    license_scope: str = "unknown"
    freshness_note: str = ""


class RiskAssessment(BaseModel):
    symbol: str
    name: str
    horizon_trading_days: int
    downside_threshold_percent: float
    historical_downside_probability: float
    annualized_volatility_percent: float
    risk_level: str
    confidence: str
    sample_count: int
    as_of: str
    explanation: str
    disclaimer: str = "基于历史价格的风险统计，不构成对未来价格的预测或任何投资建议。"


store = PortfolioStore()
market_data = MarketDataService()
news_service = NewsService()
announcement_service = AnnouncementService()
risk_service = RiskService()

GLOSSARY = {
    "pe": GlossaryCard(term="PE（市盈率）", plain_explanation="股价相对于每股盈利的倍数。它不是越低越好，要结合行业和盈利质量判断。", watch_for="亏损或一次性收益会使 PE 失真。"),
    "减持": GlossaryCard(term="减持", plain_explanation="股东卖出持有的公司股份。原因可能很多，单则消息不能证明基本面变差。", watch_for="看减持主体、比例、期限与公告全文。"),
    "回购": GlossaryCard(term="回购", plain_explanation="公司用资金买回自身股份，可能用于注销、激励或库存股。", watch_for="区分回购计划和实际完成金额。"),
}


def seed_news(symbols: list[str]) -> list[NewsItem]:
    related = symbols or ["600519"]
    return [NewsItem(
        id="demo-buyback", title="示例：公司发布回购进展公告", source_name="交易所公告（示例）",
        source_url="https://www.sse.com.cn/", published_at=beijing_now(), related_symbols=related,
        explanation="为什么相关：公告涉及你的持仓或自选股。请打开原文核查实际回购数量、金额和后续安排。",
        confidence=0.65,
    )]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/feed", response_model=list[NewsItem])
def feed(symbols: Annotated[list[str], Query()] = []) -> list[NewsItem]:
    requested = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
    holdings = store.list()
    if not requested:
        requested = [str(holding["symbol"]) for holding in holdings]
    if not requested:
        return seed_news([])
    names_by_symbol = {str(holding["symbol"]): str(holding["name"]) for holding in holdings}
    try:
        return [NewsItem.model_validate(item) for item in news_service.fetch(requested, names_by_symbol)]
    except NewsDataUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/v1/announcements", response_model=list[NewsItem])
def announcements(
    symbols: Annotated[list[str], Query()] = [],
    days: Annotated[int, Query(ge=1, le=90)] = 30,
) -> list[NewsItem]:
    requested = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
    holdings = store.list()
    if not requested:
        requested = [str(holding["symbol"]) for holding in holdings]
    names_by_symbol = {str(holding["symbol"]): str(holding["name"]) for holding in holdings}
    try:
        return [NewsItem.model_validate(item) for item in announcement_service.fetch(requested, names_by_symbol, days)]
    except AnnouncementDataUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def refresh_quote_cache(symbols: list[str]) -> None:
    try:
        store.save_quotes(market_data.quotes(symbols))
    except MarketDataUnavailable:
        pass


@app.get("/v1/market/quotes", response_model=list[MarketQuote])
def market_quotes(symbols: Annotated[list[str], Query()], background_tasks: BackgroundTasks) -> list[MarketQuote]:
    """Return the last saved snapshot immediately, then refresh it in the background."""
    requested = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))
    cached = store.cached_quotes(requested)
    if cached:
        background_tasks.add_task(refresh_quote_cache, requested)
        return [MarketQuote.model_validate(item) for item in cached]
    try:
        quotes = market_data.quotes(requested)
        store.save_quotes(quotes)
        return [MarketQuote.model_validate(item) for item in quotes]
    except MarketDataUnavailable as error:
        raise HTTPException(status_code=503, detail={"message": str(error), "code": error.code}) from error


@app.get("/v1/market/symbols", response_model=list[SymbolLookupResult])
def market_symbol_lookup(names: Annotated[list[str], Query()]) -> list[SymbolLookupResult]:
    """Return name-matched listings for OCR review; this endpoint never creates holdings."""
    try:
        return [SymbolLookupResult.model_validate(item) for item in market_data.lookup_symbols(names)]
    except MarketDataUnavailable as error:
        raise HTTPException(status_code=503, detail={"message": str(error), "code": error.code}) from error


@app.get("/v1/risk/assessments", response_model=list[RiskAssessment])
def risk_assessments() -> list[RiskAssessment]:
    """Return historical risk statistics for holdings that have a confirmed symbol."""
    try:
        return [
            RiskAssessment.model_validate(risk_service.assess(str(holding["symbol"]), str(holding["name"])))
            for holding in store.list()
        ]
    except RiskDataUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/v1/glossary/{term}", response_model=GlossaryCard)
def glossary(term: str) -> GlossaryCard:
    item = GLOSSARY.get(term.strip().lower())
    if not item:
        raise HTTPException(status_code=404, detail="词条尚未收录")
    return item


@app.get("/v1/holdings", response_model=list[Holding])
def list_holdings() -> list[Holding]:
    return [Holding.model_validate(item) for item in store.list()]


@app.post("/v1/holdings", response_model=Holding, status_code=status.HTTP_201_CREATED)
def create_holding(payload: HoldingInput) -> Holding:
    return Holding.model_validate(store.add(str(uuid4()), **payload.model_dump()))


@app.delete("/v1/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(holding_id: str) -> Response:
    if not store.delete(holding_id):
        raise HTTPException(status_code=404, detail="未找到持仓")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/v1/holding-drafts", response_model=list[HoldingDraft])
def list_holding_drafts() -> list[HoldingDraft]:
    return [HoldingDraft.model_validate(item) for item in store.list_drafts()]


@app.post("/v1/holding-drafts", response_model=HoldingDraft, status_code=status.HTTP_201_CREATED)
def create_holding_draft(payload: HoldingDraftInput) -> HoldingDraft:
    return HoldingDraft.model_validate(store.add_draft(str(uuid4()), **payload.model_dump()))


@app.post("/v1/holding-drafts/batch", response_model=list[HoldingDraft], status_code=status.HTTP_201_CREATED)
def create_holding_drafts(payload: HoldingDraftBatchInput) -> list[HoldingDraft]:
    created_at = beijing_now().isoformat()
    drafts = [
        {"id": str(uuid4()), **item.model_dump(), "created_at": created_at}
        for item in payload.items
    ]
    return [HoldingDraft.model_validate(item) for item in store.add_drafts(drafts)]


@app.post("/v1/holding-drafts/{draft_id}/confirm", response_model=Holding, status_code=status.HTTP_201_CREATED)
def confirm_holding_draft(draft_id: str, payload: HoldingInput) -> Holding:
    confirmed = store.confirm_draft(draft_id, str(uuid4()), **payload.model_dump())
    if not confirmed:
        raise HTTPException(status_code=404, detail="未找到待补全持仓")
    return Holding.model_validate(confirmed)


@app.delete("/v1/holding-drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding_draft(draft_id: str) -> Response:
    if not store.delete_draft(draft_id):
        raise HTTPException(status_code=404, detail="未找到待补全持仓")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/v1/holdings/import", response_model=ImportResult)
def import_holdings(csv_content: str) -> ImportResult:
    """Validate and import CSV text from a user-selected export; credentials are never accepted."""
    try:
        reader = csv.DictReader(io.StringIO(csv_content.lstrip("\ufeff")))
        if reader.fieldnames != ["symbol", "name", "quantity", "average_cost"]:
            raise HTTPException(status_code=422, detail="CSV 表头必须为 symbol,name,quantity,average_cost")
        rows = list(reader)
    except csv.Error as error:
        raise HTTPException(status_code=422, detail=f"CSV 解析失败：{error}") from error
    rejected: list[int] = []
    accepted = 0
    for line_number, row in enumerate(rows, start=2):
        try:
            payload = HoldingInput(**row)
            store.add(str(uuid4()), **payload.model_dump())
            accepted += 1
        except (ValueError, TypeError):
            rejected.append(line_number)
    return ImportResult(accepted=accepted, rejected_rows=rejected, message="已导入有效行；原始 CSV 与任何券商凭证均不会保存。")
