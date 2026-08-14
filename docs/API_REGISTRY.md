# Third-Hand API Registry

本表是 Architecture Refactor v2 的迁移账本。重构期间 URL 与语义默认保持不变；任何删除或 breaking change 必须先从 ACTIVE/MIGRATING 变为 DEPRECATED，再经调用审计后进入 REMOVE_READY。

## Android 已确认直接依赖

以下 endpoint 已从当前 `ApiClient.kt` 静态确认，重构期间视为 ACTIVE，不能改 URL 或删除。

### Health / Admin / Update

- `GET /health`
- `GET /v1/app-update`
- `GET /v1/admin/overview`
- `GET /v1/admin/config`
- `PUT /v1/admin/config`

### Paper Trading / Audit

- `GET /v1/paper-trading/account`
- `PUT /v1/paper-trading/account`
- `PUT /v1/paper-trading/net-contributions`
- `GET /v1/paper-trading/logs`
- `GET /v1/paper-trading/equity-snapshots`
- `GET /v1/paper-trading/status`
- `GET /v1/paper-trading/dashboard`
- `POST /v1/paper-trading/run`
- `GET /v1/paper-trading/runs`
- `GET /v1/paper-trading/runs/{runId}`
- `GET /v1/paper-trading/decision-audit/{decisionId}`
- `GET /v1/decisions/{decisionId}/lineage`

### Data Quality

- `GET /v1/data-quality/provider-health`
- `GET /v1/data-quality/daily-history-attempts`（后端生产审计使用；Android 当前未直接调用也仍保留）

### Market / Instrument

- `GET /v1/market/history/{symbol}`
- `POST /v1/market/history/{symbol}/refresh`
- `DELETE /v1/market/history/{symbol}`
- `GET /v1/market/intraday/{symbol}`
- `POST /v1/market/quotes/batch`
- `GET /v1/market/quotes`（Android 405 兼容 fallback，当前不能删除）
- `GET /v1/market/cached-quotes`
- `GET /v1/market/intelligence`
- `GET /v1/market/intelligence/sectors/{sector}`
- `POST /v1/market/symbols/resolve`
- `GET /v1/instruments/{symbol}/metadata`
- `PUT /v1/instruments/{symbol}/metadata`

### Portfolio / Account

- `GET /v1/holdings`
- `POST /v1/holdings`
- `PUT /v1/holdings/{id}`
- `DELETE /v1/holdings/{id}`
- `POST /v1/holdings/{id}/sales`
- `GET /v1/sales`
- `GET /v1/watchlist`
- `POST /v1/watchlist`
- `DELETE /v1/watchlist/{symbol}`
- `GET /v1/account/cash`
- `PUT /v1/account/cash`
- holding-draft batch/confirm/delete endpoint family
- `GET /v1/risk/assessments`
- `GET /v1/portfolio/analysis`
- `GET /v1/portfolio/impact-graph`
- `GET /v1/trade-plans`
- `GET /v1/trade-plans/draft/{symbol}`
- `POST /v1/trade-plans`
- `GET/POST /v1/personal-rules*`

### Decision

- `GET /v1/decisions/context/{symbol}`
- `POST /v1/decisions/generate`
- `GET /v1/decisions/jobs/{jobId}`
- `GET /v1/decisions/latest`
- `GET /v1/decisions`
- `GET /v1/decisions/{decisionId}`

### Research / AI / Learning

- `GET /v1/news/cached`
- `GET /v1/feed`
- `GET /v1/announcements`
- `GET /v1/research/targets`
- `POST /v1/research-recommendations/generate`
- `GET /v1/research-recommendations`
- `GET /v1/research-recommendations/{id}/evaluations`
- `GET /v1/opportunity-scan`
- `POST /v1/opportunity-scan/refresh`
- daily-review endpoint family
- AI-job list/retry endpoint family
- learning-case CRUD + analysis
- `GET /v1/research-rules`
- glossary endpoint family
- Research Chat router（当前由 `app.research_chat.routes` 注册）

## Domain migration ledger

| Domain | Status | Target owner | Notes |
|---|---|---|---|
| health | ACTIVE / MIGRATING | `api.v1.health` | 容器 healthcheck 依赖 |
| app_update | ACTIVE / MIGRATING | `api.v1.app_update` | Android 更新链依赖 |
| admin | ACTIVE / MIGRATING | `api.v1.admin` | 系统配置与运维概览 |
| paper | ACTIVE / MIGRATING | `api.v1.paper` | Day0 纸面账户、run、执行审计核心 |
| data_quality | ACTIVE / MIGRATING | `api.v1.data_quality` | provider lineage / health/backfill |
| market | ACTIVE / MIGRATING | `api.v1.market` | quote/history/intraday/intelligence/instrument |
| portfolio | ACTIVE / MIGRATING | `api.v1.portfolio` | holdings/watchlist/sales/risk/plan/account |
| decision | ACTIVE / MIGRATING | `api.v1.decision` | 不改变 ActionPolicy |
| research | ACTIVE / MIGRATING | `api.v1.research` | news/announcement/report/learning/glossary |
| ai | ACTIVE / MIGRATING | `api.v1.ai` | AI jobs + Research Chat/SSE |
| candidate | ACTIVE / PLANNED | `api.v1.candidate` + `domain.candidate` | deterministic rotation 保留；人工候选/生命周期后续实现 |
| company | PLANNED | `api.v1.research` + `domain.company` | Company Intelligence 后续实现 |

## 特别兼容项

`GET /v1/market/quotes` 不是可以立即删除的“旧接口”。Android 当前在 `POST /v1/market/quotes/batch` 返回 405 时显式 fallback 到该 GET，因此至少要等所有生产服务确认支持 batch POST、并删除移动端 fallback 后，才能进入 DEPRECATED。

## 状态规则

- `ACTIVE`：生产使用；
- `MIGRATING`：功能保留，正在从 `application.py` 迁出；
- `DEPRECATED`：保留兼容，不允许新客户端依赖；
- `REMOVE_READY`：全仓/Android/生产依赖检查完成，可删除；
- `REMOVED`：已删除；
- `PLANNED`：尚未上线的新 API。

## 删除前检查

任何 ACTIVE 历史接口不得仅凭名称或代码年代删除。至少检查：Android `ApiClient`、后端测试、生产 health/deploy、其他 endpoint 内部调用、文档/脚本和数据回放需求。