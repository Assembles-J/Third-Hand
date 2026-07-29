# 持仓分析能力设计

## 目标

为个人研究提供可追溯的持仓复核，而不是自动下单或确定性荐股。每项结论必须能回看：当时行情、公告/新闻、个人规则、模型输出和后续表现。

## 流程

```text
行情/公告/新闻 ─┐
个人持仓与成本 ─┼─> 证据快照 ─> 规则引擎 ─> 持仓分析
个人风险规则 ───┘                       │
                                            ├─> 立即返回规则结论
                                            └─> AI 后台解释与待核验清单
```

## 数据模型

### personal_rules

- `scope`：全局、个股、行业或 ETF；
- `max_position_percent`：最大仓位；
- `loss_review_percent`：成本偏离复核阈值；
- `volatility_review_percent`：波动复核阈值；
- `enabled`、`version`、`updated_at`。

### analysis_runs

- `id`、`holding_symbol`、`created_at`；
- `evidence_snapshot`：行情、风险、事件与数据时效；
- `rules_snapshot`：参与判断的规则版本；
- `action`：`observe`、`risk_review`、`wait_for_confirmation`、`data_insufficient`；
- `reason`、`evidence`、`ai_status`。

### ai_jobs

- `id`、`content_id` 或 `analysis_run_id`；
- `status`：`pending/running/succeeded/failed`；
- `attempts`、`model`、`input_hash`、`output`、`error`、`token_usage`；
- 相同输入哈希只执行一次。

## 行为约束

1. API 先返回规则结论；DeepSeek 超时、限流或未配置均不得阻塞页面。
2. AI 只能解释证据、列待核验项和不确定性，不能生成下单指令或保证收益。
3. 对于仓位比例，系统展示“你的规则上限、当前暴露、触发原因”，不替用户决定金额。
4. 原始公告和来源链接优先于新闻摘要与模型表述。

## 实施顺序

1. 建表并提供个人规则 CRUD；
2. 持仓分析读取个人规则，保存 `analysis_runs`；
3. 用进程内任务队列实现 AI 后台任务，并提供状态查询；
4. Android 显示分析卡、规则来源、AI 状态和证据链接；
5. 记录 5/20/60 日后的结果，形成回测审计。
