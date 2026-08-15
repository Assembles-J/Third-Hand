# Third-Hand Day 0 运行诊断与 Policy v3 修订

**版本：1.0（2026-08-15）**  
**适用阶段：PRE_OBSERVATION / DAY_0_AUDIT**  
**上位规范：`Third-Hand_Unified_Governance_and_Observation_Spec.md`、`Third-Hand_Candidate_AI_Governance_Boundary_Spec.md`**

## 1. 修订目的

本修订解决 Day 0 期间已经确认的两个审计缺口：

1. 生产 DecisionReport 的 `audit_versions.git_commit` 可能为 `unknown`，无法把运行结果绑定到实际部署制品；
2. 候选池治理补充规范仍记录 `swing-policy-v2-research-isolation`，但当前正式 ActionPolicy 已因“无持仓不得 REDUCE”的正确性修复升级到 v3。

本修订同时新增一个只读生产诊断端点，用于从已持久化的 simulation audit 中回答“为什么没有 OPEN”，而不是通过降低 OPEN 条件、增加因子或重新运行策略来制造交易。

## 2. 当前正式版本口径

自本修订起，Day 0 当前正式版本组为：

```text
evidence-v2-usage-scope
swing-policy-v3-position-action-semantics
open-gate-audit-v1
candidate-rotation-v1
research-priority-v1
```

其中 `swing-policy-v3-position-action-semantics` 相比 v2 只修正动作语义：

```text
REDUCE 必须存在当前持仓。
```

它不降低 OPEN/ADD 门槛，不增加正向证据，不修改 PositionSizing，不授权 AI 参与正式动作。

若旧文档任何位置仍显示 `swing-policy-v2-research-isolation` 作为“当前版本”，以本修订和运行时 `decision_config.ACTION_POLICY_VERSION` 为准；历史 v2 DecisionReport 不得进入 v3 的当前版本执行队列。

## 3. 部署制品身份

GitHub Deploy workflow 已把本次部署 commit 保存为远端进程环境变量 `DEPLOY_SHA`。生产 Compose 必须把：

```text
DEPLOY_SHA -> container GIT_COMMIT
```

映射到 API 容器。

DecisionReport 的：

```text
audit_versions.git_commit
```

必须等于实际部署 commit，且不得为 `unknown`。本地手工启动若没有明确制品身份，可以继续显示 `unknown`，但不能据此通过生产 Day 0。

## 4. Day 0 只读诊断接口

新增：

```http
GET /v1/admin/day0-diagnostics
```

### 4.1 权限边界

该接口：

- 只读取已经持久化的 simulation run / stage / provider-health 审计；
- 不重新运行 ActionPolicy；
- 不调用 LLM；
- 不创建 DecisionReport；
- 不修改纸面账户；
- 不执行交易；
- 不暴露 token、环境变量、现金余额、持仓数量、AI 原始推理或 Provider 原始错误文本。

### 4.2 返回范围

接口返回：

- 当前部署 `git_commit` 与版本快照；
- 最新 simulation run 的开始/结束时间、总耗时、生成/执行/跳过数量；
- candidate pool 的版本、hash、rotation key、算法、rank 与 reason；
- 每只股票的正式 action；
- `open_gate_audit.permission`；
- OPEN 未通过的具体 check id；
- 正向 POLICY evidence ids；
- AI shadow action / agreement，仅作为研究对照；
- execution stage 的最终状态与跳过原因；
- Provider circuit/counter 摘要；
- 常见英文参数的中文释义。

## 5. OPEN 诊断口径

OPEN 必须继续区分两层：

### 5.1 Data / Action Gate

由 Data Quality 决定关键输入是否齐全、新鲜并允许 OPEN。

### 5.2 Formal ActionPolicy predicate

即使基础 action gate 为 `allowed`，还必须同时满足：

```text
position.absent
quote.available
risk.available
cash.positive
positive_policy_evidence.present
market.not_defensive
```

当前正向正式 POLICY evidence 仅包括：

```text
trend.above_sma20
trend.sma20_above_sma60
market.supportive
relative.outperform_20d
```

诊断端点只汇总这些已经由正式代码生成的审计结果，不能修改其含义或权重。

## 6. “没有 OPEN”的正确处理

以下均为合法观察结果：

- `action_gate.open = blocked`；
- `positive_policy_evidence.present = false`；
- `market.not_defensive = false`；
- 全部正式候选最终均为 WATCH；
- 本轮执行数为 0。

不得因为连续没有 OPEN 就在 Observation 前静默降低阈值。只有当诊断证明代码与当前治理文档不一致、数据错误、语义错误或 traceability 缺失时，才按 Day 0 correctness fix 处理并重新冻结版本。

## 7. 英文参数释义原则

诊断接口内的 `parameter_guide` 是展示/解释层，不参与 Policy。重点释义：

- `score_percent`：数据完整度评分，不是胜率；
- `policy_score`：确定性动作优先级归一化值，不是上涨概率；
- `ai_shadow_action`：AI 影子研究动作，不参与正式执行；
- `positive_evidence_ids`：当前命中的正式正向 POLICY 证据；
- `NEXT_ELIGIBLE_OBSERVED_QUOTE`：决策日期之后下一次满足执行条件的已观察行情，不等同于“下一交易日开盘价”。

## 8. Day 0 验收补充

在原有 Day 0 清单外增加：

- [ ] `/v1/admin/day0-diagnostics` 为 GET-only；
- [ ] 诊断接口不产生数据库写入或交易副作用；
- [ ] 生产 `deployment.identity_ok = true`；
- [ ] `audit_versions.git_commit` 等于实际 deploy SHA；
- [ ] 当前 ActionPolicy 版本为 `swing-policy-v3-position-action-semantics`；
- [ ] latest run 中正式 decision stage 可回查 `open_gate_audit`；
- [ ] 没有 OPEN 时可以区分 Data Gate、正向 POLICY evidence、market defensive 等原因；
- [ ] Provider 原始错误文本、密钥、现金和仓位数量不会通过该接口暴露。

---

**执行口径：**本修订是 Day 0 可观测性与制品身份修复，不是策略优化，不得被解释为允许为了增加 OPEN 数量而修改当前阈值。
