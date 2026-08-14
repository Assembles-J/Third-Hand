# Third-Hand v2 前后台技术设计方案

## 1. 产品与治理目标

Third-Hand v2 从“行情 + 规则决策 + 纸面执行”演进为“候选管理 + 公司研究 + AI Research + 确定性交易决策 + 纸面执行”的受约束投资研究系统。

核心边界保持：

- AI 负责研究、解释、归档、提出可验证的再次激活条件；
- ActionPolicy 负责正式动作；
- PositionSizing 负责正式仓位；
- execution 只消费历史正式 DecisionReport；
- 动态 Research 数据默认 `RESEARCH_ONLY`；
- 人工加入候选池只增加研究优先级，不直接获得 OPEN 权限。

## 2. 总体架构

```text
Android
  |
  v
api/v1 domain routers
  |
  v
application_services
  |
  +----------------------+----------------------+------------------+
  |                      |                      |                  |
Candidate Domain    Decision Domain      Research Domain     Trading Domain
  |                      |                      |                  |
  |                 ActionPolicy          Company Intelligence   |
  |                 Gate Audit            Research Thesis        |
  |                      |                Activation Proposal     |
  +----------------------+----------------------+------------------+
                         |
                         v
                 repositories / local store
                         |
             +-----------+-----------+
             |                       |
       Local persisted data     Provider adapters
                                   |
                         Tencent/Tushare/AKShare/LLM
```

## 3. Backend package

```text
app/
  bootstrap/
  api/v1/
    health/
    admin/
    app_update/
    market/
    data_quality/
    portfolio/
    paper/
    decision/
    candidate/
    research/
    ai/
  application_services/
    candidate/
    decision/
    research/
    market/
    paper/
  domain/
    candidate/
    company/
    decision/
    research/
    market/
    trading/
  infrastructure/
    database/
    providers/
    market_data/
    ai/
  legacy/
```

当前 `app.application` 为迁移源，不是未来目标结构。新功能禁止继续新增到该文件。

## 4. Candidate Management

### 4.1 Candidate Source

支持四类来源：

- `PAPER_POSITION`：已有纸面持仓，始终进入风险监控；
- `DETERMINISTIC_ROTATION`：全市场确定性轮换；
- `USER_ADDED`：用户主动加入研究候选；
- `OPPORTUNITY_SCAN`：未来基于确定性基础条件产生的研究机会候选。

人工加入只表示“请优先研究”，不表示买入。

### 4.2 Lifecycle

```text
NEW
 -> ANALYZING
 -> ACTIVE
 -> WAITING_TRIGGER
 -> REACTIVATED
 -> OPEN_READY_RESEARCH
 -> ARCHIVED
```

`OPEN_READY_RESEARCH` 也不等于正式 OPEN；仍需 DecisionContext + ActionPolicy。

### 4.3 冷却与重复分析

AI 完成一次深度分析后，候选不能每天无条件重复消耗同一套工具。保存：

- `last_deep_analysis_at`
- `analysis_version`
- `thesis_hash`
- `cooldown_until`
- `reactivation_rules`

WAITING_TRIGGER 时只执行低成本 deterministic trigger checks，命中后才重新进入深度 Research。

### 4.4 Reactivation Rule

规则分为：

- PRICE：价格进入研究区间；
- TECHNICAL：趋势/均线/相对强度出现可验证变化；
- FUNDAMENTAL：收入、毛利、利润、现金流等公开指标达到条件；
- EVENT：存在指定类型、可验证来源的公告/事件；
- TIME：财报/定期复核日期到达。

AI 可以提出规则草案，但保存前必须结构化，不能只保存“新闻足够利好”这种不可判定文本。

示例：

```json
{
  "type": "PRICE",
  "metric": "last_price",
  "operator": "<=",
  "value": 18.5,
  "reason": "当前估值研究区间上沿",
  "source": "ai_research_proposal",
  "usage_scope": "RESEARCH_ONLY"
}
```

## 5. Company Intelligence

不是所有股票都只看行情、日线和普通新闻。重点研究股票需要 CompanyContext。

### 5.1 CompanyContext

```text
identity
business_model
products_and_segments
revenue_segments
margin_structure
profit_drivers
cash_flow_drivers
industry_position
competitors
competitive_advantages
management_and_capital_allocation
key_risks
catalysts
valuation_framework
key_metrics
source_lineage
as_of
```

例如小米集团的深度研究应至少能够组织：手机、IoT/生活消费品、互联网服务、智能汽车等业务线，以及对应收入、毛利/毛利率、利润驱动和关键经营指标，而不是只重复当天行情和新闻标题。

### 5.2 Research Priority

- L0：普通轮换，只做基础行情/风险；
- L1：技术观察；
- L2：重点跟踪；
- L3：深度公司研究；
- L4：持仓管理。

L3/L4 才默认加载较完整 CompanyContext，降低不必要的远程调用和 token 成本。

## 6. DecisionContext v2

不把 CompanyContext 生硬塞成 POLICY 因子，而是明确分区：

