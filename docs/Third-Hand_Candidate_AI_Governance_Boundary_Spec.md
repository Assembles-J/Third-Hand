# Third-Hand 候选池、AI 与策略权限治理补充规范

**版本：1.2（2026-08-14）**  
**适用阶段：PRE_OBSERVATION / DAY_0_AUDIT**  
**上位规范：`Third-Hand_Unified_Governance_and_Observation_Spec.md`**

## 1. 目的

本文补齐统一治理规范中三个容易被忽略的前置策略边界：

1. 候选池与候选调度本身属于策略治理范围，不能以“只是扫描”绕过版本、审计和冻结要求；
2. 新闻、资金流、Research、Thesis 与 LLM 输出必须在类型层与 ActionPolicy 物理隔离，不能仅依赖提示词或把 impact 临时改成 `uncertain`；
3. Observation / P2 批准前，不得把人工启发式分数命名、展示或持久化为“上涨概率”“胜率”或类似概率结论。

本规范不扩大交易能力，不引入新买卖因子，不优化 PositionSizing baseline，不授权 AI 执行交易。

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
| Candidate Scheduler | 是（决定被分析对象） | 否 | 确定性 cohort |
| Data Prewarm Scope | 否 | 否 | 报价 / 日线 / 风险预热 |
| Pending Decision Queue | 否（不生成新动作） | 否 | 保留历史执行义务 |
| ActionPolicyEngine | 是 | 间接 | 唯一正式动作基线 |
| PositionSizingEngine | 否 | 是 | 唯一正式数量基线 |
| Paper Execution | 否 | 否 | 仅执行已保存且版本匹配的 DecisionReport |

任何代码改动若改变上表任一“可影响”关系，必须视为策略版本变更，重新执行 Day 0，不得混入既有 Observation 样本。

## 3. Evidence Usage Scope

`EvidenceItem` 必须包含 `usage_scope`：

- `POLICY`：允许 ActionPolicyEngine 消费；
- `RESEARCH_ONLY`：可进入 ResearchReport、DeepSeek、UI、审计，但禁止影响正式 Action / Quantity；
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
Market / Local Data Universe
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

以下内容可用于 UI / Research / 数据刷新优先级，但不得改变正式 paper decision cohort：

- watchlist；
- 热门板块；
- 当日涨跌幅排名；
- 成交额 / 量比热点；
- 主力资金 / 北向资金；
- 新闻热度；
- LLM 评分或结论。

已有 paper position 是安全例外：**全部持仓必须保留风险监控资格，即使其日线尚未达到 eligibility、即使持仓数量超过普通 candidate limit。** 数据不足可以让 ActionGate 阻断，但不能让持仓从风险监控集合中消失。

### 4.2 Eligibility 与冷启动规则

正式非持仓候选的当前 eligibility 只要求：

```text
本地 daily_price_cache >= 60 根日线
```

候选选择阶段**不要求已有 cached quote**。

原因：报价新鲜度属于后续 Data Quality / ActionGate。如果 Candidate Scheduler 在报价刷新之前强制要求 cached quote，冷启动时会先得到空候选池，从而没有机会进入正常报价刷新流程。

因此顺序固定为：

```text
>= 60 日线历史资格
  -> deterministic candidate selection
  -> refresh quote / risk / derived data
  -> Data Quality / Freshness gate
  -> formal decision
```

Quote 缺失、过期或刷新失败仍可阻断 OPEN / ADD；本条只消除候选前置阶段的冷启动死锁，不放宽正式交易门禁。

### 4.3 Deterministic Rotation

Observation 的正式候选调度采用确定性轮转：

1. 输入为满足固定 eligibility 的全量本地 symbol 集合；
2. 所有 paper position 无条件优先保留；
3. 若 position 数量超过普通 candidate limit，风险监控集合自动扩容，不丢持仓；
4. 剩余槽位按 `candidate_selection_version + rotation_key + symbol` 的稳定 hash 排序；
5. `rotation_key` 使用稳定交易日或 Observation cycle key；
6. 保存 eligible universe 的 `candidate_pool_hash`；
7. 相同 universe、positions、rotation_key、version 必须得到完全相同结果。

最低审计字段：

```text
candidate_selection_version
candidate_pool_hash
rotation_key
selection_reason
candidate_rank
```

### 4.4 当前运行接线

`backend/app/candidate_selection.py` 是 deterministic scheduler。

`backend/app/paper_runtime.py` 负责：

- 从 `daily_price_cache` 读取 >= 60 根历史的 eligibility；
- 强制保留全部 paper positions；
- 当前版本 pending DecisionReport；
- candidate pool audit；
- 同版本 DecisionReport 复用判断；
- 显式请求与 formal cohort 的权限分离。

