# ThirdHand UI/UX Rebuild v1

> Status: APPROVED TARGET DESIGN CONTRACT
>
> Reset owner: UIX0 / #140
>
> Goal: align the Android product shell and visual hierarchy with the approved target screenshots while reusing current authoritative product capability. This document does **not** authorize new trading capability, new AI authority, new backend behavior, or a real-broker order flow.

## 1. Approved product shell

The previous five-tab shell is no longer the acceptance baseline.

The approved primary Android navigation is:

```text
首页 | 行情 | 组合 | 策略 | 自选
```

This is an information-architecture and presentation reset only. Existing routes and capabilities are to be reorganized under this shell rather than replaced with speculative backend behavior.

### 1.1 Product mapping

- `首页`: aggregate existing attention, portfolio, decision/review, research and currentness facts where current APIs already provide them. Unsupported sections must be absent or explicitly empty/partial; Android must not invent a server summary.
- `行情`: existing market overview, quote search and stock-detail entry.
- `组合`: current Holdings / Position Detail factual path.
- `策略`: organize the existing simulated-account execution console, Decision Workspace and available review/research-plan surfaces. This remains simulated-account / research functionality, not a real brokerage screen.
- `自选`: current Personal Universe / Watchlist management and monitoring path.

The old `资讯 | 行情 | 持仓 | 交易 | 自选` shell remains implementation history only and must not be used as a reason to reject the approved target shell.

## 2. Visual direction

ThirdHand should read like a compact Chinese securities product, not a decorative AI dashboard.

The approved reference direction requires:

- Third-Hand brand red as the primary shell/action color;
- white / cool-light canvas;
- dense Chinese financial typography;
- red-up / green-down A-share market semantics;
- compact top bars and bottom navigation;
- restrained cards, low elevation and thin dividers;
- aligned financial values and scan-first row anatomy;
- screenshot and physical-device comparison against the approved reference direction, not merely self-generated screenshot hashes.

Do not copy third-party logos, proprietary illustrations or branded trade dress. The target references define hierarchy, density and product character, not a license to clone another app.

## 3. Brand and market color roles

Target role mapping:

```text
Brand / primary shell:  #F52D3A class Third-Hand red
Brand container:        pale red / pink only for selected or grouped emphasis
Canvas:                 cool light neutral
Surface:                white
Primary text:           near-black neutral
Secondary text:         medium cool gray
Rise:                    red
Fall:                    green
Flat / neutral:          gray
Error:                   Material error role, separate from market fall green
```

The selected primary-navigation item, key actions and shell accents use brand red. Market rise/fall colors remain semantic and must not be repurposed to indicate navigation state.

Color is never the only state carrier. BUY/SELL, enabled/paused/running, stale/current, review mode and failures retain explicit text.

## 4. Density and typography

Recommended compact Android roles:

```text
10-11sp  auxiliary / metadata / navigation label
12sp     secondary information
13-14sp  body / financial value / list row
15-16sp  section title / primary security name
18-20sp  page title or one truly primary financial number
```

Avoid 28-40sp dashboard typography except where a reference-critical single financial figure genuinely needs dominance.

Spacing rules:

- 16dp class horizontal content inset on dense screens;
- 6-8dp row vertical rhythm where touch targets still reach 44dp;
- 8-12dp section rhythm;
- thin separators between comparable rows;
- 6-10dp radii for controls/small groups;
- 10-14dp radius only for meaningful summary surfaces.

## 5. Global shell behavior

Primary navigation:

```text
首页 | 行情 | 组合 | 策略 | 自选
```

Shell rules:

- bottom navigation is compact, low-chrome and visually anchored by the selected brand-red item;
- unselected items use neutral icon/text treatment;
- top bars stay compact and screen-specific;
- primary shell actions use brand red, while destructive actions keep their explicit destructive role;
- existing feature routes may be reused internally during migration, but user-visible labels and destinations must converge on the target shell;
- the old `资讯`, `持仓` and `交易` primary labels are not immutable compatibility requirements.

## 6. 首页

`首页` is an attention and change surface built only from currently available facts.

Target hierarchy may include, when backed by existing data:

```text
Account / portfolio snapshot
Material attention or review items
Important decision / research state
Market or currentness notices
Quick routes to 组合 / 策略 / 自选
```

Rules:

- do not fabricate a market brief, AI daily summary, performance statistic or recommendation that is not supplied by current APIs;
- explicit loading/empty/partial/error states are required for independently loaded sections;
- one failed section must not blank the rest of Home;
- Home should answer “what needs my attention?” rather than duplicate full Market, Portfolio or Strategy screens.

The current News capability may be reused as one Home content source, but `资讯` is no longer required as a primary bottom-navigation destination.

## 7. 行情

Use the existing `MarketScreen`, search and stock-detail routes as the market capability foundation.

Target structure:

