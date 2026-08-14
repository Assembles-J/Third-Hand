"""Third-Hand MVP API.

The application intentionally keeps portfolio data in process for the MVP.  Swap
``PortfolioStore`` for a database repository after authentication is added.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
import sys
from datetime import date, timezone, timedelta
import os
import time
from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Annotated, Literal
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
from app.llm_client import LlmClientError
from app.portfolio_analysis import assess_holdings
from app.technical_analysis import TechnicalAnalysisService
from app.price_history import PriceHistoryService, PriceHistoryUnavailable
from app.impact_graph import build_impact_graph
from app.decision_snapshot import build_decision_snapshot
from app.calibration import summarize_calibration
from app.market_regime import MarketRegimeService
from app.relative_strength import RelativeStrengthService
from app.trading_calendar import TradingCalendarService
from app.recommendations import candidate as build_candidate, first_fill, evaluations
from app.opportunity_scoring import score_opportunity
from app.decision_context import DecisionContextBuilder
from app.execution_precheck import validate_daily_execution
from app.research_report import ResearchReportBuilder
from app.research_thesis import ResearchThesisService
from app.decision_models import DecisionContext, ResearchReport, ThesisVersion
from app.evidence_engine import EvidenceEngine
from app import decision_config as config
from app.action_policy import ActionPolicyEngine
from app.decision_models import ShadowDecisionReport
from app.position_sizing import PositionSizingEngine
from app.decision_ai import DecisionAiService
from app.decision_guard import DecisionGuard
from app.decision_orchestrator import DecisionOrchestrator

app = FastAPI(title="Third-Hand API", version="0.2.0")
APP_STARTED_AT = time.monotonic()
logger = logging.getLogger(__name__)
BEIJING_TIMEZONE = timezone(timedelta(hours=8))


class BeijingLogFormatter(logging.Formatter):
    """Plain-text formatter with Beijing time, kept as an opt-out for local debugging."""
    def formatTime(self, record, datefmt=None):  # noqa: N802 - logging API name
        return datetime.fromtimestamp(record.created, BEIJING_TIMEZONE).strftime(datefmt or "%Y-%m-%d %H:%M:%S%z")


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line so logs are machine-parseable and Chinese-safe.

    The existing ``key=value`` messages stay inside ``message`` unchanged, so
    grep-style queries such as ``provider=akshare`` remain valid while the
    surrounding fields (ts, level, logger, exception) become structured.
    """
    def formatTime(self, record, datefmt=None):  # noqa: N802 - logging API name
        return datetime.fromtimestamp(record.created, BEIJING_TIMEZONE).strftime(datefmt or "%Y-%m-%dT%H:%M:%S%z")

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _reconfigure_stdio_utf8() -> None:
    """Force UTF-8 on stdout/stderr so Chinese text never degrades to GBK on Windows."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def _install_log_formatter() -> None:
    """Apply JSON logging by default; THIRD_HAND_LOG_FORMAT=text keeps plain lines."""
    _reconfigure_stdio_utf8()
    text_format = os.getenv("THIRD_HAND_LOG_FORMAT", "json").lower() in {"text", "plain", "0", "false"}
    formatter = BeijingLogFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s") if text_format else JsonLogFormatter()
    for _logger_name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        for _handler in logging.getLogger(_logger_name).handlers:
            _handler.setFormatter(formatter)
    # Uvicorn configures its own loggers but does not always enable application
    # loggers.  Explicitly set the app namespace so market diagnostics are emitted.
    logging.getLogger("app").setLevel(os.getenv("THIRD_HAND_LOG_LEVEL", "INFO").upper())


_install_log_formatter()


def positive_environment_integer(name: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        logger.warning("%s 不是有效整数，使用默认值 %s", name, default)
        return default


MARKET_REFRESH_ENABLED = os.getenv("MARKET_REFRESH_ENABLED", "true").lower() not in {"0", "false", "no"}
MARKET_REFRESH_INTERVAL_SECONDS = positive_environment_integer("MARKET_REFRESH_INTERVAL_SECONDS", 60, 30)
MARKET_UNIVERSE_SCAN_INTERVAL_SECONDS = positive_environment_integer("MARKET_UNIVERSE_SCAN_INTERVAL_SECONDS", 300, 60)
PAPER_TRADING_INTERVAL_SECONDS = positive_environment_integer("PAPER_TRADING_INTERVAL_SECONDS", 600, 300)
PAPER_TRADING_CANDIDATE_LIMIT = positive_environment_integer("PAPER_TRADING_CANDIDATE_LIMIT", 8, 1)
DAILY_HISTORY_RETRY_SECONDS = positive_environment_integer("DAILY_HISTORY_RETRY_SECONDS", 300, 30)
HISTORY_BACKFILL_ENABLED = os.getenv("HISTORY_BACKFILL_ENABLED", "true").lower() not in {"0", "false", "no"}
HISTORY_BACKFILL_INTERVAL_SECONDS = positive_environment_integer("HISTORY_BACKFILL_INTERVAL_SECONDS", 1800, 300)
market_refresh_stop = Event()
market_refresh_thread: Thread | None = None
market_refresh_state_lock = Lock()
market_collection_lock = Lock()
derived_refresh_lock = Lock()
intraday_refresh_lock = Lock()
daily_history_refreshed_for: dict[str, str] = {}
daily_history_attempted_for: dict[str, str] = {}
daily_history_retry_after: dict[str, float] = {}
daily_review_generated_dates: set[str] = set()
last_paper_trading_run_at = 0.0
paper_trading_state_lock = Lock()
paper_trading_state: dict[str, object] = {
    "running": False, "last_started_at": None, "last_finished_at": None,
    "last_status": "never_run", "last_message": "尚未执行交易判断", "last_executed": 0,
    "last_skipped": 0, "last_symbols": [], "last_run_id": None,
}
history_backfill_stop = Event()
history_backfill_thread: Thread | None = None
history_backfill_state_lock = Lock()
history_backfill_state: dict[str, object] = {
    "last_attempt_at": None, "last_success_at": None, "last_symbols": [], "last_error": None,
}
market_refresh_state: dict[str, object] = {
    "last_attempt_at": None,
    "last_success_at": None,
    "last_error": None,
    "last_trigger": None,
    "symbols": [],
    "result_count": 0,
}
universe_scan_state_lock = Lock()
universe_scan_state: dict[str, object] = {
    "last_attempt_at": None,
    "last_success_at": None,
    "last_error": None,
    "hot_sectors": [],
    "candidates": {},
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
    found: bool = True
    source: str = "built_in"


class GlossaryLookupInput(BaseModel):
    term: str = Field(min_length=1, max_length=64)
    context: str = Field(default="", max_length=240)


class GlossaryEntryInput(BaseModel):
    term: str = Field(min_length=1, max_length=64)
    plain_explanation: str = Field(min_length=2, max_length=800)
    watch_for: str = Field(default="", max_length=400)


class AdminOverview(BaseModel):
    status: str
    generated_at: datetime
    uptime_seconds: int
    holdings_count: int
    draft_count: int
    pending_draft_count: int
    cached_quotes_count: int
    market_history_count: int
    latest_market_at: datetime | None = None
    cached_content_count: int
    database_bytes: int
    market_refresh_enabled: bool
    market_refresh_interval_seconds: int
    market_worker_running: bool
    market_last_attempt_at: datetime | None = None
    market_last_success_at: datetime | None = None
    market_last_error: str | None = None


class SystemConfig(BaseModel):
    update_check_enabled: bool = True
    paper_trading_enabled: bool = False
    paper_trading_interval_seconds: int = Field(default=600, ge=300, le=86_400)


class PaperTradingConfig(BaseModel):
    available_cash: float = Field(ge=0, le=1_000_000_000)


class PaperTradingCapitalReconciliation(BaseModel):
    net_contributions: float = Field(ge=0, le=1_000_000_000)


class PaperTradingPosition(BaseModel):
    symbol: str; name: str; quantity: float; average_cost: float; last_price: float = 0; market_value: float = 0; unrealized_pnl: float = 0; unrealized_return_percent: float = 0; updated_at: datetime


class PaperTradingLog(BaseModel):
    id: str; symbol: str; name: str; side: Literal["BUY", "SELL", "SKIP"]; quantity: float; price: float
    fee: float = 0; cash_before: float; cash_after: float; decision_id: str | None = None; reason: str; status: Literal["executed", "skipped"] = "executed"
    execution_quote_at: datetime | None = None; execution_quote_source: str | None = None
    fill_price_mode: Literal["NEXT_ELIGIBLE_OBSERVED_QUOTE"] | None = None; executed_at: datetime


class PaperTradingAccount(BaseModel):
    available_cash: float; initial_cash: float = 0; net_contributions: float = 0; market_value: float = 0; total_equity: float = 0; total_pnl: float = 0; total_return_percent: float = 0; updated_at: datetime; enabled: bool; positions: list[PaperTradingPosition] = Field(default_factory=list)


class PaperEquitySnapshot(BaseModel):
    total_equity: float; available_cash: float; market_value: float; total_pnl: float; recorded_at: datetime


class PaperTradingStatus(BaseModel):
    enabled: bool; interval_seconds: int; running: bool; last_started_at: datetime | None = None
    last_finished_at: datetime | None = None; last_status: str; last_message: str
    last_executed: int = 0; last_skipped: int = 0; last_symbols: list[str] = Field(default_factory=list)
    seconds_until_next_run: int = 0; last_run_id: str | None = None


class PaperTradingDashboard(BaseModel):
    account: PaperTradingAccount
    logs: list[PaperTradingLog] = Field(default_factory=list)
    snapshots: list[PaperEquitySnapshot] = Field(default_factory=list)
    status: PaperTradingStatus


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


class SaleInput(BaseModel):
    quantity: float = Field(gt=0)
    sale_price: float = Field(gt=0)
    reason: str = Field(default="", max_length=1000)


class SaleRecord(BaseModel):
    id: str; holding_id: str; symbol: str; name: str; quantity: float; sale_price: float; average_cost: float
    proceeds: float; cost_basis: float; realized_pnl: float; realized_pnl_percent: float; remaining_quantity: float
    reason: str = ""; analysis_snapshot: dict[str, object] = Field(default_factory=dict); sold_at: datetime


class ResearchTarget(BaseModel):
    symbol: str
    name: str
    status: Literal["active_holding", "closed_position", "watchlist"]
    last_activity_at: datetime


class WatchlistInput(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    name: str = Field(default="", max_length=100)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class WatchlistItem(WatchlistInput):
    created_at: datetime
    updated_at: datetime


class DailyPrice(BaseModel):
    trading_date: str
    open: float | None = None
    close: float
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    amount: float | None = None
    turnover_rate: float | None = None
    amplitude_percent: float | None = None
    change_percent: float | None = None
    change_amount: float | None = None
    adjustment: str = "qfq"
    source: str = ""


class MarketHistoryRefreshRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None


class RecommendationRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=50)


class DecisionGenerateRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=50)
    force: bool = False


class AvailableCashInput(BaseModel):
    available_cash: float = Field(ge=0, le=1_000_000_000)


class AvailableCash(AvailableCashInput):
    updated_at: datetime


class ResearchRecommendation(BaseModel):
    id: str; symbol: str; status: str; action: str | None = None
    price_zone: dict[str, float] | None = None; invalidation_price: float | None = None
    suggested_quantity: float | None = None; quantity_status: str | None = None
    conditions: list[dict[str, object]] = Field(default_factory=list); blocked_reasons: list[str] = Field(default_factory=list)
    automatic_execution: bool = False; evaluation_version: str | None = None
    generated_at: datetime | None = None; generated_trading_date: str | None = None
    evaluation_status: str | None = None


class OpportunityScanItem(BaseModel):
    symbol: str
    name: str
    sector: str | None = None
    sources: list[str] = Field(default_factory=list)
    action: Literal["watch", "add", "trim"]
    score: int = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)
    upside_likelihood: int = Field(ge=0, le=100)
    risk_level: Literal["低", "中", "高"]
    summary: str
    reasons: list[str] = Field(default_factory=list)
    buy_condition: str
    avoid_condition: str
    invalidation_price: float | None = None
    data_as_of: str | None = None


class OpportunityScan(BaseModel):
    generated_at: datetime
    coverage_note: str
    hot_sectors: list[str] = Field(default_factory=list)
    items: list[OpportunityScanItem] = Field(default_factory=list)


class DailyReviewGenerateRequest(BaseModel):
    symbols: list[str] | None = Field(default=None, max_length=50)


class DailyReviewExecutionInput(BaseModel):
    execution_status: Literal["executed", "partial", "skipped"]
    executed_quantity: float = Field(ge=0)
    executed_price: float | None = Field(default=None, gt=0)
    note: str = Field(default="", max_length=500)


class DailyReviewItem(BaseModel):
    symbol: str
    name: str = ""
    action: Literal["add", "trim", "watch"]
    suggested_quantity: float | None = None
    price_zone: dict[str, float] | None = None
    invalidation_price: float | None = None
    rationale: str
    reference_price: float
    execution_status: Literal["pending", "executed", "partial", "skipped"] = "pending"
    executed_quantity: float | None = None
    executed_price: float | None = None
    execution_note: str = ""
    theoretical_pnl: float | None = None
    actual_pnl: float | None = None


class DailyReview(BaseModel):
    id: str
    review_date: str
    generated_at: datetime
    suggested_position_band: str
    market_snapshot: dict[str, object]
    items: list[DailyReviewItem]
    status: Literal["pending", "evaluated"] = "pending"
    evaluated_at: datetime | None = None
    theoretical_pnl: float | None = None
    actual_pnl: float | None = None
    highlights: list[str] = Field(default_factory=list)
    mistakes: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


class AiJob(BaseModel):
    id: str; target_id: str; input_hash: str; status: str; attempts: int; max_attempts: int
    payload: dict[str, object]; error_message: str | None = None; created_at: datetime; updated_at: datetime
    volume: float | None = None
    amount: float | None = None
    adjustment: str = "qfq"


class IntradayPrice(BaseModel):
    bar_time: str; open: float; close: float; high: float; low: float
    volume: float | None = None; amount: float | None = None; average_price: float | None = None
    source: str; updated_at: datetime


class InstrumentMetadataInput(BaseModel):
    market: str = Field(min_length=1, max_length=16)
    currency: str = Field(min_length=1, max_length=8)
    lot_size: int | None = Field(default=None, gt=0)
    price_tick: str | None = None
    source: str = Field(min_length=1, max_length=200)
    as_of: str = Field(min_length=1, max_length=64)


class InstrumentMetadata(InstrumentMetadataInput):
    symbol: str
    updated_at: datetime


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
    lookup_status: str = "not_found"
    lookup_message: str = ""


class SymbolResolveRequest(BaseModel):
    names: list[str] = Field(min_length=1, max_length=100)


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


class OrderBookLevel(BaseModel):
    price: float | None = None
    volume: float | None = None


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
    bid_price: float | None = None
    ask_price: float | None = None
    bid_levels: list[OrderBookLevel] = []
    ask_levels: list[OrderBookLevel] = []
    volume_ratio: float | None = None
    turnover_rate: float | None = None
    currency: str
    source: str = ""
    retrieved_at: datetime | None = None
    as_of: str | None = None
    is_realtime: bool = False
    delay_seconds: int | None = None
    license_scope: str = "unknown"
    freshness_note: str = ""
    refresh_status: str = "fresh"
    error_code: str | None = None
    error_message: str | None = None


class MarketQuoteBatchRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=200)
    refresh: bool = False


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


class MarketIntelligence(BaseModel):
    retrieved_at: datetime | None = None
    source: str = "AKShare"
    breadth: dict[str, object] = Field(default_factory=dict)
    indices: list[dict[str, object]] = Field(default_factory=list)
    fund_flow: dict[str, object] = Field(default_factory=dict)
    northbound: list[dict[str, object]] = Field(default_factory=list)
    sectors: list[dict[str, object]] = Field(default_factory=list)
    rankings: dict[str, list[dict[str, object]]] = Field(default_factory=dict)
    data_health: str = "pending"
    error_message: str | None = None


class MarketSectorDetail(BaseModel):
    sector: str
    retrieved_at: datetime | None = None
    source: str = "AKShare"
    rows: list[dict[str, object]] = Field(default_factory=list)
    data_health: str = "pending"
    error_message: str | None = None


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
    status: str = "ready"
    message: str = ""
    disclaimer: str = "基于历史价格的风险统计，不构成对未来价格的预测或任何投资建议。"

class PortfolioAnalysisItem(BaseModel):
    symbol: str; name: str; action: str; reason: str; evidence: list[str]; confidence_percent: int = Field(ge=0, le=100); rule_snapshot: dict[str, object] | None = None; technical_snapshot: dict[str, object] | None = None; decision_snapshot: dict[str, object] = Field(default_factory=dict); analysis_trace: list[dict[str, str]] = Field(default_factory=list); disclaimer: str
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


class LearningCaseAnalysis(BaseModel):
    summary: str = Field(min_length=1, max_length=1200)
    recurring_patterns: list[str] = Field(default_factory=list, max_length=5)
    next_review_focus: list[str] = Field(default_factory=list, max_length=5)
    confidence: str = Field(pattern="^(low|medium|high)$")
    disclaimer: str = DISCLAIMER
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


class TradePlanInput(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    horizon: str = Field(pattern="^(swing|short)$")
    thesis: str = Field(min_length=10, max_length=1200)
    market_expectation: str = Field(min_length=5, max_length=800)
    benchmark_symbol: str | None = Field(default=None, max_length=16)
    benchmark_name: str | None = Field(default=None, max_length=80)
    catalysts: list[str] = Field(min_length=1, max_length=6)
    entry_condition: str = Field(min_length=5, max_length=800)
    add_condition: str = Field(min_length=5, max_length=800)
    reduce_condition: str = Field(min_length=5, max_length=800)
    exit_condition: str = Field(min_length=5, max_length=800)
    max_position_percent: float = Field(gt=0, le=100)
    risk_budget_percent: float = Field(gt=0, le=100)
    invalidation_price: float | None = Field(default=None, gt=0)
    enabled: bool = True
    # These are machine-readable counterparts to the explanatory text above.
    # A plan remains backward compatible while users gradually add conditions.
    structured_conditions: list[dict[str, object]] = Field(default_factory=list, max_length=12)

    @field_validator("symbol")
    @classmethod
    def normalize_trade_plan_symbol(cls, value: str) -> str:
        return value.strip().upper()


class TradePlan(TradePlanInput):
    id: str
    version: int
    updated_at: datetime


class TradePlanDraft(BaseModel):
    symbol: str
    horizon: str
    thesis: str
    market_expectation: str
    catalysts: list[str]
    entry_condition: str
    add_condition: str
    reduce_condition: str
    exit_condition: str
    max_position_percent: float
    risk_budget_percent: float
    notice: str


store = PortfolioStore()
# Existing local databases used a one-hour default.  Migrate once to the
# product's current ten-minute simulation cadence; later admin changes remain
# fully user-controlled.
store.migrate_paper_trading_default_interval(PAPER_TRADING_INTERVAL_SECONDS)
market_data = MarketDataService()
trading_calendar = TradingCalendarService()

news_service = NewsService()
announcement_service = AnnouncementService()
risk_service = RiskService()
ai_analysis_service = AiAnalysisService(store)
technical_analysis_service = TechnicalAnalysisService()
price_history_service = PriceHistoryService()
market_regime_service = MarketRegimeService()
relative_strength_service = RelativeStrengthService()
decision_context_builder = DecisionContextBuilder(store, technical_analysis_service)
evidence_engine = EvidenceEngine()
action_policy_engine = ActionPolicyEngine()
position_sizing_engine = PositionSizingEngine()
decision_ai_service = DecisionAiService(store)
decision_guard = DecisionGuard()
decision_orchestrator = DecisionOrchestrator(evidence_engine, action_policy_engine, position_sizing_engine, decision_ai_service, decision_guard)
research_report_builder = ResearchReportBuilder(evidence_engine)
research_thesis_service = ResearchThesisService()
from app.research_chat.routes import build_router
app.include_router(build_router(store, decision_context_builder, decision_orchestrator, lambda symbol: price_history_service.refresh(store, symbol)))

GLOSSARY = {
    "历史下行概率": GlossaryCard(term="历史下行概率", plain_explanation="在历史日线样本中，未来 5 个交易日累计下跌至少 5% 的出现频率。它是历史统计，不是未来发生概率的保证。", watch_for="先看统计窗口、下跌阈值和样本数量；样本不足时不应据此操作。"),
    "年化波动": GlossaryCard(term="年化波动", plain_explanation="把每日价格涨跌的离散程度换算到一年尺度，数值越高表示价格路径通常越不平稳；它不表示必然下跌。", watch_for="波动率只衡量幅度，不判断方向；需结合仓位大小和承受范围。"),
    "中期复核": GlossaryCard(term="中期复核", plain_explanation="不是买卖指令，而是在价格偏离成本、计划或基本假设时，重新检查原有判断是否仍成立。", watch_for="复核应查看公告、财报、行业环境和仓位，而非只看单日涨跌。"),
    "波动复核": GlossaryCard(term="波动复核", plain_explanation="当年化波动超过你设置的阈值时，系统提醒你检查仓位是否仍匹配风险承受能力。", watch_for="它不要求立刻卖出，只提示需要重新核对风险预算。"),
    "亏损复核": GlossaryCard(term="亏损复核", plain_explanation="当现价相对你的持仓成本跌幅超过设定阈值时，系统提醒复查原先买入逻辑、仓位和风险承受能力。", watch_for="它不是止损或补仓命令，不能只凭成本价做决定。"),
    "技术面中期偏强": GlossaryCard(term="技术面中期偏强", plain_explanation="通常指价格与 60 日均线等中期趋势指标呈现较强的历史形态。它只描述价格趋势，不证明公司价值或未来收益。", watch_for="结合成交量、基本面、估值和市场环境，避免把技术标签当作结论。"),
    "研究候选方案": GlossaryCard(term="研究候选方案", plain_explanation="系统基于已保存的交易计划、历史价格和可用资金计算的研究清单：候选价格区间、失效价、数量与交易复盘。它不会自动交易。", watch_for="交易计划是你的风险边界；AI 可以协助提出假设和解释证据，但建议必须标明来源并由你确认。"),
    "pe": GlossaryCard(term="PE（市盈率）", plain_explanation="股价相对于每股盈利的倍数。它不是越低越好，要结合行业和盈利质量判断。", watch_for="亏损或一次性收益会使 PE 失真。"),
    "减持": GlossaryCard(term="减持", plain_explanation="股东卖出持有的公司股份。原因可能很多，单则消息不能证明基本面变差。", watch_for="看减持主体、比例、期限与公告全文。"),
    "回购": GlossaryCard(term="回购", plain_explanation="公司用资金买回自身股份，可能用于注销、激励或库存股。", watch_for="区分回购计划和实际完成金额。"),
    "ma20": GlossaryCard(term="MA20（20日均线）", plain_explanation="最近 20 个交易日收盘价的平均值，用来观察短中期价格趋势。", watch_for="均线只描述历史价格，不能单独预测涨跌。"),
    "ma60": GlossaryCard(term="MA60（60日均线）", plain_explanation="最近 60 个交易日收盘价的平均值，常用于观察中期趋势。", watch_for="需要结合成交量、基本面和市场环境判断。"),
    "rsi": GlossaryCard(term="RSI（相对强弱指标）", plain_explanation="衡量一段时间内上涨与下跌力度的指标，数值通常在 0 到 100 之间。", watch_for="超买或超卖不等于会立刻反转。"),
    "macd": GlossaryCard(term="MACD", plain_explanation="用快慢均线差异观察动能变化的指标；柱状图反映两者差距的变化。", watch_for="信号可能滞后，震荡行情中容易反复。"),
    "atr": GlossaryCard(term="ATR（平均真实波幅）", plain_explanation="衡量一段时间内价格日常波动幅度的指标，数值越大通常代表波动越明显。", watch_for="ATR 不判断涨跌方向，只描述波动程度。"),
    "回撤": GlossaryCard(term="回撤", plain_explanation="价格从一段时间高点回落的幅度，用来观察阶段性下跌压力。", watch_for="先确认统计区间，避免把短期波动当成长期风险。"),
    "空头排列": GlossaryCard(term="空头排列", plain_explanation="短期均线低于中期均线，且中期均线低于长期均线，表示价格趋势偏弱的历史状态。", watch_for="它是趋势描述，不是自动卖出指令。"),
    "多头排列": GlossaryCard(term="多头排列", plain_explanation="短期均线高于中期均线，且中期均线高于长期均线，表示价格趋势偏强的历史状态。", watch_for="仍需留意估值、成交量与市场整体风险。"),
    "中期偏弱": GlossaryCard(term="中期偏弱", plain_explanation="价格趋势指标显示中期走势偏弱，但尚未同时满足典型空头排列。它是需要复核的技术状态，不是卖出指令。", watch_for="系统仅在趋势偏弱且 60 日回撤达到 -12% 或更低时，才会把它作为持仓风险复核的一项依据。"),
    "现价相对成本": GlossaryCard(term="现价相对成本", plain_explanation="把当前价格与平均持仓成本比较后的浮动盈亏百分比。例如成本 10 元、现价 9 元，就是 -10%。", watch_for="若跌幅达到个人规则中的“亏损复核阈值”（默认 -15%），持仓分析会转为“等待确认”，要求复核基本面和风险，而不是自动卖出。"),
    "亏损复核阈值": GlossaryCard(term="亏损复核阈值", plain_explanation="你为单个标的或全局设置的浮亏提醒线；默认值是 15%。它衡量的是当前价相对成本的跌幅。", watch_for="调低阈值会更早触发复核，调高阈值会减少提醒；它只改变“何时提醒复核”，不自动止损或补仓。"),
    "波动复核阈值": GlossaryCard(term="波动复核阈值", plain_explanation="你设置的年化波动率提醒线；默认值是 50%。波动率越高，表示价格路径通常越不平稳。", watch_for="当历史下行概率达到 20%，或年化波动达到该阈值时，持仓分析会输出“风险复核”。它不判断涨跌方向。"),
    "证据完整度": GlossaryCard(term="证据完整度", plain_explanation="持仓分析中的置信度分数，表示行情、风险、技术指标和个人规则等输入是否齐全、是否适用。它不是上涨概率或收益预测。", watch_for="缺少行情会直接得到“数据不足”；风险、技术指标或个人规则缺失时分数会较低，应优先补数据而不是据此交易。"),
    "数据不足": GlossaryCard(term="数据不足", plain_explanation="系统缺少形成可靠复核所需的关键输入，例如可用行情或足够的历史日线。", watch_for="此状态不会给出价格相关结论；应先检查证券代码、行情来源和历史数据是否已刷新。"),
    "风险复核": GlossaryCard(term="风险复核", plain_explanation="系统发现历史下行风险、年化波动，或趋势与回撤组合达到预设条件后给出的复查状态。", watch_for="它要求复核仓位上限、风险承受能力、公告和交易计划，不等同于立即减仓或卖出。"),
    "等待确认": GlossaryCard(term="等待确认", plain_explanation="当前价格相对成本的跌幅达到个人亏损复核阈值时的保守状态。", watch_for="先确认公司基本面、公告和原始持有逻辑；系统不会因为这一状态自动执行交易。"),
    "RSI偏热": GlossaryCard(term="RSI偏热", plain_explanation="RSI(14) 不低于 70，表示近期上涨动能较集中，价格处于相对偏热区间。", watch_for="偏热不等于马上下跌；它仅在决策证据中提示不要把短期强势误作低风险。"),
    "RSI偏冷": GlossaryCard(term="RSI偏冷", plain_explanation="RSI(14) 不高于 30，表示近期下跌动能较集中，价格处于相对偏冷区间。", watch_for="偏冷不等于马上反弹；应结合趋势、公告和风险，而不是据此自动补仓。"),
    "MACD动能": GlossaryCard(term="MACD动能", plain_explanation="MACD 柱状图用于描述短中期动能的强弱：大于 0 偏强，小于 0 偏弱。", watch_for="它是价格历史的滞后描述；在震荡行情中容易反复，不会单独触发持仓操作。"),
    "ATR/收盘价": GlossaryCard(term="ATR/收盘价", plain_explanation="把 ATR 日常波动幅度除以当前收盘价后的百分比，便于不同价格股票横向比较。", watch_for="数值高说明日常价格波动更大；目前用于风险证据，不会独自改变持仓分析结论。"),
    "60日回撤": GlossaryCard(term="60日回撤", plain_explanation="当前收盘价相对最近 60 个交易日最高收盘价的跌幅。", watch_for="在持仓分析中，趋势偏弱且 60 日回撤不高于 -12% 时，会触发“风险复核”；单独回撤不会自动卖出。"),
}


def glossary_key(term: str) -> str:
    return "".join(term.strip().lower().split())


def lookup_glossary(term: str, context: str = "") -> GlossaryCard:
    cleaned = term.strip()
    key = glossary_key(cleaned)
    saved = store.glossary_entry(key)
    if saved:
        card = GlossaryCard(
            term=str(saved["term"]), plain_explanation=str(saved["plain_explanation"]),
            watch_for=str(saved["watch_for"]), source=str(saved["source"]),
        )
    elif key in GLOSSARY:
        card = GLOSSARY[key]
    else:
        card = GlossaryCard(
            term=cleaned,
            plain_explanation="暂未收录这个词。你可以在下方补充自己的理解，保存后下次会优先显示。",
            watch_for="建议保留它出现的原句，并核验指标口径、时间区间和数据来源。",
            found=False,
            source="unresolved",
        )
    store.record_glossary_lookup(key, cleaned, context, card.found)
    return card


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


@app.get("/v1/system/ai-capabilities")
def ai_capabilities() -> dict[str, object]:
    """Expose effective AI switches without ever exposing the API key."""
    enabled_values = {"1", "true", "yes", "on"}

    def flag(name: str, default: str = "false") -> bool:
        return os.getenv(name, default).strip().lower() in enabled_values

    settings = decision_ai_service.client.settings
    return {
        "decision_ai_enabled": flag("DECISION_AI_ENABLED"),
        "decision_ai_runtime_enabled": config.DECISION_AI_ENABLED,
        "deepseek_key_configured": bool(settings.api_key),
        "deepseek_model": settings.model,
        "deepseek_reasoning_model": settings.reasoning_model,
        "research_chat_enabled": flag("RESEARCH_CHAT_ENABLED"),
        "research_chat_sse_enabled": flag("RESEARCH_CHAT_SSE_ENABLED"),
        "research_chat_reasoning_visible": flag("RESEARCH_CHAT_REASONING_VISIBLE"),
        "research_chat_tool_calling_enabled": flag("RESEARCH_CHAT_TOOL_CALLING_ENABLED"),
        "research_chat_clarification_enabled": flag("RESEARCH_CHAT_CLARIFICATION_ENABLED"),
        "research_chat_decision_output_enabled": flag("RESEARCH_CHAT_DECISION_OUTPUT_ENABLED"),
    }


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
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


def configured_update_url(apk: Path) -> str | None:
    """Prefer a dedicated static-download origin, while preserving the API fallback."""
    download_base_url = os.getenv("APP_UPDATE_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if download_base_url:
        if not download_base_url.startswith("https://"):
            return None
        return f"{download_base_url}/{apk.name}"

    public_base_url = os.getenv("APP_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not public_base_url.startswith("https://"):
        return None
    return f"{public_base_url}/v1/app-update/apk"


@app.get("/v1/app-update", response_model=AppUpdate, responses={204: {"description": "No update configured"}})
def app_update(response: Response) -> Response | AppUpdate:
    """Return fresh metadata; the versioned APK itself may be cached indefinitely."""
    response.headers["Cache-Control"] = "no-store"
    if not store.system_settings()["update_check_enabled"]:
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})
    apk = configured_release_apk()
    apk_url = configured_update_url(apk) if apk is not None else None
    if apk is None or apk_url is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})
    return AppUpdate(
        version_code=int(os.getenv("APP_UPDATE_VERSION_CODE", "1")),
        version_name=os.getenv("APP_UPDATE_VERSION_NAME", "0.1.0"),
        apk_url=apk_url,
        changelog=os.getenv("APP_UPDATE_CHANGELOG", ""),
        sha256=apk_sha256(apk),
        size_bytes=apk.stat().st_size,
    )


@app.get("/v1/admin/overview", response_model=AdminOverview)
def admin_overview() -> AdminOverview:
    """Read-only aggregate health data; no holdings, identities, or credentials are exposed."""
    with market_refresh_state_lock:
        refresh_state = dict(market_refresh_state)
    return AdminOverview(
        status="ok",
        generated_at=beijing_now(),
        uptime_seconds=int(time.monotonic() - APP_STARTED_AT),
        market_refresh_enabled=MARKET_REFRESH_ENABLED,
        market_refresh_interval_seconds=MARKET_REFRESH_INTERVAL_SECONDS,
        market_worker_running=bool(market_refresh_thread and market_refresh_thread.is_alive()),
        market_last_attempt_at=refresh_state["last_attempt_at"],
        market_last_success_at=refresh_state["last_success_at"],
        market_last_error=refresh_state["last_error"],
        **store.admin_summary(),
    )


@app.get("/v1/admin/config", response_model=SystemConfig)
def admin_config() -> SystemConfig:
    return SystemConfig(**store.system_settings())


@app.put("/v1/admin/config", response_model=SystemConfig)
def save_admin_config(payload: SystemConfig) -> SystemConfig:
    return SystemConfig(**store.save_system_settings(payload.model_dump()))


@app.get("/v1/paper-trading/account", response_model=PaperTradingAccount)
def paper_trading_account() -> PaperTradingAccount:
    return PaperTradingAccount.model_validate(store.paper_account())


@app.put("/v1/paper-trading/account", response_model=PaperTradingAccount)
def save_paper_trading_account(payload: PaperTradingConfig) -> PaperTradingAccount:
    return PaperTradingAccount.model_validate(store.save_paper_account(payload.available_cash))


@app.put("/v1/paper-trading/net-contributions", response_model=PaperTradingAccount)
def reconcile_paper_trading_contributions(payload: PaperTradingCapitalReconciliation) -> PaperTradingAccount:
    return PaperTradingAccount.model_validate(store.set_paper_net_contributions(payload.net_contributions))


@app.get("/v1/paper-trading/logs", response_model=list[PaperTradingLog])
def paper_trading_logs(symbol: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> list[PaperTradingLog]:
    return [PaperTradingLog.model_validate(item) for item in store.paper_logs(symbol, limit)]


@app.get("/v1/paper-trading/equity-snapshots", response_model=list[PaperEquitySnapshot])
def paper_trading_equity_snapshots(limit: int = Query(default=120, ge=1, le=500)) -> list[PaperEquitySnapshot]:
    return [PaperEquitySnapshot.model_validate(item) for item in store.paper_equity_snapshots(limit)]


@app.get("/v1/paper-trading/status", response_model=PaperTradingStatus)
def paper_trading_status() -> PaperTradingStatus:
    with paper_trading_state_lock:
        state = dict(paper_trading_state)
    settings = store.system_settings()
    interval_seconds = int(settings["paper_trading_interval_seconds"])
    elapsed = max(0.0, time.monotonic() - last_paper_trading_run_at)
    seconds_until_next_run = max(0, int(interval_seconds - elapsed)) if last_paper_trading_run_at else 0
    return PaperTradingStatus(
        enabled=bool(settings["paper_trading_enabled"]),
        interval_seconds=interval_seconds,
        seconds_until_next_run=seconds_until_next_run,
        **state,
    )


@app.get("/v1/paper-trading/dashboard", response_model=PaperTradingDashboard)
def paper_trading_dashboard() -> PaperTradingDashboard:
    """Return the complete paper-ledger view in one bounded request."""
    return PaperTradingDashboard(
        account=paper_trading_account(),
        logs=paper_trading_logs(limit=100),
        snapshots=paper_trading_equity_snapshots(limit=120),
        status=paper_trading_status(),
    )


@app.get("/v1/paper-trading/runs")
def paper_trading_runs(limit: int = Query(default=50, ge=1, le=500)) -> list[dict[str, object]]:
    """List every auditable simulation pass with its aggregate outcome."""
    return store.simulation_runs(limit)


@app.get("/v1/paper-trading/runs/{run_id}")
def paper_trading_run_detail(run_id: str) -> dict[str, object]:
    """Return one run with every persisted stage and per-symbol terminal state."""
    run = store.simulation_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="simulation run not found")
    return run


@app.get("/v1/data-quality/daily-history-attempts")
def daily_history_provider_attempts(symbol: str | None = None, limit: int = Query(default=200, ge=1, le=1000)) -> list[dict[str, object]]:
    """Return structured provider attempts with timing, counts and failure reasons."""
    return store.daily_history_attempts(symbol, limit)


@app.get("/v1/data-quality/provider-health")
def data_provider_health() -> dict[str, object]:
    """Return per-provider health, the auto-backfill queue and its last cycle state."""
    with history_backfill_state_lock:
        backfill_state = dict(history_backfill_state)
    return {
        "providers": store.provider_health_summary(),
        "backfill_queue": store.failed_history_symbols(since_hours=24, limit=100),
        "backfill": backfill_state,
    }


@app.post("/v1/paper-trading/run")
def run_paper_trading_now() -> dict[str, object]:
    """Queue a requested paper pass; provider refreshes must never hold HTTP open."""
    with paper_trading_state_lock:
        if paper_trading_state.get("running"):
            return {"status": "queued", "message": "交易任务已在运行，请在页面查看进度。", "symbols": list(paper_trading_state.get("last_symbols") or [])}
        paper_trading_state.update({"running": True, "last_started_at": beijing_now(), "last_status": "queued", "last_message": "交易任务已提交，正在后台准备行情、日线、风险和决策数据。", "last_executed": 0, "last_skipped": 0})
    queue_background(_run_paper_trading_now)
    return {"status": "queued", "message": "交易任务已提交，页面将自动更新进度与结果。", "symbols": []}


def _run_paper_trading_now() -> None:
    """Long-running manual path kept out of the request/response lifecycle."""
    try:
        _run_paper_trading_now_impl()
    except Exception as error:
        logger.exception("manual paper-trading task failed")
        with paper_trading_state_lock:
            paper_trading_state.update({"running": False, "last_finished_at": beijing_now(), "last_status": "failed", "last_message": f"交易任务异常：{type(error).__name__}: {error}"})


def _run_paper_trading_now_impl() -> None:
    symbols = paper_trading_symbols()
    active = trading_calendar.open_symbols(symbols, moment=beijing_now())
    if not symbols:
        try:
            refresh_universe_opportunity_inputs("paper-trading-manual-bootstrap")
            symbols = paper_trading_symbols()
        except MarketDataUnavailable as error:
            run_id = _create_simulation_run("manual", [], "候选行情池不可用")
            _record_simulation_stage(run_id, "candidate_pool", "failed", detail={"error": str(error)})
            _finish_simulation_run(run_id, "failed", "无法建立全市场行情池；行情源暂不可用，稍后会自动重试。")
            with paper_trading_state_lock:
                paper_trading_state.update({"last_finished_at": beijing_now(), "last_status": "market_data_unavailable", "last_message": "无法建立全市场行情池；行情源暂不可用，稍后会自动重试。", "last_executed": 0, "last_skipped": 0, "last_symbols": [], "last_run_id": run_id})
            return
        active = trading_calendar.open_symbols(symbols, moment=beijing_now())
    if not symbols:
        run_id = _create_simulation_run("manual", [], "行情池建立中")
        _record_simulation_stage(run_id, "candidate_pool", "skipped", detail={"reason": "no_candidates"})
        _finish_simulation_run(run_id, "completed", "全市场行情池正在建立；候选的日线、风险和新闻数据准备完成后会自动决策。")
        with paper_trading_state_lock:
            paper_trading_state.update({"last_finished_at": beijing_now(), "last_status": "market_scan_pending", "last_message": "全市场行情池正在建立；候选的日线、风险和新闻数据准备完成后会自动决策。", "last_executed": 0, "last_skipped": 0, "last_symbols": [], "last_run_id": run_id})
        return
    selected = active or symbols
    result = run_paper_trading_cycle(selected, force=True, allow_when_disabled=True)
    if not active:
        with paper_trading_state_lock:
            paper_trading_state.update({"last_status": "completed_closed_market_snapshot", "last_message": "休市期间已按最近保存的决策和价格快照完成手动交易；这不是实时行情或真实交易。", "last_run_id": result.get("run_id")})


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
            cached = ai_analysis_service.cached(item)
            if cached: item["ai_analysis"] = cached
            else:
                job = store.enqueue_ai_job({"id": str(uuid4()), "target_id": str(item["id"]), "input_hash": hashlib.sha256(json.dumps(item, ensure_ascii=False, default=str, sort_keys=True).encode()).hexdigest(), "payload": item})
                if job["status"] in {"pending", "retrying"}: queue_background(run_ai_job, str(job["id"]))
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
            cached = ai_analysis_service.cached(item)
            if cached: item["ai_analysis"] = cached
            else:
                job = store.enqueue_ai_job({"id": str(uuid4()), "target_id": str(item["id"]), "input_hash": hashlib.sha256(json.dumps(item, ensure_ascii=False, default=str, sort_keys=True).encode()).hexdigest(), "payload": item})
                if job["status"] in {"pending", "retrying"}: queue_background(run_ai_job, str(job["id"]))
        store.save_content(items)
        return [NewsItem.model_validate(item) for item in items]
    except AnnouncementDataUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def fetch_and_store_quotes(
    symbols: list[str],
    *,
    force_refresh: bool,
    trigger: str,
    run_id: str | None = None,
) -> list[dict[str, object]]:
    attempted_at = beijing_now()
    started_at = time.monotonic()
    stage_started_at = attempted_at.isoformat()
    logger.info(
        "行情刷新开始 trigger=%s symbols=%s force_refresh=%s",
        trigger, ",".join(symbols), force_refresh,
    )
    with market_refresh_state_lock:
        market_refresh_state.update({
            "last_attempt_at": attempted_at,
            "last_trigger": trigger,
            "symbols": list(symbols),
        })
    try:
        # A market-wide provider request is serialized.  This prevents two API
        # workers from independently downloading the same paginated universe.
        with market_collection_lock:
            quotes = market_data.quotes(symbols, force_refresh=force_refresh)
            markets = {
                "hk" if len(symbol) == 5 and symbol.isdigit()
                else "etf" if len(symbol) == 6 and symbol.startswith(("15", "16", "51", "56", "58"))
                else "a"
                for symbol in symbols
            }
            # The upstream frame already contains the whole market.  Persist one
            # normalized latest row per symbol, never the raw response/history.
            try:
                store.save_quotes(market_data.latest_market_snapshot(markets))
            except MarketDataUnavailable as error:
                # Quote collection may have succeeded through Tushare or a
                # previous in-memory frame.  A fresh full-universe snapshot is
                # an optimization, never a reason to discard those results.
                logger.warning("全市场快照入库跳过，不影响已获取持仓行情 markets=%s error=%s", ",".join(sorted(markets)), error)
        successful = [quote for quote in quotes if quote.get("price") is not None and not quote.get("error_code")]
        store.save_quotes(successful)
        try:
            store.record_provider_health(provider="market_quotes", success=True, circuit_threshold=1_000_000)
        except Exception:
            logger.warning("market quote health audit write skipped")
        _record_simulation_stage(
            run_id, "market_quotes", "ok",
            detail={"requested": len(symbols), "success": len(successful), "failed": len(quotes) - len(successful)},
            started_at=stage_started_at,
        )
        logger.info(
            "行情刷新结果 trigger=%s quotes=%s",
            trigger,
            [
                {
                    "symbol": quote.get("symbol"), "price": quote.get("price"),
                    "source": quote.get("source"), "as_of": quote.get("as_of"),
                    "retrieved_at": str(quote.get("retrieved_at")), "error_code": quote.get("error_code"),
                }
                for quote in quotes
            ],
        )
    except Exception as error:
        try:
            store.record_provider_health(provider="market_quotes", success=False, error_type=type(error).__name__, error_message=str(error), circuit_threshold=1_000_000)
        except Exception:
            logger.warning("market quote health audit write skipped")
        _record_simulation_stage(
            run_id, "market_quotes", "failed",
            detail={"error": f"{type(error).__name__}: {error}"},
            started_at=stage_started_at,
        )
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
    state_update: dict[str, object] = {
        "last_error": None if len(successful) == len(quotes) else f"{len(quotes) - len(successful)} 个代码刷新失败",
        "result_count": len(successful),
    }
    if successful:
        state_update["last_success_at"] = beijing_now()
    with market_refresh_state_lock:
        market_refresh_state.update(state_update)
    logger.info(
        "行情刷新完成 trigger=%s symbols=%s success=%s failed=%s elapsed_ms=%s",
        trigger, ",".join(symbols), len(successful), len(quotes) - len(successful),
        round((time.monotonic() - started_at) * 1000),
    )
    return quotes


def refresh_quote_cache(
    symbols: list[str],
    force_refresh: bool = False,
    trigger: str = "request-background",
) -> None:
    try:
        fetch_and_store_quotes(symbols, force_refresh=force_refresh, trigger=trigger)
        queue_background(refresh_intraday_cache, symbols, trigger)
    except Exception:
        # The failure and its upstream code have already been recorded and logged.
        return


def refresh_market_intelligence() -> None:
    """Refresh optional market-wide data outside request handlers."""
    try:
        store.save_market_intelligence("overview", market_data.market_intelligence())
    except Exception as error:
        previous = store.cached_market_intelligence("overview") or {}
        if previous:
            previous.update({"data_health": "stale_fallback", "error_message": str(error)[:180]})
            store.save_market_intelligence("overview", previous)
        logger.warning("market intelligence refresh unavailable error_type=%s", type(error).__name__)


def refresh_sector_intelligence(sector: str) -> None:
    cache_key = f"sector:{sector.strip()}"
    try:
        store.save_market_intelligence(cache_key, market_data.sector_intelligence(sector))
    except Exception as error:
        previous = store.cached_market_intelligence(cache_key) or {"sector": sector.strip(), "rows": []}
        previous.update({"data_health": "stale_fallback" if previous.get("rows") else "unavailable", "error_message": str(error)[:180]})
        store.save_market_intelligence(cache_key, previous)
        logger.warning("sector intelligence refresh unavailable sector=%s error_type=%s", sector, type(error).__name__)


def refresh_intraday_cache(symbols: list[str], trigger: str) -> None:
    """One-minute collection stays outside read APIs and is serialized per process."""
    if not symbols or not intraday_refresh_lock.acquire(blocking=False):
        return
    try:
        for symbol in symbols:
            try:
                price_history_service.refresh_intraday(store, symbol)
            except PriceHistoryUnavailable as error:
                logger.info("分钟行情刷新跳过 trigger=%s symbol=%s error=%s", trigger, symbol, error)
    finally:
        intraday_refresh_lock.release()


def queue_background(target, *args) -> None:
    """Do not let FastAPI's in-process BackgroundTasks hold the HTTP response open."""
    Thread(target=target, args=args, daemon=True).start()


