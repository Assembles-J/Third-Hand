from datetime import datetime, timezone
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(title="Third-Hand API", version="0.1.0")


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
    disclaimer: str


class ImportResult(BaseModel):
    accepted: int
    rejected_rows: list[int]
    message: str


GLOSSARY = {
    "pe": GlossaryCard(term="PE（市盈率）", plain_explanation="股价相对于每股盈利的倍数。它不是越低越好，需结合行业和盈利质量判断。", watch_for="亏损或一次性收益会令 PE 失真。"),
    "减持": GlossaryCard(term="减持", plain_explanation="股东卖出持有的公司股份。原因可能很多，单独一则消息不能证明基本面变差。", watch_for="看减持主体、比例、期限与公告全文。"),
    "回购": GlossaryCard(term="回购", plain_explanation="公司用资金买回自身股份，可能用于注销、激励或库存股。", watch_for="区分回购计划与实际完成金额。"),
}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/feed", response_model=list[NewsItem])
def feed(symbols: Annotated[list[str], Query()] = []) -> list[NewsItem]:
    related = ["600519"] if not symbols else symbols
    return [NewsItem(
        id="demo-1", title="示例：公司发布回购进展公告", source_name="待接入的授权公告源",
        source_url="https://www.sse.com.cn/", published_at=datetime.now(timezone.utc),
        related_symbols=related,
        explanation="这是示例卡片：请打开原文确认实际回购数量、金额和后续安排。",
        confidence=0.65, disclaimer="信息仅供学习与核查，不构成投资建议。",
    )]


@app.get("/v1/glossary/{term}", response_model=GlossaryCard)
def glossary(term: str) -> GlossaryCard:
    item = GLOSSARY.get(term.strip().lower())
    if not item:
        raise HTTPException(status_code=404, detail="词条尚未收录")
    return item


@app.post("/v1/holdings/import", response_model=ImportResult)
def import_holdings(csv_content: str) -> ImportResult:
    """Validate a user-exported CSV. Persistence requires authenticated storage."""
    rows = [row for row in csv_content.strip().splitlines() if row.strip()]
    expected_header = "symbol,name,quantity,average_cost"
    if not rows or rows[0].replace(" ", "").lower() != expected_header:
        raise HTTPException(status_code=422, detail=f"CSV 表头必须为 {expected_header}")
    rejected = [index for index, row in enumerate(rows[1:], start=2) if len(row.split(",")) != 4]
    return ImportResult(
        accepted=len(rows) - 1 - len(rejected), rejected_rows=rejected,
        message="仅完成格式校验；原型不会保存持仓或任何券商凭证。",
    )
