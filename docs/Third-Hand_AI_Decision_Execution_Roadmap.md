# Third-Hand AI 决策助手工程执行路线

> 文档用途：直接交给编码 Agent，作为后续重构和实现的唯一主路线。
>
> 目标：消除行情、技术面、风险、新闻、持仓、交易计划、个人规则、DeepSeek 分析和历史评估之间的信息孤岛，形成一条可审计、可回放、可测试、可回滚的 AI 辅助决策链。
>
> 本文不是产品畅想。所有阶段必须有明确输入、输出、数据库结构、接口、测试和验收条件。

---

## 1. 当前代码基线

当前仓库已经具有以下能力：

- 持仓与卖出记录；
- 可用现金录入；
- 实时或缓存行情；
- 历史日线；
- RSI、MACD、均线、ATR、回撤等技术指标；
- 历史风险统计；
- 市场环境；
- 相对强弱；
- 新闻、公告和 DeepSeek 结构化摘要；
- 个人规则；
- 交易计划；
- 建议生成、建议事件、纸面持仓和收益评估；
- AI 任务、缓存、模型版本和分析运行记录。

当前核心问题不是“缺少模块”，而是这些模块没有进入同一决策上下文：

```text
新闻/公告 -> DeepSeek 摘要
行情/风险/技术 -> portfolio_analysis 固定规则
交易计划/现金 -> recommendations 简单 add/trim
历史评估 -> 独立评估
```

现有结论往往先生成，再补充新闻、市场环境和相对强弱。DeepSeek 目前只参与新闻事实归纳，没有参与完整证据权衡；建议数量仍主要由固定 25% 规则产生。

---

## 2. 最终目标架构

必须实现以下单向流程：

```text
数据采集与持久化
        ↓
DecisionContextBuilder
        ↓
DataQualityGate
        ↓
EvidenceEngine
        ↓
ActionPolicyEngine
        ↓
DeepSeekResearchService
        ↓
DecisionGuard
        ↓
PositionSizingEngine
        ↓
DecisionReportAssembler
        ↓
持久化、展示、纸面跟踪、历史校准
```

核心原则：

1. 数据负责事实。
2. 程序负责计算、规则、约束和股数。
3. DeepSeek 负责事件理解、证据权衡、冲突识别和可读解释。
4. DeepSeek 不得直接决定最终股数。
5. DeepSeek 不得绕过硬性风控。
6. 所有结论必须能追溯到输入快照、证据、规则和版本。
7. 所有建议默认只用于研究和纸面跟踪，不自动连接券商执行。

---

## 3. 严格边界

### 3.1 必须实现

- 建立统一决策上下文；
- 统一数据时间、来源、新鲜度和缺失状态；
- 建立标准证据模型；
- 建立确定性动作策略；
- 建立受约束的 DeepSeek 研究判断；
- 建立确定性仓位计算；
- 输出结构化分析过程和最终操作候选；
- 保存每次分析的不可变快照；
- 建立建议生命周期；
- 修复历史评估的时间穿越；
- 建立纸面收益、MFE、MAE 和历史校准；
- 提供完整单元测试和集成测试。

### 3.2 本轮禁止实现

- 自动下单；
- 券商账号、密码、Cookie 或短信验证码接入；
- 高频交易；
- 秒级盘口策略；
- 让 DeepSeek 自由生成无约束买卖数量；
- 用单个置信度同时表达数据完整度、模型不确定性和历史表现；
- 用历史未来数据生成当时建议；
- 用新闻标题代替公告原文；
- 将模型自然语言直接写入交易执行逻辑；
- 在 HTTP 请求线程中同步抓取全部上游行情和运行复杂 AI；
- 大规模 Agent 自主循环修改生产数据。

### 3.3 非目标

第一阶段不追求“预测明天涨跌”。目标是：

- 形成一致的证据链；
- 判断当前是否应该观察、持有、加仓、减仓或退出；
- 解释为什么；
- 给出受风险预算约束的数量候选；
- 长期验证建议是否有效。

---

## 4. 新目录与模块职责

在 `backend/app/` 下增加：

```text
decision_models.py
decision_context.py
data_quality.py
evidence_engine.py
action_policy.py
decision_ai.py
decision_guard.py
position_sizing.py
decision_orchestrator.py
decision_evaluator.py
decision_prompts.py
```

保留现有模块，但重新限定职责：

```text
ai_analysis.py
    只负责新闻和公告的事实结构化。

technical_analysis.py
    只负责技术指标计算，不产生买卖动作。

risk.py
    只负责风险统计，不产生买卖动作。

portfolio_analysis.py
    逐步退化为兼容层，最终由 decision_orchestrator 替代。

recommendations.py
    第一阶段保留兼容接口，内部改为调用 decision_orchestrator；
    后续只保留成交模拟与评估函数。

storage.py
    只负责持久化，不包含决策业务逻辑。

main.py
    只做 API 编排、鉴权、参数校验和任务提交；
    不直接拼接复杂决策逻辑。
```

---

## 5. 统一数据模型

所有模型使用 Pydantic，必须 `extra="forbid"`，重要枚举使用 `Literal` 或 Enum。

### 5.1 DecisionContext

文件：`backend/app/decision_models.py`

