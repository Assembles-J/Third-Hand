# P1 Order Flow / Active Buying Intelligence

## 0. Purpose

This document defines a proposed end-to-end capability for Third-Hand to answer a practical intraday question:

> Is there observable active buying / support in this stock right now, and how strong is the evidence?

The product must **not** claim that it can identify a specific institution or "主力账户". Public-market data does not expose beneficial account identity. Third-Hand therefore models **observable order-flow evidence** only: active buy/sell prints, large-order imbalance, price response, order-book support, intraday volume/price structure, and provider-reported fund-flow classifications.

The output is a research/decision-support signal, not a prediction and not an autonomous trading authority.

This design is intentionally compatible with the current v3 authority boundary:

```text
Market data -> deterministic order-flow facts -> deterministic score/state
                                          -> Decision Evidence / UI explanation
                                          -> AI may explain, never own the score/action
```

Order-flow evidence must never bypass `ActionPolicy`, `DecisionArbiter`, execution precheck, position sizing, or the unified freeze boundary.

---

## 1. Why this belongs in Third-Hand

The current app already has the foundations needed for a useful first slice:

- A-share quote refresh through `MarketDataService`.
- Five-level A-share order book enrichment in stock-detail requests via AKShare `stock_bid_ask_em`.
- Market/sector/individual provider-reported fund-flow rankings.
- Intraday bar models in Android and existing K-line display.
- `StockDetailDecisionScreen` as the natural decision surface.
- Explicit freshness/source metadata and deterministic decision evidence concepts.

The missing piece is not another generic "主力净流入" number. The missing piece is a **traceable, multi-signal order-flow snapshot** that explains whether money entering the tape is actually moving/holding price.

---

## 2. Product semantics

### 2.1 Terms shown to users

Preferred user-facing terms:

- `主动买盘` — prints classified as buyer-initiated by the upstream source/rule.
- `主动卖盘` — seller-initiated prints.
- `大单/超大单资金` — provider-defined large-order buckets; classification methodology is upstream-specific.
- `承接` — repeated selling is absorbed without materially breaking the local price area.
- `进攻` — buying pushes price through a local reference/pressure level with confirming volume.
- `资金承接评分` — deterministic composite score from observable facts.

Avoid user-facing claims such as:

- `主力正在吸筹`
- `机构正在建仓`
- `庄家护盘`

unless shown as a clearly labeled hypothesis such as `疑似承接`, with the underlying evidence visible.

### 2.2 State model

The primary deterministic state is:

```text
UNAVAILABLE
WEAK_SELLING
SELLING_PRESSURE
NEUTRAL
PASSIVE_SUPPORT
ACTIVE_BUYING
ACTIVE_BUYING_CONFIRMED
```

Suggested Chinese labels:

| State | UI label |
| --- | --- |
| UNAVAILABLE | 数据不足 |
| WEAK_SELLING | 偏弱 |
| SELLING_PRESSURE | 卖压明显 |
| NEUTRAL | 多空均衡 |
| PASSIVE_SUPPORT | 有承接，未转强 |
| ACTIVE_BUYING | 主动买盘增强 |
| ACTIVE_BUYING_CONFIRMED | 主动买盘较强 |

`ACTIVE_BUYING_CONFIRMED` must require both **flow evidence and price-response evidence**. A positive fund-flow number alone can never produce this state.

---

## 3. Data acquisition

### 3.1 Provider adapters

Initial A-share implementation may use AKShare/public Eastmoney/Sina adapters already present in the backend.

Candidate inputs:

1. **Five-level order book**
   - existing: `ak.stock_bid_ask_em(symbol=...)`
   - bid 1–5 / ask 1–5 price and size.

2. **Provider-reported individual fund flow**
   - `ak.stock_individual_fund_flow(stock=..., market=...)`
   - main / super-large / large / medium / small net flow and percentages.

3. **Intraday prints / active side**
   - preferred where stable: `ak.stock_intraday_em(symbol=...)`
   - fallback where available: `ak.stock_intraday_sina(symbol=..., date=...)`
   - normalize trade time, price, size/amount and upstream side classification.

4. **Intraday minute bars**
   - `ak.stock_zh_a_hist_min_em(...)`
   - use 1m or 5m bars for price response, local VWAP/average-price relationship and volume expansion.

