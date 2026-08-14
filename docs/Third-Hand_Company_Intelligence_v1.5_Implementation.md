# Third-Hand Company Intelligence v1.5 实施说明

## 1. 解决的问题

当前多数股票研究输入过于同质化：行情、日线、技术、风险、基础新闻较完整，但对重点标的缺少“公司为什么赚钱”的结构化理解。

v1.5 增加独立 `CompanyContext`：

```text
formal DecisionContext        CompanyContext
(行情/风险/技术/市场)         (商业模式/产品/财务/毛利/竞争/...)
          \                   /
           \                 /
             AI Research View
                    ↓
         ResearchReport / Thesis
```

**CompanyContext 不直接进入 ActionPolicy。**

这是对“把所有公司研究直接塞进 DecisionContext”的调整：深度公司数据适合参与 AI Research 和 Thesis，但如果直接成为 formal DecisionContext 字段，会模糊 POLICY / RESEARCH_ONLY 边界，并让尚未 point-in-time 验证的数据看起来拥有交易权限。

## 2. Research Priority 决定分析深度

### L0

- 公司身份、商业模式

### L1

- L0
- 产品线 / 业务分部

### L2

- L1
- 财务摘要
- 毛利/利润结构
- 风险与催化剂

### L3 / L4 Deep Company

- L2
- 盈利与现金流驱动
- 行业与竞争格局
- 管理层与资本配置
- 估值框架

L4 仍不代表“必买”，只是持仓/核心标的需要最高研究深度。

## 3. CompanyContext 数据集

当前 schema：

```text
identity_business_model
products_segments
financial_summary
margin_structure
profit_cashflow_drivers
industry_competition
management_capital_allocation
risks_catalysts
valuation_framework
```

例如小米集团 L3 研究不应只得到行情 + 新闻，而应能回答：

- 手机、IoT、互联网服务、智能汽车各自承担什么业务角色；
- 各业务收入/毛利变化；
- 利润与现金流主要驱动因素；
- 汽车交付、ASP、毛利等需要验证的关键变量；
- 主要竞争者和结构性风险；
- 催化剂对应什么可验证事实；
- 当前估值框架用了哪些输入、数据截至何时。

如果数据不存在，输出 `missing_datasets`，禁止 AI 补脑。

## 4. Local-First

所有 Company dataset 通过 `ResearchDataGateway`：

```text
CompanyIntelligenceService
        ↓
ResearchDataGateway
        ↓
local fresh snapshot ?
    YES -> remote = 0
    NO  -> registered provider adapter
          -> normalize
          -> persist
          -> reread
          -> CompanyContext
```

Company service 本身不 import AKShare/Tushare/HTTP SDK。

## 5. 数据追溯

CompanyContext 保存每个 dataset 的：

- snapshot_id
- payload_hash
- provider
- as_of
- available_at
- freshness_status

Context 本身保存独立 context_id / payload_hash。

所有字段：

```text
usage_scope = RESEARCH_ONLY
formal_trade_authority = false
```

## 6. 数据表

```text
company_profiles
company_research_snapshots
```

原始/规范化 dataset 不在这里重复保存，而复用 `research_data_snapshots`。

## 7. HTTP API（独立 router，待 bootstrap 接入）

```text
GET  /v1/company-intelligence/{symbol}/requirements
POST /v1/company-intelligence/{symbol}/build
GET  /v1/company-intelligence/{symbol}
```

不存在 `/open` / `/trade` 接口。

## 8. 当前 Provider 状态

v1.5 本身只定义 Provider Registry，不在 Company service 中硬编码第三方 SDK。没有 provider 且没有本地 snapshot 时：

```text
research_ready = false
missing_datasets = [...]
```

下一 PR 才注册 AKShare / 已有缓存 / 财务与公司信息 Provider Adapter；所有 Adapter 强制走 ResearchDataGateway。

## 9. 下一阶段

1. 注册 Company provider adapters；
2. AKShare Registry 发现接口；
3. 先查询本地 snapshot，再补缺；
4. L3/L4 candidate analysis worker 先通过 candidate `analysis_readiness`；
5. CompanyContext + formal DecisionContext 组成 AI Research 输入；
6. AI 输出 Thesis / 风险 / 催化剂 / structured reactivation proposal；
7. AI 输出仍不能修改 ActionPolicy 或 PositionSizing。