```python
class DecisionContext(BaseModel):
    context_id: str
    symbol: str
    name: str
    generated_at: datetime
    decision_horizon: Literal["intraday", "swing", "position"]

    account: AccountSnapshot
    position: PositionSnapshot | None
    quote: QuoteSnapshot | None
    daily_bars: DailyBarSummary
    technical: TechnicalSnapshot | None
    risk: RiskSnapshot | None
    market_regime: MarketRegimeSnapshot | None
    relative_strength: RelativeStrengthSnapshot | None
    events: list[EventSnapshot]
    trade_plan: TradePlanSnapshot | None
    personal_rule: PersonalRuleSnapshot | None
    instrument: InstrumentSnapshot | None
    data_quality: DataQualitySummary

    source_versions: dict[str, str]
    input_hash: str
```

### 5.2 AccountSnapshot

至少包含：

```text
available_cash
total_market_value
total_assets
cash_percent
account_currency
```

`total_assets` 第一版计算方式：

```text
available_cash + 全部有效持仓市值
```

如果存在行情缺失：

```text
total_assets = None
position sizing 被阻止
```

不得使用成本金额代替缺失的当前市值。

### 5.3 PositionSnapshot

至少包含：

```text
quantity
average_cost
current_price
market_value
cost_value
unrealized_pnl
unrealized_pnl_percent
position_percent
```

### 5.4 QuoteSnapshot

至少包含：

```text
price
open
high
low
previous_close
change_percent
volume
amount
source
as_of
retrieved_at
is_realtime
delay_seconds
freshness_status
```

### 5.5 DataQualitySummary

```python
class DataQualitySummary(BaseModel):
    status: Literal["ready", "degraded", "blocked"]
    score_percent: int
    missing_fields: list[str]
    stale_fields: list[str]
    warnings: list[str]
```

### 5.6 EvidenceItem

```python
class EvidenceItem(BaseModel):
    evidence_id: str
    category: Literal[
        "position", "price", "trend", "momentum", "volatility",
        "volume", "event", "fundamental", "market", "relative",
        "liquidity", "plan", "risk", "data_quality"
    ]
    direction: Literal["positive", "negative", "neutral", "uncertain"]
    strength: float = Field(ge=0, le=1)
    title: str
    description: str
    value: float | str | bool | None
    threshold: float | str | None
    source: str
    as_of: datetime | str | None
    fresh: bool
    rule_id: str | None
    source_reference: str | None
```

### 5.7 ActionCandidate

```python
class ActionCandidate(BaseModel):
    action: Literal["OPEN", "ADD", "HOLD", "WATCH", "REDUCE", "EXIT", "BLOCKED"]
    priority: int
    policy_score: float
    supporting_evidence_ids: list[str]
    opposing_evidence_ids: list[str]
    triggered_rule_ids: list[str]
    blocked_reasons: list[str]
```

### 5.8 AiResearchAssessment

```python
class AiResearchAssessment(BaseModel):
    thesis_status: Literal["strengthened", "unchanged", "weakened", "invalidated", "unknown"]
    preferred_action: Literal["OPEN", "ADD", "HOLD", "WATCH", "REDUCE", "EXIT", "BLOCKED"]
    supporting_evidence_ids: list[str]
    opposing_evidence_ids: list[str]
    missing_evidence: list[str]
    reasoning_steps: list[ReasoningStep]
    uncertainty: Literal["low", "medium", "high"]
    summary: str
```

模型只能引用输入中已经存在的 `evidence_id`。出现未知 ID 必须判定输出无效并重试一次。

### 5.9 PositionSizingResult

```python
class PositionSizingResult(BaseModel):
    status: Literal["ready", "blocked", "not_applicable"]
    current_quantity: float
    suggested_quantity: float | None
    target_quantity: float | None
    current_position_percent: float | None
    target_position_percent: float | None
    quantity_by_risk: float | None
    quantity_by_cash: float | None
    quantity_by_position_cap: float | None
    quantity_by_liquidity: float | None
    lot_size: int | None
    entry_price: float | None
    invalidation_price: float | None
    risk_per_share: float | None
    risk_capital: float | None
    blocked_reasons: list[str]
    sizing_version: str
```

### 5.10 DecisionReport

```python
class DecisionReport(BaseModel):
    decision_id: str
    context_id: str
    symbol: str
    generated_at: datetime
    status: Literal["READY", "BLOCKED", "DEGRADED"]
    action: Literal["OPEN", "ADD", "HOLD", "WATCH", "REDUCE", "EXIT", "BLOCKED"]
    action_level: Literal["LOW", "MEDIUM", "HIGH"]

    summary: str
    analysis_trace: list[AnalysisTraceStep]
    evidence: list[EvidenceItem]
    action_candidates: list[ActionCandidate]
    ai_assessment: AiResearchAssessment | None
    sizing: PositionSizingResult

    evidence_coverage_percent: int
    model_uncertainty: Literal["low", "medium", "high", "not_used"]
    historical_calibration: dict[str, object] | None

    policy_version: str
    prompt_version: str | None
    schema_version: str
    model: str | None
    input_hash: str
    automatic_execution: bool = False
```

---

## 6. DecisionContextBuilder

文件：`backend/app/decision_context.py`

### 6.1 输入

```text
symbol
store
quote cache
technical service
risk cache
market regime service
relative strength service
content cache
trade plan
personal rules
instrument metadata
```

### 6.2 输出

只输出一个完整的 `DecisionContext`。

### 6.3 实现要求

1. 所有数据从持久化缓存或明确的服务接口读取。
2. 不允许在 Builder 内直接调用 DeepSeek。
3. 不允许在 Builder 内产生最终动作。
4. 每个字段记录数据来源和时间。
5. 对 `symbol` 做统一标准化。
6. 计算账户总资产和当前仓位占比。
7. 事件只取与目标证券明确关联的内容。
8. 事件优先级：交易所公告 > 公司公告 > 正规财经媒体 > 其他来源。
9. 最多保留最近 10 个事件，默认 5 个。
10. 所有输入序列化后计算 `input_hash`。
11. 相同输入必须产生相同 hash。
12. 构建完成后不得修改原对象。