def refresh_derived_cache(symbols: list[str], trigger: str, force_history: bool = False, run_id: str | None = None) -> None:
    """Collect daily bars and compute risk/technical results outside HTTP handlers.

    A usable local history must remain usable when a provider is unavailable.
    Remote history is therefore a cache-bootstrap mechanism here, rather than a
    prerequisite for every paper-trading pass.  Risk currently needs 65 closes,
    so that is the minimum local history that can independently support the
    downstream decision context.
    """
    if not symbols or not derived_refresh_lock.acquire(blocking=False):
        return
    try:
        names = {str(item["symbol"]): str(item["name"]) for item in store.list()}
        today = beijing_now().date().isoformat()
        for symbol in symbols:
            stage_started_at = beijing_now().isoformat()
            try:
                bars = store.daily_prices(symbol)
                local_history_ready = len(bars) >= 65
                persisted_retry_seconds = _daily_history_retry_seconds_left(symbol)
                retry_due = time.monotonic() >= daily_history_retry_after.get(symbol, 0.0) and persisted_retry_seconds == 0
                # Do not turn an optional remote supplement into an analysis
                # outage.  In particular, a manual paper pass used to force a
                # provider request even when the local cache already contained
                # enough bars to calculate risk and generate a decision.
                history_detail: dict[str, object] = {
                    "local_bar_count": len(bars),
                    "local_latest_date": str(bars[-1].get("trading_date")) if bars else None,
                    "local_ready": local_history_ready,
                    "remote_refresh": "skipped" if local_history_ready else "attempted" if retry_due else "cooldown",
                    "retry_after_seconds": persisted_retry_seconds or max(0, round(daily_history_retry_after.get(symbol, time.monotonic()) - time.monotonic())),
                }
                if not local_history_ready and retry_due and (
                    force_history or daily_history_refreshed_for.get(symbol) != today
                ):
                    daily_history_attempted_for[symbol] = today
                    price_history_service.refresh(store, symbol, trigger=trigger, run_id=run_id)
                    daily_history_refreshed_for[symbol] = today
                    daily_history_retry_after.pop(symbol, None)
                    bars = store.daily_prices(symbol)
                    history_detail.update({"remote_refresh": "ok", "bar_count_after_refresh": len(bars)})
                    _record_simulation_stage(run_id, "daily_history", "ok", symbol=symbol, detail=history_detail, started_at=stage_started_at)
                elif local_history_ready:
                    logger.info(
                        "daily history local-cache accepted trigger=%s symbol=%s bar_count=%s remote_refresh=skipped",
                        trigger, symbol, len(bars),
                    )
                    _record_simulation_stage(run_id, "daily_history", "ok", symbol=symbol, detail=history_detail, started_at=stage_started_at)
                else:
                    logger.info(
                        "派生数据等待历史日线 trigger=%s symbol=%s retry_after_seconds=%s",
                        trigger,
                        symbol,
                        history_detail["retry_after_seconds"],
                    )
                    _record_simulation_stage(run_id, "daily_history", "skipped", symbol=symbol, detail={**history_detail, "reason": "waiting_for_daily_history"}, started_at=stage_started_at)
                    continue
                if not bars:
                    logger.info(
                        "派生数据缺少可用日线 trigger=%s symbol=%s",
                        trigger, symbol,
                    )
                    _record_simulation_stage(run_id, "daily_history", "skipped", symbol=symbol, detail={**history_detail, "reason": "no_daily_bars"}, started_at=stage_started_at)
                    continue
                risk_started_at = beijing_now().isoformat()
                item = risk_service.assess(symbol, names.get(symbol, symbol), [float(bar["close"]) for bar in bars], str(bars[-1]["trading_date"]))
                store.save_risk(item)
                _record_simulation_stage(
                    run_id, "risk", "ok", symbol=symbol,
                    detail={"bar_count": len(bars), "latest_date": str(bars[-1]["trading_date"]), "risk_as_of": str(item.get("as_of") or "")},
                    started_at=risk_started_at,
                )
            except PriceHistoryUnavailable as error:
                daily_history_retry_after[symbol] = time.monotonic() + DAILY_HISTORY_RETRY_SECONDS
                logger.warning(
                    "历史日线刷新失败 trigger=%s symbol=%s error=%s retry_after_seconds=%s",
                    trigger,
                    symbol,
                    error,
                    DAILY_HISTORY_RETRY_SECONDS,
                )
                _record_simulation_stage(
                    run_id, "daily_history", "failed", symbol=symbol,
                    detail={"error": str(error), "retry_after_seconds": DAILY_HISTORY_RETRY_SECONDS},
                    started_at=stage_started_at,
                )
            except RiskDataUnavailable as error:
                logger.warning("派生数据刷新失败 trigger=%s symbol=%s error=%s", trigger, symbol, error)
                _record_simulation_stage(
                    run_id, "risk", "failed", symbol=symbol,
                    detail={"error": str(error)},
                    started_at=stage_started_at,
                )
        holdings = store.list()
        symbols = [str(item["symbol"]) for item in holdings]
        quotes = store.cached_quotes(symbols)
        quote_by_symbol = {str(item["symbol"]): item for item in quotes}
        payload = assess_holdings(holdings, quotes, store, technical_analysis_service)
        content_items = store.cached_content(symbols)
        holding_by_symbol = {str(item["symbol"]): item for item in holdings}
        market_regime = market_regime_service.assess()
        for review in payload["items"]:
            symbol = str(review["symbol"])
            plan = store.trade_plan(symbol)
            relative_strength = relative_strength_service.assess(store.daily_prices(symbol), plan.get("benchmark_symbol") if plan else None, plan.get("benchmark_name") if plan else None)
            review["decision_snapshot"] = build_decision_snapshot(
                holding_by_symbol[symbol], quote_by_symbol.get(symbol), store.cached_risk(symbol),
                review.get("rule_snapshot"), content_items, str(review["action"]), plan, market_regime, relative_strength,
            )
        payload["generated_at"] = beijing_now().isoformat()
        store.save_calibration_observations(payload)
        for review in payload["items"]:
            symbol = str(review["symbol"])
            review["decision_snapshot"]["historical_calibration"] = summarize_calibration(
                [item for item in store.calibration_observations(symbol) if item["action"] == review["action"]],
                store.daily_prices(symbol), str(review["action"]),
            )
        store.save_portfolio_analysis(payload)
        store.save_analysis_run(payload)
    finally:
        derived_refresh_lock.release()


