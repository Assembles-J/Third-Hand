# Third-Hand AKShare 多数据源与 LLM 接口检索改造方案 v1.2

## 1. 状态

本版将 v1.1 的设计推进到第一阶段实施。当前 PR 只落地 P0 数据基础设施，不放宽交易门禁，也不把动态 AKShare Registry 数据提升为正式 POLICY 证据。

### 已确认的生产问题

2026-08-14 对线上 `/app/data/third_hand.db` 的核验得到：

- `daily_price_cache` ISO 日期 `YYYY-MM-DD`：38,248 条；
- compact 日期 `YYYYMMDD`：6,011 条；
- 同股票同日 compact/ISO 双份记录：1,618 对；
- compact 记录比 ISO 更新：0 对；
- 同股票同日 close 不一致：679 对，涉及 8 只股票；
- mismatch 来源：Tushare vs Tencent 555 对，Tushare vs AKShare 124 对；
- Tencent `qfq`：30,149 条；
- AKShare/Eastmoney `qfq`：7,393 条；
- Tushare `provider-default`：6,712 条；
- Sina minute aggregation `qfq`：5 条。

这证明正式历史序列同时存在日期格式与复权口径污染，可能造成假 missing、重复远程拉取，以及 risk/trend/relative-strength 的派生污染。

## 2. 正式日线数据契约

普通 A 股正式历史数据统一要求：

```text
trading_date = YYYY-MM-DD
adjustment   = qfq
volume       = shares
amount       = CNY
```

第三方 provider 的原始格式不能直接决定正式缓存格式。Provider 必须先完成 normalization，再进入 `daily_price_cache`。

## 3. Local-First

正式数据访问遵循：

```text
本地缓存
  -> 检查交易日缺口
  -> 无缺口：0 次远程调用
  -> 有缺口：只请求连续 missing session range
  -> provider normalization
  -> 落本地
  -> 下游 risk / feature / DecisionContext 只读本地正式快照
```

远程数据源是“补缺/刷新 Provider”，不是 AI 每次分析都即时抓取的主数据平面。

## 4. A 股 Provider 顺序

普通沪深 A 股：

```text
Local qfq cache
  -> Tencent / AKShare stock_zh_a_hist_tx
  -> Tushare pro_bar(adj=qfq)
  -> Eastmoney / AKShare stock_zh_a_hist(qfq), last resort
  -> Sina minute aggregation, post-close one-bar supplement
```

北京市场继续根据 provider 能力路由；Tencent 不适用时直接进入 Tushare/后续 fallback。

### 生产验证

服务器已验证：

- AKShare 1.18.91；
- `stock_zh_a_hist_tx('sh600519')` 可返回腾讯历史日线；
- `stock_zh_a_hist_tx('sz000001')` 可返回腾讯历史日线；
- Sina 实时行情可返回 2026-08-14 收盘行情；
- Third-Hand 的 provider audit 已有 Tencent/Tushare 成功记录。

因此不再把 Eastmoney 作为普通 A 股历史日线的首选来源。

## 5. Tushare qfq 规范化

旧路径使用 `pro_api().daily()` 并以 `provider-default` 写入正式缓存，导致与 Tencent/Eastmoney qfq 序列产生系统性价格差异。

P0 改为：

```text
Tushare pro_bar
  asset=E
  freq=D
  adj=qfq
```

并将：

- `vol` 从手转换为股；
- `amount` 从千元转换为元；
- `trade_date` 统一成 ISO 日期；
- `adjustment` 固定为 `qfq`。

## 6. 历史数据清理与审计

启动时运行独立的数据契约清理 `daily_price_iso_qfq_v1`，记录在：

```text
daily_price_contract_migrations
```

它与现有 `schema_migrations` 分离，避免把数据清理伪装成 schema migration。

清理流程：

1. 创建 `daily_price_quarantine`；
2. 将 non-qfq、compact date、invalid date key 的旧记录先复制到 quarantine；
3. 从正式缓存删除 non-qfq；
4. qfq compact 与 ISO 重复时保留 ISO；
5. 无重复的 qfq compact 安全转换为 ISO；
6. 清理 malformed date key；
7. 对受影响股票 invalidate `risk_cache`；
8. 清空可重建的 `portfolio_analysis_cache` 与 `feature_values`；
9. 保留历史 DecisionReport，不改写历史审计结论。

部署前必须先备份生产数据库。

## 7. Provider 限流与熔断

现有 provider health / circuit breaker 继续保留，并增加保守的最小调用间隔：

- Tencent：默认 0.5 秒；
- Tushare：默认 0.5 秒；
- Sina minute：默认 2.0 秒；
- Eastmoney：默认 2.0 秒。

可通过环境变量调整：

```text
HISTORY_TENCENT_MIN_INTERVAL_SECONDS
HISTORY_TUSHARE_MIN_INTERVAL_SECONDS
HISTORY_SINA_MIN_INTERVAL_SECONDS
HISTORY_EASTMONEY_MIN_INTERVAL_SECONDS
```

这些值是 Third-Hand 的安全默认值，不代表第三方平台公布的官方额度。

## 8. AI / Research 数据 Local-First

AI 需要的数据同样遵循：

```text
本地存在 + fresh + schema/version compatible
  -> 直接读取本地
否则
  -> 只拉缺失/过期部分
  -> normalize + validate
  -> 先落库
  -> AI 再读取本地快照
```

不得把第三方原始 DataFrame/JSON 绕过本地正式数据层直接当作可交易事实。

## 9. AKShare Registry / LLM 接口发现（后续 P2）

后续 Research AI 可接入：

```python
ak.search(...)
ak.interface_info(...)
ak.list_categories()
```

这层是离线接口元数据检索，用于让 LLM 从 AKShare 大量接口中发现合适的数据函数，不是新的行情数据源。

动态发现并调用的数据默认：

```text
RESEARCH_ONLY
```

不能直接影响 ActionPolicy、PositionSizing、execution price 或正式交易概率。若未来某个 Research 特征希望升级到 POLICY，必须另行版本化、point-in-time 验证与治理审批。

## 10. 交易恢复验收顺序

P0 部署后按以下顺序验收，不以“是否马上出现买入”作为成功标准：

1. `daily_price_cache` 正式数据不再有 compact date；
2. 正式 A 股历史不再有 `provider-default`；
3. 本地已有完整 session 时 provider 调用次数为 0；
4. 只缺一个 session 时只拉该缺口；
5. `daily_bars.stale` 消失；
6. `risk.stale` 消失；
7. `market_regime` 可用；
8. `relative_strength` 可用；
9. `OPEN` gate 不再因数据基础设施问题 blocked。

允许最终状态是：

```text
OPEN permission = allowed
action = WATCH
```

这表示基础设施恢复正常，但当天策略没有满足开仓条件。

## 11. 后续阶段

### P1

- provider adapter 模块化；
- provider capability matrix（沪深/北交所/ETF/HK）；
- 更细粒度 freshness 与 lineage；
- provider 指标与运维看板。

### P2

- AKShare Registry Tool；
- Research AI 动态接口发现；
- Local-First research cache；
- `RESEARCH_ONLY` 证据审计。

### P3

只有经过正式验证的研究特征才允许提出 POLICY promotion，不在本次 P0 范围内。