### 6.4 数据时间规则

第一版以波段分析为主：

```text
决策周期：swing
行情最大允许延迟：交易时段 5 分钟，非交易时段允许使用最近收盘
日线最大允许延迟：最近一个已结束交易日
新闻/公告：默认 30 日，重大事件允许 90 日
风险指标：必须基于至少 60 根日线
技术指标：必须基于至少 60 根日线
```

时间阈值配置化：

```env
DECISION_QUOTE_MAX_AGE_SECONDS=300
DECISION_EVENT_LOOKBACK_DAYS=30
DECISION_MAJOR_EVENT_LOOKBACK_DAYS=90
DECISION_MIN_DAILY_BARS=60
```

---

## 7. DataQualityGate

文件：`backend/app/data_quality.py`

### 7.1 硬阻断条件

任一条件成立时，最终动作只能是 `BLOCKED` 或 `WATCH`，不得输出股数：

- 无当前价格；
- 行情时间无法判断；
- 历史日线少于 60 根；
- 无法计算账户总资产；
- 无证券手数信息且动作涉及买卖数量；
- 无启用的交易计划；
- 交易计划缺少失效条件；
- 交易计划缺少最大仓位；
- 交易计划缺少风险预算；
- 持仓数量或成本异常；
- 现金为负；
- 关键数据时间晚于分析时间；
- 输入 hash 不可生成；
- 数据源返回明显矛盾价格。

### 7.2 降级条件

以下条件允许继续分析，但状态为 `DEGRADED`：

- 新闻正文缺失，仅有标题；
- 风险指标暂不可用；
- 市场环境不可用；
- 相对强弱未配置；
- 财务与估值数据缺失；
- 事件来源级别较低。

### 7.3 数据质量分数

分数只表示输入完整度，不表示操作正确率。

建议权重：

```text
行情与时间       20
持仓与账户       20
交易计划         20
历史日线与技术   15
风险统计         10
事件证据         10
市场和相对强弱    5
```

---

## 8. EvidenceEngine

文件：`backend/app/evidence_engine.py`

EvidenceEngine 只把事实转换为标准证据，不做最终动作。

### 8.1 第一版必须实现的证据

#### 持仓证据

```text
position.above_max
position.near_max
position.loss_exceeds_review_threshold
position.profit_large
position.cash_constrained
```

#### 趋势证据

```text
trend.above_sma20
trend.above_sma60
trend.sma20_above_sma60
trend.below_sma20_and_sma60
trend.drawdown_60d
```

#### 动量证据

```text
momentum.rsi_hot
momentum.rsi_cold
momentum.macd_positive
momentum.macd_negative
```

#### 波动与风险证据

```text
volatility.atr_high
risk.historical_downside_high
risk.annualized_volatility_high
```

#### 市场证据

```text
market.supportive
market.mixed
market.defensive
```

#### 相对强弱证据

```text
relative.outperform_20d
relative.neutral_20d
relative.underperform_20d
```

#### 事件证据

从 `ai_analysis.py` 已结构化事件生成：

```text
event.positive
 event.negative
 event.uncertain
 event.major_unverified
```

事件证据必须带原始来源 URL 或内容 ID。

#### 交易计划证据

```text
plan.entry_condition_met
plan.add_condition_met
plan.reduce_condition_met
plan.exit_condition_met
plan.thesis_invalidated
```

### 8.2 强度规则

强度必须由确定性函数计算，不交给模型自由评分。

示例：

```text
仓位超过上限 0-10%：0.5
仓位超过上限 10-30%：0.7
仓位超过上限 30%以上：0.9
```

所有阈值集中配置，不可散落在多个文件中。

建议新增：

```text
backend/app/decision_config.py
```

---

## 9. ActionPolicyEngine

文件：`backend/app/action_policy.py`

ActionPolicyEngine 是确定性的。相同上下文和证据必须产生相同候选。

### 9.1 动作定义

```text
OPEN     无持仓，新建仓候选
ADD      已有持仓，增加仓位候选
HOLD     继续持有，不调整
WATCH    等待条件或证据，不产生数量
REDUCE   减少部分仓位
EXIT     全部退出
BLOCKED  数据或规则不允许形成候选
```

### 9.2 硬规则优先级

从高到低：

```text
1. 数据阻断
2. 交易逻辑失效
3. 仓位硬上限
4. 风险预算
5. 流动性与手数
6. 重大负面事件
7. 技术与相对强弱
8. 市场环境
9. 正面事件和加仓条件
10. 默认 HOLD/WATCH
```

### 9.3 第一版动作规则

#### BLOCKED

```text
DataQualityGate.status == blocked
```

#### EXIT

满足任一：

```text
交易计划 exit_condition 明确命中
交易逻辑 thesis_status == invalidated 且证据完整
持仓证券已退市/停牌等不可持续条件，由独立状态源确认
```

#### REDUCE

满足任一：

```text
当前仓位 > max_position_percent
reduce_condition 命中
重大负面事件 + 趋势偏弱
市场防守 + 相对弱 + 趋势偏弱
历史风险超过个人阈值
```

#### ADD

必须同时满足：

```text
已有持仓
add_condition 命中
当前仓位低于最大仓位
有足够现金
风险预算可计算
无重大未核验负面事件
趋势不为明确空头
市场环境不是 defensive，或交易计划明确允许逆势
```

