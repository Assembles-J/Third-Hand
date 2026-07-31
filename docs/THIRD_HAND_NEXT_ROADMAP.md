# Third-Hand 后续实施路线

> 面向本地开发 Agent 的执行文档  
> 审查基线：`pengpengno/Third-Hand` `main@89dd173`（2026-07-31）  
> 基线已包含：PR #8 DeepSeek 基础设施、后台派生分析、AI 日线历史分析、历史校准、K 线页面

## 1. 这份文档要解决什么

后续建设分成两条互相依赖、但必须解耦的主线：

1. **研究证据链**：保存新闻/公告正文，建立可恢复的 AI 分析任务，让 AI 从“标题摘要器”升级为有正文、有状态、有证据的研究解释器。
2. **仓位候选方案与历史复盘**：依据行情、持仓、个人交易计划、风险上限和可用现金，生成可解释的加仓、减仓或退出候选区间与数量；无论用户是否真实成交，都保留当时快照并计算后续模拟表现。

系统定位仍然是：

> 数据负责事实，程序负责计算和约束，AI 负责提取、归纳和解释，用户负责最终决策。

禁止把它改成：

- DeepSeek 直接猜一个买入价和数量；
- 自动连接券商下单；
- 用“胜率”“置信度”暗示确定收益；
- 用未来数据反向美化历史建议；
- 没有现金、仓位、交易单位和数据时效时仍输出精确数量。

---

## 2. 当前代码真实状态

### 2.1 已经具备的能力

| 能力 | 当前实现 | 可复用程度 |
|---|---|---|
| 持仓 | `holdings`，记录代码、名称、数量、平均成本 | 高 |
| 卖出记录 | `sale_records`，记录真实卖出价格、数量、已实现盈亏和分析快照 | 高 |
| 最新行情 | `market_quote_cache`，包含价格、币种、来源、时间和 stale fallback | 高 |
| 日线数据 | `daily_price_cache` + `PriceHistoryService` | 中 |
| 技术指标 | SMA、RSI、MACD、ATR、60 日回撤 | 高 |
| 风险统计 | 5 日历史下行频率、年化波动、样本量 | 高 |
| 个人规则 | 最大仓位、亏损复核阈值、波动复核阈值 | 中 |
| 交易计划 | `trade_plans`，包含逻辑、催化剂、入场/加仓/减仓/退出条件、仓位上限、风险预算 | 高 |
| 证据快照 | `decision_snapshot.py` 保存行情、风险、事件、规则、交易计划、市场环境和相对强弱 | 高 |
| 分析历史 | `analysis_runs` 保存完整 JSON 快照 | 中 |
| 历史校准 | `calibration_observations` + 1/5/20 日规则一致率 | 中 |
| DeepSeek | 独立客户端、Pydantic 校验、重试、熔断、版本缓存 | 高 |
| Android | 行情自动刷新、持仓分析、交易计划、日线/K 线入口、复盘记录 | 高 |
| APK 发布隔离 | Android 目录发生变化或手工指定时才发布 APK | 已正确实现 |

### 2.2 仍然存在的关键缺口

1. `news.py` 虽然拿到了“新闻内容”，但最终返回对象没有保存正文。
2. 公告适配器只保存标题和链接，没有下载、解析和保存 PDF/HTML 正文。
3. `content_cache` 仍是一个 JSON blob，没有正文状态、内容哈希、来源权威度、附件和提取错误字段。
4. 新闻/公告的 AI 分析仍使用进程内后台调用，没有持久化 `ai_jobs` 状态；服务重启后任务无法可靠恢复。
5. Android 信息流不能显示 `pending/running/failed`，也不能针对失败任务重试。
6. 当前 `portfolio_analysis.py` 只输出 `observe/risk_review/wait_for_confirmation/data_insufficient`，不会输出数值区间和数量。
7. `trade_plans` 的入场、加仓、减仓、退出条件都是自然语言，还没有机器可计算的条件结构。
8. 当前没有账户、可用现金、现金保留比例、基础币种、交易费率、滑点和单笔最大金额。
9. 当前持仓没有 `account_id`，无法区分多个账户或不同币种现金。
10. `daily_price_cache` 当前主要保存 `close/high/low`；**数值点位和真正蜡烛图需要先补 `open/volume/amount`**。
11. 当前没有证券最小交易单位、价格最小变动单位。A 股买入通常要处理整手，港股每手股数不能统一写死。
12. `calibration_observations` 记录的是“分析动作发生时的现价”，不是“建议价格区间被触发后的模拟成交”，所以不能直接当成建议收益。
13. 当前“规则一致率”只判断价格方向是否与动作大致一致，不等于策略收益率，也不包含手续费、滑点、最大有利/不利波动。
14. `analysis_runs` 是整体 JSON，方便回看但不方便查询“某个建议是否触发、触发价、模拟持仓和每天浮盈”。

