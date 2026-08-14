# Third-Hand Architecture Refactor v2.0

## 1. 目标

本阶段是结构重构，不是策略调参。目标是把当前约 158 KB 的 `app/application.py` 从“API、Schema、运行时状态、后台线程、业务编排、持久化调用都写在一个模块”逐步拆成可维护的 package，同时保持现有 URL、响应语义、ActionPolicy、Local-First、成交时序和 AI 权限边界不变。

### 不可改变的行为

- `ActionPolicyEngine`、PositionSizing、DecisionGuard 的正式交易权限不因重构改变。
- AI / Research 仍不能覆盖正式 action、仓位或 execution price。
- `NEXT_ELIGIBLE_OBSERVED_QUOTE` 成交语义不变。
- 正式 A 股日线继续执行 ISO + qfq + Local-First 契约。
- 现有生产 API 在确认移动端/服务端无调用前不得删除或改 URL。
- 历史 DecisionReport / ResearchReport / Thesis / execution audit 不改写。

## 2. 当前代码问题

当前 `main.py` 已经只是治理安装与 `app.application` 的兼容别名，但 `application.py` 实际承担了原先 main 的全部巨石职责：

1. FastAPI app、CORS、日志初始化；
2. 所有 Pydantic API Schema；
3. PortfolioStore 与全部 Service 单例创建；
4. 市场行情、日线、风险、Research、AI、Paper Trading、Admin、App Update 等 endpoint；
5. 后台刷新线程、锁、运行状态；
6. paper simulation 编排与候选池流程；
7. helper、格式化、兼容行为。

这种结构会直接阻碍 Candidate Management、Company Intelligence、Research Local-First Gateway 和后续 UI 可解释性开发。

## 3. 目标 package

```text
backend/app/
  main.py
  bootstrap/
    runtime.py
    app_factory.py          # 后续阶段
    lifecycle.py            # 后续阶段
    logging.py              # 后续阶段
  api/
    v1/
      health/
      admin/
      market/
      data_quality/
      portfolio/
      paper/
      decision/
      candidate/
      research/
      ai/
      app_update/
  application_services/
    market/
    decision/
    candidate/
    research/
    paper/
  domain/
    market/
    decision/
    candidate/
    company/
    research/
    trading/
  infrastructure/
    database/
    market_data/
    providers/
    ai/
  legacy/
```

这里故意使用 `application_services/`，避免与当前历史巨石 `application.py` 名称冲突。等最后一个 legacy route 迁出后，再删除 `application.py`，届时可以把 `application_services` 重命名为 `application` package。

## 4. 依赖方向

允许：

```text
api -> application_services -> domain
                         \-> repositories / infrastructure adapters
bootstrap -> api + infrastructure
```

禁止：

- domain import FastAPI / router；
- domain import `app.application`；
- Research/AI 直接写正式 ActionPolicy；
- router 内新增复杂 SQL / provider 访问；
- 新代码继续往 `application.py` 增 endpoint。

## 5. Strangler 迁移策略

不一次性重写 158 KB 文件。采用分域迁移：

1. 建立 bootstrap 与 package 边界；
2. 建立 API Registry，给每个旧 endpoint 标记 owner/status；
3. 按域提取 Schema；
4. 按域提取 Application Service；
5. 把 endpoint 搬到对应 `api/v1/<domain>/router.py`；
6. 保持 URL 与 response model；
7. 旧实现确认无引用后，从 `application.py` 删除；
8. 最终 `application.py` 归零并删除。

任何阶段都必须保持 `app.main:app` 兼容。

## 6. API 域划分

- health: `/health`
- admin: `/v1/admin/*`
- app_update: `/v1/app-update*`
- market: quote/history/intelligence/sector/intraday
- data_quality: `/v1/data-quality/*`
- portfolio: holdings/watchlist/sales/trade-plan/risk/analysis
- paper: `/v1/paper-trading/*`
- decision: DecisionContext/DecisionReport/jobs/generate/audit
- candidate: 候选池、人工加入、生命周期、激活规则（新）
- research: reports/thesis/news/announcements/company intelligence
- ai: AI jobs / Research Chat / SSE / tool gateway

## 7. Legacy / 删除规则

代码不因为“看起来旧”就删除。每个候选删除项必须同时满足：

1. GitHub 全仓无运行时 import；
2. Android / API client 无调用；
3. 当前生产路由表不依赖；
4. 测试不依赖，或测试已迁到替代实现；
5. 有明确替代模块；
6. 数据库历史审计不要求该代码回放。

状态：

- ACTIVE: 当前生产路径；
- MIGRATING: 正迁出巨石模块；
- DEPRECATED: 仍兼容但不允许新增调用；
- REMOVE_READY: 已满足删除条件；
- REMOVED: 已删除并在 changelog 记录。

数据库表遵循更严格规则：代码废弃不等于立即 DROP 表。历史 Decision/Research/Execution audit 表不得因代码整理删除。

## 8. Candidate / Decision v1.3 预留

本次结构重构必须为下一版本预留，但不提前改变策略：

- 人工 `USER_ADDED` Research Candidate；
- deterministic rotation；
- existing paper position risk monitor；
- Candidate lifecycle / cooldown / reactivation conditions；
- OPEN Gate Audit；
- Company Intelligence Context；
- AI Research 深度等级；
- Research Local-First Data Gateway。

这些对象先拥有明确 package owner，后续 PR 才实现业务。

## 9. 前端技术边界

Android 后续按 domain 消费 API，不依赖后端内部 package。接口 URL 在迁移阶段保持不变。

后续 UI 改造：

- 行情、日线、风险、决策、执行统一显示 `股票名称 · symbol`；
- simulation run 展示总耗时；
- 候选池展示 selection version、rotation key、pool hash、rank、reason；
- Decision Detail 展示 OPEN Gate Audit；
- Candidate Center 支持人工加入、研究优先级、生命周期和再次激活条件；
- Company Research 展示商业模式、产品线、收入/毛利驱动、竞争、风险与催化剂。

## 10. PR 拆分

### PR-A1 Bootstrap & Architecture Guard

- bootstrap package；
- API/domain/application_services/infrastructure package skeleton；
- API Registry；
- deprecated registry；
- 架构边界测试；
- 不改业务路由。

### PR-A2 Router Extraction

按 health/admin/app-update/data-quality/paper/market/portfolio/decision/research/ai 顺序搬 endpoint。每移动一组都删除原 decorator/implementation，禁止双路由。

### PR-A3 Service Extraction

把 router 内依赖 `store` / provider / orchestrator 的复杂流程提取到 application services。

### PR-A4 Legacy Cleanup

只有 REMOVE_READY 项才删除。

### PR-B Candidate + Decision Explainability

修复空仓 REDUCE、增加 OPEN Gate Audit、候选 selection 可视化、名称/耗时展示。

### PR-C Candidate Management + Company Intelligence

人工候选、生命周期、再激活规则、Research Priority、CompanyContext。

### PR-D Research Local-First + AKShare Registry

ResearchDataGateway、snapshot lineage、AKShare Registry，动态数据保持 RESEARCH_ONLY。

## 11. 验收

每一阶段必须：

- 全量 pytest 不少于当前基线；
- compileall 通过；
- Docker build 通过；
- `app.main:app` 可启动；
- OpenAPI path 集合与迁移前一致（除明确新增接口）；
- 生产关键 API 响应模型不变；
- ActionPolicy / execution governance 测试不回退；
- 新模块不得反向 import legacy 巨石，迁移 bridge 除外。

最终完成标志：`application.py` 不再拥有 API schema、endpoint、后台线程和业务编排，可安全删除。