#### OPEN

必须同时满足：

```text
无持仓
entry_condition 命中
有完整交易计划
有失效价格
有现金
风险预算可计算
```

#### HOLD

```text
已有持仓
无退出、减仓或加仓条件
数据完整
```

#### WATCH

```text
有分析价值但关键条件未确认
存在重大未核验事件
多空证据明显冲突
数据质量 degraded 且不足以形成数量
```

### 9.4 策略输出

输出至少 1 个候选，最多 3 个候选，按优先级排序。

不能只输出分数，必须输出：

```text
action
supporting_evidence_ids
opposing_evidence_ids
triggered_rule_ids
blocked_reasons
```

---

## 10. DeepSeekResearchService

文件：`backend/app/decision_ai.py`

### 10.1 DeepSeek 的职责

- 解释公告和事件对交易逻辑的可能影响；
- 比较正反证据；
- 识别证据冲突；
- 判断原交易逻辑是增强、未变、减弱还是失效；
- 在允许的候选动作中选择偏好动作；
- 输出用户可读的分析摘要；
- 指出缺失证据。

### 10.2 DeepSeek 禁止事项

- 不得生成候选列表之外的动作；
- 不得生成股数；
- 不得修改价格、技术指标或持仓数据；
- 不得声明未提供的数据为事实；
- 不得输出“必涨、必跌、确定盈利”；
- 不得把模型不确定性写成胜率；
- 不得直接生成自动执行指令；
- 不得返回未知 evidence_id；
- 不得输出 Markdown；
- 不得要求或保存隐藏思维链。

### 10.3 输入

只允许输入压缩后的：

```text
DecisionContext 摘要
EvidenceItem 列表
ActionCandidate 列表
最近相关复盘案例，最多 5 条
历史校准摘要
```

不得直接输入全部数据库内容。

### 10.4 输出 Schema

使用 `AiResearchAssessment`，严格校验。

### 10.5 模型策略

```text
新闻/公告结构化：现有快速模型
完整决策权衡：推理模型
```

环境变量：

```env
DECISION_AI_ENABLED=true
DECISION_AI_MODEL=${DEEPSEEK_REASONING_MODEL}
DECISION_AI_PROMPT_VERSION=decision-research-v1
DECISION_AI_SCHEMA_VERSION=decision-research-schema-v1
DECISION_AI_TIMEOUT_SECONDS=60
DECISION_AI_MAX_TOKENS=1800
DECISION_AI_SCHEMA_RETRIES=1
```

### 10.6 失败策略

DeepSeek 失败时：

- 不得使整个决策接口失败；
- 使用确定性 ActionPolicyEngine 结果；
- `model_uncertainty=not_used`；
- `ai_assessment=None`；
- 报告状态可保持 READY 或 DEGRADED；
- 记录错误码，不记录完整敏感 Prompt；
- 不得生成空对象伪装成功。

### 10.7 输出修复

最多一次 Schema 修复重试。

修复仍失败：

```text
放弃 AI 结果
保留规则候选
写入 ai_job failed
```

---

## 11. DecisionGuard

文件：`backend/app/decision_guard.py`

DeepSeek 输出后必须经过守卫层。

### 11.1 校验项目

- AI 动作是否在候选动作中；
- 引用 evidence_id 是否全部存在；
- AI 是否尝试产生数量；
- AI 是否出现绝对收益承诺；
- EXIT 是否有失效逻辑或强证据；
- ADD/OPEN 是否被数据质量或负面事件阻止；
- REDUCE/EXIT 是否超过持仓数量；
- HOLD 是否与命中的硬性退出规则冲突；
- 输出是否包含未知字段；
- Prompt、Schema、模型版本是否记录。

### 11.2 最终动作确定

规则：

```text
硬规则永远优先于 AI
AI 只能在合法候选中选择
AI 缺失时使用最高优先级候选
AI 与硬规则冲突时使用硬规则
```

---

## 12. PositionSizingEngine

文件：`backend/app/position_sizing.py`

数量必须由程序计算。

### 12.1 输入

```text
final_action
DecisionContext
trade_plan.max_position_percent
trade_plan.risk_budget_percent
entry_price
invalidation_price
instrument.lot_size
instrument.price_tick
```

### 12.2 OPEN/ADD 计算

```text
risk_capital = total_assets * risk_budget_percent / 100
risk_per_share = abs(entry_price - invalidation_price)
quantity_by_risk = risk_capital / risk_per_share
quantity_by_cash = available_cash / entry_price
max_position_value = total_assets * max_position_percent / 100
quantity_by_position_cap = (max_position_value - current_market_value) / entry_price
```

流动性限制第一版：

```text
建议金额不得超过最近有效日均成交额的 0.1%
```

```text
quantity_by_liquidity = liquidity_value_cap / entry_price
```

最终数量：

```text
min(
  quantity_by_risk,
  quantity_by_cash,
  quantity_by_position_cap,
  quantity_by_liquidity
)
```

按照 `lot_size` 向下取整。

### 12.3 REDUCE 计算

优先减到目标仓位：

```text
target_position_percent = min(
  max_position_percent,
  policy_target_percent
)

target_market_value = total_assets * target_position_percent / 100
quantity_to_reduce = (current_market_value - target_market_value) / current_price
```

如果只是轻度风险：

```text
policy_target_percent = 当前仓位和最大仓位之间的中位值
```

中度风险：

```text
policy_target_percent = max_position_percent
```

高风险：

