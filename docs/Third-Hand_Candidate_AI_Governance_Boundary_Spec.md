# Third-Hand 候选池、AI 与策略权限治理补充规范

**版本：1.0（2026-08-14）**  
**适用阶段：PRE_OBSERVATION / DAY_0_AUDIT**  
**上位规范：`Third-Hand_Unified_Governance_and_Observation_Spec.md`**

## 1. 目的

本文补齐统一治理规范中三个容易被忽略的前置策略边界：

1. 候选池与候选调度本身属于策略治理范围，不能以“只是扫描”绕过版本、审计和冻结要求；
2. 新闻、资金流、Research、Thesis 与 LLM 输出必须在类型层与 ActionPolicy 物理隔离，不能仅依赖提示词或把 impact 临时改成 `uncertain`；
3. Observation/P2 批准前不得把人工启发式分数命名、展示或持久化为“上涨概率”“胜率”或类似概率结论。

本规范不扩大交易能力，不引入新买卖因子，不改变 PositionSizing 的当前 baseline 参数，不授权 AI 执行交易。

## 2. 权力矩阵

| 模块 / 数据 | 可影响正式 Action | 可影响 Quantity | Observation 阶段用途 |
| --- | --- | --- | --- |
| Data Quality / Freshness | 是 | 间接 | 阻断与降级 |
| Position | 是 | 是 | 仓位与风险约束 |
| POLICY Technical Evidence | 是 | 间接 | 确定性基线 |
| Risk | 是 | 是 | 风险基线 |
| Market Regime | 是 | 间接 | 确定性环境 |
| Relative Strength | 是 | 否 | 确定性相对强弱 |
| News / Announcement | 否 | 否 | RESEARCH_ONLY |
| Fund Flow | 否 | 否 | RESEARCH_ONLY |
| ResearchReport / Thesis | 否 | 否 | RESEARCH_ONLY |
| DeepSeek Decision AI | 否 | 否 | 解释、冲突、shadow preference |
| Research Chat | 否 | 否 | 对话研究 |
| ActionPolicyEngine | 是 | 间接 | 唯一正式动作基线 |
| PositionSizingEngine | 否 | 是 | 唯一正式数量基线 |
| Paper Execution | 否 | 否 | 仅执行已保存 DecisionReport |

任何代码改动若改变上表任一“可影响”关系，必须视为策略版本变更，重新执行 Day 0，不得混入既有 Observation 样本。

## 3. Evidence Usage Scope

`EvidenceItem` 必须包含 `usage_scope`：

- `POLICY`：允许 ActionPolicyEngine 消费；
- `RESEARCH_ONLY`：可进入 ResearchReport、DeepSeek、UI、审计，但禁止影响正式 Action/Quantity；
- `AUDIT_ONLY`：仅用于来源、质量、追踪与复核。

### 3.1 当前固定分类

`POLICY`：

- data quality / freshness gate；
- position cap / position risk；
- 已冻结的 deterministic technical evidence；
- deterministic risk evidence；
- market regime；
- relative strength。

`RESEARCH_ONLY`：

- 新闻、公告及其 LLM impact；
- 主力资金、北向资金等资金流；
- ResearchReport / Thesis；
- LLM reasoning、preferred action、research chat tool result。

### 3.2 ActionPolicy 硬边界

ActionPolicyEngine 入口必须先过滤：

```python
policy_evidence = tuple(
    item for item in evidence
    if item.usage_scope == "POLICY"
)
```

禁止在 Policy 内重新解析 `RESEARCH_ONLY` 的 title、description、category、direction 或 evidence_id。

`event.negative.*` 不得作为 REDUCE、EXIT、ADD block 或 OPEN block 的条件。未来若事件类数据需要晋升策略，必须形成独立、确定性、point-in-time 可回放的 promoted feature，并经过 P2 预注册、OOS 和人工 Promotion。

## 4. 候选池本身属于策略

系统必须区分：

```text
Market Universe
  -> Eligibility Filter
  -> Candidate Scheduler
  -> DecisionContext
  -> EvidenceEngine
  -> ActionPolicyEngine
  -> PositionSizingEngine
  -> DecisionReport
```

只要某个规则决定“哪些股票会得到 DecisionReport”，它就可能影响最终交易分布，因此属于策略治理范围。

### 4.1 Observation 期间禁止作为正式候选选择依据

以下内容可用于 UI / Research 优先级，但不得改变正式 paper decision cohort：

- watchlist；
- 热门板块；
- 当日涨跌幅排名；
- 成交额/量比热点；
- 主力资金/北向资金；
- 新闻热度；
- LLM 评分或结论。

已有 paper position 是例外：必须优先保留风险监控资格，但不能因此改变该标的的特征、阈值或策略规则。

### 4.2 Deterministic Rotation

