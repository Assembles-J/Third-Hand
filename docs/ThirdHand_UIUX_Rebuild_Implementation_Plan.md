# ThirdHand UI/UX Rebuild Implementation Plan

> Status: UIX0 TARGET-SHELL DELIVERY PLAN
>
> **Current-status note (2026-09-02):** the UIX0 target shell has already landed. This file preserves the delivery plan and acceptance contract; use `ThirdHand_Current_Implementation_Status_and_Mobile_Entry_Roadmap.md` for live repository/mobile-entry status.
>
> Companion to `ThirdHand_UIUX_Rebuild_v1.md`.
>
> Scope: incremental Android delivery against the approved target shell and reference direction, using existing ThirdHand capability only.

## 1. Delivery policy

Every UI slice follows the same chain:

```text
Issue / accepted target
 -> existing backend/API contract check
 -> Android implementation
 -> screenshot regression + target-reference comparison
 -> CI
 -> physical-device comparison
 -> roadmap/ledger sync where required
```

Screenshot hashes protect regressions. They are not, by themselves, proof that the UI matches the approved target direction.

A UI slice must not silently create new backend semantics, local decision authority or real-broker trading capability.

## 2. Approved target shell

The target primary Android navigation is:

```text
首页 | 行情 | 组合 | 策略 | 自选
```

The former `资讯 | 行情 | 持仓 | 交易 | 自选` shell is implementation history, not an immutable acceptance requirement.

Product mapping:

- `首页`: attention/change aggregation from current authoritative facts only;
- `行情`: existing market/search/detail capability;
- `组合`: current Holdings / Position Detail factual capability;
- `策略`: current simulated-account execution, Decision Workspace and available review/research-plan capability;
- `自选`: current Personal Universe / Watchlist capability.

## 3. Shared visual acceptance

Every target-shell slice must be reviewed for all of the following:

- Third-Hand brand red is the primary shell/action color;
- canvas is white / cool-light rather than dark or decorative;
- Chinese securities-app density is compact and scan-first;
- red-up / green-down market semantics use project market-color roles;
- primary values align consistently across comparable rows;
- cards are restrained and thin dividers/flat rows are preferred;
- top and bottom navigation remain compact;
- 44dp minimum interaction targets are preserved;
- loading, empty, partial/stale and error states remain explicit;
- no wording or control implies unsupported real-broker authority.

Target-reference review must compare hierarchy, whitespace, density, typography, alignment, color role and card restraint against the approved screenshots at normal phone scale.

## 4. UIX0 — target-shell reset (#140)

### 4.1 Documentation baseline

Land before additional screen-specific work:

- rewrite `ThirdHand_UIUX_Rebuild_v1.md` around the approved shell;
- rewrite this implementation plan;
- synchronize `.superdesign/design-system.md`;
- synchronize the canonical roadmap/ledger;
- explicitly mark old-shell language as historical where it remains in delivery logs.

Acceptance:

- canonical UI docs name `首页 | 行情 | 组合 | 策略 | 自选` as the target shell;
- brand-red shell/action tokens are explicit;
- reference-driven acceptance is explicit;
- simulated-account / no-real-broker boundary is preserved;
- documentation governance and CI pass.

### 4.2 Android shell implementation

After the documentation baseline merges, implement the smallest runtime shell change:

- replace user-visible bottom-nav destinations with `首页 | 行情 | 组合 | 策略 | 自选`;
- wire each destination to existing capability or an explicit honest placeholder/partial state when a composed Home section is not yet implemented;
- reuse current routes rather than inventing server behavior;
- move current Holdings entry under `组合`;
- organize current simulated-account/Decision capability under `策略`;
- keep `自选` on the current Personal Universe path;
- keep `行情` on the current Market path.

Home should be composed incrementally from existing facts. Do not build a fake dashboard simply to fill the new tab.

## 5. Reconciliation of UIX1-UIX6

Previously completed or in-flight work remains useful, but it must converge on the new shell.

| Track | New target responsibility | Reconciliation |
| --- | --- | --- |
| #129 UIX1 | shared brand/density foundation | keep compact primitives; wire brand-red target shell and remove old-shell acceptance assumptions |
| #130 UIX2 | 首页 + 行情 | reuse News/Market density work; News becomes Home content where appropriate rather than a mandatory primary tab |
| #131 UIX3 | 自选 | preserve Personal Universe density and management; align shell/header/reference visuals |
| #132 UIX4 | 组合 | preserve fact-first Holdings/Position Detail work; rename/re-route target destination from `持仓` to `组合` |
| #133 UIX5 | 策略 | place simulated-account execution console under Strategy and align Decision/review entry hierarchy |
| #134 UIX6 | detail + Decision | align factual detail and Decision Workspace to the target visual language without merging authority |

Historical delivery note: PR #139 was subsequently reconciled onto the approved shell and squash-merged on 2026-08-28. Its remaining physical-device acceptance stayed with #132; do not treat the old “stay draft / rebase later” instruction as current work.

## 6. 首页 delivery

### Goal

Create a low-effort attention surface using only existing facts.

### Allowed sources

Where existing contracts already provide them, Home may show:

