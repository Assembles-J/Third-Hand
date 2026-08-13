# Third-Hand：统一治理、Day 0 与 20 日观察规范

**版本：1.0（2026-08-13）**  
**文档状态：唯一当前口径 / 审阅与执行依据**  
**当前阶段：`PRE_OBSERVATION / DAY_0_AUDIT`**

> 本文统一此前的可靠性路线、前后台设计、P1/P2 设计、研究证据层评审、实现偏差审计、当前方向简报及 Day 0 观察门槛。此前仓库内的重复文档已在用户授权下整合删除；本文是唯一当前口径。

## 1. 总目标与一句话路线

Third-Hand 是一个**受约束的决策研究与纸面模拟执行系统**，不是预测涨跌、自动选股或保证胜率的模型。

唯一正确的推进顺序：

```text
冻结现有策略
  -> Day 0 审计通过
  -> 真实数据运行并累计 20 个有效交易日
  -> 审阅一致性与审计报告
  -> 批准后才启动 P2：只读回放、实验预注册、影子策略
  -> 再讨论任何策略提升或对纸面交易的影响
```

当前不得回到“增加因子、修改阈值、追求更多成交或提前回测优化”的阶段。

## 2. 不可变产品边界

| 主题 | 已确认边界 |
| --- | --- |
| 标的范围 | 全市场候选池；人工自选仅提高刷新/展示优先级，绝不改变同一标的的特征、证据权重、阈值或动作。 |
| OPEN / ADD | 报价、日线、风险、账户资产、市场环境、工具元数据等关键输入须完整且新鲜；数据不足时阻断。交易更少可以接受。 |
| HOLD / WATCH / REDUCE / EXIT | 保留防御性研究或人工复核路径；不可把研究态伪装成可成交。 |
| 资金流 | 仅展示或研究证据；不得作为 OPEN/ADD 因子，不得叙述为“主力吸筹/洗盘/出货”。 |
| LLM、Research、Thesis | 仅可摘要、解释、归档、复盘；不得改变确定性动作、仓位、成本或收益概率。 |
| 成交时序 | 决策与成交隔离：只消费历史 DecisionReport，成交报价日期必须严格晚于决策日期。 |
| 成交价格名称 | 当前仅可称 `NEXT_ELIGIBLE_OBSERVED_QUOTE`，不是“下一交易日开盘价”。 |
| 概率/胜率 | 观察期和 P2 之前不得展示上涨概率、胜率、最优参数、Sharpe 或策略收益结论。 |
| 历史不可变性 | 历史 Context、DecisionReport、ResearchReport、Thesis 版本不得被后续数据或结果改写。 |

## 3. 当前真实状态：设计、代码、部署必须分开看

### 3.1 代码状态

| 范围 | 状态 | 已实现事实 |
| --- | --- | --- |
| P0 风控 | 本地代码完成 | Freshness、按动作门禁、OPEN/ADD 阻断、后续时段成交检查、全市场/自选优先级隔离。 |
| Day 0 越权修复 | 本地代码完成 | 已切断 `LLM news impact -> event.negative -> ActionPolicy`；执行只读取 `report.action`。 |
| Day 0 审计字段 | 本地代码完成 | 新报告保存版本/配置哈希；纸面成交日志保存报价时间、来源和价格语义。 |
| P1 最小血缘 | 本地代码部分完成 | 上下文规范化快照、质量事件、8 个 `enabled=0` 影子特征、lineage API。 |
| R1/R2 研究层 | 本地代码部分完成 | 确定性只读 Report、Evidence/Claim、不可变 Thesis 版本与差异复核。 |
| P2 成本 | 本地代码最小完成 | 纯成本计算函数；未产生策略回测结果。 |
| P2 回放与影子策略 | 未开始 | 没有 point-in-time 回放、预注册、滚动切分、OOS 或候选策略。 |

### 3.2 部署与运行状态

- Compose 配置的运行数据库是宿主 `data/third_hand.db`，挂载至 `/app/data/third_hand.db`。
- 2026-08-13 本地核验：该库 `decision_reports=0`、不同交易日数为 `0`；`0010_p1_data_lineage`、`0011_research_reports`、`0012_research_theses` 尚未记录为已执行。
- Docker Desktop 当时不可连接，因此无法从本机确认运行容器/镜像版本。
- 结论：**20 日观察尚未开始。** 本地代码通过测试不等于实际部署已经启用。

## 4. Day 0 审计门槛

Day 0 只确认审计可信度，不增加策略能力。任何未通过项都不得将下一交易日记为 Day 1。

### 4.1 必须通过的检查表