### 2.3 对新功能的直接判断

用户录入可用现金是必要条件之一，但**现金不是唯一界限**。要给出数量，至少还需要：

- 当前持仓数量和市值；
- 当前可用现金及币种；
- 账户总权益；
- 最低现金保留比例；
- 单标的最大仓位；
- 单笔最大投入比例；
- 单笔风险预算；
- 建议入场区间与失效区间；
- 证券交易单位和最小价格跳动；
- 行情时间和数据是否过期。

如果这些信息不完整，系统只能输出：

- 加仓/减仓的条件；
- 建议目标仓位区间；
- 缺失信息清单；

不得伪造一个精确股数。

---

## 3. 产品语言与边界

建议后端内部使用 `research_recommendation`，前端显示：

- “研究候选方案”
- “计划区间”
- “风险失效条件”
- “模拟跟踪”

避免直接显示：

- “精准买点”
- “必涨买入价”
- “系统让你买 500 股”

建议类型：

```text
watch      观察，不生成数量
add        加仓候选
trim       减仓候选
exit       退出候选
hold       维持现状
blocked    数据或规则不足，禁止数值建议
```

系统只能生成候选方案，不能生成订单。任何真实成交都必须由用户单独确认并手工记录。

如果项目以后向他人公开提供或商业化，数值化点位和数量已接近投资建议服务，应在上线前做专门合规评估。中国证监会现行规则要求避免对不确定事项给出确定性判断，并强调投资者适当性、风险揭示和留痕。参考：