```text
DecisionContextV2
  formal:
    quote
    daily_bars
    technical
    risk
    market_regime
    relative_strength
    account
    position
    action_gates
  candidate:
    source
    lifecycle
    rank
    selection_reason
    reactivation_state
  research:
    company_snapshot_id
    thesis_id
    research_report_id
    catalyst_evidence_ids
```

`formal` 可以进入确定性 Evidence/Policy；`research` 默认只进入解释与 Research AI。

## 7. OPEN Gate Audit

为每次无持仓 DecisionReport 输出结构化 OPEN 诊断：

```json
{
  "permission": "blocked",
  "checks": [
    {"id":"quote.fresh","passed":true},
    {"id":"daily_bars.fresh","passed":true},
    {"id":"risk.available","passed":true},
    {"id":"market_regime.available","passed":false}
  ],
  "positive_evidence": ["trend.above_sma20"],
  "blockers": ["market_regime unavailable"]
}
```

修正规则：没有 `context.position` 时不得输出正式 `REDUCE`。高风险无持仓股票应是 WATCH/blocked OPEN，而不是“建议减仓 0 股”。

## 8. Opportunity Scan

不能通过“不断换候选直到出现 OPEN”来追求交易结果。Opportunity Scan 的职责是诊断市场中是否存在满足基础条件的研究机会。

输出至少区分：

- eligible universe 数量；
- basic-data-ready 数量；
- open-gate-ready 数量；
- 被 risk / market / relative / technical 各类条件阻断的数量；
- 本轮进入正式 candidate cohort 的数量。

扫描本身不调用 LLM 决定正式股票，不允许热点/新闻直接成为正式 selection 权重。

## 9. AI / Research Local-First Gateway

所有 AI Research 数据遵循：

```text
request
 -> local lookup
 -> freshness / coverage / schema / version check
 -> valid: remote calls = 0
 -> invalid: fetch missing/expired subset only
 -> normalize + validate
 -> persist
 -> snapshot id/hash/as_of/lineage
 -> AI reads persisted snapshot
```

禁止第三方原始 DataFrame/JSON 不落库直接成为正式 Research 上下文。

Freshness 按数据类型定义：日线按交易日；新闻按 published/fetched；财务按 report period + announcement time；公司元数据使用较长 TTL。

## 10. Android 技术设计

### 10.1 Simulation Run

顶部展示：

```text
状态
候选数 / 决策数 / 执行数 / 跳过数
总耗时
开始时间 / 完成时间
```

stage/card 标题统一：`股票名称 · symbol`，适用于行情、日线、风险、新闻、决策、执行。

### 10.2 Candidate Center

展示：

- candidate source；
- selection version；
- rotation key；
- pool hash；
- rank；
- selection reason；
- research priority；
- lifecycle；
- cooldown；
- reactivation conditions。

允许用户主动添加/移出 Research Candidate。

### 10.3 Decision Detail

增加：

- OPEN Gate Audit；
- 为什么 WATCH；
- 为什么不能 OPEN；
- 哪些数据已满足；
- 哪些条件未满足；
- AI shadow 与正式 action 的差异。

### 10.4 Company Research

重点股票提供独立页面：

- 公司怎么赚钱；
- 产品/业务线；
- 收入结构；
- 毛利结构；
- 盈利驱动；
- 行业与竞争；
- 核心风险；
- 催化剂；
- Thesis 当前状态与失效条件；
- 数据来源/as-of。

## 11. 建议数据库对象

后续 migrations：

- `candidate_entries`
- `candidate_events`
- `candidate_activation_rules`
- `candidate_analysis_runs`
- `open_gate_audits`
- `company_profiles`
- `company_metric_snapshots`
- `company_research_snapshots`
- `research_data_snapshots`

历史 DecisionReport/ResearchReport/Thesis/Execution tables 不删除。

## 12. Legacy Cleanup

删除顺序：

1. 先迁 route ownership；
2. 再迁 Schema；
3. 再迁 service implementation；
4. Android/API 调用审计；
5. tests/OpenAPI 一致；
6. 标记 REMOVE_READY；
7. 删除 legacy function/module；
8. 最后删除 `app.application`。

禁止直接建立一个长期存在的“垃圾 legacy 目录”；`legacy/` 只是临时隔离区，每一项必须有 replacement 与删除条件。

## 13. 实施顺序

1. Architecture bootstrap + router ownership；
2. Paper/Decision route extraction；
3. Market/Portfolio/Research route extraction；
4. service/schema extraction；
5. 空仓 REDUCE + OPEN Gate Audit；
6. Candidate UI 可观测性：名称/总耗时/selection lineage；
7. Candidate Management；
8. Company Intelligence；
9. Research Local-First Gateway；
10. AKShare Registry；
11. 完整 Day0 审计后冻结观察版本。

## 14. 验收原则

成功不是“出现更多 OPEN”。成功标准是系统能明确回答：

- 为什么今天选中这只股票；
- 为什么没有选另一只；
- 为什么不能 OPEN；
- 哪个正式条件阻断；
- 下一次什么时候值得重新深度分析；
- 深度研究用了哪些公司数据；
- AI 的研究结论有没有越过正式交易边界；
- 所有输入能否回查到 snapshot/hash/as-of/source。