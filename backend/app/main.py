"""Third-Hand MVP API.

The application intentionally keeps portfolio data in process for the MVP.  Swap
``PortfolioStore`` for a database repository after authentication is added.
"""
from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Annotated
from uuid import uuid4
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from app.market import MarketDataService, MarketDataUnavailable
from app.news import NewsDataUnavailable, NewsService
from app.announcements import AnnouncementDataUnavailable, AnnouncementService
from app.storage import PortfolioStore
from app.time_utils import beijing_now
from app.risk import RiskDataUnavailable, RiskService
from app.ai_analysis import AiAnalysisService
from app.portfolio_analysis import assess_holdings
from app.technical_analysis import TechnicalAnalysisService
from app.trading_calendar import TradingCalendarService

app = FastAPI(title="Third-Hand API", version="0.2.0")
APP_STARTED_AT = time.monotonic()
logger = logging.getLogger(__name__)


def positive_environment_integer(name: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        logger.warning("%s 不是有效整数，使用默认值 %s", name, default)
        return default


MARKET_REFRESH_ENABLED = os.getenv("MARKET_REFRESH_ENABLED", "true").lower() not in {"0", "false", "no"}
MARKET_REFRESH_INTERVAL_SECONDS = positive_environment_integer("MARKET_REFRESH_INTERVAL_SECONDS", 60, 30)
market_refresh_stop = Event()
market_refresh_thread: Thread | None = None
market_refresh_state_lock = Lock()
market_refresh_state: dict[str, object] = {
    "last_attempt_at": None,
    "last_success_at": None,
    "last_error": None,
    "last_trigger": None,
    "symbols": [],
    "result_count": 0,
}
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


class AdminOverview(BaseModel):
    status: str
    generated_at: datetime
    uptime_seconds: int
    holdings_count: int
    draft_count: int
    pending_draft_count: int
    cached_quotes_count: int
    cached_content_count: int
    database_bytes: int


class AppUpdate(BaseModel):
    version_code: int = Field(ge=1)
    version_name: str = Field(min_length=1)
    apk_url: str
    changelog: str = ""
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    size_bytes: int = Field(gt=0)


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
    client_row_id: str | None = Field(default=None, min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    quantity: float = Field(gt=0)
    average_cost: float = Field(ge=0)
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)


class HoldingDraft(HoldingDraftInput):
    id: str
    created_at: datetime
    lookup_status: str = "pending"
    lookup_message: str = "等待后台查询证券代码"
    lookup_updated_at: datetime | None = None
    candidates: list["SecurityCandidate"] = Field(default_factory=list)


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


class HoldingDraftSelection(BaseModel):
    draft_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=100)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class HoldingDraftCommitInput(BaseModel):
    items: list[HoldingDraftSelection] = Field(min_length=1, max_length=100)


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
    refresh_status: str = "fresh"


class MarketRefreshStatus(BaseModel):
    enabled: bool
    interval_seconds: int
    worker_running: bool
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_trigger: str | None = None
    symbols: list[str] = Field(default_factory=list)
    result_count: int = 0


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
    symbol: str; name: str; action: str; reason: str; evidence: list[str]; confidence_percent: int = Field(ge=0, le=100); rule_snapshot: dict[str, object] | None = None; technical_snapshot: dict[str, object] | None = None; analysis_trace: list[dict[str, str]] = Field(default_factory=list); disclaimer: str
class PortfolioAnalysis(BaseModel):
    id: str; generated_at: datetime; items: list[PortfolioAnalysisItem]
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
class PersonalRuleInput(BaseModel):
    scope: str = Field(pattern="^(global|symbol)$")
    symbol: str | None = None
    max_position_percent: float = Field(gt=0, le=100)
    loss_review_percent: float = Field(gt=0, le=100)
    volatility_review_percent: float = Field(gt=0, le=200)
    enabled: bool = True
class PersonalRule(PersonalRuleInput):
    id: str; version: int; updated_at: datetime


store = PortfolioStore()
market_data = MarketDataService()
trading_calendar = TradingCalendarService()

news_service = NewsService()
announcement_service = AnnouncementService()
risk_service = RiskService()
ai_analysis_service = AiAnalysisService(store)
technical_analysis_service = TechnicalAnalysisService()

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