- [ ] 固定实际部署的 `git_commit`、制品版本与容器镜像摘要（如使用容器）。
- [ ] 确认运行数据库路径正确，且 `0010–0012` 迁移已执行。
- [ ] 确认部署中的 `GIT_COMMIT` 不为 `unknown`。
- [ ] 确认 DecisionReport 保存 context/evidence/policy/sizing/freshness/prompt 版本及 `config_hash`。
- [ ] 确认 OPEN/ADD 的 Freshness 与硬门禁在实际运行中生效。
- [ ] 构造一次测试：同一交易日的决策不得成交；后续日期的报价才允许成交。
- [ ] 确认执行层只消费 `report.action`，没有 AI `preferred_action` 回退。
- [ ] 确认缓存 AI 新闻 impact 只形成研究证据，不能形成 `event.negative` 策略条件。
- [ ] 确认 ResearchReport、Thesis、资金流都没有进入 ActionPolicyEngine。
- [ ] 确认输入 Context、input_hash、关键来源时间、成交报价时间/来源/价格语义可回查。
- [ ] 锁定策略、阈值、仓位规则、配置版本；Day 1 后不得静默变更。

### 4.2 Day 0 的本地代码核验结论

| 项 | 结论 |
| --- | --- |
| 同周期即时成交 | 已由 `execute_due_paper_decisions` + `validate_daily_execution` 规避；需在部署环境实测。 |
| LLM 新闻影响策略 | 原本存在，现已修复：DecisionContext 将缓存 AI 新闻 impact 固定为 `uncertain`。 |
| AI action 回退 | 本地执行路径只读取 `report.action`。 |
| 成交价格语义 | 报告和成交日志均显式记录 `NEXT_ELIGIBLE_OBSERVED_QUOTE`。 |
| 版本审计 | 每份新报告保存非秘密版本快照与 config hash；部署必须注入真实 commit。 |

若策略性字段、数据质量门禁或成交时序必须修复，则当前观察窗口作废或尚未开始；不得把不同版本混入同一 20 日样本。

## 5. 20 个有效交易日观察规范

### 5.1 目的

不是验证“赚钱”，而是验证：

```text
没有未来数据泄漏
没有同周期成交
没有 LLM / Research 越权
没有不可追溯输入
没有版本混用
```

### 5.2 每份决策与成交必须保留

| 类别 | 最低字段 |
| --- | --- |
| 身份/版本 | `decision_id`、`context_id`、`symbol`、`input_hash`、版本快照、`config_hash`。 |
| 决策时间 | `generated_at`、`market_as_of`、关键输入的 `as_of/retrieved_at/available_at`。 |
| 质量门禁 | `status`、缺失/过期项、warnings、OPEN/ADD gate 及阻断原因。 |
| 决策依据 | Evidence IDs、Action Candidates、触发规则、最终确定性 `report.action`。 |
| 参考价格 | 决策价格、决策报价来源/时间。 |
| 实际成交 | `executed_at`、成交价、数量、方向、成交报价时间/来源、价格语义。 |
| 成本 | 手续费、税费、滑点、其他成本和总成本；当前纸面账本成本口径需在报告中单独注明。 |

### 5.3 零容忍指标

以下均必须为零：

```text
future_data_violation_count
same_cycle_fill_violation_count
llm_action_override_count
research_to_policy_override_count
untraceable_input_count
missing_decision_version_count
```

OPEN/ADD 被阻断、没有交易、未成交或数据源失败均是应保留的观察结果，不是删除样本的理由。

### 5.4 观察期内的开发纪律

允许并行且不改变交易输出：原始供应商报文保存、修订链、逐特征 `available_at`、只读研究/Thesis 页面、监控、审计面板、日志与告警。

禁止：新增买卖因子、修改 ActionPolicy 阈值、修改 PositionSizing、用近期结果调参、将资金流/新闻/Thesis 引入策略、LLM 影响仓位、展示胜率或上涨概率、运行策略优化。

## 6. 数据与特征治理（P1）

### 6.1 已有最小闭环

`data_source_registry`、`raw_data_snapshots`、`data_quality_events`、`feature_catalog`、`feature_values` 已在本地迁移代码中定义。首批影子特征固定为 8 个：趋势、RSI、MACD、ATR、下行概率、年化波动和市场状态；全部 `enabled=0`，不能影响 ActionPolicy。

### 6.2 尚未完成但不阻塞 Day 1 的工作

- 保存上游供应商**原始报文**，而非仅保存 Context 的规范化载荷。
- 同一报文去重、修订 `supersedes_snapshot_id`、完整 revision chain。
- 按特征而非 Context 生成精确 `available_at`。
- 供应商修订、停牌、涨跌停、复权变化等更完整的质量事件。

