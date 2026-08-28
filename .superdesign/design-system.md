# Third-Hand Mobile Research Design System

## Product context

Third-Hand is a mobile-first A-share research, portfolio review and simulated-account execution assistant. The Android product shell must visually align with the approved target screenshots while preserving current authoritative backend/API boundaries.

## Primary shell

The active target navigation is:

```text
首页 | 行情 | 组合 | 策略 | 自选
```

This supersedes the previous UIX shell `资讯 | 行情 | 持仓 | 交易 | 自选`.

Mapping:

- 首页: overview from existing authoritative portfolio/review/research facts;
- 行情: market/search/detail;
- 组合: factual Holdings / Position Detail;
- 策略: simulated AI execution + Decision Workspace + available research-plan surfaces;
- 自选: Personal Universe / Watchlist.

## Visual direction

Use a light-first, red-first Chinese financial-market language with the scan density of mature securities apps while keeping Third-Hand's own identity.

- Canvas: `#F7F8FA`.
- Surface: `#FFFFFF`.
- Brand / primary action: `#F52D3A`.
- Brand container: `#FFE0E3`.
- Primary text: `#1F2329`.
- Secondary text: `#667085`.
- A-share rise: `#F52D3A`.
- A-share fall: `#16A05D`.
- Flat: `#7A8492`.
- Errors remain a distinct Material error role and must not be conflated with market rise red.

The selected bottom-navigation state must use brand red, not the default blue Material primary.

## Typography

Use Android system sans with compact financial roles:

- 10-11sp auxiliary/caption/navigation labels;
- 12sp secondary metadata;
- 13-14sp body and financial values;
- 15-16sp section/list title;
- 18-20sp only for page-critical values.

Avoid oversized marketing/dashboard headings on scan-heavy screens.

## Spacing and surfaces

- dense surfaces prefer 16dp horizontal content inset;
- row vertical padding around 8dp;
- section rhythm around 10dp;
- minimum 44dp interactive target;
- use thin neutral dividers for financial lists;
- use cards only for meaningful grouping;
- prefer 6-10dp radius for small controls and 10-14dp for major summary panels;
- avoid decorative elevation and gradients as the primary visual language.

## Global shell components

### Top bars

- compact 44-52dp class;
- red-accent or red-brand treatment where the target screenshot calls for a branded header;
- action icons only for existing screen capabilities;
- no oversized title blocks.

### Bottom navigation

- compact labels/icons;
- selected icon/text in brand red;
- neutral unselected items;
- restrained selection indicator;
- no blue Material default treatment;
- destinations: `首页 | 行情 | 组合 | 策略 | 自选`.

### Tabs

- compact horizontal tabs;
- brand-red active indicator/text;
- neutral inactive text;
- no large pill chrome unless the approved reference clearly requires it.

## Dense financial layout rules

- align comparable numeric values to the right;
- keep security identity/name on the left and quote/status values on the right;
- use text labels in addition to rise/fall/state colors;
- prefer section header + rows/dividers over one card per row;
- keep symbol, market, time, freshness and review metadata visually secondary;
- never invent decorative charts or financial metrics without authoritative data.

## Screen boundaries

### 首页

Use existing authoritative facts only. Preferred hierarchy:

```text
组合总览
今日决策/交易信号
待处理事项
最新研究
```

Unavailable sections use explicit empty/partial states rather than fabricated values.

### 行情

Search-first, tab-first, dense quote rows, right-aligned values, explicit stale/partial/error states.

### 组合

Portfolio and Position Detail remain fact-first: price/freshness, quantity, cost, market value, P/L, holding duration, weight, K-line and existing transaction facts. AI/research narrative remains a secondary route.

### 策略

Primary target tabs:

```text
AI交易 | 决策工作台 | 研究计划
```

`AI交易` maps to the existing simulated-account / Paper Trading capability. It may visually use target-style AI holdings/history/analysis sub-surfaces, but it does not authorize real-broker execution.

`决策工作台` keeps existing Formal Decision / evidence / risk / what-changed / lineage authority.

`研究计划` may show ReviewPlan/research scheduling facts only where authoritative API data exists.

### 自选

Use existing Personal Universe / Watchlist capabilities with dense monitoring rows and compact metadata.

## Simulated trading boundary

Preserve current simulated-account capability only:

- equity, cash, market value and P/L;
- simulated positions;
- persisted auto-execution enabled/paused state;
- manual `立即运行决策轮换`;
- execution-chain history;
- executed records and decision/audit drill-down.

Order-like confirmation UI must explicitly state that it applies to a simulated account. Do not introduce real broker BUY/SELL tickets, transfers, broker switching, or real cancellation flows.

## Screenshot and device acceptance

Screenshot hashes are regression tools, not design approval.

Every target UI slice must be checked for:

- shell/color alignment with approved screenshots;
- hierarchy and information density;
- spacing, typography, corners and dividers;
- loading/empty/stale/partial/error states;
- physical-device readability and interaction;
- minimum 44dp touch targets.

Do not update a screenshot hash merely to approve an unintended visual regression.

## Accessibility and interaction

- every icon action has a text label or content description;
- status uses text in addition to color;
- long titles truncate predictably;
- native Material controls remain acceptable when styled to the target design;
- no hidden gesture is required for a primary function.