`backend/app/paper_runtime_integration.py` 在 FastAPI startup 之前把治理后的实现接入运行模块。

正式 paper decision cohort 当前只读取：

```text
daily_price_cache >= 60 bars
paper positions
candidate_selection_version
rotation_key
```

明确不读取 watchlist、hot sector、top gainer、fund flow、news 或 LLM。

原有大体量 API 组装未手工重写，原始 Git blob 原样移动为 `backend/app/application.py`；`backend/app/main.py` 仅作为小型入口，在 startup 之前安装 runtime governance，并把 `app.main` 别名到 application 模块以保留既有 monkeypatch / import 兼容性。

## 5. 数据预热与正式候选必须分权

### 5.1 全市场 history prewarm

热门板块和涨幅榜仍可生成 Opportunity / Research 元数据，但**正式历史日线预热队列不再从热点列表中选择**。

A 股全市场快照保存后，history prewarm 从完整有报价 symbol 集合执行独立 deterministic rotation：

```text
rotation_key = YYYY-MM-DD:history-prewarm
limit = 24
```

因此热点只影响 Research / UI，不再通过“谁先拥有 60 根日线”间接改变正式候选资格。

### 5.2 显式请求可以预热，但不能越权生成正式动作

`requested_symbols`、人工点击或市场 scope 可以提高数据刷新优先级。

如果一个显式请求不属于：

```text
当前 deterministic cohort
或
当前版本 pending due decision
```

它可以进入：

```text
quote/history/risk data prewarm
simulation audit
```

但**不能进入本轮 `decision_symbols`，不能生成正式 DecisionReport，不能执行交易**。

如果其历史不足 60 根，运行审计记录 `skipped_data_unavailable / insufficient_daily_bars`；如果数据完整但未被本轮 scheduler 选中，记录 `not_selected_by_deterministic_scheduler`。

这保证“人工请求可以让数据更快准备好”，但不能把人工请求本身变成隐藏交易策略。

## 6. 新决策候选与历史执行义务必须分离

新交易日轮转 cohort 后，上一交易日已经生成且尚未成交的 DecisionReport 不能因为“今天未被轮转选中”而消失。

运行集合分为：

```text
new_decision_symbols = 当前 deterministic cohort ∩ 当前正式执行 scope
pending_due_symbols   = 当前治理版本的未执行历史 DecisionReport ∩ 当前正式执行 scope
formal_runtime_symbols = union(new_decision_symbols, pending_due_symbols)
```

数据预热集合可以额外包含被 formal scheduler 拒绝的显式请求，但这些 symbol 不会进入 `new_decision_symbols`。

Pending queue 仅接受：

- 当前 `policy_version`；
- 当前 `candidate_selection_version`；
- 尚无 executed paper log 的最新 formal DecisionReport。

如果某个 symbol 后来又生成了更晚的手工 / Research DecisionReport，但该报告没有当前 candidate lineage，它不能遮住上一份仍有效的 formal paper DecisionReport。

因此部署治理版本后：

- 旧 policy / candidate 版本历史报告不会被新 Observation 账本成交；
- 新一日轮转不会让昨日合法待执行报告凭空消失；
- 手工报告不能抢占 formal execution queue。

## 7. DecisionReport 候选与 AI Shadow 血缘

由 paper runtime 生成的每份新 DecisionReport 必须保存：

```text
candidate_selection_version
candidate_pool_hash
candidate_rotation_key
candidate_rank
candidate_selection_reason
```

短间隔内复用旧 formal report 时，除时间窗口外还必须同时满足：

```text
policy_version 相同
candidate_selection_version 相同
candidate_pool_hash 相同
candidate_rotation_key 相同
```

任一不一致都重新生成报告，不得跨治理版本复用。

Observation 阶段正式动作仍为：

```text
baseline_action = ActionPolicyEngine candidates[0].action
```

DeepSeek 可以保存：

```text
ai_shadow_action = guarded preferred_action
ai_shadow_agreement = ai_shadow_action == baseline_action
```

但必须满足：

- 只能来自 deterministic candidate actions；
- 只能引用当前 evidence IDs；
- 不得生成价格或数量；
- 不得进入 paper execution；
- 不得修改 baseline action；
- disagreement 只用于之后的复盘和 P2 研究。

## 8. Opportunity Scan 语义

Opportunity Scan 是研究排序，不是预测服务。

正式语义：

- `research_priority_score` / legacy `score`：研究优先级启发式分数；
- `confidence`：证据覆盖 / 质量；
- `risk_level`：历史风险标签。

