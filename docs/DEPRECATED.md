# Third-Hand Deprecation Registry

本文件用于记录 Architecture Refactor v2 中准备废弃/删除的代码。当前只按真实运行依赖删除，不凭文件名或历史印象删除生产能力。

## 状态

- `ACTIVE`：生产路径，不能删除；
- `DEPRECATED`：保留兼容但禁止新增依赖；
- `REMOVE_READY`：已验证无运行时/Android/测试/审计依赖；
- `REMOVED`：已删除。

## 已删除的治理冲突代码

| Module / area | Status | Replacement / reason |
|---|---|---|
| Research Chat tool `paper_add_position` | REMOVED | Research/LLM 不得直接写纸面账本；买入只能来自当前版本 DecisionReport，再由 next eligible observed quote 执行 |
| Research Chat tool `paper_reduce_position` | REMOVED | Research/LLM 不得直接写纸面账本；减仓/卖出只能走 formal paper execution governance |

这两个工具同时从 LLM tool registry 和 `ToolExecutor` 执行分支移除，避免使用历史 tool name 绕过正式执行边界。

## 当前明确不能删除

| Module / area | Status | Reason |
|---|---|---|
| `app.application` compatibility alias / `app.legacy.application_legacy` | ACTIVE / MIGRATING | 仍持有多数历史 endpoint/后台任务；只能逐域搬空后删除 |
| `app.daily_history_policy` | ACTIVE | PR #13 正式日线数据契约与 Local-First 生产修复 |
| `app.daily_history_compat` | ACTIVE | 旧 provider surface / test-double 兼容；需等 provider adapter 模块化后复核 |
| `app.paper_runtime_integration` | ACTIVE | Day0 candidate/execution governance 注入 |
| DecisionReport / execution audit storage | ACTIVE | 历史审计不可删 |

## 待审计候选

- 旧版 recommendation/backtest API；
- debug/test-only endpoint；
- 被新版 DecisionReport/ResearchReport 完全取代的历史 DTO/helper；
- 重复的行情/分析 wrapper；
- 已无调用的兼容导入。

### 删除判定模板

```text
name:
replacement:
backend runtime imports: 0
android calls: 0
tests migrated: yes/no
openapi/client compatibility: checked/not checked
historical audit dependency: none/present
status: DEPRECATED | REMOVE_READY | REMOVED
```

数据库表不随代码删除自动 DROP。涉及历史交易、决策、Research、Thesis、provider lineage 的表默认保留。