```text
policy_target_percent = max_position_percent * 0.5
```

必须按 `lot_size` 取整，且不得超过当前持仓。

### 12.4 EXIT 计算

```text
suggested_quantity = current_quantity
target_quantity = 0
```

### 12.5 HOLD/WATCH/BLOCKED

不得输出建议数量。

### 12.6 阻断条件

- `total_assets` 缺失；
- `entry_price <= 0`；
- `invalidation_price` 缺失；
- `risk_per_share <= 0`；
- `lot_size` 缺失；
- `max_position_percent` 非法；
- `risk_budget_percent` 非法；
- 流动性数据缺失且配置要求必须检查；
- 计算结果小于一手。

禁止使用固定“现金 25%”或“持仓 25%”作为最终算法。

---

## 13. DecisionOrchestrator

文件：`backend/app/decision_orchestrator.py`

### 13.1 流程

```python
context = context_builder.build(symbol)
quality = data_quality_gate.evaluate(context)
evidence = evidence_engine.build(context)
candidates = action_policy.evaluate(context, evidence)
ai_assessment = decision_ai.assess(context, evidence, candidates)
final_action = decision_guard.resolve(context, evidence, candidates, ai_assessment)
sizing = position_sizing.calculate(final_action, context, evidence)
report = assembler.build(...)
store.save_decision_context(context)
store.save_decision_report(report)
store.save_decision_events(report)
return report
```

### 13.2 事务边界

- 构建上下文不写数据库；
- 保存 context、report 和初始事件必须在同一事务；
- AI 失败不得回滚确定性报告；
- 重复请求以 `input_hash + policy_version + prompt_version` 幂等；
- 相同输入默认返回已有报告；
- `force=true` 仅管理员或开发接口允许。

### 13.3 并发控制

同一 `symbol + input_hash` 只允许一个运行中的决策任务。

实现方式：

- 数据库唯一键；
- 或进程锁加数据库幂等；
- 不依赖单纯内存锁保证生产幂等。

---

## 14. 数据库迁移

不得继续只使用 `CREATE TABLE IF NOT EXISTS` 无版本迁移。

引入轻量迁移目录：

```text
backend/migrations/
001_decision_contexts.sql
002_decision_reports.sql
003_decision_events.sql
004_decision_ai_runs.sql
005_recommendation_time_fix.sql
```

新增表：

### 14.1 decision_contexts

```sql
CREATE TABLE decision_contexts (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    payload TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    UNIQUE(symbol, input_hash)
);
```

### 14.2 decision_reports

```sql
CREATE TABLE decision_reports (
    id TEXT PRIMARY KEY,
    context_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    prompt_version TEXT,
    schema_version TEXT NOT NULL,
    model TEXT,
    input_hash TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(context_id) REFERENCES decision_contexts(id)
);
```

索引：

```sql
CREATE INDEX idx_decision_reports_symbol_time
ON decision_reports(symbol, created_at DESC);
```

### 14.3 decision_events

```sql
CREATE TABLE decision_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_time TEXT NOT NULL,
    payload TEXT NOT NULL,
    FOREIGN KEY(decision_id) REFERENCES decision_reports(id)
);
```

事件类型：

```text
CREATED
AI_STARTED
AI_SUCCEEDED
AI_FAILED
TRIGGERED
INVALIDATED
EXPIRED
PAPER_FILLED
EVALUATED_1D
EVALUATED_5D
EVALUATED_20D
EVALUATED_60D
USER_EXECUTED
USER_IGNORED
```

### 14.4 decision_ai_runs

```sql
CREATE TABLE decision_ai_runs (
    id TEXT PRIMARY KEY,
    decision_id TEXT,
    input_hash TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    status TEXT NOT NULL,
    response_id TEXT,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    output_payload TEXT,
    created_at TEXT NOT NULL
);
```

### 14.5 修复旧建议表

`research_recommendations.payload` 必须增加：

```text
created_at
generated_trading_date
input_hash
policy_version
```

旧数据无法确认生成时间时：

```text
status = legacy_unverifiable
不得进入历史胜率统计
```

---

## 15. 修复历史评估时间穿越

文件：`backend/app/decision_evaluator.py` 和 `backend/app/recommendations.py`

当前任何建议只能使用建议生成之后的行情。

### 15.1 first_fill 新签名

```python
def first_fill(
    recommendation: dict,
    bars: list[dict],
    generated_trading_date: str,
) -> tuple[dict | None, int | None]:
```

过滤规则：

```text
只保留 trading_date > generated_trading_date 的 bar
```

如果策略定义允许“当日收盘生成，下一交易日执行”，必须严格从下一交易日开始。

### 15.2 禁止事项

- 不得从完整历史第一根 K 线搜索成交；
- 不得用生成前的价格评估建议；
- 不得把未触发建议视作亏损或盈利；
- 不得把样本数小于配置阈值的结果显示为可靠胜率。

### 15.3 评估指标

每个 1/5/20/60 交易日窗口记录：

```text
fill_date
fill_price
mark_price
gross_pnl
net_pnl
return_percent
mfe_percent
mae_percent
fee_rate
slippage_rate
```

额外记录：

```text
triggered
expired
invalidated_before_fill
```

---

## 16. API 设计

### 16.1 生成决策

```http
POST /v1/decisions/generate
```

请求：

```json
{
  "symbols": ["600519"],
  "force": false
}
```

响应：

```json
{
  "jobs": [
    {
      "symbol": "600519",
      "job_id": "uuid",
      "status": "pending"
    }
  ]
}
```

默认异步生成，避免 HTTP 请求同步等待 DeepSeek。