def configured_release_apk() -> Path | None:
    """Return the configured APK only when it remains inside the releases directory."""
    filename = os.getenv("APP_UPDATE_APK_FILE", "").strip()
    if not filename or Path(filename).name != filename:
        return None
    release_directory = Path(os.getenv("APP_UPDATE_DIRECTORY", "/app/releases")).resolve()
    candidate = (release_directory / filename).resolve()
    try:
        candidate.relative_to(release_directory)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def apk_sha256(apk: Path) -> str:
    digest = hashlib.sha256()
    with apk.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@app.get("/v1/app-update/apk", response_class=FileResponse, responses={404: {"description": "Release APK not found"}})
def download_app_update() -> FileResponse:
    apk = configured_release_apk()
    if apk is None:
        raise HTTPException(status_code=404, detail="Release APK is not configured")
    return FileResponse(
        apk,
        media_type="application/vnd.android.package-archive",
        filename=apk.name,
        headers={"Cache-Control": "no-store"},
    )


@app.get("/v1/app-update", response_model=AppUpdate, responses={204: {"description": "No update configured"}})
def app_update() -> Response | AppUpdate:
    """Return metadata for the APK served by this API deployment."""
    public_base_url = os.getenv("APP_PUBLIC_BASE_URL", "").strip().rstrip("/")
    apk = configured_release_apk()
    if apk is None or not public_base_url.startswith("https://"):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return AppUpdate(
        version_code=int(os.getenv("APP_UPDATE_VERSION_CODE", "1")),
        version_name=os.getenv("APP_UPDATE_VERSION_NAME", "0.1.0"),
        apk_url=f"{public_base_url}/v1/app-update/apk",
        changelog=os.getenv("APP_UPDATE_CHANGELOG", ""),
        sha256=apk_sha256(apk),
        size_bytes=apk.stat().st_size,
    )


@app.get("/v1/admin/overview", response_model=AdminOverview)
def admin_overview() -> AdminOverview:
    """Read-only aggregate health data; no holdings, identities, or credentials are exposed."""
    return AdminOverview(
        status="ok",
        generated_at=beijing_now(),
        uptime_seconds=int(time.monotonic() - APP_STARTED_AT),
        **store.admin_summary(),
    )


@app.get("/v1/feed", response_model=list[NewsItem])
def feed(background_tasks: BackgroundTasks, symbols: Annotated[list[str], Query()] = []) -> list[NewsItem]:
    requested = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
    holdings = store.list()
    if not requested:
        requested = [str(holding["symbol"]) for holding in holdings]
    if not requested:
        return seed_news([])
    names_by_symbol = {str(holding["symbol"]): str(holding["name"]) for holding in holdings}
    try:
        items = news_service.fetch(requested, names_by_symbol)
        for item in items:
            cached = store.cached_analysis(str(item["id"]))
            if cached: item["ai_analysis"] = cached
            else: background_tasks.add_task(ai_analysis_service.enrich, item)
        store.save_content(items)
        return [NewsItem.model_validate(item) for item in items]
    except NewsDataUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/v1/announcements", response_model=list[NewsItem])
def announcements(
    background_tasks: BackgroundTasks,
    symbols: Annotated[list[str], Query()] = [],
    days: Annotated[int, Query(ge=1, le=90)] = 30,
) -> list[NewsItem]:
    requested = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
    holdings = store.list()
    if not requested:
        requested = [str(holding["symbol"]) for holding in holdings]
    names_by_symbol = {str(holding["symbol"]): str(holding["name"]) for holding in holdings}
    try:
        items = announcement_service.fetch(requested, names_by_symbol, days)
        for item in items:
            cached = store.cached_analysis(str(item["id"]))
            if cached: item["ai_analysis"] = cached
            else: background_tasks.add_task(ai_analysis_service.enrich, item)
        store.save_content(items)
        return [NewsItem.model_validate(item) for item in items]
    except AnnouncementDataUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def fetch_and_store_quotes(
    symbols: list[str],
    *,
    force_refresh: bool,
    trigger: str,
) -> list[dict[str, object]]:
    attempted_at = beijing_now()
    with market_refresh_state_lock:
        market_refresh_state.update({
            "last_attempt_at": attempted_at,
            "last_trigger": trigger,
            "symbols": list(symbols),
        })
    try:
        quotes = market_data.quotes(symbols, force_refresh=force_refresh)
        store.save_quotes(quotes)
    except Exception as error:
        with market_refresh_state_lock:
            market_refresh_state["last_error"] = f"{type(error).__name__}: {error}"
            market_refresh_state["result_count"] = 0
        if isinstance(error, MarketDataUnavailable):
            logger.warning(
                "行情刷新失败 trigger=%s symbols=%s code=%s error=%s",
                trigger,
                ",".join(symbols),
                error.code,
                error,
            )
        else:
            logger.exception("行情刷新异常 trigger=%s symbols=%s", trigger, ",".join(symbols))
        raise
    with market_refresh_state_lock:
        market_refresh_state.update({
            "last_success_at": beijing_now(),
            "last_error": None,
            "result_count": len(quotes),
        })
    logger.info("行情刷新成功 trigger=%s symbols=%s count=%s", trigger, ",".join(symbols), len(quotes))
    return quotes


