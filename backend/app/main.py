"""Third-Hand MVP API.

The application intentionally keeps portfolio data in process for the MVP.  Swap
``PortfolioStore`` for a database repository after authentication is added.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from threading import Thread
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
from app.ai_analysis import AiAnalysisService
from app.portfolio_analysis import assess_holdings

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
    ai_analysis: dict[str, object] | None = None
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
    lookup_status: str = "pending"
    lookup_message: str = "等待后台查询证券代码"
    lookup_updated_at: datetime | None = None


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

class PortfolioAnalysisItem(BaseModel):
    symbol: str; name: str; action: str; reason: str; evidence: list[str]; disclaimer: str
class PortfolioAnalysis(BaseModel):
    items: list[PortfolioAnalysisItem]
class LearningCaseInput(BaseModel):
    symbol: str | None = Field(default=None, max_length=16)
    title: str = Field(min_length=3, max_length=120)
    context: str = Field(min_length=10, max_length=4000)
    lesson: str = Field(min_length=5, max_length=2000)
    outcome: str = Field(min_length=2, max_length=500)
    position_band: str = Field(min_length=3, max_length=100)
    planned_action: str = Field(min_length=3, max_length=500)
    confidence: float = Field(ge=0, le=1)
    evidence_links: list[str] = Field(default_factory=list, max_length=8)
class LearningCase(LearningCaseInput):
    id: str; created_at: datetime
class ResearchRule(BaseModel):
    id: str; category: str; title: str; trigger_text: str; guidance: str; confidence_ceiling: float; source_url: str; version: str


store = PortfolioStore()
market_data = MarketDataService()
news_service = NewsService()
announcement_service = AnnouncementService()
risk_service = RiskService()
ai_analysis_service = AiAnalysisService(store)

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
        items = [ai_analysis_service.enrich(item) for item in news_service.fetch(requested, names_by_symbol)]
        store.save_content(items)
        return [NewsItem.model_validate(item) for item in items]
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
        items = [ai_analysis_service.enrich(item) for item in announcement_service.fetch(requested, names_by_symbol, days)]
        store.save_content(items)
        return [NewsItem.model_validate(item) for item in items]
    except AnnouncementDataUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def refresh_quote_cache(symbols: list[str]) -> None:
    try:
        store.save_quotes(market_data.quotes(symbols))
    except MarketDataUnavailable:
        pass


def resolve_holding_drafts(draft_ids: list[str]) -> None:
    """Resolve draft names outside the request path and persist every lookup outcome."""
    store.mark_drafts_querying(draft_ids)
    drafts = store.drafts_by_ids(draft_ids)
    if not drafts:
        return
    try:
        results = market_data.lookup_symbols([str(draft["name"]) for draft in drafts])
        store.save_symbol_lookups(results)
    except Exception as error:
        for draft in drafts:
            store.set_draft_lookup_status(str(draft["id"]), "failed", f"查询失败：{error}")
        return

    matches_by_name = {str(result["query"]): list(result.get("matches", [])) for result in results}
    for draft in drafts:
        candidates = matches_by_name.get(str(draft["name"]), [])
        exact = [candidate for candidate in candidates if str(candidate.get("match_type", "")) == "exact"]
        if len(exact) == 1:
            candidate = exact[0]
            store.confirm_draft(
                str(draft["id"]), str(uuid4()), str(candidate["symbol"]), str(candidate["name"]),
                float(draft["quantity"]), float(draft["average_cost"]),
            )
        elif candidates:
            store.set_draft_lookup_status(str(draft["id"]), "needs_review", f"找到 {len(candidates)} 个候选代码，请手动补全")
        else:
            store.set_draft_lookup_status(str(draft["id"]), "not_found", "未找到可用证券代码，请手动补全")


@app.on_event("startup")
def resume_draft_lookups() -> None:
    """Resume work persisted before an API container restart."""
    draft_ids = store.draft_ids_needing_lookup()
    if draft_ids:
        Thread(target=resolve_holding_drafts, args=(draft_ids,), daemon=True).start()


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
        items = [risk_service.assess(str(holding["symbol"]), str(holding["name"])) for holding in store.list()]
        for item in items: store.save_risk(item)
        return [RiskAssessment.model_validate(item) for item in items]
    except RiskDataUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

@app.get("/v1/portfolio/analysis", response_model=PortfolioAnalysis)
def portfolio_analysis() -> PortfolioAnalysis:
    holdings = store.list()
    payload = assess_holdings(holdings, store.cached_quotes([str(item["symbol"]) for item in holdings]), store)
    store.save_portfolio_analysis(payload)
    return PortfolioAnalysis.model_validate(payload)

@app.get("/v1/learning-cases", response_model=list[LearningCase])
def list_learning_cases(symbol: str | None = None) -> list[LearningCase]:
    return [LearningCase.model_validate(item) for item in store.learning_cases(symbol)]

@app.post("/v1/learning-cases", response_model=LearningCase, status_code=status.HTTP_201_CREATED)
def create_learning_case(payload: LearningCaseInput) -> LearningCase:
    item = {"id": str(uuid4()), **payload.model_dump(), "created_at": beijing_now().isoformat()}
    return LearningCase.model_validate(store.add_learning_case(item))

@app.get("/v1/research-rules", response_model=list[ResearchRule])
def research_rules() -> list[ResearchRule]:
    return [ResearchRule.model_validate(item) for item in store.research_rules()]


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
def create_holding_draft(payload: HoldingDraftInput, background_tasks: BackgroundTasks) -> HoldingDraft:
    created = store.add_draft(str(uuid4()), **payload.model_dump())
    background_tasks.add_task(resolve_holding_drafts, [str(created["id"])])
    return HoldingDraft.model_validate(created)


@app.post("/v1/holding-drafts/batch", response_model=list[HoldingDraft], status_code=status.HTTP_201_CREATED)
def create_holding_drafts(payload: HoldingDraftBatchInput, background_tasks: BackgroundTasks) -> list[HoldingDraft]:
    created_at = beijing_now().isoformat()
    drafts = [
        {"id": str(uuid4()), **item.model_dump(), "created_at": created_at}
        for item in payload.items
    ]
    created = store.add_drafts(drafts)
    background_tasks.add_task(resolve_holding_drafts, [str(item["id"]) for item in created])
    return [HoldingDraft.model_validate(item) for item in created]


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
