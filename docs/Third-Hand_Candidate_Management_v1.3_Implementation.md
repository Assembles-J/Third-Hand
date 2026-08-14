# Third-Hand Candidate Management v1.3 实施说明

## 1. 定位

Candidate Management 管理“研究资源何时花在什么股票上”，不是交易授权层。

```text
USER_ADDED / PAPER_POSITION / DETERMINISTIC_ROTATION / OPPORTUNITY_SCAN
                    ↓
            Candidate lifecycle
                    ↓
          Research scheduling / AI
                    ↓
        ResearchReport / Thesis / Rule proposal
                    ↓
          （仍需正式 DecisionContext）
                    ↓
             ActionPolicy
```

人工加入候选只意味着“请研究它”，不意味着 OPEN。

## 2. 生命周期

```text
NEW
 -> ANALYZING
 -> ACTIVE
 -> WAITING_TRIGGER
 -> REACTIVATED
 -> ANALYZING / OPEN_READY_RESEARCH
 -> ARCHIVED
```

`OPEN_READY_RESEARCH` 仍是研究状态，不是正式交易动作。

## 3. 防止无止境重复分析

所有未来 Deep Research worker 必须先调用 analysis-readiness：

- `ANALYZING`：拒绝，已有分析运行；
- `WAITING_TRIGGER`：拒绝，等待结构化再次激活条件；
- `ARCHIVED`：拒绝；
- `OPEN_READY_RESEARCH`：拒绝重复深度分析；
- `cooldown_until > now`：拒绝；
- `NEW / ACTIVE / REACTIVATED`：允许。

分析开始必须通过 `/analysis/start` 进入 `ANALYZING`；分析结果只有在 `ANALYZING` 状态才能写入。

L0/L1 推荐 basic，L2 focused，L3/L4 deep_company。

## 4. 再次激活规则

可执行研究激活条件只能是结构化类型：

- `PRICE`
- `TECHNICAL`
- `FUNDAMENTAL`
- `EVENT`
- `TIME`

每条规则必须有：`metric + operator + value`（`exists` 可无 value）。

例如：

```json
{
  "rule_type": "PRICE",
  "metric": "last_price",
  "operator": "<=",
  "value": 18.5,
  "reason": "进入研究估值区间",
  "source": "ai_research_proposal"
}
```

“新闻足够利好”“感觉估值合理”等文字只能作为研究备注，不能成为执行 predicate。

所有 activation rule 固定：

```text
usage_scope = RESEARCH_ONLY
```

## 5. 新 API

```text
GET  /v1/candidates
POST /v1/candidates
GET  /v1/candidates/{symbol}
PUT  /v1/candidates/{symbol}/lifecycle
PUT  /v1/candidates/{symbol}/priority
POST /v1/candidates/{symbol}/activation-rules
PUT  /v1/candidates/{symbol}/activation-rules/{rule_id}
GET  /v1/candidates/{symbol}/analysis-readiness
POST /v1/candidates/{symbol}/analysis/start
POST /v1/candidates/{symbol}/analysis-result
```

这些 API 均不存在 trade/open endpoint。

## 6. 新数据表

```text
candidate_entries
candidate_sources
candidate_activation_rules
candidate_events
candidate_analysis_runs
```

它们由 v2 `CandidateRepository` 管理，不再向 legacy `PortfolioStore` 继续堆 candidate SQL。

## 7. 架构依赖

```text
api/v1/candidate
       ↓
application_services/candidate
       ↓
domain/candidate
       ↓
infrastructure/database/candidate_repository
```

Candidate domain 不 import FastAPI，不 import `app.legacy`。

Bootstrap 只做依赖注入，将新 router 追加到现有 FastAPI shell；不修改旧路由表，也不往 legacy application 新增 endpoint。

## 8. 下一阶段

下一阶段接入：

1. 低成本 deterministic reactivation evaluator；
2. Research Local-First Data Gateway；
3. L3/L4 Company Intelligence 深度分析；
4. AI 生成结构化 activation-rule proposal；
5. Android Candidate Center。

任何 AI proposal 仍为研究层内容，不能跳过 ActionPolicy。