5. **Existing quote snapshot**
   - price, previous close, high/low, amount, volume ratio, turnover, bid/ask.

### 3.2 Provider lineage and limitations

Every input must carry:

```text
provider
source_endpoint
observed_at / market_as_of
retrieved_at
freshness_status
classification_method (provider | inferred | unknown)
license_scope
```

Provider-defined `主力/大单/超大单` classifications are **not canonical account identity**. They are evidence inputs with source lineage.

If active-side print classification is not available or unstable, the score must degrade rather than infer an authoritative side from price movement alone.

### 3.3 Polling policy

Do not poll tick endpoints for the entire market.

Initial scope:

- stock detail screen: on-demand refresh;
- current holdings/watchlist: optional bounded background refresh;
- market ranking: keep existing coarse fund-flow ranking path;
- server cache: 10–30 seconds for order-flow snapshot during open session, configurable;
- closed market: freeze the latest session snapshot and label it `收盘快照`.

---

## 4. Backend domain model

Add a read model separate from formal action semantics.

```python
OrderFlowSnapshot(
    symbol: str,
    market: str,
    session_date: str,
    as_of: datetime,
    state: str,
    score: int,                  # 0..100
    confidence: int,             # data/evidence confidence, 0..100
    data_health: str,            # fresh | stale | partial | unavailable

    active_buy_amount: float | None,
    active_sell_amount: float | None,
    active_buy_sell_ratio: float | None,

    main_net_amount: float | None,
    main_net_percent: float | None,
    super_large_net_amount: float | None,
    large_net_amount: float | None,

    bid_depth_amount: float | None,
    ask_depth_amount: float | None,
    book_imbalance: float | None,

    last_price: float | None,
    session_vwap: float | None,
    price_vs_vwap_percent: float | None,
    local_return_percent: float | None,
    volume_expansion_ratio: float | None,

    support_retests: int,
    support_hold_ratio: float | None,
    breakout_confirmed: bool,

    evidence: list[OrderFlowEvidence],
    warnings: list[str],
    sources: list[OrderFlowSource],
    scoring_version: str,
)
```

Evidence item:

```python
OrderFlowEvidence(
    code: str,
    direction: "supportive" | "adverse" | "neutral",
    weight: int,
    title: str,
    detail: str,
    observed_value: float | str | None,
    threshold: float | str | None,
    source_key: str,
)
```

This snapshot is an auditable research read model. It is **not** an execution instruction.

---

## 5. Deterministic scoring v1

### 5.1 Principles

The score must reward agreement among independent observable dimensions:

1. capital-flow direction;
2. active print imbalance;
3. price response;
4. support/absorption;
5. volume confirmation;
6. data quality.

It must penalize the common false positive:

> large positive flow classification while price continues to break lower.

### 5.2 Proposed weights

Maximum raw score: 100.

#### A. Provider-reported large-order flow — 25 points

- main net flow positive and meaningful vs turnover: up to 10
- super-large + large both positive: up to 10
- improving flow slope over last samples: up to 5

#### B. Active print imbalance — 25 points

Use recent 10/20/30-minute windows where available.

```text
active_buy_sell_ratio = active_buy_amount / max(active_sell_amount, epsilon)
```

Example bands:

- >= 1.50: 25
- >= 1.25: 18
- >= 1.10: 10
- 0.90–1.10: 5
- < 0.90: 0

Thresholds must be versioned and benchmarked, not hard-coded forever.

#### C. Price response / VWAP — 20 points

- price above session VWAP: +5
- recent local return positive while buy imbalance positive: +5
- higher low / reclaimed local reference: +5
- breakout of local resistance with confirmation: +5

#### D. Support / absorption — 20 points

A support retest is only valid when a local reference area is revisited with bounded tolerance.

Signals:

- 2+ retests without lower-low continuation: +5
- sell-side volume absorbed and close recovers from local low: +5
- bid depth replenishes after trades: +5 (only if repeated snapshots are available)
- support hold ratio >= configured threshold: +5

#### E. Volume confirmation — 10 points

- advancing bars show larger volume than pullbacks: up to 5
- volume expansion during reclaim/breakout: up to 5