- portfolio/account summary;
- material review/attention state;
- important decision/research status;
- data/currentness notices;
- selected current news/market context;
- quick links to `组合`, `策略` and `自选`.

### Non-goals

Do not invent:

- a new AI daily brief;
- a new recommendation model;
- a new portfolio-performance metric;
- a new market breadth statistic;
- a hidden local aggregation with trading authority.

### Acceptance

- independent sections have loading/empty/partial/error behavior;
- one failed section does not blank Home;
- Home answers what needs attention rather than duplicating full Market/Portfolio/Strategy screens.

## 7. 行情 delivery

Reuse the current Market/search/detail capability.

Scope:

- compact market/session header;
- index/breadth/sector/ranking facts already available;
- dense quote rows with aligned prices/change values;
- existing stock-detail routing;
- current News/market context where it materially helps scanning.

Non-goals:

- no new provider;
- no decorative unsupported market metric;
- no local decision calculation.

## 8. 组合 delivery (#132)

Goal: make current Holdings / Position Detail a compact fact-first portfolio path.

Scope:

- compact account/portfolio summary;
- table-like holdings rows;
- current price/freshness, quantity, cost, market value, P/L, holding days and weight when supplied;
- preserve Position Detail routing;
- preserve K-line and transaction history;
- preserve secondary Decision entry;
- preserve loading/empty/partial/stale/error states.

Non-goals:

- no AI narrative in every holding row;
- no new portfolio analytics endpoint;
- no manual broker trade controls.

Acceptance includes visual comparison against the approved `组合` direction, not only screenshot hash updates.

## 9. 策略 delivery (#133)

Goal: organize current strategy/decision and simulated-account functionality under one authority-accurate primary destination.

### Existing capability to preserve

- simulated-account total equity, cash, market value and cumulative P/L;
- paper positions;
- persisted simulated-account automatic-execution enabled/paused state;
- manual `立即运行决策轮换` action;
- execution-chain history;
- executed records and decision/audit drill-down;
- Decision Workspace;
- available server-owned ReviewPlan/research-plan facts;
- current Strategy Lab/evaluation entry where already implemented.

### Target hierarchy

```text
策略

决策 / 复核入口
模拟账套摘要
模拟账户持仓
模拟账户自动执行 [switch]
状态说明
[立即运行决策轮换]
执行链路记录 >
最近成交记录
其他现有策略/评估入口
```

### Explicit non-goals

Do not add:

- manual BUY/SELL broker ticket;
- limit-price field;
- quantity stepper;
- order cancellation;
- broker account switching;
- real-money transfer;
- real-broker execution;
- N5 isolated AI-agent paper account behavior unless separately implemented and accepted.

Acceptance:

- `paper_trading_enabled` behavior unchanged;
- manual run behavior unchanged;
- execution-chain and decision-audit routes reachable;
- enabled/paused/running states explicit in text;
- real-broker safety boundary visible;
- target-reference comparison passes.

## 10. 自选 delivery (#131)

Keep existing Personal Universe / Watchlist behavior.

Scope:

- dense name/symbol + quote/change rows;
- priority/note/enabled/paused metadata where already available;
- server-owned review status/reason where already available;
- add/edit/remove flows;
- correct held-symbol vs watchlist-only routing.

No Android ReviewPolicy calculation and no automatic Discovery promotion.

## 11. Detail + Decision delivery (#134)

This slice aligns two responsibilities visually while keeping them separate.

Factual detail:

- quote/freshness;
- K-line;
- position facts when applicable;
- existing financial/event/currentness facts that belong to factual detail.

Decision Workspace/research:

- Formal Decision/action;
- evidence/support;
- risk;
- what changed;
- review/lineage;
- deeper AI Research route.

Android remains a renderer of authoritative state, not a local arbiter.

## 12. Implementation order

Preferred sequence:

```text
1. docs/uix0-target-shell-reset
2. ui/uix0-target-shell
3. ui/uix1-brand-density reconciliation
4. ui/uix2-home-market reconciliation
5. ui/uix3-watchlist reconciliation
6. ui/uix4-portfolio reconciliation
7. ui/uix5-strategy-console reconciliation
8. ui/uix6-detail-decision reconciliation
```

#131-#133 may proceed with controlled file overlap once the runtime shell is stable, but no branch should reintroduce the old shell as an acceptance requirement.

## 13. PR strategy

Prefer one focused PR per slice.

Recommended branches:

```text
docs/uix0-target-shell-reset
ui/uix0-target-shell
ui/uix1-brand-density
ui/uix2-home-market
ui/uix3-watchlist
ui/uix4-portfolio
ui/uix5-strategy-console
ui/uix6-detail-decision
```

Do not combine the entire Android redesign into one mega-PR.

## 14. Governance and delivery state

UI presentation-only changes still state:

- Authority Impact;
- Strategy Impact;
- API / Android Visibility Impact;
- Backward Compatibility;
- Evaluation Impact;
- Acceptance Tests;
- Delivery State.

No user-facing slice is `PRODUCT_DONE` before repository CI, reference-driven screenshot review and physical-device acceptance are complete.