def refresh_quote_cache(
    symbols: list[str],
    force_refresh: bool = False,
    trigger: str = "request-background",
) -> None:
    try:
        fetch_and_store_quotes(symbols, force_refresh=force_refresh, trigger=trigger)
    except Exception:
        # The failure and its upstream code have already been recorded and logged.
        return


def scheduled_market_refresh_loop() -> None:
    logger.info(
        "行情定时刷新已启动 interval_seconds=%s",
        MARKET_REFRESH_INTERVAL_SECONDS,
    )

    previous_open_symbols: tuple[str, ...] | None = None

    while not market_refresh_stop.is_set():
        try:
            all_symbols = list(
                dict.fromkeys(
                    str(holding["symbol"]).strip().upper()
                    for holding in store.list()
                    if str(holding.get("symbol", "")).strip()
                )
            )

            now = beijing_now()

            # 只保留当前交易所正在开盘的证券。
            #
            # 示例：
            # 600519 -> XSHG 日历
            # 01810  -> XHKG 日历
            refreshable_symbols = trading_calendar.open_symbols(
                all_symbols,
                moment=now,
            )

            open_symbols_key = tuple(refreshable_symbols)

            if refreshable_symbols:
                refresh_quote_cache(
                    refreshable_symbols,
                    force_refresh=True,
                    trigger="scheduler-trading-session",
                )
            elif all_symbols and previous_open_symbols != open_symbols_key:
                # 只在状态发生变化时记录，避免休市期间每分钟刷日志。
                logger.info(
                    "当前交易所休市或处于午间休市，跳过行情刷新 now=%s symbols=%s",
                    now.isoformat(),
                    ",".join(all_symbols),
                )

            previous_open_symbols = open_symbols_key

        except Exception:
            # 日历判断自身发生错误时不应杀死后台线程。
            # 本轮跳过，下一轮继续尝试。
            logger.exception("行情定时任务执行异常")

        if market_refresh_stop.wait(MARKET_REFRESH_INTERVAL_SECONDS):
            break

    logger.info("行情定时刷新已停止")


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
            store.set_draft_resolution(
                str(draft["id"]), "matched", "已找到唯一代码，请核对后确认导入", candidates,
            )
        elif candidates:
            store.set_draft_resolution(
                str(draft["id"]), "needs_review", f"找到 {len(candidates)} 个候选代码，请选择后确认", candidates,
            )
        else:
            store.set_draft_resolution(str(draft["id"]), "not_found", "未找到可用证券代码，请手动补全", [])


@app.on_event("startup")
def resume_background_work() -> None:
    """Resume persisted lookups and start the server-side quote refresh worker."""
    global market_refresh_thread
    draft_ids = store.draft_ids_needing_lookup()
    if draft_ids:
        Thread(target=resolve_holding_drafts, args=(draft_ids,), daemon=True).start()
    if MARKET_REFRESH_ENABLED and (market_refresh_thread is None or not market_refresh_thread.is_alive()):
        market_refresh_stop.clear()
        market_refresh_thread = Thread(target=scheduled_market_refresh_loop, daemon=True, name="market-refresh")
        market_refresh_thread.start()


@app.on_event("shutdown")
def stop_background_work() -> None:
    market_refresh_stop.set()


@app.get("/v1/market/quotes", response_model=list[MarketQuote])
def market_quotes(
    symbols: Annotated[list[str], Query()],
    background_tasks: BackgroundTasks,
    refresh: Annotated[bool, Query()] = False,
) -> list[MarketQuote]:
    """Return cached data quickly, or synchronously refresh when the client asks."""
    requested = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))
    cached = store.cached_quotes(requested)
    cached_symbols = {str(item["symbol"]) for item in cached}
    has_complete_cache = cached_symbols.issuperset(requested)
    if refresh or not has_complete_cache:
        try:
            quotes = fetch_and_store_quotes(
                requested,
                force_refresh=refresh,
                trigger="request-forced" if refresh else "request-cache-miss",
            )
            return [MarketQuote.model_validate({**item, "refresh_status": "fresh"}) for item in quotes]
        except MarketDataUnavailable as error:
            if not cached:
                raise HTTPException(status_code=503, detail={"message": str(error), "code": error.code}) from error
            stale = [{
                **item,
                "refresh_status": "stale_fallback",
                "freshness_note": f"{item.get('freshness_note', '')} 本次刷新失败：{error}".strip(),
            } for item in cached]
            return [MarketQuote.model_validate(item) for item in stale]
    if cached:
        background_tasks.add_task(refresh_quote_cache, requested, False, "request-background")
        return [MarketQuote.model_validate({**item, "refresh_status": "cached_refreshing"}) for item in cached]
    return []