Observation 的正式候选调度采用确定性轮转：

1. 输入为满足固定 eligibility 条件的全量 symbol 集合；
2. position symbols 优先保留；
3. 剩余槽位按 `candidate_selection_version + rotation_key + symbol` 的稳定 hash 排序；
4. `rotation_key` 使用稳定交易日或 Observation cycle key；
5. 保存 eligible universe 的 `candidate_pool_hash`；
6. 相同 universe、positions、rotation_key、version 必须得到完全相同结果。

最低审计字段：

```text
candidate_selection_version
candidate_pool_hash
rotation_key
selection_reason
candidate_rank
```

### 4.3 当前代码迁移要求

`backend/app/candidate_selection.py` 是正式 deterministic scheduler 实现入口。Observation Day 1 前，paper-trading 主循环必须只从该 scheduler 获取正式非持仓 cohort；旧的 hot-sector / top-gainer / watchlist 优先选择只能保留为 Research/UI 路径。

在完成主循环接线前，Day 0 不得标记候选池治理项为通过。

## 5. Opportunity Scan 语义

Opportunity Scan 是研究排序，不是预测服务。

正式命名：

- `research_priority_score`：研究优先级启发式分数；
- `confidence`：证据覆盖/质量；
- `risk_level`：历史风险标签。

禁止解释为：

- 上涨概率；
- 买入胜率；
- 未来收益概率；
- 模型置信概率。

当前旧客户端字段 `upside_likelihood` 仅作为兼容占位，固定返回中性值 `50`，不得用于排序、策略、校准、审计结论或 UI 的概率文案。完成客户端迁移后删除该字段。

## 6. AI Shadow Preference

Observation 阶段正式动作仍为：

```text
baseline_action = ActionPolicyEngine candidates[0].action
```

DeepSeek 可以输出：

```text
ai_shadow_action = guarded preferred_action
```

但必须满足：

- 只能来自 deterministic candidate actions；
- 只能引用当前 evidence IDs；
- 不得生成价格或数量；
- 不得进入 paper execution；
- 不得修改 baseline action；
- disagreement 只用于之后的复盘和 P2 研究。

建议长期保存：

```text
baseline_action
ai_shadow_action
agreement
context_id
input_hash
prompt_version
model
policy_version
```

该机制的目标是测量 AI 的新增研究价值，而不是提前授予交易权。

## 7. Baseline Known Limitations

Observation 开始前必须明确记录而不是静默修正：

- 当前 ActionPolicy 的 `EXIT` 路径尚未形成正式 deterministic trigger；
- 当前 PositionSizing baseline 仍使用系统级最大仓位约 20%；
- 当前风险预算 baseline 约为总资产 1%；
- 当前默认 invalidation 约为 entry 的 -5%；
- 上述参数属于 baseline 行为，任何修改都要求新版本与重新 Day 0。

Observation 的目标是先验证基线可审计、可重复和不越权，不是在观察期内优化这些参数。

## 8. Day 0 新增零容忍检查

在统一规范原有清单之外新增：

- [ ] `RESEARCH_ONLY` evidence 无法改变 ActionPolicy 结果；
- [ ] `event.negative.*` 不存在正式策略通路；
- [ ] fund flow 不能改变 ActionPolicy；
- [ ] Opportunity 不输出真实方向概率；
- [ ] 正式 candidate scheduler 不消费 watchlist/hot sector/top gainer/fund flow/LLM；
- [ ] 相同 universe + rotation key 的 candidate cohort 可重复；
- [ ] candidate pool hash 与 selection version 可回查；
- [ ] AI shadow action 与 baseline action 分栏保存且 execution 只消费 baseline。

任一项失败：Day 0 不通过。

## 9. 本次代码版本边界

本次治理变更升级：

```text
evidence-v2-usage-scope
swing-policy-v2-research-isolation
candidate-rotation-v1
research-priority-v1
```

因此不得与 `evidence-v1 / swing-policy-v1` 的 Observation 数据混为同一个冻结样本。

## 10. 验收定义

最小自动测试必须证明：

1. 一个 `direction=negative, strength=0.95` 的 `RESEARCH_ONLY` event 不能把 HOLD/OPEN/ADD 改成 REDUCE；
2. fund flow 无论正负均保持 `RESEARCH_ONLY`；
3. Opportunity 的旧 `upside_likelihood` 不再携带方向信息；
4. candidate scheduler 对输入顺序不敏感；
5. position symbol 优先保留；
6. 同日相同 pool 结果完全一致；
7. 不同 rotation key 可轮转 cohort，但 pool hash 不变。

---

**执行口径：**本规范是统一治理规范的补充，不授权新增因子或收益优化。完成 candidate scheduler 主循环接线及本节 Day 0 检查后，方可开始 Observation Day 1。