### 16.2 查询最新决策

```http
GET /v1/decisions/latest?symbol=600519
```

### 16.3 查询历史决策

```http
GET /v1/decisions?symbol=600519&limit=50
```

### 16.4 查询完整分析链

```http
GET /v1/decisions/{decision_id}
```

返回：

- context 摘要；
- evidence；
- candidates；
- AI assessment；
- sizing；
- lifecycle events；
- evaluations。

### 16.5 重试 AI

```http
POST /v1/decisions/{decision_id}/retry-ai
```

限制：

- 只重试 AI；
- 不重新抓行情；
- 使用原 context 和 evidence；
- 超过重试次数返回 422。

### 16.6 重新生成

```http
POST /v1/decisions/{symbol}/regenerate
```

必须构建新 context，不覆盖旧报告。

### 16.7 兼容接口

现有：

```text
/v1/research-recommendations/generate
```

第一阶段内部调用新 Orchestrator，并将新报告映射为旧 DTO。

兼容期至少保留一个版本，增加响应头或字段：

```text
deprecated=true
replacement=/v1/decisions/generate
```

---

## 17. 后台任务

第一版可继续使用现有轻量任务机制，但必须抽象任务执行器接口：

```python
class DecisionJobExecutor(Protocol):
    def submit(self, job_id: str) -> None: ...
```

开发环境：线程执行器。

生产演进：Celery/RQ/Arq。

任务状态：

```text
pending
running
succeeded
failed
retrying
cancelled
```

任务必须记录：

```text
attempts
max_attempts
error_code
error_message
started_at
finished_at
input_hash
```

服务重启后恢复 pending/retrying，running 任务重置为 pending。

---

## 18. 分析过程输出

用户需要看到“分析依据”，但不要暴露模型隐藏思维链。

统一 `analysis_trace`：

```json
[
  {
    "stage": "DATA_QUALITY",
    "status": "ok",
    "summary": "行情、日线、持仓和交易计划完整",
    "evidence_ids": []
  },
  {
    "stage": "POSITION_RISK",
    "status": "warning",
    "summary": "当前仓位 18.2%，高于个人上限 12%",
    "evidence_ids": ["position.above_max"]
  },
  {
    "stage": "TECHNICAL",
    "status": "negative",
    "summary": "价格低于 20 日和 60 日均线，MACD 动能偏弱",
    "evidence_ids": ["trend.below_sma20_and_sma60", "momentum.macd_negative"]
  },
  {
    "stage": "EVENT",
    "status": "uncertain",
    "summary": "存在减持事件，实际完成比例仍需核验",
    "evidence_ids": ["event.major_unverified"]
  },
  {
    "stage": "ACTION_POLICY",
    "status": "ok",
    "summary": "合法候选为 REDUCE 和 WATCH，REDUCE 优先级更高",
    "evidence_ids": ["position.above_max", "trend.below_sma20_and_sma60"]
  },
  {
    "stage": "POSITION_SIZING",
    "status": "ok",
    "summary": "按最大仓位限制计算建议减仓 300 股",
    "evidence_ids": ["position.above_max"]
  }
]
```

---

## 19. 决策示例

```json
{
  "decision_id": "uuid",
  "symbol": "600519",
  "status": "READY",
  "action": "REDUCE",
  "action_level": "MEDIUM",
  "summary": "当前仓位超过个人上限，技术趋势和相对强弱偏弱，建议将仓位降至风险上限以内。",
  "sizing": {
    "status": "ready",
    "current_quantity": 1000,
    "suggested_quantity": 300,
    "target_quantity": 700,
    "current_position_percent": 18.2,
    "target_position_percent": 12.7,
    "lot_size": 100,
    "sizing_version": "risk-sizing-v1"
  },
  "evidence_coverage_percent": 86,
  "model_uncertainty": "medium",
  "automatic_execution": false
}
```

---

## 20. 版本管理

必须单独记录：

```text
context_schema_version
evidence_schema_version
policy_version
prompt_version
ai_schema_version
sizing_version
evaluation_version
model
```

禁止只保存一个模糊的 `analysis_version`。

建议初始版本：

```text
context-v1
evidence-v1
swing-policy-v1
decision-research-v1
decision-research-schema-v1
risk-sizing-v1
paper-evaluation-v2
```

任何影响结果的规则修改必须提升对应版本。

---

## 21. 日志与监控

### 21.1 必须记录

```text
decision_id
context_id
symbol
input_hash
job_id
policy_version
prompt_version
model
status
latency_ms
token_usage
blocked_reasons
error_code
```

### 21.2 禁止记录

- API Key；
- 完整用户持仓快照；
- 完整 Prompt；
- 新闻全文；
- 个人隐私字段；
- 模型隐藏推理过程。

### 21.3 指标

```text
decision_job_success_rate
decision_job_latency_p50/p95
ai_success_rate
ai_schema_failure_rate
ai_circuit_open_count
blocked_decision_rate
data_quality_degraded_rate
paper_fill_rate
recommendation_expiry_rate
```

---

## 22. 测试要求

### 22.1 单元测试

#### DecisionContextBuilder

- 正确合并全部数据；
- 数据来源和时间正确；
- input_hash 稳定；
- 数据变化后 hash 变化；
- 不修改输入对象。

#### DataQualityGate

- 缺行情阻断；
- 日线不足阻断；
- 无交易计划阻断；
- 新闻正文缺失降级；
- 非交易时段允许最近收盘。

#### EvidenceEngine

