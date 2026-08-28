# ThirdHand UI/UX Rebuild v1

> Status: DESIGN CONTRACT
>
> Goal: rebuild the Android visual system and information density around the product that already exists today. This document does **not** authorize new trading capability, new AI authority, new backend behavior, or a broker-style manual order flow.

## 1. Design direction

ThirdHand should look and behave like a dense Chinese-market research utility rather than a decorative AI dashboard.

Reference principles may be taken from mature securities apps such as Tonghuashun:

- compact typography;
- high information density;
- aligned numeric columns;
- white/light canvas with restrained separators;
- clear red-up / green-down market semantics;
- tab-first navigation and compact list rows;
- fast scanning before decoration.

Do not copy third-party logos, illustrations, proprietary graphics, branded assets, or exact trade dress.

## 2. Non-negotiable product boundary

The redesign must follow current repository capability.

Current primary Android navigation remains:

```text
资讯 | 行情 | 持仓 | 交易 | 自选
```

The `交易` entry is the existing **simulated-account / paper-trading execution surface**. It is not a real broker order page and must not be redesigned as user-driven Buy / Sell / Cancel order entry.

The current Paper Trading surface already owns:

- simulated account total equity;
- available cash;
- position market value;
- cumulative P/L;
- simulated-account positions;
- automatic execution enable/pause control;
- manual `run now` decision-cycle trigger;
- execution-chain history;
- executed trade records;
- decision/audit drill-down from execution records.

The visual redesign must expose those existing facts more clearly. It must not add unsupported controls such as:

- manual limit-order entry;
- manual BUY / SELL buttons;
- broker account switching;
- real order cancellation;
- settlement transfer;
- real-broker execution.

## 3. Visual language

### 3.1 Density

Target a high-density mobile layout.

Recommended Android typography hierarchy:

```text
10-11sp  auxiliary / metadata
12sp     secondary information
13-14sp  body / list values
15-16sp  section title / primary row name
18-20sp  page-critical number only
```

Avoid 28-40sp dashboard headings except for a truly primary financial number.

### 3.2 Surfaces

Prefer:

- white or very light neutral canvas;
- compact section headers;
- thin neutral dividers;
- low/no elevation for list rows;
- 6-10dp radius for small controls;
- 10-14dp radius only for major summary panels.

Avoid:

- every row inside a large rounded card;
- excessive whitespace;
- marketing-style hero blocks;
- oversized AI labels;
- decorative gradients as the main visual language.

### 3.3 Color

Reuse the existing ThirdHand red-up / green-down market semantics.

Suggested visual role mapping:

```text
Brand / primary action: existing project primary red
Rise: existing market rise red
Fall: existing market fall green
Primary text: near-black neutral
Secondary text: medium neutral gray
Canvas: light neutral
Surface: white
Separator: low-contrast neutral gray
```

Color must never be the only carrier of state. BUY/SELL, enabled/paused, execution state, review state and error state must retain text labels.

## 4. Global navigation and shell

Keep the current five-tab product shell during this rebuild:

```text
资讯 | 行情 | 持仓 | 交易 | 自选
```

This UI/UX slice is not the place to replace the information architecture with a speculative future navigation model.

Global shell rules:

- bottom navigation height should remain compact;
- selected tab uses primary red + label;
- unselected tabs use neutral text/icons;
- top bars remain 44-52dp class, not oversized;
- action icons are limited to functions that already exist on the screen.

## 5. 资讯 screen

The existing `NewsScreen` remains the entry.

Design objective:

- compact headline scanning;
- clear timestamps and source/context where already available;
- reduce card chrome;
- use section headers and separators;
- preserve existing data and actions only.

Do not invent a new AI daily brief unless current API/runtime already provides it.

## 6. 行情 screen

The existing `MarketScreen` remains the market entry.

Target structure:

```text
Top market tabs / search
Market overview
Index strip
Breadth / market statistics already available
Dense stock / market lists
Existing news or market context sections
```

Rules:

- numeric columns right-aligned;
- rise/fall values visually strong but compact;
- spark lines remain secondary to the quote value;
- scrolling density should be closer to a professional quote app than a dashboard.

## 7. 自选 screen

Use the already implemented Watchlist / Personal Universe data only.

Primary sibling relationship:

