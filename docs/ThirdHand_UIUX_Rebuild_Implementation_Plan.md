# ThirdHand UI/UX Rebuild Implementation Plan

> Companion document to `ThirdHand_UIUX_Rebuild_v1.md`.
>
> Scope: issue/PR decomposition for an incremental Android UI rebuild using existing ThirdHand capability only.

## 1. Delivery policy

Each UI slice must follow:

```text
Issue
 -> existing backend/API contract check
 -> Android implementation
 -> screenshot/unit coverage
 -> CI
 -> physical-device acceptance
 -> roadmap/ledger sync where required
```

A UI slice must not silently create new backend semantics or new trading authority.

## 2. Shared acceptance rules

Every slice must satisfy:

- no unsupported feature is introduced;
- no real-broker trading UI is introduced;
- current navigation/routing remains reachable;
- existing loading/empty/error/stale states remain represented;
- compact typography and high information density are used;
- minimum touch target remains accessible;
- red-up / green-down semantics reuse the project market-color abstraction;
- representative screenshot baselines are updated intentionally;
- Debug and Release builds remain green.

## 3. UIX1 — global density and shared primitives

### Goal

Create the compact visual foundation before rewriting individual screens.

### Scope

- typography scale cleanup;
- spacing density cleanup;
- compact top bar/bottom navigation treatment;
- dense section header;
- dense quote/value row;
- table/list divider primitives;
- compact state/tag treatment;
- consistent numeric alignment.

### Non-goals

- no navigation change;
- no API change;
- no business behavior change;
- no new dashboard content.

### Acceptance

- existing five primary tabs remain unchanged;
- common text does not use oversized dashboard typography;
- list surfaces use separators instead of unnecessary nested cards;
- screenshot fixtures show the new global density.

## 4. UIX2 — 资讯 + 行情 visual rebuild

### Goal

Make the two scan-heavy surfaces faster to read.

### 资讯 scope

- compact headline rows;
- smaller metadata/time/source text;
- reduced card chrome;
- section grouping using dividers and whitespace rather than large rounded cards.

### 行情 scope

- compact market tabs;
- dense index overview;
- right-aligned prices/change values;
- tighter market list rows;
- preserve existing stock-detail route.

### Non-goals

- no new market provider;
- no new AI summary;
- no invented breadth/statistics endpoint.

## 5. UIX3 — 自选 / Personal Universe visual rebuild

### Goal

Make Watchlist a high-density monitoring surface.

### Scope

- retain existing Watchlist/Positions sibling relationship;
- dense row anatomy for name, symbol, latest price, change and compact review metadata where already available;
- preserve add/edit/remove/priority/note/enabled flows already implemented;
- preserve routing to stock/holding detail;
- reduce oversized cards.

### Non-goals

- no broker order actions;
- no automatic promotion of Discovery into Watchlist;
- no new review calculation on Android.

## 6. UIX4 — 持仓 + factual detail cleanup

### Goal

Turn portfolio reading into a compact table-first experience.

### Scope

- compact portfolio summary;
- table-like holdings header/row layout;
- name/symbol, market value, P/L, quantity/available, cost/current price;
- keep quote freshness, holding days and weight where existing data supports them;
- preserve holding-detail route;
- visually separate factual holding information from Decision Workspace research.

### Non-goals

- no AI reasoning embedded in basic holding rows;
- no new portfolio analytics endpoint;
- no manual trade actions.

## 7. UIX5 — 交易 / simulated-account execution console

### Goal

Redesign the existing `PaperTradingScreen` around what it actually is: a simulated-account execution and audit surface driven by the existing decision chain.

### Current authoritative UI capability

The implementation already exposes:

- account equity;
- available cash;
- market value;
- cumulative P/L;
- paper positions;
- simulated-account automatic execution enabled/paused state;
- manual decision-cycle run trigger;
- execution-chain history;
- execution/fill log rows;
- decision/audit drill-down.

### Target hierarchy

```text
交易账户 / 模拟账套

总权益 + 收益率
现金 | 持仓市值 | 累计盈亏

持仓明细

模拟账户自动执行    [switch]
状态说明
[立即运行决策轮换]

执行链路记录 >

最近成交记录
```

### Visual rules

- reduce the height of the existing primary-color equity card;
- use compact financial typography;
- align paper-position rows like a securities holding table;
- make enabled/paused/running state textual and explicit;
- keep the real-broker boundary visible;
- execution rows emphasize B/S, symbol/name, price, quantity and time;
- retain the `分析记录` drill-down.

### Explicit non-goals

Do not add:

- manual order ticket;
- BUY/SELL form;
- limit-price field;
- quantity stepper;
- order cancellation;
- broker selection;
- real money transfer;
- N5 isolated AI-agent paper account behavior unless separately implemented and accepted.

## 8. UIX6 — stock detail + Decision Workspace visual alignment

### Goal

Give factual quote data and structured research one coherent visual system without merging their responsibilities.

### Scope

Stock/position detail:

- compact quote header;
- K-line area;
- factual position fields where applicable;
- existing financial/currentness/event information.

Decision Workspace/research:

- Formal action/conclusion;
- evidence/support;
- risk;
- what changed;
- review/lineage information where currently available.

### Non-goals

- no new forecast output;
- no new AI authority;
- no hidden local decision calculation.

## 9. PR strategy

Prefer one PR per implementation slice after the documentation PR merges.

Recommended branch/PR order:

```text
ui/uiux-density-foundation
ui/news-market-density
ui/watchlist-density
ui/holdings-density
ui/paper-trading-console
ui/detail-decision-alignment
```

Do not combine all Android surfaces into one mega-PR.

## 10. Dependency notes

- UIX1 should merge first because the later screens should consume shared tokens/primitives.
- UIX2-UIX4 can follow independently after UIX1 if file overlap is controlled.
- UIX5 should explicitly account for the current simulated-account terminology work and must preserve `paper_trading_enabled` semantics.
- UIX6 should be last among the visual slices because it touches the largest cross-surface information hierarchy.

## 11. Product wording

Preferred wording for the existing transaction surface:

```text
交易
模拟账套
模拟账户自动执行
立即运行决策轮换
执行链路记录
最近成交记录
分析记录
```

Avoid wording that overstates authority:

```text
AI 下单
确认下单
真实交易
自动实盘
券商下单
```

unless a future, separately approved product capability actually implements those semantics.