前提是 Day 1 起已能不可逆保存“当时系统实际看到了什么、何时看到、来源为何、输入 hash 与确定性动作为何”。若该前提不能满足，Day 0 不通过。

## 7. 受限研究证据层（R1/R2/R3）

### 7.1 证据与结论规则

- 结论类型只能是 `FACT / INFERENCE / HYPOTHESIS / UNKNOWN`。
- FACT 必须引用已有 snapshot/evidence ID；INFERENCE/HYPOTHESIS 必须有反证据或明确的缺失项与失效条件。
- 冲突证据必须同时保留；LLM 不裁定“哪个是真的”。
- 不存在可追溯一致预期、公司指引、估值输入或可用时间时，输出 `unknown/unavailable`，不得脑补。

### 7.2 Thesis 与催化剂

Thesis 只读且版本不可变。催化剂只记录已有来源、日期和待验证指标；没有日期或结果时不得伪造未来时间、预期数值或“支持/削弱”的自动结论。

### 7.3 进入策略的唯一通道

```text
正式/授权数据
  -> 确定性结构化特征
  -> P2 point-in-time 回放与样本外验证
  -> 人工 Promotion 审批
  -> 才可能进入 ActionPolicy
```

Research、Thesis、新闻摘要、LLM impact 和资金流均不能绕过该通道。

## 8. P2：仅在批准后启动

P2 的目标是验证可复现性，不是找“最赚钱因子”。

- 基线为当前版本化 `ActionPolicyEngine`。
- 一次实验只能登记一个预先定义的变更，必须有 `strategy_id`、版本、配置 hash、数据截点和停止条件。
- 回放只读取 `available_at <= 决策时点` 的数据；收盘后信号只可用后续时段价格成交。
- 必须模拟现金、最小交易单位、T+1、停牌、涨跌停、无成交量、未成交、佣金、税费、滑点。
- 必须执行时间切分、间隔、滚动验证与最终留出期；最终留出期策略冻结后只使用一次。
- 候选策略先 `shadow_only=true`，不写入纸面账本。

### 8.1 已确认的成本默认值（P2 纯函数）

| 项目 | 默认值 |
| --- | --- |
| 佣金 | 买卖均按万分之一，最低佣金 0（按用户的近似设置）。 |
| A 股普通股票印花税 | 仅卖出万分之五。 |
| A 股 ETF 印花税 | 卖出为 0。 |
| 港股通印花税 | 买入、卖出均按千分之一。 |
| 滑点 | 2 bps。 |

这些参数仅用于 P2 的成本计算，不得在观察期输出收益、胜率、Sharpe 或最优参数。

## 9. 防过拟合与发布门槛

- 首阶段开仓/加仓方向性特征上限 12 个；当前影子目录只登记 8 个。
- 禁止遍历大量窗口、阈值和特征组合再挑选最佳结果；若搜索，必须预注册候选集、预算和主指标。
- 固定基线长期保留；新增策略不得仅凭收益优于基线，还需不恶化回撤、换手、覆盖率与未成交率。
- 上涨、震荡、下跌环境分别报告；样本不足必须显示“无法判断”。
- 只有完成最终留出期、成本/不可成交模拟与人工审阅，才可从影子阶段进入更长期观察。

## 10. 阶段状态机

```text
PRE_OBSERVATION / DAY_0_AUDIT
  -- Day 0 全部通过 --> OBSERVATION_FROZEN
  -- 20 个有效交易日完成 --> OBSERVATION_COMPLETE_PENDING_REVIEW
  -- 人工审阅通过 --> P2_APPROVED
  -- P2 回放和预注册完成 --> SHADOW_ONLY
```

任意发现时间泄漏、策略越权、版本混用或不可追溯输入时：停止计日，记录 version break；不可把修复前后数据合并。

## 11. 验证与审阅记录

本地针对数据时效、门禁、LLM 新闻隔离、纸面账本、证据/Thesis、P1 lineage、成本计算的相关测试共 **26 项通过**，并已完成后端编译检查。该结果只证明本地代码回归通过；Day 0 部署核验仍是开始观察的必要条件。

## 12. 文档归类

仓库内与本规范重复的路线、P1/P2 设计、研究层评审、偏差审计和辩论简报已完成整合并删除。外部提供的 Day 0 原文保留在用户下载目录，本文已吸收其执行要求。

---

**当前唯一可执行下一步：**在实际部署环境完成 Day 0 清单，冻结版本后才标记 Observation Day 1。除 Day 0 阻断修复和不改变交易输出的审计工作外，不继续扩展策略能力。
