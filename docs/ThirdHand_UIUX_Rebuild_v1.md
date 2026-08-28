# ThirdHand UI/UX Rebuild v2

> Status: APPROVED TARGET DESIGN CONTRACT
>
> Goal: align Android with the approved target screenshots while preserving the repository's current authority and backend/API boundaries.

## 1. Product shell

Primary Android navigation is now:

```text
首页 | 行情 | 组合 | 策略 | 自选
```

This supersedes the previous UIX requirement that the shell remain `资讯 | 行情 | 持仓 | 交易 | 自选`.

Mapping:

- 首页: daily overview built from existing portfolio, decision/review, research and attention facts where available;
- 行情: existing market/search/detail capability;
- 组合: existing Holdings -> Position Detail factual portfolio path;
- 策略: existing simulated-account execution, Decision Workspace and available review/research-plan surfaces grouped under one strategy entry;
- 自选: existing Personal Universe / Watchlist capability.

No navigation change may imply a new authority boundary. Real-broker trading remains out of scope.

## 2. Visual baseline

The approved screenshots are the visual direction. Implementation should reproduce their product feel without copying third-party branded assets or trade dress.

Required language:

- light-first Chinese securities-app layout;
- primary brand/action red `#F52D3A`;
- canvas `#F7F8FA`, surface `#FFFFFF`;
- primary text `#1F2329`, secondary text `#667085`;
- A-share rise red `#F52D3A`, fall green `#16A05D`, flat `#7A8492`;
- compact top bars, compact tabs and compact bottom navigation;
- restrained rounded cards only for major grouping;
- dense rows, thin dividers and aligned financial values;
- system sans typography with approximately 10-11sp auxiliary, 12sp secondary, 13-14sp body/value, 15-16sp section/row title and 18-20sp only for page-critical values;
- minimum 44dp touch targets.

The selected bottom-navigation state must use the brand red treatment, not the default blue Material primary.

## 3. Screenshot acceptance

Screenshot hashes alone are not visual acceptance.

Every UI slice must include:

1. deterministic Compose screenshot states;
2. comparison with the approved target direction for shell, density, hierarchy, spacing and color;
3. physical-device readability/interaction acceptance;
4. CI Debug/Release success.

A screenshot baseline may not be updated merely to bless an unintended visual regression.

## 4. 首页

Target hierarchy should follow the approved dashboard direction while rendering only authoritative data already exposed by current APIs.

Preferred order:

```text
Third-Hand / AI交易助手
首页 | 行情 | 组合 | 策略 | 自选

组合总览
今日盈亏 / 总资产 / 现金 / 持仓市值

今日决策/交易信号
待处理事项
最新研究
```

Rules:

- if a section has no authoritative data, show an explicit empty/partial state rather than invented values;
- do not manufacture AI recommendations locally;
- tap targets should route into the existing authoritative detail/workspace surfaces.

## 5. 行情

Preserve current market/search/detail capability but align presentation with the target design:

- compact red-accent shell;
- search near the top;
- tab-first market navigation;
- aligned quote values and changes;
- dense rows and restrained cards;
- existing loading, stale, partial and error states remain explicit.

Do not invent new provider data solely to fill the design.

## 6. 组合

`组合` owns factual portfolio data and replaces `持仓` as the primary navigation label.

Keep:

- available cash;
- market value;
- total P/L;
- name/symbol;
- current price and freshness;
- quantity/cost;
- market value;
- P/L amount and percentage;
- holding days and position weight where supplied;
- Position Detail routing.

The list remains fact-first. Decision/AI explanation stays behind an explicit secondary route.

## 7. 策略

`策略` is a navigation/workspace grouping, not a new decision engine.

Primary sub-tabs should use the target hierarchy where current capability supports it:

```text
AI交易 | 决策工作台 | 研究计划
```

### AI交易

Map the existing simulated-account / Paper Trading capability here:

- simulated account equity/cash/market value/P&L;
- simulated positions;
- persisted automatic-execution enabled/paused state;
- manual `立即运行决策轮换` trigger;
- execution-chain history;
- fills/executed records;
- decision/audit drill-down.

The visual design may resemble the approved `AI交易`, `AI持仓`, `AI交易历史`, `AI交易分析` screenshots, but all actions remain simulated-account actions.

Do not introduce real broker BUY/SELL, transfer, broker switching or cancellation.

### 决策工作台

Reuse existing Decision Workspace authority and read models. Keep formal action, evidence, risk, what-changed and lineage visually distinct from factual portfolio data.

### 研究计划

Expose existing ReviewPlan / research scheduling facts only where already supported. Do not calculate ReviewPolicy authority locally on Android.

## 8. 自选

Preserve Personal Universe / Watchlist behavior, including existing add/edit/remove/priority/note/enabled flows.

Use dense securities rows with right-aligned quote values and compact metadata. Held positions must remain protected from Watchlist membership edits according to existing product semantics.

## 9. Safety and wording boundary

The target screenshots are a visual/product-navigation reference, not authorization for real brokerage execution.

Preferred simulated wording includes:

```text
AI交易
模拟账户
自动执行
立即运行决策轮换
执行记录
分析记录
```

Any confirmation sheet that resembles an order confirmation must clearly indicate that it applies to the simulated account unless a later accepted capability explicitly changes this boundary.

## 10. Implementation constraints

Required:

- reuse existing APIs and DTOs;
- preserve Formal Decision, ReviewPolicy, Risk, sizing, ExecutionPrecheck, Paper Broker and Evaluation authority;
- keep new feature state outside `MainActivity.kt` where practical;
- implement shell/tokens before screen-specific polish;
- use target-design visual acceptance, not merely density metrics.

Do not claim `PRODUCT_DONE` before CI and physical-device acceptance.

## 11. Delivery order

```text
UIX0  target shell + design-contract reset
UIX1R shell/theme/navigation wiring
UIX2R 首页 + 行情
UIX3R 组合 + 自选
UIX4R 策略 / simulated AI execution
UIX5R Stock/Position Detail + Decision Workspace alignment
UIX6R final cross-screen visual consistency + device acceptance
```