def refresh_universe_opportunity_inputs(trigger: str) -> list[str]:
    """Refresh whole-market quotes and queue bounded daily-history analysis."""
    with universe_scan_state_lock:
        universe_scan_state["last_attempt_at"] = beijing_now()
    try:
        with market_collection_lock:
            snapshot = market_data.a_share_universe_snapshot(force_refresh=True)
            store.save_quotes(snapshot)
            hot_sectors = market_data.hot_a_share_sectors(limit=3)
            members = [
                member
                for sector in hot_sectors
                for member in market_data.a_share_sector_members(str(sector["name"]), limit=12)
            ]
        quote_by_symbol = {str(item["symbol"]): item for item in snapshot}
        metadata: dict[str, dict[str, str]] = {}
        for member in members:
            symbol = str(member["symbol"])
            if symbol in quote_by_symbol:
                metadata[symbol] = {
                    "name": str(quote_by_symbol[symbol].get("name") or member["name"] or symbol),
                    "sector": str(member["sector"]),
                }
        if not metadata:
            ranked = sorted(
                (item for item in snapshot if item.get("price") is not None),
                key=lambda item: float(item.get("change_percent") or -999),
                reverse=True,
            )[:24]
            metadata = {
                str(item["symbol"]): {"name": str(item.get("name") or item["symbol"]), "sector": "市场活跃股"}
                for item in ranked
            }
        selected = list(metadata)[:24]
        with universe_scan_state_lock:
            universe_scan_state.update({
                "last_success_at": beijing_now(), "last_error": None,
                "hot_sectors": hot_sectors, "candidates": metadata,
            })
        logger.info(
            "全市场机会扫描输入刷新 trigger=%s quotes=%s sectors=%s history_queue=%s",
            trigger, len(snapshot), ",".join(str(item["name"]) for item in hot_sectors) or "fallback", ",".join(selected),
        )
        queue_background(refresh_derived_cache, selected, f"{trigger}-candidate-history")
        return selected
    except MarketDataUnavailable as error:
        with universe_scan_state_lock:
            universe_scan_state["last_error"] = f"{error.code}: {error}"
        logger.warning("全市场机会扫描不可用 trigger=%s code=%s", trigger, error.code)
        raise


