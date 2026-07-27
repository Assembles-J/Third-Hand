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

from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from app.market import MarketDataService, MarketDataUnavailable
from app.storage import PortfolioStore
from app.time_utils import beijing_now

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


class ImportResult(BaseModel):
    accepted: int
    rejected_rows: list[int]
    message: str


store = PortfolioStore()
market_data = MarketDataService()

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
    if not requested:
        requested = [str(holding["symbol"]) for holding in store.list()]
    return seed_news(requested)


@app.get("/v1/market/quotes")
def market_quotes(symbols: Annotated[list[str], Query()]) -> list[dict[str, object]]:
    """Return cached public-source snapshots for A shares and Hong Kong listings."""
    try:
        return market_data.quotes(symbols)
    except MarketDataUnavailable as error:
        raise HTTPException(status_code=503, detail={"message": str(error), "code": error.code}) from error


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
