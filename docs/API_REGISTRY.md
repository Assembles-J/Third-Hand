# Third-Hand API Registry

本表是 Architecture Refactor v2 的迁移账本。重构期间 URL 与语义默认保持不变；任何删除或 breaking change 必须先从 ACTIVE/MIGRATING 变为 DEPRECATED，再经调用审计后进入 REMOVE_READY。

| Domain | Path family / endpoint | Status | Target owner | Notes |
|---|---|---|---|---|
| health | `/health` | ACTIVE | `api.v1.health` | 容器 healthcheck 依赖，禁止删除 |
| app_update | `/v1/app-update*` | ACTIVE | `api.v1.app_update` | Android 更新链依赖 |
| admin | `/v1/admin/*` | ACTIVE | `api.v1.admin` | 系统配置与运维概览 |
| paper | `/v1/paper-trading/*` | ACTIVE | `api.v1.paper` | Day0 纸面账户、run、执行审计核心 |
| data_quality | `/v1/data-quality/daily-history-attempts` | ACTIVE | `api.v1.data_quality` | provider lineage |
| data_quality | `/v1/data-quality/provider-health` | ACTIVE | `api.v1.data_quality` | provider health/backfill |
| research | `/v1/feed` | ACTIVE | `api.v1.research` | 新闻研究，后续 Local-First gateway |
| research | `/v1/announcements` | ACTIVE | `api.v1.research` | 公告研究，后续 Local-First gateway |
| ai | Research Chat router | ACTIVE | `api.v1.ai` | 当前由 `app.research_chat.routes` 注册 |
| market | quote/history/intraday/intelligence routes in `application.py` | MIGRATING | `api.v1.market` | 精确 path 在 A2 静态盘点时逐条登记 |
| portfolio | holding/watchlist/sale/risk/trade-plan/analysis routes | MIGRATING | `api.v1.portfolio` | 精确 path 在 A2 逐条登记 |
| decision | decision context/report/jobs/generate routes | MIGRATING | `api.v1.decision` | 不改变 ActionPolicy |
| candidate | existing paper candidate-selection lineage | ACTIVE | `domain.candidate` | 当前 deterministic rotation；API 待 v1.3 |
| candidate | manual candidate/lifecycle/reactivation APIs | PLANNED | `api.v1.candidate` | 后续 PR-C |
| company | company intelligence APIs | PLANNED | `api.v1.research` | 后续 PR-C |

## 状态规则

- `ACTIVE`：生产使用；
- `MIGRATING`：功能保留，正在从 `application.py` 迁出；
- `DEPRECATED`：保留兼容，不允许新客户端依赖；
- `REMOVE_READY`：全仓/Android/生产依赖检查完成，可删除；
- `REMOVED`：已删除；
- `PLANNED`：尚未上线的新 API。

## 删除前检查

任何 ACTIVE 历史接口不得仅凭名称或代码年代删除。至少检查：Android `ApiClient`、后端测试、生产 health/deploy、其他 endpoint 内部调用、文档/脚本和数据回放需求。