def scheduled_market_refresh_loop() -> None:
    logger.info(
        "行情定时刷新已启动 interval_seconds=%s",
        MARKET_REFRESH_INTERVAL_SECONDS,
    )

    previous_open_symbols: tuple[str, ...] | None = None
    last_universe_scan_at = 0.0

    while not market_refresh_stop.is_set():
        try:
            now = beijing_now()
            if (
                trading_calendar.is_market_open("CN", now)
                and time.monotonic() - last_universe_scan_at >= MARKET_UNIVERSE_SCAN_INTERVAL_SECONDS
            ):
                try:
                    refresh_universe_opportunity_inputs("scheduler-whole-market")
                finally:
                    last_universe_scan_at = time.monotonic()
            all_symbols = paper_trading_symbols()

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

            logger.info(
                "行情定时任务轮询 now=%s holdings=%s refreshable=%s",
                now.isoformat(), ",".join(all_symbols) or "none",
                ",".join(refreshable_symbols) or "none",
            )

            if refreshable_symbols:
                refresh_quote_cache(
                    refreshable_symbols,
                    force_refresh=True,
                    trigger="scheduler-trading-session",
                )
                refresh_derived_cache(refreshable_symbols, "scheduler-trading-session")
                run_paper_trading_cycle(refreshable_symbols)
            elif all_symbols and previous_open_symbols:
                # Capture one final close snapshot when the session ends.  This
                # also refreshes that day's daily bar once, rather than fetching
                # full history every scheduler minute.
                refresh_quote_cache(all_symbols, force_refresh=True, trigger="scheduler-close-snapshot")
                refresh_derived_cache(all_symbols, "scheduler-close-snapshot", force_history=True)
                review_date = now.date().isoformat()
                if review_date not in daily_review_generated_dates:
                    # Close snapshots create the one daily decision record.  It is
                    # intentionally server-side so users never need to maintain a
                    # separate plan or hand-written review before paper P&L works.
                    generate_daily_review(DailyReviewGenerateRequest(symbols=all_symbols))
                    daily_review_generated_dates.add(review_date)
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


def paper_trading_symbols() -> list[str]:
    """Bounded active set ranked from a persisted whole-market snapshot."""
    with universe_scan_state_lock:
        market_candidates = list((universe_scan_state.get("candidates") or {}).keys())
    positions = [str(item["symbol"]).strip().upper() for item in store.paper_account().get("positions", [])]
    watch_symbols = [str(item["symbol"]).strip().upper() for item in store.watchlist()]
    ready_market = store.opportunity_symbols(minimum_daily_bars=60, limit=PAPER_TRADING_CANDIDATE_LIMIT * 3)
    # A watchlist only changes refresh/display priority. It is intentionally
    # absent from DecisionContext and never changes a symbol's policy inputs.
    market_first = list(dict.fromkeys([*market_candidates, *ready_market]))
    reserved_for_risk = min(len(positions), PAPER_TRADING_CANDIDATE_LIMIT)
    available = max(0, PAPER_TRADING_CANDIDATE_LIMIT - reserved_for_risk)
    return list(dict.fromkeys([*watch_symbols, *market_first]))[:available] + [item for item in positions if item not in watch_symbols][:reserved_for_risk]


def paper_trading_names(symbols: list[str]) -> dict[str, str]:
    names = {str(x["symbol"]): str(x["name"]) for x in [*store.list(), *store.watchlist()]}
    names.update({str(x["symbol"]): str(x.get("name") or x["symbol"]) for x in store.cached_quotes(symbols)})
    return names


def _record_simulation_stage(run_id: str | None, stage: str, status: str, symbol: str | None = None, detail: dict[str, object] | None = None, started_at: str | None = None) -> None:
    """Append one stage row; audit writes never break the trading pass itself."""
    if not run_id:
        return
    try:
        store.record_simulation_stage(run_id=run_id, stage=stage, status=status, symbol=symbol, detail=detail, started_at=started_at)
    except Exception:
        logger.warning("simulation stage audit write skipped run_id=%s stage=%s status=%s", run_id, stage, status)


def _record_simulation_symbol_state(run_id: str | None, symbol: str, terminal_state: str, detail: dict[str, object] | None = None) -> None:
    if not run_id:
        return
    try:
        store.record_simulation_symbol(run_id=run_id, symbol=symbol, terminal_state=terminal_state, detail=detail)
    except Exception:
        logger.warning("simulation symbol audit write skipped run_id=%s symbol=%s state=%s", run_id, symbol, terminal_state)


def _create_simulation_run(trigger: str, symbols: list[str], message: str) -> str:
    run_id = str(uuid4())
    try:
        store.create_simulation_run(run_id=run_id, trigger=trigger, symbols=symbols, message=message)
    except Exception:
        logger.warning("simulation run audit create skipped trigger=%s symbols=%s", trigger, len(symbols))
    return run_id


def _finish_simulation_run(run_id: str, status: str, message: str, executed: int = 0, skipped: int = 0, generated: int = 0) -> None:
    try:
        store.finish_simulation_run(run_id=run_id, status=status, message=message, executed=executed, skipped=skipped, generated=generated)
    except Exception:
        logger.warning("simulation run audit finish skipped run_id=%s status=%s", run_id, status)


def _daily_history_retry_seconds_left(symbol: str) -> int:
    """Persisted provider backoff survives restarts; in-memory state stays a fast path."""
    try:
        failure = store.latest_daily_history_failure(symbol)
    except Exception:
        return 0
    if not failure:
        return 0
    try:
        failed_at = datetime.fromisoformat(str(failure.get("started_at") or ""))
    except ValueError:
        return 0
    remaining = DAILY_HISTORY_RETRY_SECONDS - (beijing_now() - failed_at).total_seconds()
    return max(0, round(remaining)) if remaining > 0 else 0


def run_history_backfill() -> dict[str, object]:
    """Retry symbols whose daily history failed once the provider recovers.

    The per-symbol persisted backoff and the provider circuit breaker both live
    inside ``refresh_derived_cache`` / ``price_history_service``, so this loop
    can safely run on a fixed cadence without hammering an unhealthy source.
    """
    failed = store.failed_history_symbols(since_hours=24, limit=100)
    symbols = [str(item["symbol"]) for item in failed]
    with history_backfill_state_lock:
        history_backfill_state.update({"last_attempt_at": beijing_now(), "last_symbols": symbols, "last_error": None})
    if symbols:
        refresh_derived_cache(symbols, "history-backfill")
        with history_backfill_state_lock:
            history_backfill_state.update({"last_success_at": beijing_now(), "last_symbols": symbols})
    return {"symbols": symbols}


def history_backfill_loop() -> None:
    while not history_backfill_stop.wait(HISTORY_BACKFILL_INTERVAL_SECONDS):
        try:
            run_history_backfill()
        except Exception as error:
            with history_backfill_state_lock:
                history_backfill_state["last_error"] = f"{type(error).__name__}: {error}"
            logger.warning("history backfill cycle failed error_type=%s", type(error).__name__)


def refresh_paper_market_intelligence(symbols: list[str], names: dict[str, str]) -> None:
    """Persist current news for the active market candidates without blocking the cycle."""
    try:
        store.save_content(news_service.fetch(symbols, names))
    except NewsDataUnavailable as error:
        logger.info("paper intelligence news unavailable: %s", error)
    except Exception:
        logger.exception("paper intelligence refresh failed")


def refresh_paper_candidate_data(symbols: list[str], *, force_refresh: bool, run_id: str | None = None) -> None:
    """Make cached holdings/watchlist data decision-ready before paper simulation."""
    if not symbols:
        return
    with paper_trading_state_lock:
        paper_trading_state.update({
            "last_status": "preparing_data",
            "last_message": f"正在优先补齐 {len(symbols)} 只持仓、自选及市场候选的行情、日线和风险数据。",
            "last_symbols": symbols,
        })
    try:
        fetch_and_store_quotes(symbols, force_refresh=force_refresh, trigger="paper-trading-decision", run_id=run_id)
    except MarketDataUnavailable as error:
        logger.info("paper candidate quote refresh unavailable: %s", error)
    # The routine persists daily bars and risk data. It deliberately keeps
    # its own lock, so a scheduler refresh cannot duplicate provider calls.
    refresh_derived_cache(symbols, "paper-trading-decision", force_history=force_refresh, run_id=run_id)