### 5.3 Critical contradiction penalties

Apply after raw score:

- price makes a fresh local/session low while reported main flow stays positive: `-15`
- active buy ratio > 1.2 but price response remains materially negative for N minutes: `-10`
- large positive order-book imbalance disappears without execution (suspected cancel/ephemeral book): `-5` to `-15`, only if repeated snapshots support this conclusion
- stale/partial data: cap final score and confidence

### 5.4 State mapping

Proposed v1 mapping:

```text
0–24   SELLING_PRESSURE
25–39  WEAK_SELLING
40–59  NEUTRAL
60–69  PASSIVE_SUPPORT
70–84  ACTIVE_BUYING
85–100 ACTIVE_BUYING_CONFIRMED
```

Additional gate:

`ACTIVE_BUYING_CONFIRMED` requires:

- confidence >= 70;
- at least one flow/active-print supportive signal;
- at least one price-response supportive signal;
- no critical contradiction.

---

## 6. API contract

Add a dedicated market research endpoint:

```http
GET /v1/market/order-flow/{symbol}?refresh=true&window_minutes=30
```

Response is `OrderFlowSnapshot`.

Optional later endpoints:

```http
GET /v1/market/order-flow/{symbol}/history?session_date=&interval=5m
GET /v1/market/order-flow/rankings?scope=holdings|watchlist|market
```

The stock-detail endpoint should remain independent from formal decision generation so users can refresh tape evidence without regenerating an AI/decision report.

### Error/degraded semantics

Use structured states:

- `fresh`
- `partial`
- `stale`
- `unavailable`

Examples:

- order book available but prints unavailable -> `partial`; no active-print score.
- historical fund flow only -> show as prior-session context, never `fresh`.
- closed session -> latest completed snapshot with explicit timestamp.

---

## 7. Decision-system integration

### 7.1 Phase 1: read-only evidence

The first implementation must **not** change formal `BUY/WAIT/HOLD/ADD/REDUCE/EXIT` semantics.

It may be added to:

- `DecisionReport.evidence` as an informational evidence category;
- AI explanation context as structured facts;
- stock-detail UI;
- decision journal snapshot for later evaluation.

### 7.2 Phase 2: execution-timing authority only

After offline evaluation, a separately versioned policy may allow intraday order flow to influence **execution timing**, not strategic action creation.

Example:

```text
Daily policy says BUY candidate
+ price is in allowed buy zone
+ execution precheck passes
+ order-flow state >= ACTIVE_BUYING
=> execution timing condition satisfied
```

Conversely:

```text
Daily policy says BUY candidate
+ order-flow shows SELLING_PRESSURE
=> WAIT for execution confirmation
```

Order flow must never create a BUY candidate when the strategic action path does not already permit new risk.

This aligns with the current v3 timeframe authority: intraday data can become execution-timing evidence only after its own versioned policy is approved.

---

## 8. Android UI design

### 8.1 Primary location: Stock Detail

Add a compact `资金承接 / 主动买盘` section in `StockDetailDecisionScreen`, positioned after intraday K-line and before Company Intelligence / AI explanation.

The card must answer four questions immediately:

1. **现在是什么状态？**
2. **为什么？**
3. **数据新不新？**
4. **什么情况会推翻这个判断？**

Suggested compact layout:

```text
资金承接                         12:47:20 · 实时/近实时
主动买盘增强                 76 / 100   证据置信 82

主动买/卖      1.38x      主力净流入       +3,268万
价格 vs 均价   +0.7%      大单/超大单       双双净流入

✓ 11.00 附近 3 次回踩未破
✓ 上涨段放量，回调段缩量
! 主力流入为数据源分类，不代表具体机构账户

[查看证据明细]
```

### 8.2 Evidence drill-down

Tap `查看证据明细` to open a bottom sheet.

Sections:

#### 资金方向
- 主力净额 / 净占比
- 超大单 / 大单
- 30m active buy/sell ratio

#### 价格响应
- current vs VWAP
- recent local return
- reclaim/breakout state

#### 承接
- local support area
- number of retests
- lower-low status
- volume on retest vs rebound

#### 盘口
- bid 1–5 total vs ask 1–5 total
- imbalance
- snapshot timestamp
- clearly label that visible orders may be cancelled