- 阈值边界测试；
- 仓位超限强度；
- 技术指标证据；
- 事件证据来源；
- 证据 ID 唯一。

#### ActionPolicyEngine

- BLOCKED 优先；
- EXIT 高于 REDUCE；
- REDUCE 高于 ADD；
- 重大负面事件阻止 ADD；
- 防守市场和相对弱产生 REDUCE/WATCH；
- 无条件时 HOLD。

#### DeepSeekResearchService

使用 FakeClient：

- 合法输出；
- 未知 evidence_id；
- 非法动作；
- JSON 错误后修复；
- 超时；
- 熔断；
- AI 失败时规则结果仍可用。

#### DecisionGuard

- AI 不得绕过硬规则；
- AI 不得产生候选之外动作；
- AI 不得改变数量；
- EXIT 必须有强规则依据。

#### PositionSizingEngine

- 风险预算限制；
- 现金限制；
- 最大仓位限制；
- 流动性限制；
- 手数取整；
- 不足一手；
- REDUCE 不超过持仓；
- EXIT 全部退出；
- WATCH 无数量。

#### DecisionEvaluator

- 只使用建议生成日之后的 K 线；
- 未触发不评估收益；
- 正确计算 MFE/MAE；
- 手续费和滑点；
- ADD 和 REDUCE 符号方向正确。

### 22.2 集成测试

至少覆盖：

1. 完整数据 + AI 成功；
2. 完整数据 + AI 失败；
3. 行情缺失；
4. 交易计划缺失；
5. 仓位超过上限；
6. 重大负面事件；
7. 触发 ADD 但现金不足；
8. 触发 REDUCE；
9. 触发 EXIT；
10. 重复请求幂等；
11. 服务重启后任务恢复；
12. 旧接口兼容。

### 22.3 Golden Tests

为典型场景保存固定输入和预期结构：

```text
tests/golden/decision_add.json
tests/golden/decision_reduce.json
tests/golden/decision_exit.json
tests/golden/decision_blocked.json
```

Golden Test 不要求模型自然语言完全相同，但要求：

- 动作合法；
- 证据引用合法；
- 数量一致；
- 版本完整；
- 无未知字段。

---

## 23. 分阶段执行计划

每个阶段独立提交，不得跨阶段大爆炸重构。

### 阶段 0：保护现状与补测试

目标：建立安全网。

任务：

- 为现有 `portfolio_analysis.py`、`recommendations.py`、`ai_analysis.py` 补足测试；
- 固化现有 API 响应；
- 添加数据库备份脚本；
- 添加 migration runner；
- 明确当前行为基线。

验收：

- 当前全部测试通过；
- 迁移可以重复运行；
- 数据库可备份和恢复；
- 未改变生产行为。

建议提交：

```text
chore: add decision refactor safety net and migration runner
```

### 阶段 1：统一 DecisionContext

任务：

- 新增 decision_models.py；
- 新增 decision_context.py；
- 新增 data_quality.py；
- 保存 decision_contexts；
- 新增只读调试接口：

```http
GET /v1/decisions/context/{symbol}
```

此阶段不产生新动作。

验收：

- 一只持仓可以生成完整 Context；
- 所有输入有来源和时间；
- hash 稳定；
- 缺失数据正确标记；
- 不影响旧接口。

提交：

```text
feat: add unified immutable decision context
```

### 阶段 2：EvidenceEngine

任务：

- 实现第一版证据；
- 增加证据调试接口；
- 阈值集中配置；
- 补完整边界测试。

接口：

```http
GET /v1/decisions/evidence/{symbol}
```

验收：

- 同输入产生同证据；
- 每条证据可追溯；
- 不产生最终动作；
- 无重复 ID。

提交：

```text
feat: add deterministic evidence engine
```

### 阶段 3：ActionPolicyEngine

任务：

- 实现动作枚举；
- 实现硬规则；
- 产生最多三个候选；
- 暂不调用 DeepSeek；
- 用新策略生成 shadow report，不替换旧建议。

Shadow 模式：

```env
DECISION_SHADOW_MODE=true
```

验收：

- 所有候选可解释；
- 硬规则优先级正确；
- 旧功能不受影响；
- shadow report 可查看但不展示为正式建议。

提交：

```text
feat: add deterministic action policy in shadow mode
```

### 阶段 4：PositionSizingEngine

任务：

- 使用总资产、最大仓位、风险预算、失效价格和流动性；
- 使用 instrument_metadata.lot_size；
- 删除最终算法中的固定 25%；
- 保留旧算法兼容开关。

配置：

```env
DECISION_SIZING_ENABLED=false
```

验收：

- 所有数量可重复计算；
- 数量不超过现金、仓位和风险限制；
- 不足一手时阻断；
- REDUCE/EXIT 数量合法。

提交：

```text
feat: add deterministic risk-based position sizing
```

### 阶段 5：修复建议评估

任务：

- 建议保存生成时间和交易日；
- first_fill 从下一交易日开始；
- 旧数据标记 legacy_unverifiable；
- 新增 60 日评估；
- 补 MFE/MAE 和触发状态。

验收：

- 不存在时间穿越；
- 未触发建议不产生收益；
- 历史校准只使用有效样本。

提交：

```text
fix: remove look-ahead bias from recommendation evaluation
```

### 阶段 6：接入 DeepSeek 决策研究

任务：

- 新增 decision_prompts.py；
- 新增 decision_ai.py；
- 新增 decision_guard.py；
- 引用 evidence_id；
- AI 只能在候选动作中选择；
- AI 失败回退规则候选；
- 保存 decision_ai_runs。