def prepare_paper_decisions(symbols: list[str], run_id: str | None = None) -> int:
    """Create a fresh, auditable decision only for a bounded market slice."""
    generated = 0
    paper_account = store.paper_account()
    paper_holdings = [
        {"symbol": item["symbol"], "name": item["name"], "quantity": item["quantity"], "average_cost": item["average_cost"], "created_at": item.get("updated_at")}
        for item in paper_account.get("positions", [])
    ]
    for symbol in symbols:
        stage_started_at = beijing_now().isoformat()
        quote = next(iter(store.cached_quotes([symbol])), None)
        daily_bars = store.daily_prices(symbol, 60)
        if not quote or quote.get("price") is None or len(daily_bars) < 60:
            reason = "missing_quote" if (not quote or quote.get("price") is None) else "insufficient_daily_bars"
            detail = {
                "reason": reason,
                "quote_price": quote.get("price") if quote else None,
                "daily_bar_count": len(daily_bars),
            }
            _record_simulation_symbol_state(run_id, symbol, "skipped_data_unavailable", detail)
            _record_simulation_stage(run_id, "decision", "skipped", symbol=symbol, detail={"terminal_state": "skipped_data_unavailable", **detail}, started_at=stage_started_at)
            continue
        latest = (store.decision_reports(symbol, 1) or [None])[0]
        if latest:
            try:
                if (beijing_now() - datetime.fromisoformat(str(latest["generated_at"]))).total_seconds() < PAPER_TRADING_INTERVAL_SECONDS:
                    _record_simulation_symbol_state(run_id, symbol, "decision_reused", {
                        "decision_id": str(latest.get("decision_id") or ""),
                        "generated_at": str(latest.get("generated_at") or ""),
                        "reason": "within_interval",
                    })
                    _record_simulation_stage(run_id, "decision", "ok", symbol=symbol, detail={
                        "terminal_state": "decision_reused",
                        "decision_id": str(latest.get("decision_id") or ""),
                        "reason": "within_interval",
                    }, started_at=stage_started_at)
                    generated += 1
                    continue
            except ValueError:
                pass
        if not store.instrument_metadata(symbol):
            store.save_instrument_metadata({"symbol": symbol, "market": "CN", "currency": "CNY", "lot_size": 100, "price_tick": 0.01, "source": "paper_market_default", "as_of": str(quote.get("as_of") or beijing_now().isoformat())})
        context = decision_context_builder.build(
            symbol,
            holdings_override=paper_holdings,
            available_cash_override=float(paper_account.get("available_cash") or 0),
        )
        store.save_decision_context(context.model_dump(mode="json"))
        report = decision_orchestrator.generate(context).model_dump(mode="json")
        store.save_decision_report(report)
        terminal_state = "blocked_by_gate" if str(report.get("status") or "").upper() == "BLOCKED" else "decision_generated"
        decision_detail = {
            "decision_id": str(report.get("decision_id") or ""),
            "action": report.get("action"),
            "status": report.get("status"),
            "data_quality_status": str((report.get("data_quality") or {}).get("status") or ""),
        }
        _record_simulation_symbol_state(run_id, symbol, terminal_state, decision_detail)
        _record_simulation_stage(run_id, "decision", "ok", symbol=symbol, detail={"terminal_state": terminal_state, **decision_detail}, started_at=stage_started_at)
        generated += 1
    return generated


def execute_due_paper_decisions(symbols: list[str], names: dict[str, str], run_id: str | None = None) -> tuple[int, int]:
    """Fill only a previous daily decision at a later market-session price."""
    positions = {str(item["symbol"]).strip().upper(): float(item["quantity"]) for item in store.paper_account().get("positions", [])}
    executed = skipped = 0
    for symbol in symbols:
        stage_started_at = beijing_now().isoformat()
        report = (store.decision_reports(symbol, 1) or [None])[0]
        quote = next(iter(store.cached_quotes([symbol])), None)
        if not report:
            _record_simulation_symbol_state(run_id, symbol, "not_due", {"reason": "no_decision_report"})
            _record_simulation_stage(run_id, "execution", "skipped", symbol=symbol, detail={"terminal_state": "not_due", "reason": "no_decision_report"}, started_at=stage_started_at)
            continue
        check = validate_daily_execution(report, quote)
        if not check.allowed:
            terminal_state = (
                "not_due" if check.reason == "execution_not_due_next_market_session"
                else "blocked_by_gate" if check.reason == "execution_action_gate_blocked"
                else "skipped_execution"
            )
            _record_simulation_symbol_state(run_id, symbol, terminal_state, {
                "decision_id": str(report.get("decision_id") or ""),
                "reason": check.reason,
            })
            _record_simulation_stage(run_id, "execution", "skipped", symbol=symbol, detail={"terminal_state": terminal_state, "reason": check.reason}, started_at=stage_started_at)
            continue
        action = str(report.get("action") or "").upper()
        sizing = report.get("sizing") or {}
        quantity = float(sizing.get("suggested_quantity") or sizing.get("target_quantity") or 0)
        price = float((quote or {}).get("price") or 0)
        side = "BUY" if action in {"OPEN", "ADD"} else "SELL" if action in {"REDUCE", "EXIT"} else None
        if not side or quantity <= 0 or price <= 0:
            _record_simulation_symbol_state(run_id, symbol, "skipped_execution", {
                "decision_id": str(report.get("decision_id") or ""),
                "reason": "invalid_side_or_sizing",
                "action": action, "quantity": quantity, "price": price,
            })
            _record_simulation_stage(run_id, "execution", "skipped", symbol=symbol, detail={"terminal_state": "skipped_execution", "reason": "invalid_side_or_sizing"}, started_at=stage_started_at)
            continue
        if side == "SELL" and positions.get(symbol, 0.0) <= 0:
            store.record_paper_skip(symbol=symbol, name=names.get(symbol, symbol), decision_id=str(report.get("decision_id") or "") or None, reason="paper_sell_blocked_no_position", price=price)
            _record_simulation_symbol_state(run_id, symbol, "skipped_execution", {"decision_id": str(report.get("decision_id") or ""), "reason": "paper_sell_blocked_no_position"})
            _record_simulation_stage(run_id, "execution", "skipped", symbol=symbol, detail={"terminal_state": "skipped_execution", "reason": "paper_sell_blocked_no_position"}, started_at=stage_started_at)
            skipped += 1
            continue
        if side == "SELL":
            quantity = min(quantity, positions.get(symbol, 0.0))
        try:
            store.execute_paper_trade(trade_id=str(uuid4()), symbol=symbol, name=names.get(symbol, symbol), side=side, quantity=quantity, price=price, decision_id=str(report.get("decision_id") or "") or None, reason=f"next_market_session:{action}; {str(report.get('summary') or '')[:180]}", execution_quote_at=str((quote or {}).get("as_of") or (quote or {}).get("retrieved_at") or "") or None, execution_quote_source=str((quote or {}).get("source") or "") or None, fill_price_mode="NEXT_ELIGIBLE_OBSERVED_QUOTE")
            _record_simulation_symbol_state(run_id, symbol, "executed", {
                "decision_id": str(report.get("decision_id") or ""),
                "side": side, "quantity": quantity, "price": price,
            })
            _record_simulation_stage(run_id, "execution", "ok", symbol=symbol, detail={"terminal_state": "executed", "side": side, "quantity": quantity, "price": price}, started_at=stage_started_at)
            executed += 1
            positions[symbol] = positions.get(symbol, 0.0) + (quantity if side == "BUY" else -quantity)
        except ValueError as error:
            if str(error) != "paper_decision_already_executed":
                store.record_paper_skip(symbol=symbol, name=names.get(symbol, symbol), decision_id=str(report.get("decision_id") or "") or None, reason=str(error), price=price)
                _record_simulation_symbol_state(run_id, symbol, "skipped_execution", {"decision_id": str(report.get("decision_id") or ""), "reason": str(error)})
                _record_simulation_stage(run_id, "execution", "skipped", symbol=symbol, detail={"terminal_state": "skipped_execution", "reason": str(error)}, started_at=stage_started_at)
                skipped += 1
            else:
                _record_simulation_symbol_state(run_id, symbol, "not_due", {"decision_id": str(report.get("decision_id") or ""), "reason": "decision_already_executed"})
                _record_simulation_stage(run_id, "execution", "skipped", symbol=symbol, detail={"terminal_state": "not_due", "reason": "decision_already_executed"}, started_at=stage_started_at)
    return executed, skipped


def run_paper_trading_cycle(symbols: list[str], force: bool = False, allow_when_disabled: bool = False) -> dict[str, object]:
    """Apply the sole persisted DecisionReport output to an isolated paper ledger."""
    global last_paper_trading_run_at
    if not allow_when_disabled and not store.system_settings()["paper_trading_enabled"]:
        with paper_trading_state_lock:
            paper_trading_state.update({"running": False, "last_status": "disabled", "last_message": "自动执行已关闭；可在系统管理中开启。"})
        return {"executed": 0, "skipped": 0, "run_id": None}
    configured_interval = int(store.system_settings().get("paper_trading_interval_seconds", PAPER_TRADING_INTERVAL_SECONDS))
    if not force and time.monotonic() - last_paper_trading_run_at < configured_interval:
        with paper_trading_state_lock:
            paper_trading_state.update({"running": False, "last_status": "waiting_interval", "last_message": "等待已配置的执行间隔；到期后会自动读取最新 AI 决策。"})
        return {"executed": 0, "skipped": 0, "run_id": None}
    with paper_trading_state_lock:
        paper_trading_state.update({"running": True, "last_started_at": beijing_now(), "last_status": "running", "last_message": "正在读取已保存的统一 AI 决策与交易账本", "last_symbols": symbols})
    last_paper_trading_run_at = time.monotonic()
    symbols = list(dict.fromkeys([*symbols, *paper_trading_symbols()]))[:PAPER_TRADING_CANDIDATE_LIMIT]
    names = paper_trading_names(symbols)
    run_id = _create_simulation_run("manual" if force else "scheduler", symbols, "交易运行开始")
    _record_simulation_stage(run_id, "candidate_pool", "ok", detail={"symbol_count": len(symbols), "symbols": symbols})
    executed = 0
    skipped = 0
    no_action_reasons: list[str] = []
    try:
        refresh_paper_candidate_data(symbols, force_refresh=force, run_id=run_id)
        names = paper_trading_names(symbols)
        with paper_trading_state_lock:
            paper_trading_state.update({"last_status": "researching", "last_message": "行情已同步，正在检索新闻并为可用候选生成 AI 决策。"})
        refresh_paper_market_intelligence(symbols, names)
        _record_simulation_stage(run_id, "news", "ok", detail={"symbol_count": len(symbols)})
        due_executed, due_skipped = execute_due_paper_decisions(symbols, names, run_id=run_id)
        executed += due_executed
        skipped += due_skipped
        generated_reports = prepare_paper_decisions(symbols, run_id=run_id)
        if not due_executed:
            no_action_reasons.append("本交易时段没有到期且可执行的历史决策")
        store.record_paper_equity_snapshot()
        _record_simulation_stage(run_id, "equity_snapshot", "ok", detail={})
        result = {"executed": executed, "skipped": skipped, "run_id": run_id}
        with paper_trading_state_lock:
            summary = f"本轮主动检索 {len(symbols)} 只市场候选，生成或复用 {generated_reports} 份 AI 决策，执行 {executed} 笔。"
            if not executed and no_action_reasons:
                summary += " 暂不交易：" + "；".join(no_action_reasons[:2]) + "。"
            paper_trading_state.update({"running": False, "last_finished_at": beijing_now(), "last_status": "completed", "last_message": summary, "last_executed": executed, "last_skipped": skipped, "last_run_id": run_id})
        _finish_simulation_run(run_id, "completed", summary, executed=executed, skipped=skipped, generated=generated_reports)
        return result
    except Exception as error:
        with paper_trading_state_lock:
            paper_trading_state.update({"running": False, "last_finished_at": beijing_now(), "last_status": "failed", "last_message": f"交易判断异常：{type(error).__name__}: {error}", "last_run_id": run_id})
        _finish_simulation_run(run_id, "failed", f"交易判断异常：{type(error).__name__}: {error}", executed=executed, skipped=skipped)
        raise


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
    global market_refresh_thread, history_backfill_thread
    draft_ids = store.draft_ids_needing_lookup()
    if draft_ids:
        Thread(target=resolve_holding_drafts, args=(draft_ids,), daemon=True).start()
    for job in store.ai_jobs():
        if job["status"] in {"pending", "retrying", "running"} and int(job["attempts"]) < int(job["max_attempts"]):
            store.update_ai_job(str(job["id"]), "pending")
            queue_background(run_ai_job, str(job["id"]))
    symbols = [str(item["symbol"]).strip().upper() for item in store.list()]
    # Market overview is independent of personal holdings: it always uses the
    # provider's whole-market snapshot and warms asynchronously on startup.
    Thread(target=refresh_market_intelligence, daemon=True, name="market-intelligence").start()
    if symbols:
        # Startup pre-warms latest quotes and daily derived data even while the
        # exchange is closed, so a restart never leaves the app blank.
        Thread(target=refresh_quote_cache, args=(symbols, True, "startup-prewarm"), daemon=True).start()
        Thread(target=refresh_derived_cache, args=(symbols, "startup-prewarm"), daemon=True).start()
    if MARKET_REFRESH_ENABLED and (market_refresh_thread is None or not market_refresh_thread.is_alive()):
        market_refresh_stop.clear()
        market_refresh_thread = Thread(target=scheduled_market_refresh_loop, daemon=True, name="market-refresh")
        market_refresh_thread.start()
    if HISTORY_BACKFILL_ENABLED and (history_backfill_thread is None or not history_backfill_thread.is_alive()):
        history_backfill_stop.clear()
        history_backfill_thread = Thread(target=history_backfill_loop, daemon=True, name="history-backfill")
        history_backfill_thread.start()


@app.on_event("shutdown")
def stop_background_work() -> None:
    market_refresh_stop.set()
    history_backfill_stop.set()


@app.get("/v1/market/quotes", response_model=list[MarketQuote])
def market_quotes(
    symbols: Annotated[list[str], Query()],
    background_tasks: BackgroundTasks,
    refresh: Annotated[bool, Query()] = False,
) -> list[MarketQuote]:
    """Backward-compatible GET wrapper; new clients should use the POST batch endpoint."""
    return resolve_market_quotes(symbols, refresh, background_tasks)


@app.get("/v1/market/cached-quotes", response_model=list[MarketQuote])
def cached_market_quotes(limit: int = Query(default=1000, ge=1, le=5000)) -> list[MarketQuote]:
    """Expose all locally stored market symbols for the market module."""
    return [MarketQuote.model_validate(item) for item in store.all_cached_quotes(limit)]


@app.get("/v1/market/intelligence", response_model=MarketIntelligence)
def cached_market_intelligence(refresh: bool = Query(default=False)) -> MarketIntelligence:
    """Read the persisted market dashboard snapshot; never blocks on AKShare."""
    if refresh:
        queue_background(refresh_market_intelligence)
    cached = store.cached_market_intelligence("overview")
    if cached:
        return MarketIntelligence.model_validate(cached)
    return MarketIntelligence(data_health="pending", error_message="大盘数据正在后台采集，请稍后刷新。")


@app.get("/v1/market/intelligence/sectors/{sector}", response_model=MarketSectorDetail)
def cached_sector_intelligence(sector: str, refresh: bool = Query(default=False)) -> MarketSectorDetail:
    """Read a cached sector constituent snapshot and optionally trigger its refresh."""
    cleaned = sector.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="板块名称不能为空")
    if refresh:
        queue_background(refresh_sector_intelligence, cleaned)
    cached = store.cached_market_intelligence(f"sector:{cleaned}")
    if cached:
        return MarketSectorDetail.model_validate(cached)
    return MarketSectorDetail(sector=cleaned, data_health="pending", error_message="板块成分股正在后台采集，请稍后刷新。")


