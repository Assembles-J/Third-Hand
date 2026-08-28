# ThirdHand UI/UX Rebuild Implementation Plan v2

> Companion plan for `ThirdHand_UIUX_Rebuild_v1.md` v2.
>
> Scope: incremental Android migration toward the approved target screenshots while preserving existing backend/API and trading-authority boundaries.

## 1. Delivery policy

Every UI slice follows:

```text
Issue
 -> authoritative contract check
 -> Android implementation
 -> deterministic screenshots
 -> visual comparison against approved target direction
 -> CI Debug/Release
 -> physical-device acceptance
 -> canonical ledger sync when required
```

Updating screenshot hashes is not sufficient acceptance by itself.

## 2. Target shell first

Before more page-level density work, wire the new primary shell:

```text
首页 | 行情 | 组合 | 策略 | 自选
```

Required shell changes:

- brand red primary treatment;
- compact red-accent top app bars where appropriate;
- compact bottom navigation with red selected state;
- light canvas/surface tokens;
- consistent compact typography and spacing;
- no default-blue Material navigation treatment;
- preserve all existing reachable feature routes through the new shell.

## 3. UIX0 — design reset

Tracked by #140.

Deliverables:

- rewrite target design contract;
- rewrite implementation plan;
- synchronize `.superdesign/design-system.md`;
- synchronize canonical roadmap/ledger;
- re-scope UIX1-UIX6 so old shell preservation is no longer an acceptance requirement;
- keep in-flight page PRs draft until rebased/reconciled.

## 4. UIX1R — shell/theme/navigation wiring

Goal: make the installed app immediately read as the approved Third-Hand target before individual content pages are finished.

Scope:

- replace old bottom navigation labels with `首页 | 行情 | 组合 | 策略 | 自选`;
- wire brand red shell tokens;
- replace default Material blue selection states;
- introduce reusable compact target top bar / tabs / section header / financial row primitives;
- keep minimum 44dp touch targets;
- preserve existing routes through mapped entries.

Acceptance:

- shell visual similarity is materially aligned with the approved screenshots;
- every primary destination is reachable;
- no old `资讯 | 行情 | 持仓 | 交易 | 自选` acceptance assertion remains in active UI docs/tests;
- CI and device acceptance pass.

## 5. UIX2R — 首页 + 行情

### 首页

Build from existing authoritative read models only:

- portfolio summary;
- today's material decision/trade signals where currently available;
- attention/review items where currently available;
- latest research where currently available;
- explicit empty/partial/degraded states for unavailable sections.

No Android-local recommendation synthesis.

### 行情

- search near top;
- compact tabs;
- aligned quote values/change;
- dense market rows;
- stock-detail route preserved;
- stale/partial/error states explicit.

## 6. UIX3R — 组合 + 自选

### 组合

Adapt current Holdings and Position Detail work into the approved shell:

- compact account/portfolio summary;
- factual table-like holding rows;
- numeric alignment;
- quote freshness and explicit degraded states;
- Position Detail route;
- AI/Decision remains a secondary route.

### 自选

- retain Personal Universe/Watchlist management;
- dense monitoring rows;
- preserve position sibling behavior and routing;
- preserve add/edit/remove/priority/note/enabled flows.

## 7. UIX4R — 策略 / simulated AI execution

Goal: map current Paper Trading + Decision Workspace + available research-plan capability under the target `策略` experience.

Primary strategy tabs:

```text
AI交易 | 决策工作台 | 研究计划
```

### AI交易

Use existing simulated account only:

- equity/cash/market value/P&L;
- positions;
- automatic-execution enabled/paused state;
- manual decision-cycle trigger;
- execution history;
- executed records;
- audit/detail drill-down.

Target-style child surfaces may include simulated equivalents of:

- AI持仓;
- AI交易历史;
- AI交易分析;
- simulated confirmation/detail sheets.

Any order-like confirmation must explicitly identify the simulated account. No real-broker controls.

### 决策工作台

Preserve server-owned formal action/evidence/risk/lineage semantics.

### 研究计划

Expose ReviewPlan/research scheduling facts only if authoritative API data is present.

## 8. UIX5R — Stock/Position Detail + Decision Workspace alignment

- compact quote header;
- K-line and factual position sections;
- compact evidence/risk/what-changed sections;
- factual and research responsibilities remain visually distinct;
- no Android-local authority calculation.

## 9. UIX6R — final consistency pass

Cross-screen audit against approved screenshots:

- shell/color consistency;
- typography hierarchy;
- spacing rhythm;
- card radius/elevation discipline;
- bottom-nav/top-bar consistency;
- empty/loading/error/degraded states;
- accessibility and 44dp touch targets;
- physical-device readability.

## 10. In-flight PR policy

PR #139 remains draft until this baseline lands.

After baseline merge:

- rebase/reconcile #139;
- keep useful factual holdings components;
- adapt navigation label/shell/theme and screenshots to `组合` target;
- do not merge merely because existing compact screenshot hashes pass.

Other UIX implementation PRs must follow the same rule.

## 11. Business boundary

No UI slice may introduce:

- real broker order entry;
- real money transfer;
- broker switching;
- order cancellation against a real broker;
- AI authority over Formal Decision, Risk, sizing or ExecutionPrecheck;
- local Android reconstruction of server-owned review/decision policy.

The redesign changes presentation and navigation, not trading authority.