默认仍 Shadow：

```env
DECISION_AI_ENABLED=false
```

验收：

- AI 不生成股数；
- AI 不得绕过硬规则；
- 非法输出被拒绝；
- AI 失败仍有完整规则报告；
- token 和延迟可观测。

提交：

```text
feat: add guarded DeepSeek evidence reasoning
```

### 阶段 7：DecisionOrchestrator 和正式 API

任务：

- 串联完整流程；
- 新增 decision_reports、events 和 jobs；
- 新增异步 API；
- 兼容旧 recommendation 接口；
- 移动端新增决策详情页。

验收：

- 可以查看完整分析链；
- 相同输入幂等；
- 可重新生成但不覆盖历史；
- 旧接口仍可运行；
- 自动执行始终为 false。

提交：

```text
feat: add end-to-end auditable decision orchestration
```

### 阶段 8：Shadow 对比与灰度切换

至少运行 20 个交易日或积累足够有效样本。

对比：

```text
旧 action
新规则 action
AI preferred action
最终 guarded action
是否触发
1/5/20 日结果
MFE/MAE
```

切换条件：

- 数据阻断无误报严重问题；
- 无时间穿越；
- 规则结果可重复；
- AI 非法输出率低于配置阈值；
- AI 失败不影响主流程；
- 数量计算测试全部通过；
- 至少完成一次数据库恢复演练。

开关：

```env
DECISION_ENGINE_ENABLED=true
DECISION_SHADOW_MODE=false
DECISION_AI_ENABLED=true
DECISION_SIZING_ENABLED=true
```

---

## 24. Agent 执行协议

编码 Agent 必须遵守：

1. 每次只处理一个阶段。
2. 修改前读取相关完整文件。
3. 不做与阶段无关的 UI 或架构重写。
4. 每次提交必须包含测试。
5. 不允许删除旧接口，除非文档明确进入兼容结束阶段。
6. 不允许修改已有数据库数据而无迁移脚本。
7. 不允许把业务规则写入 Prompt 后从程序中删除。
8. 不允许让 LLM 参与数学计算的唯一来源。
9. 不允许吞掉异常；必须分类错误码。
10. 不允许把所有逻辑继续堆进 main.py。
11. 每阶段输出：

```text
变更文件
数据库迁移
新增接口
配置项
测试结果
兼容性影响
回滚方式
未完成事项
```

12. 每阶段完成后停止，等待下一阶段指令。

---

## 25. 回滚策略

所有新能力必须有开关：

```env
DECISION_ENGINE_ENABLED=false
DECISION_SHADOW_MODE=true
DECISION_AI_ENABLED=false
DECISION_SIZING_ENABLED=false
```

回滚要求：

- 关闭新引擎后旧接口继续工作；
- 新表保留，不删除历史；
- 新字段只新增，不破坏旧字段；
- API 兼容映射至少保留一个版本；
- 数据库迁移必须向前兼容；
- 不要求降级迁移删除数据。

---

## 26. 完成定义

以下条件全部满足，才算第一版成熟 AI 决策助手完成：

- [ ] 每次决策有完整不可变 DecisionContext；
- [ ] 所有数据有来源、时间和新鲜度；
- [ ] 决策基于标准 EvidenceItem；
- [ ] 硬规则和动作候选确定性可重复；
- [ ] DeepSeek 只做受约束证据权衡；
- [ ] DeepSeek 失败时系统仍可产生规则报告；
- [ ] 股数由风险、现金、仓位和流动性共同计算；
- [ ] 不再使用固定 25% 作为最终数量算法；
- [ ] AI 无法绕过硬性风控；
- [ ] 不存在历史评估时间穿越；
- [ ] 每条建议有生命周期和事件记录；
- [ ] 可以展示正面、负面、冲突和缺失证据；
- [ ] 可以展示分析过程摘要；
- [ ] 可以查看纸面成交、收益、MFE 和 MAE；
- [ ] 所有结果记录版本；
- [ ] 所有关键模块有测试；
- [ ] 新引擎可通过环境变量完全关闭；
- [ ] automatic_execution 永远为 false。

---

## 27. 第一条给 Agent 的执行指令

将以下内容原样交给 Agent：

```text
请严格按照 docs/Third-Hand_AI_Decision_Execution_Roadmap.md 执行“阶段 0：保护现状与补测试”。

本次只完成阶段 0，不要提前实现 DecisionContext、EvidenceEngine、DeepSeek 决策或仓位计算。

要求：
1. 先读取 backend/app/portfolio_analysis.py、recommendations.py、ai_analysis.py、storage.py、main.py 以及相关测试。
2. 为当前行为补齐回归测试，重点覆盖建议生成、新闻 AI Schema、纸面评估和数据库存储。
3. 增加可重复执行的 migration runner，但不修改现有业务行为。
4. 增加数据库备份与恢复说明或脚本。
5. 跑完全部后端测试。
6. 最后输出：变更文件、迁移、测试结果、兼容性影响、回滚方式和下一阶段建议。
7. 不要改动 Android UI，不要删除接口，不要重写 main.py。
```

---

## 28. 核心结论

这套系统的成熟方向不是“让 DeepSeek 更自由地炒股”，而是：

```text
统一数据
→ 标准证据
→ 硬规则候选
→ DeepSeek 证据权衡
→ 风控守卫
→ 确定性仓位计算
→ 历史追踪和校准
```

只有当每个数字、动作、证据和模型输出都能回放，Third-Hand 才能从“功能集合”变成真正可用、稳定、可持续改进的 AI 投资研究助手。