@app.post("/v1/market/quotes/batch", response_model=list[MarketQuote])
def market_quotes_batch(payload: MarketQuoteBatchRequest, background_tasks: BackgroundTasks) -> list[MarketQuote]:
    """Fetch a batch without placing every symbol in the URL."""
    return resolve_market_quotes(payload.symbols, payload.refresh, background_tasks)


def resolve_market_quotes(
    symbols: list[str],
    refresh: bool,
    background_tasks: BackgroundTasks,
) -> list[MarketQuote]:
    """Return one result per symbol; one bad symbol never invalidates the batch."""
    requested = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))
    cached = store.cached_quotes(requested)
    cached_by_symbol = {str(item["symbol"]): item for item in cached}
    cached_symbols = set(cached_by_symbol)
    logger.info(
        "行情接口只读数据库 symbols=%s requested_refresh=%s cached_symbols=%s",
        ",".join(requested), refresh, ",".join(sorted(cached_symbols)) or "none",
    )
    if refresh and requested:
        # Return the current SQLite snapshot immediately; the requested refresh
        # is queued after the response rather than turning this read endpoint
        # into a synchronous AKShare request.
        queue_background(refresh_quote_cache, requested, True, "request-forced")
    return [
        MarketQuote.model_validate({**cached_by_symbol[symbol], "refresh_status": "stored"})
        if symbol in cached_by_symbol else MarketQuote.model_validate({
            **MarketDataService._failure_quote(
                symbol, "awaiting_scheduler_refresh", "行情尚未入库，等待服务端定时任务拉取。",
            ),
            "refresh_status": "pending",
        })
        for symbol in requested
    ]


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
    """Backward-compatible GET wrapper; new clients should use the POST resolve endpoint."""
    return resolve_market_symbols(names)


@app.post("/v1/market/symbols/resolve", response_model=list[SymbolLookupResult])
def market_symbol_resolve(payload: SymbolResolveRequest) -> list[SymbolLookupResult]:
    """Resolve names from OCR or manual input without putting them in the URL."""
    return resolve_market_symbols(payload.names)


def resolve_market_symbols(names: list[str]) -> list[SymbolLookupResult]:
    try:
        return [SymbolLookupResult.model_validate(item) for item in market_data.lookup_symbols(names)]
    except MarketDataUnavailable as error:
        raise HTTPException(status_code=503, detail={"message": str(error), "code": error.code}) from error


@app.get("/v1/risk/assessments", response_model=list[RiskAssessment])
def risk_assessments() -> list[RiskAssessment]:
    """Read persisted risk results only; collection never happens in an HTTP request."""
    items = []
    for holding in store.list():
        cached = store.cached_risk(str(holding["symbol"]))
        if cached:
            items.append({**cached, "name": str(holding["name"])})
        else:
            items.append({
                "symbol": str(holding["symbol"]), "name": str(holding["name"]),
                "horizon_trading_days": 5, "downside_threshold_percent": 5.0,
                "historical_downside_probability": 0.0, "annualized_volatility_percent": 0.0,
                "risk_level": "数据不足", "confidence": "低", "sample_count": 0,
                "as_of": "", "explanation": "", "status": "data_insufficient",
                "message": "历史日线正在后台准备，完成后会自动显示风险统计。",
            })
    return [RiskAssessment.model_validate(item) for item in items]

@app.get("/v1/portfolio/analysis", response_model=PortfolioAnalysis)
def portfolio_analysis() -> PortfolioAnalysis:
    payload = store.cached_portfolio_analysis()
    if payload is None:
        holdings = store.list()
        payload = assess_holdings(holdings, store.cached_quotes([str(item["symbol"]) for item in holdings]), store)
        payload["generated_at"] = beijing_now().isoformat()
    return PortfolioAnalysis.model_validate(payload)


@app.get("/v1/decisions/context/{symbol}", response_model=DecisionContext)
def decision_context(symbol: str) -> DecisionContext:
    """Persist and return a read-only phase-1 decision input snapshot."""
    try:
        context = decision_context_builder.build(symbol)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    store.save_decision_context(context.model_dump(mode="json"))
    return context


def run_decision_job(job_id: str) -> None:
    job = store.decision_job(job_id)
    if not job:
        logger.warning("decision job missing before execution job_id=%s", job_id)
        return
    logger.info("decision job started job_id=%s context_id=%s symbol=%s", job_id, job["context_id"], job["symbol"])
    store.update_decision_job(job_id, "running")
    try:
        context_payload = store.decision_context(str(job["context_id"]))
        if not context_payload:
            raise ValueError("decision context missing")
        report = decision_orchestrator.generate(DecisionContext.model_validate(context_payload))
        store.save_decision_report(report.model_dump(mode="json"))
        store.update_decision_job(job_id, "succeeded")
        logger.info("decision job succeeded job_id=%s symbol=%s ai_status=%s ai_error_code=%s", job_id, report.symbol, report.ai_status, report.ai_error_code)
    except Exception as error:
        logger.exception("decision job failed job_id=%s", job_id)
        store.update_decision_job(job_id, "failed", str(error)[:500])


@app.post("/v1/decisions/generate")
def generate_decisions(payload: DecisionGenerateRequest) -> dict[str, object]:
    jobs = []
    for symbol in dict.fromkeys(value.strip().upper() for value in payload.symbols):
        context = decision_context_builder.build(symbol)
        store.save_decision_context(context.model_dump(mode="json"))
        input_hash = context.input_hash if not payload.force else f"{context.input_hash}:{uuid4()}"
        job = store.enqueue_decision_job({"job_id": str(uuid4()), "context_id": context.context_id, "symbol": context.symbol, "input_hash": input_hash})
        jobs.append({"symbol": context.symbol, "job_id": job["job_id"], "status": job["status"]})
        logger.info("decision job %s job_id=%s context_id=%s symbol=%s", "enqueued" if job.get("is_new") else "reused", job["job_id"], context.context_id, context.symbol)
        if job["status"] == "pending" and job.get("is_new"):
            Thread(target=run_decision_job, args=(str(job["job_id"]),), daemon=True).start()
    return {"jobs": jobs}


@app.get("/v1/decisions/latest")
def latest_decision(symbol: str) -> dict[str, object]:
    reports = store.decision_reports(symbol, 1)
    if not reports:
        raise HTTPException(status_code=404, detail="decision not found")
    return reports[0]


@app.get("/v1/decisions/jobs/{job_id}")
def decision_job_status(job_id: str) -> dict[str, object]:
    job = store.decision_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="decision job not found")
    return job


@app.get("/v1/decisions")
def decision_history(symbol: str, limit: int = Query(default=50, ge=1, le=100)) -> list[dict[str, object]]:
    return store.decision_reports(symbol, limit)


@app.get("/v1/decisions/{decision_id}")
def decision_detail(decision_id: str) -> dict[str, object]:
    report = store.decision_report(decision_id)
    if not report:
        raise HTTPException(status_code=404, detail="decision not found")
    return report


@app.get("/v1/decisions/{decision_id}/lineage")
def decision_lineage(decision_id: str) -> dict[str, object]:
    lineage = store.decision_lineage(decision_id)
    if lineage is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return lineage


@app.get("/v1/data-quality/events")
def data_quality_events(symbol: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, object]]:
    return store.data_quality_events(symbol, limit)


@app.post("/v1/research-reports/{symbol}")
def generate_research_report(symbol: str) -> dict[str, object]:
    context = decision_context_builder.build(symbol)
    store.save_decision_context(context.model_dump(mode="json"))
    report = research_report_builder.build(context)
    store.save_research_report(report.model_dump(mode="json"))
    return report.model_dump(mode="json")


@app.get("/v1/research-reports/{symbol}")
def research_report_history(symbol: str, limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, object]]:
    return store.research_reports(symbol, limit)


@app.get("/v1/research-reports/detail/{report_id}")
def research_report_detail(report_id: str) -> dict[str, object]:
    report = store.research_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="research report not found")
    return report


@app.post("/v1/research-theses/from-report/{report_id}")
def create_research_thesis(report_id: str) -> dict[str, object]:
    report = store.research_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="research report not found")
    thesis = research_thesis_service.create(ResearchReport.model_validate(report))
    store.save_research_thesis(thesis.model_dump(mode="json"))
    return thesis.model_dump(mode="json")


@app.post("/v1/research-theses/{thesis_id}/review/{report_id}")
def review_research_thesis(thesis_id: str, report_id: str) -> dict[str, object]:
    previous = store.research_thesis(thesis_id)
    report = store.research_report(report_id)
    if not previous:
        raise HTTPException(status_code=404, detail="research thesis not found")
    if not report:
        raise HTTPException(status_code=404, detail="research report not found")
    prior = ThesisVersion.model_validate(previous)
    typed_report = ResearchReport.model_validate(report)
    if prior.symbol != typed_report.symbol:
        raise HTTPException(status_code=400, detail="research thesis symbol mismatch")
    current = research_thesis_service.create(typed_report, thesis_id=thesis_id, prior=prior)
    store.save_research_thesis(current.model_dump(mode="json"))
    return {"thesis": current.model_dump(mode="json"), "review": research_thesis_service.review_summary(prior, current)}


@app.get("/v1/research-theses/detail/{thesis_id}")
def research_thesis_detail(thesis_id: str, version: int | None = Query(default=None, ge=1)) -> dict[str, object]:
    thesis = store.research_thesis(thesis_id, version)
    if not thesis:
        raise HTTPException(status_code=404, detail="research thesis not found")
    return thesis


@app.get("/v1/research-theses/{symbol}")
def research_thesis_history(symbol: str, limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, object]]:
    return store.research_theses(symbol, limit)


@app.get("/v1/paper-trading/decision-audit/{decision_id}")
def paper_trading_decision_audit(decision_id: str) -> dict[str, object]:
    """Return the immutable report plus the exact input snapshot that produced it."""
    report = store.decision_report(decision_id)
    if not report:
        raise HTTPException(status_code=404, detail="decision not found")
    return {"report": report, "context": store.decision_context(str(report["context_id"])) or {}}


@app.get("/v1/decisions/evidence/{symbol}")
def decision_evidence(symbol: str) -> list[dict[str, object]]:
    """Return deterministic evidence for a newly persisted input context."""
    try:
        context = decision_context_builder.build(symbol)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    store.save_decision_context(context.model_dump(mode="json"))
    return [item.model_dump(mode="json") for item in evidence_engine.build(context)]


@app.get("/v1/decisions/shadow/{symbol}", response_model=ShadowDecisionReport)
def decision_shadow_report(symbol: str) -> ShadowDecisionReport:
    """Generate a policy-only shadow report; it never replaces existing recommendations."""
    if not config.DECISION_SHADOW_MODE:
        raise HTTPException(status_code=404, detail="decision shadow mode is disabled")
    try:
        context = decision_context_builder.build(symbol)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    evidence = evidence_engine.build(context)
    candidates = action_policy_engine.evaluate(context, evidence)
    ai_outcome = decision_ai_service.assess(context, evidence, candidates) if config.DECISION_AI_ENABLED else None
    guarded_assessment = decision_guard.guard(candidates, ai_outcome.assessment if ai_outcome else None)
    report = ShadowDecisionReport(
        shadow_id=str(uuid4()), context_id=context.context_id, symbol=context.symbol,
        generated_at=beijing_now(),
        status="BLOCKED" if context.data_quality.status == "blocked" else "DEGRADED" if context.data_quality.status == "degraded" else "READY",
        evidence=evidence, action_candidates=candidates,
        sizing=position_sizing_engine.size(context, candidates[0].action) if config.DECISION_SIZING_ENABLED else None,
        ai_assessment=guarded_assessment,
        guarded_preferred_action=guarded_assessment.preferred_action if guarded_assessment else None,
        policy_version=action_policy_engine.version, input_hash=context.input_hash,
    )
    store.save_decision_context(context.model_dump(mode="json"))
    store.save_shadow_report(report.model_dump(mode="json"))
    return report


@app.get("/v1/portfolio/impact-graph")
def portfolio_impact_graph(symbol: str | None = None) -> dict[str, object]:
    """Return a source-linked topology of current holding influences."""
    holdings = store.list()
    symbols = [str(item["symbol"]) for item in holdings]
    return build_impact_graph(holdings, store.cached_quotes(symbols), store, symbol=symbol)

@app.get("/v1/learning-cases", response_model=list[LearningCase])
def list_learning_cases(symbol: str | None = None) -> list[LearningCase]:
    return [LearningCase.model_validate(item) for item in store.learning_cases(symbol)]

@app.post("/v1/learning-cases", response_model=LearningCase, status_code=status.HTTP_201_CREATED)
def create_learning_case(payload: LearningCaseInput) -> LearningCase:
    item = {"id": str(uuid4()), **payload.model_dump(), "created_at": beijing_now().isoformat()}
    return LearningCase.model_validate(store.add_learning_case(item))


@app.put("/v1/learning-cases/{case_id}", response_model=LearningCase)
def update_learning_case(case_id: str, payload: LearningCaseInput) -> LearningCase:
    item = store.update_learning_case(case_id, payload.model_dump())
    if not item:
        raise HTTPException(status_code=404, detail="复盘记录不存在或已删除。")
    return LearningCase.model_validate(item)