```text
自选股 | 持仓股
```

Where current implementation exposes review status, priority, note, enabled/paused or Personal Universe metadata, show those as compact secondary lines or tags.

Target row anatomy:

```text
股票名称          最新价     涨跌幅
代码 / 市场       小型走势   状态/复核信息
```

Do not add broker actions to Watchlist rows.

## 8. 持仓 screen

The current Holdings surface owns factual portfolio data.

Keep the high-value fields already defined by the product:

- name / symbol;
- current price and quote freshness;
- quantity;
- cost;
- market value;
- P/L amount;
- P/L percentage;
- holding days;
- position weight;
- available cash / portfolio summary where currently supplied.

Design target:

```text
账户/组合摘要
--------------------------------
名称/市值 | 盈亏 | 持仓/可用 | 成本/现价
--------------------------------
持仓 row
持仓 row
...
```

Use table-like alignment, not large stock cards.

Basic holdings list must remain fact-first. AI reasoning does not belong in every holding row.

## 9. 交易 screen: existing simulated-account AI execution

This is the most important correction to the previous concept.

The current screen is **not a manual broker ticket**. Redesign it as a dense simulated-account execution console.

Recommended information order:

```text
交易账户 / 模拟账套

总权益        总收益率
可用现金      持仓市值      累计盈亏

持仓明细

模拟账户自动执行
[启用/暂停开关]
状态说明
[立即运行决策轮换]

执行链路记录 >

最近成交记录
B/S | 股票 | 价格 | 数量 | 时间 | 分析记录
```

### 9.1 Account summary

The current full-width primary-red hero card should be reduced in height.

Keep total equity dominant but not oversized. Secondary metrics should fit in one compact row.

### 9.2 Position table

Reuse existing paper positions. Prefer table/list alignment similar to the Holdings screen so the user can compare live holdings and simulated holdings quickly.

### 9.3 Automatic execution control

Preserve existing authority boundary:

```text
模拟账户自动执行
已开启 / 已暂停 / 正在运行
```

The screen must retain the explicit statement that it controls only the simulated account and does not submit orders to a real broker.

The existing manual trigger remains:

```text
立即运行决策轮换
```

Do not rename this into `确认下单`, `AI 下单`, or other language suggesting a discretionary manual broker order.

### 9.4 Execution history

Current execution-chain history remains a drill-down surface.

Current executed trade rows should emphasize:

```text
B 买入 / S 卖出
股票名称 / symbol
成交价格
数量
成交时间
分析记录 >
```

Keep the route into decision/audit details.

## 10. Stock / position detail

Existing Stock Detail, Position Detail and Decision Workspace remain separate responsibilities.

Stock/position factual areas should use compact quote-app presentation:

- name/symbol;
- price/change;
- K-line;
- holding facts when applicable;
- existing events/financial/currentness facts where already present.

Decision Workspace / research views should retain the existing structured research model:

- conclusion/action;
- supporting evidence;
- risks;
- what changed;
- decision lineage / review information where already implemented.

Do not collapse factual position data and long AI reasoning into one mixed card stack.

## 11. Interaction rules

- 44dp minimum touch targets even when visual density is high.
- swipe/hidden gestures are not required for primary functions.
- destructive actions require explicit labels/confirmation where they already exist.
- loading, empty, stale/partial and error states must remain visible.
- a section failure must not make unrelated data disappear.
- no new business calculation should move into Composables.

## 12. Implementation constraints

This is an incremental UI rebuild, not a frontend rewrite.

Required:

- reuse existing APIs and DTOs;
- reuse existing feature routes;
- preserve current authority model;
- reuse `MarketColors`, typography and spacing tokens after token cleanup;
- add/update Compose screenshot baselines for each rebuilt screen;
- keep feature code out of an even larger `MainActivity.kt` where practical.

Do not claim `PRODUCT_DONE` before repository CI and physical-device acceptance.

## 13. Delivery order

Recommended sequence:

```text
UIX1  Global density / typography / shared list primitives
UIX2  资讯 + 行情
UIX3  自选
UIX4  持仓 + factual detail visual cleanup
UIX5  交易 / simulated-account execution console
UIX6  stock detail + Decision Workspace visual alignment
```

Each slice must preserve existing capability and include screenshot regression coverage.
