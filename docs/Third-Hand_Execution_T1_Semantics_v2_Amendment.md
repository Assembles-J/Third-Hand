# Third-Hand：Execution T+1 语义修正（v2 Amendment）

**版本：2.0（2026-08-17）**  
**适用范围：纸面模拟执行 / `NEXT_ELIGIBLE_OBSERVED_QUOTE`**  
**状态：对《Third-Hand_Unified_Governance_and_Observation_Spec.md》中“成交时序”相关条款的定向修正**

## 1. 修正原因

统一治理规范 v1.0 将“禁止同周期成交”错误实现/描述为“成交报价日期必须严格晚于决策日期”。该规则会把 A 股 T+1 错误地施加到 BUY：同一交易日 10:04 形成 OPEN 后，即使 10:14 出现新的独立实时报价，也会被迫等到下一交易日才能买入。

A 股 T+1 在本系统中的正确模拟语义是：**当日买入的数量当日不可卖出；它不禁止当日形成 OPEN/ADD 后，使用后续独立报价完成 BUY。**

## 2. 唯一执行口径

从 `execution-v2-t1-sell-only` 起：

1. Execution 只能消费已经持久化的历史 `DecisionReport`，不能执行本轮刚生成且尚未经历后续行情观察的报告。
2. 成交报价的实际观察时间必须严格晚于决策输入报价时间：`execution_quote_at > decision_market_as_of`。当 provider 的 `as_of` 只有日期时，以可追溯的 `retrieved_at` / `generated_at` 补足时序判断。
3. 同一交易日的后续独立报价允许成交；禁止的是 same-cycle / same-observation fill，而不是 same-day fill。
4. `OPEN / ADD`：满足正式 Action Gate、Sizing、现金和后续报价条件后，可在同一交易日执行 BUY。
5. `REDUCE / EXIT`：可在同一交易日执行，但 SELL 数量不得超过账本的 `sellable_quantity`。
6. A 股 T+1：`sellable_quantity = current_quantity - same_day_buy_quantity`（最低为 0）。当日新增 BUY 数量在当日锁定，下一交易日才进入可卖数量。
7. 混合仓位示例：昨日持有 1000 股、今日再买 500 股，则今日总持仓 1500 股、最多可卖 1000 股；今日新增 500 股不可卖。
8. 成交价格语义继续固定为 `NEXT_ELIGIBLE_OBSERVED_QUOTE`，不得称为“下一交易日开盘价”。

## 3. 对原统一治理规范的定向覆盖

本 Amendment 仅覆盖原规范中以下两类表述：

- “成交报价日期必须严格晚于决策日期”；
- “同一交易日的决策不得成交；后续日期的报价才允许成交”。

它们统一替换为：

> 决策与成交必须隔离；只消费已持久化的历史 DecisionReport。成交必须使用**严格晚于决策输入报价观察时间**的独立报价。允许同一交易日后续报价成交，禁止同一观察周期成交。A 股 T+1 仅约束 SELL 可用数量：当日 BUY 的数量当日不可卖出。

除上述成交时序/T+1 条款外，统一治理规范 v1.0 的其他边界继续有效，特别是：

- ActionPolicy 阈值冻结；
- PositionSizing 规则冻结；
- LLM / Research / Thesis / 新闻 / 资金流不得改变正式 Action 或 Quantity；
- `same_cycle_fill_violation_count` 必须保持为 0；
- 历史 DecisionReport 与成交审计不可被后续数据改写。

## 4. 版本与历史兼容

- 新 DecisionReport 必须在 `audit_versions` 中记录 `execution_policy_version=execution-v2-t1-sell-only`。
- v2 执行器不得静默消费缺少该版本或属于旧 execution policy 的正式 DecisionReport；部署后应生成新的 v2 报告，再由后续独立报价执行。
- 因执行语义发生 correctness 修正，观察样本不得把 v1 与 v2 执行结果混为同一冻结版本。

## 5. 必须通过的回归检查

```text
同一决策输入报价 -> 不可成交
同日后续独立报价 -> OPEN/ADD 可 BUY
旧仓 + 今日新仓 -> 只能 SELL 旧仓可卖数量
今日全部新买 -> 当日 SELL 被 T+1 拒绝
OPEN/ADD Action Gate blocked -> 即使有后续报价也不可执行
execution_quote_at <= decision_market_as_of -> 永远不可执行
```