@app.delete("/v1/learning-cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_learning_case(case_id: str) -> None:
    if not store.delete_learning_case(case_id):
        raise HTTPException(status_code=404, detail="复盘记录不存在或已删除。")


def _local_learning_case_analysis(cases: list[dict[str, object]]) -> LearningCaseAnalysis:
    """Useful offline fallback; it summarizes only user-authored review fields."""
    lessons = [str(case.get("lesson", "")).strip() for case in cases if str(case.get("lesson", "")).strip()]
    outcomes = [str(case.get("outcome", "")).strip() for case in cases if str(case.get("outcome", "")).strip()]
    symbols = sorted({str(case["symbol"]).upper() for case in cases if case.get("symbol")})
    scope = "、".join(symbols[:3]) if symbols else "组合"
    recurring = [f"已累计 {len(cases)} 条复盘记录；重点回看重复出现的判断依据与结果。"]
    if lessons:
        recurring.append(f"最近的复盘教训：{lessons[0][:80]}")
    focus = ["下次先记录可验证的判断依据，再记录实际结果。"]
    if outcomes:
        focus.append(f"核验上一条结果：{outcomes[0][:80]}")
    return LearningCaseAnalysis(
        summary=f"离线复盘总结：{scope} 共 {len(cases)} 条记录。当前为本地归纳，AI 服务恢复后可生成更完整的重复模式分析。",
        recurring_patterns=recurring[:5], next_review_focus=focus[:5],
        confidence="low" if len(cases) < 3 else "medium",
    )


@app.post("/v1/learning-cases/analysis", response_model=LearningCaseAnalysis)
def analyze_learning_cases() -> LearningCaseAnalysis:
    """Summarize the user's own review records without producing trading advice."""
    cases = store.learning_cases(None)
    if not cases:
        raise HTTPException(status_code=422, detail="请先至少保存一条复盘记录，再生成 AI 分析。")
    if not ai_analysis_service.client.enabled:
        return _local_learning_case_analysis(cases)

    compact_cases = [{
        "title": item.get("title"),
        "symbol": item.get("symbol"),
        "context": item.get("context"),
        "lesson": item.get("lesson"),
        "outcome": item.get("outcome"),
        "confidence": item.get("confidence"),
    } for item in cases[:20]]
    messages = [
        {
            "role": "system",
            "content": (
                "你是投资复盘记录的学习辅助工具。仅基于用户提供的复盘记录，归纳可验证的重复模式和下一次复盘关注点。"
                "不得预测价格、不得给出买卖建议、不得把推断写成事实。"
                "只输出 JSON：summary、recurring_patterns、next_review_focus、confidence；confidence 只能是 low、medium、high。"
            ),
        },
        {"role": "user", "content": json.dumps({"review_cases": compact_cases}, ensure_ascii=False)},
    ]
    try:
        response = ai_analysis_service.client.chat_json(
            messages, model=ai_analysis_service.model, max_tokens=700, thinking=False,
        )
        return LearningCaseAnalysis.model_validate_json(response.content.strip().removeprefix("```json").removesuffix("```").strip())
    except (LlmClientError, ValueError, json.JSONDecodeError) as error:
        logger.warning("复盘 AI 分析失败: %s", error)
        return _local_learning_case_analysis(cases)

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


@app.get("/v1/trade-plans", response_model=list[TradePlan])
def list_trade_plans() -> list[TradePlan]:
    return [TradePlan.model_validate(item) for item in store.trade_plans()]


@app.get("/v1/trade-plans/draft/{symbol}", response_model=TradePlanDraft)
def trade_plan_draft(symbol: str) -> TradePlanDraft:
    """Return editable, conservative defaults; never infer a user's investment thesis."""
    normalized = symbol.strip().upper()
    holding = next((item for item in store.list() if str(item["symbol"]).upper() == normalized), None)
    name = str(holding["name"]) if holding else normalized
    risk = store.cached_risk(normalized) or {}
    rules = [item for item in store.personal_rules() if item.get("enabled")]
    rule = next((item for item in rules if item.get("scope") == "symbol" and item.get("symbol") == normalized), next((item for item in rules if item.get("scope") == "global"), None))
    volatility = float(risk.get("annualized_volatility_percent") or 0)
    high_volatility = volatility >= 40
    rule_cap = float(rule["max_position_percent"]) if rule else 15.0
    max_position = min(rule_cap, 10.0) if high_volatility else rule_cap
    risk_budget = 1.0 if high_volatility else 2.0
    risk_note = f"当前年化波动 {volatility:.1f}% 偏高，已采用更保守的仓位与风险预算。" if high_volatility else "已按个人仓位上限和常用波段风险预算预填。"
    return TradePlanDraft(
        symbol=normalized, horizon="swing",
        thesis=f"待确认：{name} 的持有依据（请补充业绩、估值或行业逻辑）。",
        market_expectation="待确认：市场已计入的主要预期，以及与预期相反的风险。",
        catalysts=["财报披露", "行业数据", "公司公告"],
        entry_condition="仅在交易逻辑仍成立且风险预算允许时，分批执行。",
        add_condition="仅在逻辑强化、仓位低于上限且未触发风险条件时考虑。",
        reduce_condition="仓位接近上限、风险恶化或逻辑弱化时，复核减仓。",
        exit_condition="交易逻辑失效、核心事实被证伪或触发风险边界时退出。",
        max_position_percent=max_position, risk_budget_percent=risk_budget,
        notice=f"这是可编辑的研究草案，不是交易建议。{risk_note}",
    )


@app.post("/v1/trade-plans", response_model=TradePlan)
def save_trade_plan(payload: TradePlanInput) -> TradePlan:
    item = {"id": str(uuid4()), **payload.model_dump(), "version": 1}
    return TradePlan.model_validate(store.save_trade_plan(item))


@app.post("/v1/glossary/lookup", response_model=GlossaryCard)
def glossary_lookup(payload: GlossaryLookupInput) -> GlossaryCard:
    """Look up a highlighted or user-selected term and retain the query for reuse."""
    return lookup_glossary(payload.term, payload.context)


@app.post("/v1/glossary", response_model=GlossaryCard)
def save_glossary_entry(payload: GlossaryEntryInput) -> GlossaryCard:
    term = payload.term.strip()
    item = store.save_glossary_entry({
        "term_key": glossary_key(term), "term": term,
        "plain_explanation": payload.plain_explanation.strip(), "watch_for": payload.watch_for.strip(),
        "source": "user", "updated_at": beijing_now().isoformat(),
    })
    return GlossaryCard(
        term=str(item["term"]), plain_explanation=str(item["plain_explanation"]),
        watch_for=str(item["watch_for"]), source="user",
    )


@app.get("/v1/glossary", response_model=list[GlossaryCard])
def list_glossary_entries() -> list[GlossaryCard]:
    return [GlossaryCard(term=str(item["term"]), plain_explanation=str(item["plain_explanation"]), watch_for=str(item["watch_for"]), source=str(item["source"])) for item in store.glossary_entries()]


@app.get("/v1/glossary/{term}", response_model=GlossaryCard)
def glossary(term: str) -> GlossaryCard:
    """Compatibility endpoint; unlike the old version it also logs and finds saved terms."""
    return lookup_glossary(term)


@app.get("/v1/holdings", response_model=list[Holding])
def list_holdings() -> list[Holding]:
    return [Holding.model_validate(item) for item in store.list()]


@app.get("/v1/account/cash", response_model=AvailableCash)
def get_available_cash() -> AvailableCash:
    return AvailableCash.model_validate(store.available_cash())


@app.put("/v1/account/cash", response_model=AvailableCash)
def set_available_cash(payload: AvailableCashInput) -> AvailableCash:
    return AvailableCash.model_validate(store.save_available_cash(payload.available_cash))


@app.post("/v1/holdings", response_model=Holding, status_code=status.HTTP_201_CREATED)
def create_holding(payload: HoldingInput, background_tasks: BackgroundTasks) -> Holding:
    item = store.add(str(uuid4()), **payload.model_dump())
    queue_background(refresh_quote_cache, [item["symbol"]], True, "holding-created")
    queue_background(refresh_derived_cache, [item["symbol"]], "holding-created")
    return Holding.model_validate(item)


@app.delete("/v1/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(holding_id: str) -> Response:
    if not store.delete(holding_id):
        raise HTTPException(status_code=404, detail="未找到持仓")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.put("/v1/holdings/{holding_id}", response_model=Holding)
def update_holding(holding_id: str, payload: HoldingInput, background_tasks: BackgroundTasks) -> Holding:
    item = store.update(holding_id, **payload.model_dump())
    if not item: raise HTTPException(status_code=404, detail="未找到持仓")
    queue_background(refresh_quote_cache, [item["symbol"]], True, "holding-updated")
    queue_background(refresh_derived_cache, [item["symbol"]], "holding-updated")
    return Holding.model_validate(item)


@app.post("/v1/holdings/{holding_id}/sales", response_model=SaleRecord, status_code=status.HTTP_201_CREATED)
def sell_holding(holding_id: str, payload: SaleInput) -> SaleRecord:
    analysis = store.cached_portfolio_analysis() or {}
    analysis_item = next((item for item in analysis.get("items", []) if str(item.get("symbol")) == str(next((h["symbol"] for h in store.list() if str(h["id"]) == holding_id), ""))), {})
    try:
        item = store.sell_holding(holding_id, str(uuid4()), payload.quantity, payload.sale_price, payload.reason, analysis_item)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if item is None:
        raise HTTPException(status_code=404, detail="未找到持仓")
    return SaleRecord.model_validate(item)


@app.get("/v1/sales", response_model=list[SaleRecord])
def list_sales(symbol: str | None = None) -> list[SaleRecord]:
    return [SaleRecord.model_validate(item) for item in store.sale_records(symbol)]


@app.get("/v1/research/targets", response_model=list[ResearchTarget])
def list_research_targets() -> list[ResearchTarget]:
    """Keep fully sold symbols available for research, review, and later re-entry."""
    return [ResearchTarget.model_validate(item) for item in store.research_targets()]


@app.get("/v1/watchlist", response_model=list[WatchlistItem])
def list_watchlist() -> list[WatchlistItem]:
    return [WatchlistItem.model_validate(item) for item in store.watchlist()]


@app.post("/v1/watchlist", response_model=WatchlistItem, status_code=status.HTTP_201_CREATED)
def save_watchlist_item(payload: WatchlistInput) -> WatchlistItem:
    name = payload.name.strip()
    symbol = payload.symbol.strip().upper()
    if not name:
        cached = next(iter(store.cached_quotes([symbol])), None)
        name = str((cached or {}).get("name") or "").strip()
    if not name:
        try:
            result = market_data.lookup_symbols([symbol])
            matches = (result[0] if result else {}).get("matches", [])
            exact = next((item for item in matches if str(item.get("symbol", "")).strip().upper() == symbol), None)
            name = str((exact or {}).get("name") or "").strip()
        except MarketDataUnavailable as error:
            raise HTTPException(status_code=503, detail=f"暂时无法补齐股票名称：{error}") from error
    if not name:
        raise HTTPException(status_code=422, detail="未能根据股票代码识别名称，请核对代码或手动填写名称")
    return WatchlistItem.model_validate(store.save_watchlist_item(symbol, name))


@app.delete("/v1/watchlist/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist_item(symbol: str) -> Response:
    if not store.delete_watchlist_item(symbol):
        raise HTTPException(status_code=404, detail="未找到自选股")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/v1/market/history/{symbol}", response_model=list[DailyPrice])
def market_history(
    symbol: str,
    limit: int = Query(default=120, ge=20, le=800),
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[DailyPrice]:
    """Persisted daily bars only; chart rendering never queries an upstream source."""
    normalized_symbol = symbol.strip().upper()
    if start_date or end_date:
        if not (start_date and end_date) or start_date > end_date:
            raise HTTPException(status_code=422, detail="start_date and end_date must form a valid range")
        return [DailyPrice.model_validate(item) for item in store.daily_prices_between(
            normalized_symbol, start_date.isoformat(), end_date.isoformat(), 2000,
        )]
    return [DailyPrice.model_validate(item) for item in store.daily_prices(normalized_symbol, limit)]


@app.post("/v1/market/history/{symbol}/refresh", response_model=list[DailyPrice])
def refresh_market_history(symbol: str, payload: MarketHistoryRefreshRequest = MarketHistoryRefreshRequest()) -> list[DailyPrice]:
    """Manually retry one symbol's daily-history provider chain for mobile charts."""
    normalized_symbol = symbol.strip().upper()
    try:
        bar_count = (
            price_history_service.refresh(
                store, normalized_symbol,
                payload.start_date.isoformat(), payload.end_date.isoformat(),
                trigger="manual-daily-history-refresh",
            )
            if payload.start_date and payload.end_date
            else price_history_service.refresh(store, normalized_symbol, trigger="manual-daily-history-refresh")
        )
        daily_history_attempted_for[normalized_symbol] = beijing_now().date().isoformat()
        daily_history_refreshed_for[normalized_symbol] = beijing_now().date().isoformat()
        daily_history_retry_after.pop(normalized_symbol, None)
        logger.info(
            "历史日线手动刷新成功 symbol=%s bar_count=%s",
            normalized_symbol,
            bar_count,
        )
    except PriceHistoryUnavailable as error:
        daily_history_retry_after[normalized_symbol] = time.monotonic() + DAILY_HISTORY_RETRY_SECONDS
        logger.warning(
            "历史日线手动刷新失败 symbol=%s error=%s retry_after_seconds=%s",
            normalized_symbol,
            error,
            DAILY_HISTORY_RETRY_SECONDS,
        )
        raise HTTPException(status_code=503, detail=str(error)) from error
    queue_background(refresh_derived_cache, [normalized_symbol], "manual-daily-history-refresh")
    if payload.start_date and payload.end_date:
        return [DailyPrice.model_validate(item) for item in store.daily_prices_between(
            normalized_symbol, payload.start_date.isoformat(), payload.end_date.isoformat(), 2000,
        )]
    return [DailyPrice.model_validate(item) for item in store.daily_prices(normalized_symbol, 800)]


@app.get("/v1/news/cached", response_model=list[NewsItem])
def cached_news(
    limit: int = Query(default=20, ge=1, le=80), offset: int = Query(default=0, ge=0),
    scope: Literal["all", "paper_positions", "learning_cases"] = Query(default="all"),
) -> list[NewsItem]:
    """Fast, time-complete and scope-aware local news read for the mobile home screen."""
    if scope == "paper_positions":
        symbols = [str(item["symbol"]) for item in store.paper_account().get("positions", [])]
    elif scope == "learning_cases":
        symbols = [str(item["symbol"]) for item in store.learning_cases() if item.get("symbol")]
    else:
        symbols = []
    # Do not present a date-only item as if it were a real-time news event.
    # Read a bounded cache batch, sort by actual publication time, then page.
    items = store.cached_content(symbols or None, limit=5000)
    complete = [item for item in items if re.search(r"\d{2}:\d{2}:\d{2}", str(item.get("published_at") or ""))]
    ordered = sorted(complete, key=lambda item: str(item.get("published_at") or ""), reverse=True)
    return [NewsItem.model_validate(item) for item in ordered[offset:offset + limit]]


@app.delete("/v1/market/history/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def delete_market_history(symbol: str) -> Response:
    """Purge one symbol's daily cache; use this to remove known-bad provider data."""
    store.delete_daily_prices(symbol)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/v1/market/intraday/{symbol}", response_model=list[IntradayPrice])
def market_intraday(symbol: str, limit: int = Query(default=500, ge=20, le=1500)) -> list[IntradayPrice]:
    """SQLite-only minute bars; collection occurs in the scheduler/background task."""
    return [IntradayPrice.model_validate(item) for item in store.intraday_prices(symbol.strip().upper(), limit)]


@app.post("/v1/daily-reviews/generate", response_model=DailyReview, status_code=status.HTTP_201_CREATED)
def generate_daily_review(payload: DailyReviewGenerateRequest = DailyReviewGenerateRequest()) -> DailyReview:
    """Create a daily snapshot through the same policy used by the workbench."""
    holdings = {str(item["symbol"]): item for item in store.list()}
    watchlist = {str(item["symbol"]): item for item in store.watchlist()}
    default_symbols = [*holdings, *(symbol for symbol in watchlist if symbol not in holdings)]
    symbols = list(dict.fromkeys(item.strip().upper() for item in (payload.symbols or default_symbols)))
    if not symbols:
        review = {
            "id": str(uuid4()), "review_date": beijing_now().date().isoformat(), "generated_at": beijing_now().isoformat(),
            "suggested_position_band": "等待录入持仓或选择标的",
            "market_snapshot": {"symbols_considered": [], "ready_items": 0, "blocked_items": 0, "available_cash": float(store.available_cash()["available_cash"]), "data_basis": []},
            "items": [], "status": "pending", "highlights": ["尚未选择复盘标的；录入持仓后可生成包含行情与计划核验的复盘。"], "mistakes": [],
        }
        return DailyReview.model_validate(store.save_daily_review(review))
    quotes = {str(item["symbol"]): item for item in store.cached_quotes(symbols)}
    cash = float(store.available_cash()["available_cash"])
    items: list[dict[str, object]] = []
    review_dates: list[str] = []
    blocked = 0
    for symbol in symbols:
        bars = store.daily_prices(symbol)
        if bars and len(str(bars[-1].get("trading_date", ""))) == 10:
            review_dates.append(str(bars[-1]["trading_date"]))
        context = decision_context_builder.build(symbol)
        evidence = evidence_engine.build(context)
        policy = action_policy_engine.evaluate(context, evidence)[0]
        policy_action = policy.action
        action = {"ADD": "add", "OPEN": "add", "REDUCE": "trim", "EXIT": "trim"}.get(policy_action, "watch")
        if action == "watch":
            blocked += 1
            reference_price = float((quotes.get(symbol) or {}).get("price") or (bars[-1]["close"] if bars else 0))
            items.append({
                "symbol": symbol,
                "name": str((holdings.get(symbol) or watchlist.get(symbol) or {}).get("name", "")),
                "action": "watch",
                "suggested_quantity": None,
                "price_zone": None,
                "invalidation_price": None,
                "rationale": f"与工作台共用决策规则：当前为 {policy_action}，缺少实时行情或必要决策数据，暂不生成交易数量。",
                "reference_price": reference_price,
            })
            continue
        sizing = position_sizing_engine.size(context, policy_action)
        reference_price = float(context.quote.price) if context.quote else float(bars[-1]["close"])
        items.append({
            "symbol": symbol,
            "name": str((holdings.get(symbol) or watchlist.get(symbol) or {}).get("name", "")),
            "action": action,
            "suggested_quantity": sizing.suggested_quantity if sizing.status == "ready" else None,
            "price_zone": None,
            "invalidation_price": sizing.invalidation_price,
            "rationale": f"与工作台共用决策规则：{policy_action}；数量由统一风控仓位计算（{sizing.status}）。",
            "reference_price": reference_price,
        })
    review_date = max(review_dates) if review_dates else beijing_now().date().isoformat()
    max_position = next((float(rule["max_position_percent"]) for rule in store.personal_rules() if rule.get("scope") == "global" and rule.get("enabled")), 20.0)
    band = "防守 0–30%" if blocked else f"单标的上限 {max_position:.0f}%"
    # A partial data set is not a market call.  The former "0-30% defensive"
    # label was only a fallback marker and was easily mistaken for a position
    # instruction, so do not publish a numeric band in that state.
    if blocked:
        band = "Data incomplete: no portfolio band"
    review = {
        "id": str(uuid4()), "review_date": review_date, "generated_at": beijing_now().isoformat(),
        "suggested_position_band": band,
        "market_snapshot": {"symbols_considered": symbols, "ready_items": len(items), "blocked_items": blocked, "available_cash": cash, "data_basis": ["日线", "行情快照", "持仓", "交易计划", "个人仓位规则"]},
        "items": items, "status": "pending", "highlights": [], "mistakes": [],
    }
    return DailyReview.model_validate(store.save_daily_review(review))


@app.get("/v1/daily-reviews", response_model=list[DailyReview])
def list_daily_reviews(limit: int = Query(default=30, ge=1, le=180)) -> list[DailyReview]:
    return [DailyReview.model_validate(item) for item in store.daily_reviews(limit)]


@app.put("/v1/daily-reviews/{review_id}/items/{symbol}/execution", response_model=DailyReview)
def record_daily_review_execution(review_id: str, symbol: str, payload: DailyReviewExecutionInput) -> DailyReview:
    review = store.daily_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="未找到该盘后计划。")
    normalized = symbol.strip().upper()
    item = next((entry for entry in review["items"] if str(entry["symbol"]).upper() == normalized), None)
    if not item:
        raise HTTPException(status_code=404, detail="该计划中没有此标的。")
    if payload.execution_status in {"executed", "partial"} and (payload.executed_quantity <= 0 or payload.executed_price is None):
        raise HTTPException(status_code=422, detail="已执行或部分执行时，需要填写实际成交数量和价格。")
    item.update({"execution_status": payload.execution_status, "executed_quantity": payload.executed_quantity, "executed_price": payload.executed_price, "execution_note": payload.note})
    return DailyReview.model_validate(store.save_daily_review(review))


@app.post("/v1/daily-reviews/{review_id}/evaluate", response_model=DailyReview)
def evaluate_daily_review(review_id: str) -> DailyReview:
    review = store.daily_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="未找到该盘后计划。")
    theoretical_total = actual_total = 0.0
    completed = 0
    highlights: list[str] = []
    mistakes: list[str] = []
    for item in review["items"]:
        # Observation is not a trade signal.  It must neither create simulated
        # P&L nor pollute the execution/review state.
        if item.get("action") == "watch" or not item.get("suggested_quantity"):
            continue
        future = [bar for bar in store.daily_prices(str(item["symbol"])) if str(bar["trading_date"]) > str(review["review_date"])]
        if not future:
            continue
        close = float(future[0]["close"])
        direction = -1 if item["action"] == "trim" else 1
        quantity = float(item.get("suggested_quantity") or 0)
        planned = (close - float(item["reference_price"])) * quantity * direction
        item["theoretical_pnl"] = round(planned, 2)
        theoretical_total += planned
        if item.get("execution_status") in {"executed", "partial"}:
            actual = (close - float(item["executed_price"])) * float(item.get("executed_quantity") or 0) * direction
            item["actual_pnl"] = round(actual, 2)
            actual_total += actual
            if (planned >= 0) == (actual >= 0):
                highlights.append(f"{item['symbol']}：执行结果与计划方向一致。")
            else:
                mistakes.append(f"{item['symbol']}：实际成交价或数量使结果偏离计划，需要复核执行条件。")
        elif item.get("execution_status") == "skipped":
            mistakes.append(f"{item['symbol']}：计划未执行，已保留为执行偏差记录。")
        else:
            mistakes.append(f"{item['symbol']}：尚未录入是否执行，无法评价实际账户结果。")
        completed += 1
    if not completed:
        # A review whose items are all observation (watch) entries, or that has
        # no next-day close data, still closes the plan-execution loop.  It is
        # marked evaluated but produces no theoretical P&L, so a watch item never
        # manufactures a paper trade just to make the daily page active.
        review.update({
            "status": "evaluated",
            "evaluated_at": beijing_now().isoformat(),
            "theoretical_pnl": None,
            "actual_pnl": 0.0,
            "highlights": highlights[:6] or ["本轮无建议参与计算：所有条目为观察项或缺少下一交易日收盘数据。"],
            "mistakes": mistakes[:6],
        })
        return DailyReview.model_validate(store.save_daily_review(review))
    if theoretical_total >= 0:
        highlights.insert(0, "计划组合按下一交易日收盘衡量为正收益；这仅是单日验证，不代表策略有效性。")
    else:
        mistakes.insert(0, "计划组合按下一交易日收盘衡量为负收益；应复核市场环境、条件触发与风险边界。")
    review.update({"status": "evaluated", "evaluated_at": beijing_now().isoformat(), "theoretical_pnl": round(theoretical_total, 2), "actual_pnl": round(actual_total, 2), "highlights": highlights[:6], "mistakes": mistakes[:6]})
    return DailyReview.model_validate(store.save_daily_review(review))


@app.post("/v1/research-recommendations/generate", response_model=list[ResearchRecommendation])
def generate_recommendations(payload: RecommendationRequest) -> list[ResearchRecommendation]:
    holdings = {str(item["symbol"]): item for item in store.list()}
    quotes = {str(item["symbol"]): item for item in store.cached_quotes(payload.symbols)}
    results = []
    for symbol in dict.fromkeys(item.strip().upper() for item in payload.symbols):
        bars = store.daily_prices(symbol)
        item = {"id": str(uuid4()), "generated_at": beijing_now().isoformat(), "generated_trading_date": str(bars[-1]["trading_date"]) if bars else None, "evaluation_status": "pending", **build_candidate(symbol, holdings.get(symbol), quotes.get(symbol), bars, store.trade_plan(symbol), float(store.available_cash()["available_cash"]))}
        store.save_recommendation(item)
        store.save_recommendation_events(str(item["id"]), list(item.get("trigger_events", [])))
        results.append(item)
    return [ResearchRecommendation.model_validate(item) for item in results]


@app.get("/v1/research-recommendations", response_model=list[ResearchRecommendation])
def list_recommendations(symbol: str | None = None) -> list[ResearchRecommendation]:
    return [ResearchRecommendation.model_validate(item) for item in store.recommendations(symbol)]


@app.get("/v1/opportunity-scan", response_model=OpportunityScan)
def opportunity_scan(limit: int = Query(default=15, ge=1, le=15)) -> OpportunityScan:
    """Rank holdings, watchlist, and market candidates in one explainable daily pool."""
    with universe_scan_state_lock:
        state = dict(universe_scan_state)
    candidate_metadata = dict(state.get("candidates") or {})
    holding_by_symbol = {str(item["symbol"]): item for item in store.list()}
    watchlist_by_symbol = {str(item["symbol"]): item for item in store.watchlist()}
    symbols = list(dict.fromkeys([*holding_by_symbol, *watchlist_by_symbol, *candidate_metadata]))
    if not symbols:
        symbols = store.opportunity_symbols(limit=500)
    quotes = {str(item["symbol"]): item for item in store.cached_quotes(symbols)}
    candidates: list[OpportunityScanItem] = []
    for symbol in symbols:
        bars = store.daily_prices(symbol, 80)
        quote = quotes.get(symbol)
        sources = list(filter(None, [
            "holding" if symbol in holding_by_symbol else None,
            "watchlist" if symbol in watchlist_by_symbol else None,
            "market" if symbol in candidate_metadata else None,
        ])) or ["market"]
        sector = candidate_metadata.get(symbol, {}).get("sector")
        sector_change = next((float(item["change_percent"]) for item in state.get("hot_sectors", []) if item["name"] == sector), None)
        metrics = score_opportunity(
            quote=quote, bars=bars, risk=store.cached_risk(symbol),
            sector_change_percent=sector_change, sources=sources,
        )
        name = str(
            holding_by_symbol.get(symbol, {}).get("name")
            or watchlist_by_symbol.get(symbol, {}).get("name")
            or candidate_metadata.get(symbol, {}).get("name")
            or (quote or {}).get("name")
            or symbol
        )
        if not quote or quote.get("price") is None or len(bars) < 20:
            candidates.append(OpportunityScanItem(
                symbol=symbol, name=name, sector=sector, sources=sources,
                action="watch", score=int(metrics["score"]), confidence=int(metrics["confidence"]),
                upside_likelihood=int(metrics["upside_likelihood"]), risk_level=str(metrics["risk_level"]),
                summary="已加入每日候选池，正在补齐行情或日线；当前不生成买入结论。",
                reasons=list(metrics["factors"]), buy_condition="等待行情和至少 20 日日线补齐后重新评分。",
                avoid_condition="数据未完成前不追高、不据此下单。", invalidation_price=None,
                data_as_of=str(bars[-1]["trading_date"]) if bars else None,
            ))
            continue
        closes = [float(bar["close"]) for bar in bars]
        price = float(quote["price"])
        high20, low20 = max(closes[-20:]), min(closes[-20:])
        holding = holding_by_symbol.get(symbol)
        action: Literal["watch", "add", "trim"] = "trim" if holding and price >= high20 else "watch"
        if action == "trim":
            summary = "已有持仓接近近期高位，优先检查减仓或继续持有的条件。"
            buy_condition = "不新增仓位；先核对既有计划是否允许减仓。"
        else:
            summary = "值得加入明日观察，不是“必涨”或立即买入信号。"
            buy_condition = f"只有价格不明显高开、回到 {max(low20, price * .97):.2f} 至 {min(high20, price * 1.01):.2f} 区间并保持活跃时，再建立交易计划。"
        candidates.append(OpportunityScanItem(
            symbol=symbol, name=name, sector=sector, sources=sources, action=action,
            score=int(metrics["score"]), confidence=int(metrics["confidence"]),
            upside_likelihood=int(metrics["upside_likelihood"]), risk_level=str(metrics["risk_level"]),
            summary=summary, reasons=list(metrics["factors"]),
            buy_condition=buy_condition,
            avoid_condition=f"若跌破 {low20 * .97:.2f}，或高开后快速回落，就停止关注本次机会。",
            invalidation_price=round(low20 * .97, 2), data_as_of=str(bars[-1]["trading_date"]),
        ))
    # Actual position actions must be visible before informational WATCH items.
    ordered = sorted(
        candidates,
        key=lambda item: (0 if item.action == "trim" else 1, -item.score, -item.confidence),
    )[:limit]
    sector_labels = [f"{item['name']} {float(item['change_percent']):+.2f}%" for item in state.get("hot_sectors", [])]
    coverage = (
        f"全市场定时扫描已选出 {len(candidate_metadata)} 只热点候选，其中 {len(symbols)} 只已补齐至少 60 日日线并进入分析。"
        if candidate_metadata else
        f"暂未完成全市场扫描；当前仅有 {len(symbols)} 只本地标的具备行情和至少 60 日日线。"
    )
    return OpportunityScan(generated_at=beijing_now(), coverage_note=coverage, hot_sectors=sector_labels, items=ordered)


@app.post("/v1/opportunity-scan/refresh", response_model=OpportunityScan)
def refresh_opportunity_scan(limit: int = Query(default=15, ge=1, le=15)) -> OpportunityScan:
    """Refresh the A-share universe before reading only fully evidenced candidates.

    It is intentionally separate from the GET endpoint: callers can refresh
    public providers explicitly, while ordinary screen reloads use the local
    cache and do not repeatedly download a whole-market snapshot.
    """
    try:
        refresh_universe_opportunity_inputs("user-whole-market-refresh")
    except MarketDataUnavailable as error:
        raise HTTPException(status_code=503, detail={
            "code": error.code,
            "message": str(error),
            "next_step": "请稍后重试；若持续失败，请检查 AKShare 网络连接和 Tushare Token 配置。",
        }) from error
    return opportunity_scan(limit)


@app.post("/v1/research-recommendations/evaluate")
def evaluate_recommendations() -> dict[str, int]:
    evaluated = untriggered = legacy_unverifiable = 0
    for item in store.recommendations():
        if item.get("status") != "ready" or item.get("suggested_quantity") is None: continue
        bars = store.daily_prices(str(item["symbol"]))
        if not item.get("generated_trading_date"):
            if store.set_recommendation_evaluation_status(str(item["id"]), "legacy_unverifiable"):
                store.save_recommendation_events(str(item["id"]), [{"event_type": "legacy_unverifiable", "trading_date": None, "trigger_price": None}])
            legacy_unverifiable += 1
            continue
        fill, index = first_fill(item, bars)
        if fill is None:
            if store.set_recommendation_evaluation_status(str(item["id"]), "untriggered"):
                store.save_recommendation_events(str(item["id"]), [{"event_type": "untriggered", "trading_date": bars[-1]["trading_date"] if bars else None, "trigger_price": None}])
            untriggered += 1
            continue
        items = evaluations(fill, index, bars, float(item["suggested_quantity"]), str(item.get("action")))
        store.save_evaluations(str(item["id"]), items)
        store.save_paper_tracking(str(item["id"]), str(item["symbol"]), fill, float(item["suggested_quantity"]), str(item.get("action")), bars[index:])
        if store.set_recommendation_evaluation_status(str(item["id"]), "filled"):
            store.save_recommendation_events(str(item["id"]), [{"event_type": "filled", "trading_date": fill["date"], "trigger_price": fill["price"]}])
        evaluated += 1
    return {"evaluated": evaluated, "untriggered": untriggered, "legacy_unverifiable": legacy_unverifiable}


@app.get("/v1/research-recommendations/{recommendation_id}/evaluations")
def recommendation_evaluations(recommendation_id: str) -> list[dict[str, object]]:
    return store.recommendation_evaluations(recommendation_id)


def run_ai_job(job_id: str) -> None:
    job = next((item for item in store.ai_jobs() if item["id"] == job_id), None)
    if not job: return
    store.update_ai_job(job_id, "running", increment_attempt=True)
    content = job["payload"]
    try:
        result = ai_analysis_service.enrich(content)
        if result.get("ai_analysis"):
            store.update_ai_job(job_id, "succeeded")
        else:
            store.update_ai_job(job_id, "failed", "AI output unavailable or invalid")
    except Exception as error:
        store.update_ai_job(job_id, "failed", type(error).__name__)


@app.get("/v1/ai-jobs", response_model=list[AiJob])
def list_ai_jobs(target_id: str | None = None) -> list[AiJob]:
    return [AiJob.model_validate(item) for item in store.ai_jobs(target_id)]


@app.post("/v1/ai-jobs/{job_id}/retry", response_model=AiJob)
def retry_ai_job(job_id: str) -> AiJob:
    job = next((item for item in store.ai_jobs() if item["id"] == job_id), None)
    if not job: raise HTTPException(status_code=404, detail="AI 任务不存在")
    if int(job["attempts"]) >= int(job["max_attempts"]):
        raise HTTPException(status_code=422, detail="AI task retry limit reached")
    store.update_ai_job(job_id, "pending", None)
    queue_background(run_ai_job, job_id)
    return AiJob.model_validate(next(item for item in store.ai_jobs() if item["id"] == job_id))


@app.get("/v1/instruments/{symbol}/metadata", response_model=InstrumentMetadata)
def get_instrument_metadata(symbol: str) -> InstrumentMetadata:
    item = store.instrument_metadata(symbol)
    if not item:
        raise HTTPException(status_code=404, detail="Instrument metadata not found")
    return InstrumentMetadata.model_validate(item)


@app.put("/v1/instruments/{symbol}/metadata", response_model=InstrumentMetadata)
def put_instrument_metadata(symbol: str, payload: InstrumentMetadataInput) -> InstrumentMetadata:
    return InstrumentMetadata.model_validate(store.save_instrument_metadata({"symbol": symbol, **payload.model_dump()}))


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