```text
Compact market header / search
Index and session summary
Existing breadth / ranking / sector facts
Dense quote or ranking lists
Relevant existing market/news context
```

Rules:

- aligned right-side prices/change columns;
- rise/fall values visually strong but compact;
- no decorative statistic is added without an authoritative DTO;
- stock-detail routing remains reachable.

## 8. 组合

`组合` is the destination for current Holdings / Position Detail factual capability.

High-value fields already supported should remain visible where available:

- name / symbol;
- quote and freshness;
- quantity;
- cost;
- market value;
- P/L amount and percentage;
- holding days;
- position weight;
- available cash / portfolio summary;
- sellable / T+1 facts where the relevant authoritative paper/position contract supplies them.

Target list form is table-like and scan-first, not a stack of large stock cards.

Holding Detail remains fact-first: quote, position facts, K-line and transaction history. Decision/research stays behind the existing secondary Decision path.

## 9. 策略

`策略` is the new primary destination for currently implemented decision/research and simulated-account execution capability.

It may organize these existing surfaces:

- simulated-account equity, cash, market value and cumulative P/L;
- simulated-account positions;
- persisted `paper_trading_enabled` control;
- manual `立即运行决策轮换` trigger;
- execution-chain history and trade logs;
- decision/audit drill-down;
- Decision Workspace;
- available server-owned ReviewPlan / research-plan visibility;
- existing Strategy Lab / evaluation entry where already implemented.

### 9.1 Safety boundary

The target screenshots may visually suggest AI order/trade concepts, but ThirdHand currently has no accepted real-broker authority.

Do not add or imply:

- manual BUY/SELL broker tickets;
- limit-price or quantity order entry;
- order cancellation;
- broker account switching;
- real-money transfer;
- real-broker execution;
- N5 isolated AI-agent paper-account semantics before that capability is separately implemented and accepted.

Preferred wording remains authority-accurate:

```text
模拟账套
模拟账户自动执行
立即运行决策轮换
执行链路记录
最近成交记录
分析记录
决策与 AI
```

Avoid `AI 下单`, `确认下单`, `自动实盘` or equivalent wording.

## 10. 自选

Use the existing Personal Universe / Watchlist contracts.

Core scan model:

```text
股票名称          最新价      涨跌幅
代码 / 市场       行情状态    复核/注意信息
```

Where already available, compactly expose priority, note, enabled/paused, position overlap and server-owned review state.

Add/edit/remove flows remain accessible; position-only rows must not gain Watchlist mutation authority.

## 11. Stock / position detail and Decision Workspace

The approved design aligns these surfaces visually without merging responsibilities.

Factual detail owns:

- name / symbol;
- quote/change/freshness;
- K-line;
- holding facts where applicable;
- existing financial/event/currentness facts that belong to the factual surface.

Decision Workspace / research owns:

- formal conclusion/action;
- evidence/support;
- risks;
- what changed;
- review / lineage information;
- deeper AI Research entry.

Android must not recompute server-owned decision or review authority.

## 12. Interaction and accessibility

- 44dp minimum interactive target even when visual rows are denser;
- primary functions cannot depend on undiscoverable gestures;
- destructive actions remain explicit;
- loading, empty, stale/partial and error states remain visible;
- independent section failures stay isolated;
- long labels truncate predictably;
- every icon action has a content description or visible label.

## 13. Reference-driven acceptance

Screenshot hashes remain useful regression machinery, but they are not sufficient visual acceptance by themselves.

Every rebuilt surface must be checked against the approved target direction for:

- shell labels and destination hierarchy;
- brand-red shell/action treatment;
- density and whitespace;
- card restraint;
- financial-value alignment;
- typography scale;
- market rise/fall semantics;
- real-broker safety wording.

Physical-device acceptance must explicitly compare the rendered app against the target references at normal phone scale.

## 14. Migration and implementation history

UIX1-UIX6 work already completed or in flight remains useful implementation history, especially shared density primitives and factual screen cleanup. It must now be reconciled to the UIX0 target shell rather than treated as the final acceptance baseline.

Current re-scope:

```text
UIX0 / #140  approved shell + design baseline reset
#129          shared density primitives -> reconcile to brand-red target shell
#130          News/Market density -> Home/Market reconciliation
#131          Watchlist density -> 自选 target destination
#132          Holdings density -> 组合 target destination
#133          Paper Trading console -> 策略 simulated-execution section
#134          detail/Decision alignment -> target detail hierarchy
```

PR #139 remains draft until this baseline lands, then its useful factual `组合` work must be rebuilt/reconciled on the new base.

## 15. Authority impact

None.

This contract changes navigation, hierarchy and presentation acceptance only. Formal Decision, StrategyProfile, ReviewPolicy, Evidence, Risk, sizing, ExecutionPrecheck, Paper Broker and Evaluation authority remain unchanged and server-owned.