@app.get("/v1/market/refresh-status", response_model=MarketRefreshStatus)
def market_refresh_status() -> MarketRefreshStatus:
    with market_refresh_state_lock:
        snapshot = dict(market_refresh_state)
    return MarketRefreshStatus(
        enabled=MARKET_REFRESH_ENABLED,
        interval_seconds=MARKET_REFRESH_INTERVAL_SECONDS,
        worker_running=bool(market_refresh_thread and market_refresh_thread.is_alive()),
        **snapshot,
    )


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
    payload = assess_holdings(holdings, store.cached_quotes([str(item["symbol"]) for item in holdings]), store, technical_analysis_service)
    payload["generated_at"] = beijing_now().isoformat()
    store.save_portfolio_analysis(payload)
    store.save_analysis_run(payload)
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

@app.get("/v1/personal-rules", response_model=list[PersonalRule])
def list_personal_rules() -> list[PersonalRule]:
    return [PersonalRule.model_validate(item) for item in store.personal_rules()]

@app.post("/v1/personal-rules", response_model=PersonalRule)
def save_personal_rule(payload: PersonalRuleInput) -> PersonalRule:
    item = {"id": str(uuid4()), **payload.model_dump(), "version": 1, "updated_at": beijing_now().isoformat()}
    return PersonalRule.model_validate(store.save_personal_rule(item))


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

@app.put("/v1/holdings/{holding_id}", response_model=Holding)
def update_holding(holding_id: str, payload: HoldingInput) -> Holding:
    item = store.update(holding_id, **payload.model_dump())
    if not item: raise HTTPException(status_code=404, detail="未找到持仓")
    return Holding.model_validate(item)


@app.get("/v1/holding-drafts", response_model=list[HoldingDraft])
def list_holding_drafts() -> list[HoldingDraft]:
    return [HoldingDraft.model_validate(item) for item in store.list_drafts()]


@app.post("/v1/holding-drafts", response_model=HoldingDraft, status_code=status.HTTP_201_CREATED)
def create_holding_draft(payload: HoldingDraftInput, background_tasks: BackgroundTasks) -> HoldingDraft:
    draft_id = str(uuid4())
    created = store.add_draft(draft_id, **{
        **payload.model_dump(),
        "client_row_id": payload.client_row_id or draft_id,
    })
    background_tasks.add_task(resolve_holding_drafts, [str(created["id"])])
    return HoldingDraft.model_validate(created)


@app.post("/v1/holding-drafts/batch", response_model=list[HoldingDraft], status_code=status.HTTP_201_CREATED)
def create_holding_drafts(payload: HoldingDraftBatchInput, background_tasks: BackgroundTasks) -> list[HoldingDraft]:
    created_at = beijing_now().isoformat()
    drafts = [
        {
            "id": (draft_id := str(uuid4())),
            **item.model_dump(),
            "client_row_id": item.client_row_id or draft_id,
            "created_at": created_at,
        }
        for item in payload.items
    ]
    created = store.add_drafts(drafts)
    background_tasks.add_task(resolve_holding_drafts, [str(item["id"]) for item in created])
    return [HoldingDraft.model_validate(item) for item in created]


@app.post("/v1/holding-drafts/{draft_id}/confirm", response_model=Holding, status_code=status.HTTP_201_CREATED)
def confirm_holding_draft(draft_id: str, payload: HoldingInput) -> Holding:
    confirmed = store.confirm_draft(draft_id, str(uuid4()), payload.symbol, payload.name)
    if not confirmed:
        raise HTTPException(status_code=404, detail="未找到待补全持仓")
    return Holding.model_validate(confirmed)


@app.post("/v1/holding-drafts/commit", response_model=list[Holding], status_code=status.HTTP_201_CREATED)
def commit_holding_drafts(payload: HoldingDraftCommitInput) -> list[Holding]:
    """Atomically commit reviewed rows; quantity and cost always come from their original OCR draft."""
    try:
        committed = store.commit_drafts([item.model_dump() for item in payload.items])
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return [Holding.model_validate(item) for item in committed]


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
