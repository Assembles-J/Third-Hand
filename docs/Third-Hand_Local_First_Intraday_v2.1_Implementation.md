# Third-Hand Local-First Intraday v2.1 实施说明

## 1. 目标

本增量承接 Data Scheduling / Local-First v2，继续收紧“实时数据自动采集”和“AI 读取数据”的边界：

```text
交易时段
  ↓
Quote / Intraday Scheduler
  ↓
SQLite persisted cache
  ↓
Android / Research Chat / DecisionContext
```

休市期间自动刷新路径只读取已保存快照，不因为页面刷新、持仓后台更新或 Paper Trading 周期再次访问实时报价/分钟行情 Provider。

## 2. Quote / Intraday 调度规则

以下自动触发在证券对应交易所开盘时才允许远端 Quote 请求：

- `startup-prewarm`
- `request-forced`
- `holding-created`
- `holding-updated`
- `scheduler-trading-session`
- `paper-trading-decision`

`refresh_intraday_cache` 本身还会再次按 symbol 检查交易所是否正在开盘。因此即使调用方误触发，休市也不会继续访问分钟行情 Provider。

收盘快照例外：`scheduler-close-snapshot` 只在受限的 post-close maintenance window 内允许一次必要的收盘维护。

## 3. K 线历史数据

日线仍保持现有明确的按需 Local-First 契约：

```text
GET /v1/market/history/{symbol}
    -> 只读 SQLite

POST /v1/market/history/{symbol}/refresh
    -> 计算 requested range 的交易日
    -> 与 SQLite 已有交易日做差集
    -> 只请求 missing ranges
    -> normalize
    -> persist
    -> reread SQLite
    -> 返回完整本地区间
```

Android 的日期区间选择已经调用 `refreshMarketHistory(start_date, end_date)`；“重新加载日线”也是显式用户按需补缺，不属于后台定时拉取。

## 4. AI 分时数据

Research Chat 新增只读工具：

```text
get_intraday_history(symbol, limit)
```

约束：

- 数据来源固定为 `PortfolioStore.intraday_prices()`；
- 只读本地 SQLite；
- 不包含 provider refresh 分支；
- 默认最多 240 条，硬上限 1000 条；
- 仅为 `RESEARCH_ONLY` 上下文，不成为新的 ActionPolicy 输入；
- 不改变 OPEN / ADD / REDUCE、PositionSizing 或执行逻辑。

这样 AI 可以回答“今天上午走势如何”“最近分钟波动怎样”等问题，但不会为了回答问题临时访问第三方行情接口。

## 5. 与正式交易边界

本增量不改变：

- `swing-policy-v3-position-action-semantics`；
- OPEN Gate 条件；
- deterministic candidate rotation；
- `NEXT_ELIGIBLE_OBSERVED_QUOTE`；
- AI 的 Research / shadow-only 权限。

Quote/Intraday 调度优化只改变数据何时刷新，不给 AI 新增正式交易权限。