#### Data source
- provider
- market as-of
- retrieved time
- stale/partial warnings

### 8.3 Visual rules

- Do not encode state by color alone; always show label + score.
- Respect configurable China/HK rise/fall colors.
- Use `—` and explicit `数据不足` instead of manufacturing zeros.
- A stale snapshot gets a visible `数据延迟` badge.
- `76/100` is an evidence score, not a probability of price rise.
- Do not show `建议买入` from this card.

### 8.4 Market screen integration

The existing `主力流入/主力流出` ranking can later be upgraded to distinguish:

- `主力净流入榜` — provider-reported flow only;
- `主动买盘榜` — composite order-flow score.

Do not silently rename existing rankings, because the semantics differ.

### 8.5 Holdings / watchlist

For held symbols, a small badge may show:

```text
承接 72  |  偏强
```

This badge links to stock detail. It must not create an alert by itself until alert thresholds and anti-noise rules are separately specified.

---

## 9. Suggested Android DTOs

```kotlin
data class OrderFlowEvidenceDto(
    val code: String,
    val direction: String,
    val weight: Int,
    val title: String,
    val detail: String,
    val observed_value: Any? = null,
    val threshold: Any? = null,
    val source_key: String,
)

data class OrderFlowSnapshotDto(
    val symbol: String,
    val market: String,
    val session_date: String,
    val as_of: String,
    val state: String,
    val score: Int,
    val confidence: Int,
    val data_health: String,
    val active_buy_sell_ratio: Double? = null,
    val main_net_amount: Double? = null,
    val main_net_percent: Double? = null,
    val super_large_net_amount: Double? = null,
    val large_net_amount: Double? = null,
    val book_imbalance: Double? = null,
    val session_vwap: Double? = null,
    val price_vs_vwap_percent: Double? = null,
    val support_retests: Int = 0,
    val support_hold_ratio: Double? = null,
    val breakout_confirmed: Boolean = false,
    val evidence: List<OrderFlowEvidenceDto> = emptyList(),
    val warnings: List<String> = emptyList(),
    val scoring_version: String,
)
```

Retrofit:

```kotlin
@GET("v1/market/order-flow/{symbol}")
suspend fun orderFlow(
    @Path("symbol") symbol: String,
    @Query("refresh") refresh: Boolean = false,
    @Query("window_minutes") windowMinutes: Int = 30,
): OrderFlowSnapshotDto
```

---

## 10. Backend implementation map

Keep the first code slice small and aligned with existing structure.

Suggested components:

```text
backend/app/order_flow.py
    OrderFlowService
    OrderFlowScoringPolicy
    normalization and deterministic scoring

backend/app/market.py
    provider acquisition helpers only
    no scoring/business semantics

backend/app/api/v1/market/order_flow.py
    read-only API route

backend/tests/test_order_flow_scoring.py
backend/tests/test_order_flow_service.py
backend/tests/test_market_order_flow_api.py
```

If API route extraction is still intentionally deferred in the repository, temporarily expose the route through the current bootstrap owner, but keep the domain/service boundary as above.

Do not place the composite score inside `MarketDataService`; that service should remain a provider/normalization adapter.

---

## 11. Storage and history

### MVP

No permanent tick-by-tick archive is required.

Store only bounded snapshots needed for audit/evaluation:

```text
order_flow_snapshots(
  id,
  symbol,
  market,
  session_date,
  as_of,
  state,
  score,
  confidence,
  data_health,
  payload_json,
  snapshot_hash,
  scoring_version,
  created_at
)
```

Recommended persistence frequency for held/watchlist stocks: one snapshot every 5 minutes during open session, plus explicit snapshots attached to a generated decision/report.

Raw public-source ticks may be expensive, unstable or license-sensitive. Do not persist unbounded raw upstream payloads by default.

---

## 12. Data quality and safety

### 12.1 Required for full score

- valid in-session quote/time;
- usable intraday price bars;
- at least one flow dimension;
- no provider timestamp contradiction.

### 12.2 Optional dimensions

- order book;
- active-side prints;
- super-large/large split.

Missing optional data lowers confidence and disables the relevant score component rather than becoming zero evidence.

### 12.3 Explicit warnings

Examples:

- `大单分类来自公开数据源规则，不代表具体账户身份。`
- `盘口挂单可撤销，仅作为短时证据。`
- `主动买卖方向为数据源分类，存在误判可能。`
- `当前为盘后快照，不代表下一交易日资金方向。`

---

## 13. Acceptance tests

### Deterministic scoring

1. Same input snapshot + same scoring version => identical score/state/evidence.
2. Positive main flow + falling price + fresh local low cannot yield `ACTIVE_BUYING_CONFIRMED`.
3. Positive active-buy ratio + price reclaim + volume confirmation can yield `ACTIVE_BUYING` or higher.
4. Missing active prints does not become `active_buy_sell_ratio=0`.
5. Stale input caps confidence and prevents confirmed state.
6. Score is always 0..100.

### Provider normalization

1. Column-name changes fail explicitly with a structured degraded state.
2. All timestamps are timezone-aware or normalized to market session time.
3. Closed-session snapshots are labeled closed/frozen.
4. Provider-reported flow classification retains provider lineage.

### API

1. Unknown/non-A-share symbol returns supported/unavailable semantics, not fabricated values.
2. `refresh=false` can use bounded cache.
3. `refresh=true` does not bypass rate/TTL safeguards without reason.
4. Partial upstream failures still return available dimensions plus warnings.

### Android

1. Loading / fresh / partial / stale / unavailable states all render.
2. Score label remains understandable without color.
3. Evidence sheet exposes timestamp/source/warnings.
4. No order-flow card text says "buy", "sell", "add", or guarantees direction unless quoting the formal decision section separately.
5. Stock-detail screen can fail order-flow loading without losing quote/holding/decision content.

---

## 14. Evaluation plan

Do not optimize thresholds from one symbol or one day.

Capture historical snapshots for a diversified benchmark set and evaluate forward windows such as 5m/15m/30m/60m using:

- next-window return distribution;
- maximum favorable excursion;
- maximum adverse excursion;
- probability of new local low;
- support hold rate;
- score stability / flip rate;
- missing-data rate by provider.

The first release goal is **interpretability and false-positive reduction**, not maximum prediction accuracy.

Important benchmark question:

> When the system says `有承接，未转强`, does the subsequent tape statistically break the observed support less often than neutral/weak states?

---

## 15. Delivery slices

### Slice A — backend read-only MVP

- provider adapters for individual flow + minute bars + existing order book;
- deterministic `OrderFlowSnapshot`;
- `/v1/market/order-flow/{symbol}`;
- unit/API tests;
- no formal action impact.

### Slice B — stock-detail UI

- `资金承接 / 主动买盘` card;
- evidence bottom sheet;
- freshness/degraded states;
- no new navigation destination required.

### Slice C — audit/history

- persist 5-minute/decision-bound snapshots;
- add history mini-chart / score timeline;
- journal linkage.

### Slice D — evaluated execution-timing gate

Only after benchmark evidence and an explicit architecture/policy update:

- versioned intraday execution-timing policy;
- order flow may delay/confirm an already-permitted action;
- never creates strategic BUY/ADD/REDUCE/EXIT authority itself.

---

## 16. Non-goals

This proposal does not include:

- identifying real institutional accounts;
- Level-2 proprietary order IDs;
- broker connectivity;
- real order submission;
- automatic strategy tuning;
- treating AKShare/Eastmoney `主力净流入` as ground truth;
- making the LLM responsible for score calculation;
- using the score as a standalone buy/sell recommendation.

---

## 17. Example interpretation

For a stock around a suspected support area:

```text
资金承接评分 72/100 · 主动买盘增强

支持：
- 最近 30 分钟主动买/卖金额比 1.31x
- 大单与超大单均为净流入
- 价格重新站上分时均价
- 11.00 附近三次回踩未形成新低

限制：
- 盘口买单仅为短时快照，可撤销
- 主力资金分类来自公开数据源规则

推翻条件：
- 放量跌破 11.00 且 10 分钟内不能收回
- 主动买卖比降至 0.9 以下
- 新低同时出现主动卖盘放大
```

This is the intended Third-Hand experience: **observable facts -> deterministic interpretation -> explicit invalidation**, rather than a single opaque "主力净流入" number.