- [证券投资顾问业务暂行规定（现行有效）](https://neris.csrc.gov.cn/falvfagui/rdqsHeader/mainbody?navbarId=2&secFutrsLawId=3636153f028c44e9a00de8ed06494385)
- [证券期货投资者适当性管理办法](https://www.csrc.gov.cn/csrc/c106256/c1653849/content.shtml)

---

## 4. 目标架构

```text
行情快照 / 完整日线 / 公告正文 / 新闻正文
                    │
                    ▼
             结构化证据与数据质量
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
     技术指标     风险统计      事件事实
        └───────────┼───────────┘
                    ▼
       账户权益 / 可用现金 / 当前仓位
                    │
                    ▼
        个人规则 + 结构化交易计划
                    │
                    ▼
        确定性候选方案计算引擎
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
  DeepSeek 解释与核验项      不可变建议快照
                                  │
                                  ▼
                         每日触发与模拟成交
                                  │
                                  ▼
                       1/5/20/60 日复盘与反馈
```

核心原则：

1. 数值区间和数量由程序计算，不由 LLM 直接生成。
2. DeepSeek 可以解释“为什么进入候选区间、还缺什么证据”，不能绕过仓位和现金约束。
3. 每次建议保存不可变输入快照；以后规则变化不能改写历史。
4. 真实成交、模拟成交、仅观察三种状态严格分开。
5. 没有触发建议区间时，不能宣称存在模拟浮盈。

---

## 5. 推荐的数据模型

新表不要继续把核心查询数据全部塞进一个 JSON blob。JSON 可以保存快照，但状态、金额、日期、类型和关联键必须结构化。

### 5.1 `portfolio_accounts`

账户与风险约束。

```sql
CREATE TABLE portfolio_accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_currency TEXT NOT NULL,
    min_cash_reserve_percent REAL NOT NULL DEFAULT 20,
    max_single_trade_percent REAL NOT NULL DEFAULT 5,
    max_total_exposure_percent REAL NOT NULL DEFAULT 80,
    max_portfolio_drawdown_percent REAL,
    numeric_recommendations_enabled INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);
```

说明：

- 第一版只创建一个 `default` 账户。
- `numeric_recommendations_enabled` 必须由用户主动开启。
- 开启前展示“研究候选，不会自动下单”的确认。

### 5.2 `cash_balances`

按币种记录可用现金。

```sql
CREATE TABLE cash_balances (
    account_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    available_amount TEXT NOT NULL,
    reserved_amount TEXT NOT NULL DEFAULT '0',
    source TEXT NOT NULL DEFAULT 'manual',
    as_of TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (account_id, currency)
);
```

金额建议使用 `Decimal`，SQLite 中保存十进制字符串，避免继续扩大浮点误差。

第一版不做隐式换汇：

- CNY 现金只约束 A 股/人民币 ETF；
- HKD 现金只约束港股；
- 没有同币种现金时，数量状态为 `cash_currency_missing`。

### 5.3 调整 `holdings`

新增：

```text
account_id
currency
market
```

迁移策略：

1. 创建 `default` 账户；
2. 现有持仓全部挂到 `default`；
3. 币种优先取最近成功行情；
4. 无法判断时保留 `UNKNOWN`，禁止输出数量。

### 5.4 `instrument_metadata`

```sql
CREATE TABLE instrument_metadata (
    symbol TEXT PRIMARY KEY,
    market TEXT NOT NULL,
    currency TEXT NOT NULL,
    lot_size INTEGER,
    price_tick TEXT,
    source TEXT NOT NULL,
    as_of TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

规则：

- A 股买入数量按有效整手取整；
- 港股必须从证券元数据获取每手股数，不能统一假设 100；
- 元数据缺失时可以输出价格区间，但数量为 `null`。

### 5.5 扩展 `daily_price_cache`

补充：

```text
open
volume
amount
adjustment
```

原因：

- 模拟触发需要 `open/high/low/close`；
- 缺少 `open` 时无法判断跳空后的合理模拟成交价；
- 成交量是放量、缩量和流动性过滤的必要输入；
- 所有历史计算必须固定复权口径。

### 5.6 `recommendation_runs`

一次完整计算的顶层快照。

```sql
CREATE TABLE recommendation_runs (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    data_as_of TEXT NOT NULL,
    data_quality_status TEXT NOT NULL,
    account_snapshot_json TEXT NOT NULL,
    market_regime_json TEXT NOT NULL,
    evidence_snapshot_json TEXT NOT NULL,
    UNIQUE(account_id, input_hash)
);
```

### 5.7 `research_recommendations`

```sql
CREATE TABLE research_recommendations (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    currency TEXT NOT NULL,
    baseline_price TEXT NOT NULL,
    price_zone_low TEXT,
    price_zone_high TEXT,
    invalidation_price TEXT,
    target_weight_low_percent REAL,
    target_weight_high_percent REAL,
    suggested_quantity TEXT,
    quantity_status TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    rationale TEXT NOT NULL,
    missing_evidence_json TEXT NOT NULL,
    confidence_kind TEXT NOT NULL,
    evidence_completeness_percent REAL NOT NULL,
    created_at TEXT NOT NULL
);
```

`status`：

```text
proposed
acknowledged
triggered
paper_open
actually_executed
expired
invalidated
cancelled
```

`quantity_status`：

```text
ready
numeric_disabled
cash_missing
cash_currency_missing
lot_size_missing
price_stale
position_limit_reached
risk_budget_zero
data_insufficient
```

### 5.8 `recommendation_legs`

支持分批计划，不只保存一个点位。

```sql
CREATE TABLE recommendation_legs (
    id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL,
    sequence_no INTEGER NOT NULL,
    action TEXT NOT NULL,
    zone_low TEXT NOT NULL,
    zone_high TEXT NOT NULL,
    quantity TEXT,
    allocation_percent REAL NOT NULL,
    trigger_condition_json TEXT NOT NULL,
    UNIQUE(recommendation_id, sequence_no)
);
```

第一版最多三档，例如 40% / 30% / 30%，但具体档位必须来自确定性规则配置，不得由 LLM 临时生成。

### 5.9 `recommendation_events`

审计状态变化：

```sql
CREATE TABLE recommendation_events (
    id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_at TEXT NOT NULL,
    price TEXT,
    quantity TEXT,
    payload_json TEXT NOT NULL
);
```

事件示例：

```text
created
zone_touched
paper_filled
user_acknowledged
user_executed
expired
invalidated
evaluation_completed
```

### 5.10 `paper_positions`

```sql
CREATE TABLE paper_positions (
    id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity TEXT NOT NULL,
    fill_price TEXT NOT NULL,
    fill_date TEXT NOT NULL,
    fees TEXT NOT NULL DEFAULT '0',
    status TEXT NOT NULL,
    closed_price TEXT,
    closed_date TEXT,
    close_reason TEXT
);
```

### 5.11 `recommendation_evaluations`

```sql
CREATE TABLE recommendation_evaluations (
    id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL,
    horizon_trading_days INTEGER NOT NULL,
    evaluation_date TEXT NOT NULL,
    trigger_status TEXT NOT NULL,
    assumed_fill_price TEXT,
    mark_price TEXT,
    gross_pnl TEXT,
    net_pnl TEXT,
    return_percent REAL,
    benchmark_return_percent REAL,
    excess_return_percent REAL,
    max_favorable_excursion_percent REAL,
    max_adverse_excursion_percent REAL,
    evaluation_version TEXT NOT NULL,
    UNIQUE(recommendation_id, horizon_trading_days)
);
```

---

## 6. 点位与数量的计算规则

### 6.1 先做硬性准入检查

以下任意一项不满足，结果必须是 `blocked`，不能生成精确数量：

1. 最新行情价格为空；
2. 行情 `refresh_status=stale_fallback` 且超过允许时效；
3. 日线不足 60 个交易日；
4. 交易计划未启用；
5. 交易计划没有结构化失效条件；
6. 账户未启用数值候选方案；
7. 持仓或现金币种无法确认；
8. 证券交易单位缺失；
9. 建议会突破最大仓位；
10. 风险预算为零或失效价无法计算。

### 6.2 点位输出为区间，不输出神奇单点

候选区间可以由以下程序化证据组合：

- 20/60 日均线；
- 最近 20/60 日高低点；
- ATR；
- 前高/前低；
- 回撤幅度；
- RSI/MACD 只作过滤，不单独决定点位；
- 交易计划中的入场、加仓、减仓、退出条件；
- 市场环境和相对强弱。

建议输出：

```json
{
  "action": "add",
  "price_zone": {"low": "25.80", "high": "26.30"},
  "invalidation_price": "24.90",
  "valid_for_trading_days": 5,
  "conditions": [
    "收盘仍在 60 日均线上方",
    "没有新增正式负面公告",
    "组合仓位未超过个人上限"
  ]
}
```

不要输出：

```json
{"buy_at": 26.18, "guaranteed_target": 31.50}
```

### 6.3 加仓数量

设：

```text
equity = 同币种现金 + 当前同币种持仓市值
cash_available = 可用现金 - 最低现金保留额
current_value = 当前持仓数量 × 候选区间上沿
position_cap_value = equity × 单标的最大仓位比例
single_trade_cap = equity × 单笔最大投入比例
position_room = max(0, position_cap_value - current_value)
risk_per_share = 候选区间上沿 - 失效价
risk_budget_value = equity × 单笔风险预算比例
```

数量上限：

```text
cash_qty = floor(cash_available / 区间上沿 / lot_size) × lot_size
position_qty = floor(position_room / 区间上沿 / lot_size) × lot_size
single_trade_qty = floor(single_trade_cap / 区间上沿 / lot_size) × lot_size
risk_qty = floor(risk_budget_value / risk_per_share / lot_size) × lot_size

suggested_qty = min(cash_qty, position_qty, single_trade_qty, risk_qty)
```

附加约束：

- 使用区间上沿计算资金占用，保持保守；
- 扣除估算手续费和滑点；
- `risk_per_share <= 0` 时禁止生成；
- 数量小于一个交易单位时，返回 `risk_budget_zero` 或 `cash_missing`；
- 不能因为“现金很多”绕过单标的仓位上限。

### 6.4 减仓数量

减仓不是由可用现金决定，而由当前暴露、目标仓位和风险状态决定：

```text
target_position_value = equity × 目标仓位比例
excess_value = max(0, current_value - target_position_value)
raw_reduce_qty = excess_value / 候选卖出区间下沿
reduce_qty = 按市场卖出规则取整
```

第一版建议只允许规则化比例：

```text
trim_25
trim_50
reduce_to_position_cap
exit_all
```

每一种比例必须在交易计划或个人规则中有明确触发条件。

### 6.5 AI 的角色

DeepSeek 可以：

- 把公告正文提取为事实；
- 解释哪个交易计划条件可能已满足；
- 列出反证和待核验项；
- 用自然语言说明程序为什么给出候选区间；
- 比较当前建议与历史同类建议。

DeepSeek 不可以：

- 直接返回最终价格区间和股数；
- 修改现金、仓位、交易单位和风险预算；
- 在程序返回 `blocked` 时强行生成建议；
- 把证据完整度解释成涨跌概率。

---

## 7. 未真实成交时如何计算“模拟浮盈”

### 7.1 必须区分三种结果

1. **未触发**：价格从未进入建议区间，没有模拟成交，也没有模拟浮盈。
2. **已触发但未真实成交**：按统一规则创建 paper position，计算模拟盈亏。
3. **真实成交**：使用用户录入的真实价格、数量和费用，进入真实成交复盘。

禁止把“建议发布后的价格上涨”直接当作建议盈利。如果买入区间从未触发，最多展示：

```text
建议后标的涨跌：+X%
候选区间：未触发
模拟收益：不适用
```

### 7.2 防止未来函数

建议在 T 日收盘后生成时：

- 最早从 T+1 交易日判断触发；
- 不允许使用 T 日盘中高低点回填成交；
- 建议生成时间、行情 `as_of` 和有效起始日必须保存。

### 7.3 日线模拟成交规则

补齐 `open/high/low/close` 后，第一版使用保守规则。

买入候选区间 `[L, U]`：

```text
如果 open <= U：
    assumed_fill = min(open, U)
否则如果 low <= U：
    assumed_fill = U
否则：
    未触发
```

卖出候选区间 `[L, U]`：

```text
如果 open >= L：
    assumed_fill = max(open, L)
否则如果 high >= L：
    assumed_fill = L
否则：
    未触发
```

随后应用：

```text
买入成交价 += 滑点
卖出成交价 -= 滑点
净收益 -= 手续费和税费估算
```

注意：只有日线无法还原盘中先后顺序，因此结果必须标注 `daily_bar_assumption_v1`，不能伪装成真实可成交回测。

### 7.4 评估指标

每条触发建议至少记录：

- 1/5/20/60 个交易日净收益；
- 对应基准收益；
- 超额收益；
- 最大有利波动 MFE；
- 最大不利波动 MAE；
- 是否先触发失效条件；
- 是否在有效期内触发；
- 真实成交与模拟成交的偏差；
- 使用的评估算法版本。

### 7.5 不要用结果简单判定建议对错

建议评价拆成：

1. 当时事实是否准确；
2. 数据是否新鲜；
3. 风险是否明确；
4. 数量是否遵守现金和仓位约束；
5. 候选区间是否实际触发；
6. 触发后的收益和回撤；
7. 后续是否出现当时不可知的新事件。

---

## 8. 建议 API

### 8.1 账户与现金

```text
GET  /v1/accounts
POST /v1/accounts
PUT  /v1/accounts/{id}

GET  /v1/accounts/{id}/cash-balances
PUT  /v1/accounts/{id}/cash-balances/{currency}
GET  /v1/accounts/{id}/valuation
```

### 8.2 候选建议

```text
POST /v1/research-recommendations/generate
GET  /v1/research-recommendations
GET  /v1/research-recommendations/{id}
POST /v1/research-recommendations/{id}/acknowledge
POST /v1/research-recommendations/{id}/cancel
POST /v1/research-recommendations/{id}/executions
```

生成请求：

```json
{
  "account_id": "default",
  "symbols": ["01810"],
  "mode": "research_only"
}
```

响应必须包含：

```json
{
  "action": "add",
  "quantity_status": "cash_missing",
  "suggested_quantity": null,
  "price_zone": {"low": 25.8, "high": 26.3},
  "missing_evidence": ["HKD 可用现金"],
  "automatic_execution": false
}
```

### 8.3 模拟跟踪

```text
GET  /v1/research-recommendations/{id}/events
GET  /v1/research-recommendations/{id}/evaluations
POST /v1/research-recommendations/evaluate
GET  /v1/research-recommendations/scorecard
```

生产中由每日收盘后台任务自动评估；`POST evaluate` 只用于管理员重算和测试。

### 8.4 内容与 AI 任务

```text
GET  /v1/ai-jobs?content_ids=...
GET  /v1/ai-jobs/{id}
POST /v1/ai-jobs/{id}/retry
GET  /v1/content/{id}
```

状态：

```text
pending
running
retrying
succeeded
failed
```

---

## 9. 新闻、公告正文和 AI 任务路线

### 9.1 内容表

新增 `content_documents`：

```text
content_id
document_type
title
source_name
source_url
source_authority
source_published_at
retrieved_at
language
body_text
body_status
body_error
content_hash
raw_metadata_json
attachments_json
updated_at
```

`body_status`：

```text
available
pending
missing
extract_failed
unsupported
```

### 9.2 新闻正文

`ak.stock_news_em()` 返回的“新闻内容”必须保存到 `body_text`，不能只用于生成 explanation 后丢弃。

### 9.3 公告正文

流程：

1. 公告列表先保存标题、链接和附件元数据；
2. 后台下载巨潮 PDF/HTML；
3. 只允许受信任的巨潮域名，防止 SSRF；
4. 限制响应大小、页数和正文字符数；
5. PDF 使用 `pypdf` 提取文本；
6. 表格和扫描 PDF 暂时标记 `extract_failed/ocr_required`；
7. 正文 hash 变化时生成新的 AI 缓存键。

### 9.4 `ai_jobs`

持久化字段：

```text
id
target_type
target_id
input_hash
status
attempts
max_attempts
model
prompt_version
schema_version
output_json
error_code
error_message
created_at
started_at
completed_at
updated_at
```

要求：

- 同一个 `input_hash` 只运行一次；
- 服务启动时恢复 `pending/retrying`；
- 成功缓存已存在时直接标记 `succeeded`；
- Android 只轮询任务状态，不反复重新抓整份新闻列表；
- 错误日志不得包含 API Key 和完整个人数据。

---

## 10. Android 页面路线

### 10.1 账户设置

新增：

- 默认账户名称；
- 基础币种；
- CNY/HKD 可用现金；
- 最低现金保留比例；
- 单笔最大投入比例；
- 是否开启数值候选方案。

现金旁边显示：

> 现金仅用于计算仓位候选，不代表系统拥有资金操作权限。

### 10.2 研究候选方案卡片

显示：

- 动作：观察/加仓候选/减仓候选/退出候选；
- 价格区间；
- 有效期；
- 失效条件；
- 建议数量或不能计算数量的原因；
- 当前仓位 → 目标仓位；
- 现金占用；
- 数据时间；
- 证据完整度；
- 原始证据和待核验项。

按钮：

```text
记录为已阅读
记录真实成交
继续模拟观察
取消跟踪
```

绝不提供“一键买入”。

### 10.3 历史建议页面

筛选：

- 标的；
- 动作；
- 已触发/未触发；
- 真实成交/模拟成交；
- 1/5/20/60 日；
- 引擎版本。

展示：

- 当时建议；
- 当时行情和规则；
- 是否触发；
- 模拟成交口径；
- 后续净收益与最大回撤；
- 基准和超额收益；
- 用户反馈；
- 后来发生的新事件。

### 10.4 AI 信息流状态

新闻/公告卡片显示：

```text
AI 等待分析
正在读取正文
分析完成
正文提取失败
AI 暂时不可用
重新分析
```

---

## 11. 按 PR 拆分的执行顺序

本地 Agent 必须按顺序执行。每个 PR 只解决一个完整问题。

### PR 1：数据基线与数值安全

目标：

- 扩展日线为 OHLCV；
- 新增 `instrument_metadata`；
- 统一 `Decimal` 序列化工具；
- 补行情新鲜度硬门槛；
- 修正 K 线使用真实 `open`。

主要文件：

```text
backend/app/price_history.py
backend/app/storage.py
backend/app/main.py
backend/app/market.py
android/.../ApiClient.kt
android/.../MainActivity.kt
backend/tests/test_price_history.py
```

验收：

- A 股、ETF、港股都能保存 open/high/low/close/volume；
- 缺 lot size 时不会生成数量；
- stale 行情不会生成数值候选；
- 旧数据库可自动迁移。

### PR 2：账户、现金和估值

目标：

- `portfolio_accounts`；
- `cash_balances`；
- holdings 关联账户；
- 按币种计算账户权益；
- Android 录入可用现金。

验收：

- 不同币种现金不混用；
- 现金不足时给出明确 `quantity_status`；
- 现金修改产生版本和时间；
- 现有持仓自动归入 default 账户。

### PR 3：不可变候选建议与审计

目标：

- 创建 recommendation 相关表；
- 保存完整输入快照；
- 创建查询、确认、取消和真实成交关联 API；
- 暂不自动计算买卖点。

验收：

- 历史建议不可被新规则覆盖；
- 相同 input hash 幂等；
- 真实成交与模拟建议分开；
- 能完整回放当时证据。

### PR 4：确定性点位与数量引擎

新增建议：

```text
backend/app/recommendation_engine.py
backend/app/position_sizing.py
backend/app/recommendation_policy.py
```

目标：

- 区间生成；
- 失效价；
- 仓位上限；
- 风险预算；
- 现金和整手取整；
- blocked 原因；
- 最多三档分批方案。

验收：

- LLM 断开时引擎仍能运行；
- 所有数值都有公式和输入快照；
- 任何硬门槛失败时数量为 null；
- 加仓后不突破仓位上限；
- 结果不依赖未来日线。

### PR 5：模拟触发和历史浮盈

新增建议：

```text
backend/app/recommendation_evaluator.py
backend/app/paper_portfolio.py
backend/app/recommendation_scorecard.py
```

目标：

- 每日 OHLC 判断区间是否触发；
- 创建 paper position；
- 计算费用、滑点、1/5/20/60 日表现；
- MFE/MAE；
- 基准和超额收益；
- 未触发建议不计算模拟浮盈。

验收：

- T 日建议最早 T+1 触发；
- 跳空场景测试完整；
- 重算幂等；
- 每条评估保存版本；
- 不使用未来数据修改原建议。

### PR 6：新闻/公告正文与 AI Jobs

目标：

- `content_documents`；
- 保存新闻正文；
- 后台提取公告正文；
- `ai_jobs` 状态、恢复、重试；
- 正文变化自动失效旧缓存。

验收：

- 新闻正文实际进入 Prompt；
- PDF 失败不会拖垮信息流；
- 服务重启可恢复任务；
- 首次打开能看见 pending，完成后独立刷新状态；
- 错误原因可诊断。

### PR 7：DeepSeek 解释层

目标：

- AI 解释程序生成的候选方案；
- 输出事实、推断、限制和待核验项；
- 不允许 AI 改写区间与数量；
- 保存 model/prompt/schema/input hash。

验收：

- Pydantic 严格校验；
- AI 返回不同数值时直接丢弃该数值；
- AI 失败不影响程序建议；
- 每段解释能关联 evidence id。

### PR 8：Android 候选方案和历史复盘

目标：

- 账户现金页；
- 候选方案卡；
- 真实成交记录；
- 模拟表现页；
- AI 状态轮询。

验收：

- 不存在自动下单入口；
- 数量不可计算时显示原因；
- 真实与模拟有明显标签；
- 页面展示数据时间和评估口径；
- Android 变更合并后才按现有发布规则生成新 APK。

### PR 9：离线评测和反馈

目标：

- 固定测试案例；
- 用户反馈分类；
- 引擎版本对比；
- 建议覆盖率、触发率、收益、回撤和数据缺失率；
- 不能只看平均收益。

建议指标：

```text
data_ready_rate
recommendation_block_rate
zone_trigger_rate
paper_fill_rate
positive_net_return_rate
average_excess_return
max_adverse_excursion
position_limit_violation_count
lookahead_violation_count
schema_valid_rate
```

---

## 12. 本地 Agent 的通用执行约束

每个 PR 都必须遵守：

1. 开始前拉取最新 `main`，不要基于旧的 PR #8 分支继续开发。
2. 不修改用户已有的未提交文件。
3. 数据库变更必须支持旧 SQLite 原地迁移。
4. 金额和价格的新代码使用 `Decimal`，不得新增裸 `float` 金额运算。
5. 网络抓取不得发生在 HTTP 请求主链路。
6. 批量处理单个证券失败时，其余证券继续。
7. 每个外部数据都保存 source、as_of、retrieved_at 和 freshness。
8. 所有建议保存 engine/rule/input/evaluation 版本。
9. 不新增券商认证信息，不实现交易 API。
10. 后端 PR 不应发布 Android APK；只有实际修改 `android/` 的 PR 才发布。
11. 每个 PR 至少运行：

```bash
cd backend
python -m compileall -q app
python -m pytest -q
```

Android 有变化时再运行：

```bash
cd android
./gradlew --no-daemon :app:assembleDebug :app:assembleRelease
```

---

## 13. 第一批必须准备的测试场景

### 账户与数量

- 现金足够，但已达到最大仓位；
- 现金不足一个整手；
- CNY 持仓只有 HKD 现金；
- 港股 lot size 缺失；
- 风险预算比现金预算更严格；
- 现金很多但单笔投入上限很低；
- 减仓数量超过实际持仓；
- 退出后剩余零碎股。

### 点位

- 日线不足 60 天；
- ATR 为零；
- 支撑价高于当前价；
- 失效价高于入场区间；
- stale fallback；
- 开盘跳过买入区间；
- 开盘直接跌破失效位；
- 建议生成当天已触及区间，但 T+1 未触及。

### 模拟复盘

- 区间从未触发；
- 触发后上涨；
- 触发后先跌破失效位再上涨；
- 同一天同时触及入场位和失效位；
- 停牌和缺少日线；
- 建议有效期结束；
- 重复执行每日评估；
- 引擎升级后旧记录保持不变。

同一天既触发入场又触发失效，而只有日线无法判断先后时，应采用保守处理：

```text
标记 ambiguous_intraday_order
不计为成功建议
或按最不利顺序计算
```

---

## 14. 推荐的首个本地 Agent 指令

把下面内容作为第一条开发指令：

```text
请读取 THIRD_HAND_NEXT_ROADMAP.md，以最新 main 为基线，只实现“PR 1：数据基线与数值安全”。

本次不要实现推荐引擎、现金账户或 AI 改动。需要：
1. 扩展 daily_price_cache 和 PriceHistoryService，保存 open/high/low/close/volume/amount 与固定复权口径；
2. 新增 instrument_metadata，支持 market/currency/lot_size/price_tick/source/as_of；
3. 增加 Decimal 序列化和金额计算工具；
4. 为行情时效增加可复用的硬门槛判断；
5. Android K 线改用真实 open；
6. 补齐 A 股、ETF、港股、缺数据、旧库迁移测试；
7. 不修改 APK 发布触发规则；
8. 完成后运行后端完整测试与 Android Debug/Release 构建，提交草稿 PR。

任何数据源拿不到 lot size 时必须保留 null，不能猜测。
```

---

## 15. 最终完成定义

只有满足以下条件，才能认为新功能形成闭环：

- 用户可以选择是否录入现金并主动开启数值候选；
- 系统能解释为什么能或不能计算数量；
- 区间和数量完全受现金、风险、仓位和交易单位限制；
- 建议生成时的证据不可变；
- 未触发、模拟触发、真实成交严格区分；
- 未真实买入也能在“区间实际触发后”看到模拟浮盈和回撤；
- 历史建议可以按统一口径做 1/5/20/60 日对照；
- DeepSeek 只能解释，不能绕过程序约束；
- 任何建议都能追溯数据来源、时间、规则版本和引擎版本；
- 系统不自动下单，不把历史收益包装成未来概率。