禁止解释为：

- 上涨概率；
- 买入胜率；
- 未来收益概率；
- 模型置信概率。

当前旧客户端字段 `upside_likelihood` 仅作为兼容占位，固定返回中性值 `50`，不得用于排序、策略、校准、审计结论或 UI 的概率文案。完成客户端迁移后删除该字段。

## 9. Baseline Known Limitations

Observation 开始前必须明确记录而不是静默修正：

- 当前 ActionPolicy 的 `EXIT` 路径尚未形成正式 deterministic trigger；
- 当前 PositionSizing baseline 仍使用系统级最大仓位约 20%；
- 当前风险预算 baseline 约为总资产 1%；
- 当前默认 invalidation 约为 entry 的 -5%；
- 上述参数属于 baseline 行为，任何修改都要求新版本与重新 Day 0。

Observation 的目标是先验证基线可审计、可重复和不越权，不是在观察期内优化这些参数。

## 10. Day 0 新增零容忍检查

在统一规范原有清单之外新增：

- [ ] `RESEARCH_ONLY` evidence 无法改变 ActionPolicy 结果；
- [ ] `event.negative.*` 不存在正式策略通路；
- [ ] fund flow 不能改变 ActionPolicy；
- [ ] Opportunity 不输出真实方向概率；
- [ ] 正式 candidate scheduler 不消费 watchlist / hot sector / top gainer / fund flow / LLM；
- [ ] candidate eligibility 不因冷启动缺少 cached quote 而变成空集合；
- [ ] quote freshness 仍由 Data Quality / ActionGate 在正式动作前校验；
- [ ] 正式 history prewarm 不消费 hot sector / top gainer 作为选样依据；
- [ ] 所有 paper positions 始终进入风险监控集合，且数量超过普通 limit 时不会被截断；
- [ ] 相同 universe + rotation key 的 candidate cohort 可重复；
- [ ] requested scope 不能注入 formal cohort，但允许只读数据预热；
- [ ] 被拒绝的显式请求必须有可追溯 audit state；
- [ ] 换日轮转不会丢失当前版本未执行历史 DecisionReport；
- [ ] 更晚的手工 / Research report 不会遮住合法 formal paper report；
- [ ] 旧 policy / candidate 版本 DecisionReport 不得进入新 execution；
- [ ] candidate pool hash、rank、reason 与 selection version 可从 run / DecisionReport 回查；
- [ ] AI shadow action 与 baseline action 分栏保存且 execution 只消费 baseline；
- [ ] `app.main` 启动入口、FastAPI routes 与 startup worker 在 integration 安装后正常运行；
- [ ] CI `compileall + pytest + docker build + ci-gate` 全部通过。

任一项失败：Day 0 不通过。

## 11. 本次代码版本边界

本次治理变更升级：

```text
evidence-v2-usage-scope
swing-policy-v2-research-isolation
candidate-rotation-v1
research-priority-v1
```

因此不得与 `evidence-v1 / swing-policy-v1` 的 Observation 数据混为同一个冻结样本。

## 12. 最小自动验收

自动测试至少必须证明：

1. `direction=negative, strength=0.95` 的 `RESEARCH_ONLY` event 不能改变正式 Action；
2. fund flow 无论正负均保持 `RESEARCH_ONLY`；
3. Opportunity 的旧 `upside_likelihood` 不再携带方向信息；
4. candidate scheduler 对输入顺序不敏感；
5. position 即使不在 eligible pool 中也必须保留；
6. position 数量大于普通 limit 时不能被截断；
7. 同日相同 pool 结果完全一致；
8. 不同 rotation key 可轮转 cohort，但 pool hash 不变；
9. 有 60 日日线、无旧 cached quote 的 symbol 仍可进入候选并触发报价刷新；
10. requested scope 无法注入 formal decision cohort；
11. 被排除的 requested symbol 可触发数据预热但不能生成正式动作；
12. 历史 due decision 可独立于新 rotation cohort 保留；
13. 更晚的非 formal report 不会遮住当前 formal paper report；
14. DecisionReport 复用要求 policy + candidate lineage 完全一致；
15. `app.main` 与 `app.application` 在治理安装后保持同一运行模块对象；
16. 完整 backend pytest 与 Docker build 通过。

---

**执行口径：**代码层候选治理与运行接线已经完成；但 Observation Day 1 仍必须等待本 PR 最终 commit 的 CI 全绿，并在真实部署环境完成统一规范与本规范的全部 Day 0 实测（真实 commit / image identity、数据库与迁移、运行日志、数据血缘、成交时序等）。代码合并本身不等于 Day 0 已通过。
