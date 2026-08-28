# Third-Hand Strategy Workspace UI Contract

Status: design/implementation contract
Scope: Android `策略` primary destination
Authority: presentation only; no decision, review, sizing or execution authority moves to Android

## 1. Purpose

After UIX0/UIX5/UIX8, `策略` already owns the shipped simulated-account execution console, while `收益复盘` and `策略实验室` exist as separate Android surfaces. The next slice should make those existing capabilities feel like one compact securities workspace without inventing a new backend read model or a new trading authority.

The canonical top-level shell remains:

`首页 | 行情 | 组合 | 策略 | 自选`

The canonical Strategy workspace labels are:

`模拟执行 | 收益复盘 | 策略评估`

Do not use `AI交易` for the existing scheduler. The current execution path is the existing Formal-decision simulated-account flow and must not be confused with future N5/#96 isolated AI-agent paper trading.

## 2. Existing capability mapping

### 模拟执行

Reuse the current `PaperTradingScreen` capability unchanged:

- simulated-account total equity;
- available cash;
- position market value;
- cumulative P/L and return;
- paper positions;
- `模拟账户自动执行` enabled/paused/running state;
- guarded `立即运行决策轮换` action;
- execution-chain history;
- executed trade records;
- `分析记录` / decision-audit drill-down;
- existing position/detail and Decision Workspace routes.

No manual BUY/SELL ticket is added.

### 收益复盘

Reuse the existing `ExecutionReviewScreen` and its server/API facts:

- daily review date/status;
- executable recommendation snapshots;
- reference price;
- theoretical P/L where already returned;
- manual evaluation trigger when the server allows it;
- loading, empty and error states.

Android must not fabricate benchmark return, win rate, attribution or any other aggregate that is not returned by the existing API.

### 策略评估

Reuse the current read-only Strategy Lab capability:

- strategy/version/experiment identity;
- win rate, payoff ratio, expectancy and max drawdown where returned;
- benchmark comparison;
- action/regime/execution attribution where already returned;
- loading, empty and error states.

This is evaluation/read-only presentation. It does not create, edit or deploy a strategy.

## 3. Navigation contract

The Strategy destination should read as one workspace, not three unrelated apps.

Preferred hierarchy:

```text
策略
[ 模拟执行 ] [ 收益复盘 ] [ 策略评估 ]

<selected existing surface>
```

Rules:

- default selection: `模拟执行`;
- switching sections must preserve the main bottom navigation and return path;
- section switching must not reset global app tab selection;
- Android system back from a nested decision/position/audit detail returns to the selected Strategy section before leaving `策略`;
- no section may introduce a second competing bottom navigation;
- avoid stacked full-height headers. The workspace should present one dominant page header plus one compact section selector.

If the existing screen implementation cannot be embedded cleanly in the first code slice, a temporary explicit subroute is acceptable only if the entry labels and back behavior follow this contract. The end state remains a single Strategy workspace.

## 4. Visual contract

Follow the merged UIX8 securities chrome:

- canvas: `#F7F8FA`;
- surface: white;
- Third-Hand primary/action red: `#F52D3A`;
- market rise/fall colors remain semantic and are not replaced by brand red;
- compact typography and 4/8/10/14/16/20dp rhythm;
- minimum interactive target: 44dp;
- no gradient hero cards;
- no oversized page titles;
- no large selected-tab pill;
- no card-per-row treatment when a divider/list hierarchy is sufficient.

The Strategy section selector should be compact text-first navigation. Recommended selected treatment: red text + short underline or thin bottom indicator. Unselected labels use the neutral text color. Do not use a large pink rounded capsule.

## 5. Simulated execution hierarchy

The `模拟执行` section keeps the current accepted hierarchy:

1. compact account facts;
2. paper positions table/list;
3. execution control;
4. execution-chain entry;
5. recent executed records;
6. decision/audit drill-down.

Required wording:

- `模拟账套`;
- `模拟账户自动执行`;
- `已开启` / `已暂停` / `运行中`;
- `立即运行决策轮换`;
- `分析记录` when referring to existing decision-audit detail.

Prohibited wording includes any copy that implies a real broker order, live-money settlement, broker account switching, cancel order, limit order entry or a separately authorized AI trading agent.

## 6. State contract

Each section must visibly cover existing states rather than hiding them behind generic empty UI.

### 模拟执行

- initial loading;
- dashboard read error;
- enabled;
- paused;
- running;
- no positions;
- positions present;
- no executed logs;
- executed logs present;
- execution-chain detail loading/error;
- decision-audit loading/error.

### 收益复盘

- loading/refreshing;
- empty;
- read error;
- pending market update;
- evaluated;
- evaluation request failure.

### 策略评估

- loading;
- empty;
- error;
- ready with core metrics;
- ready with benchmark/breakdown facts where present.

## 7. Screenshot acceptance

Repository screenshot regression remains mandatory, but hash equality alone is not sufficient for the visual review.

At minimum, add/review normal-phone-scale renders for:

- Strategy workspace with `模拟执行` selected;
- Strategy workspace with `收益复盘` selected;
- Strategy workspace with `策略评估` selected;
- simulated execution paused state;
- simulated execution running state;
- review empty/error state where deterministic fixtures exist;
- Strategy Lab ready/empty/error state where deterministic fixtures exist.

The approved hashes must be written to the existing screenshot manifest only after the renders are visually reviewed.

## 8. Documentation and authority requirements for the code PR

Any Android product commit implementing this contract must update `docs/ThirdHand_v3_Roadmap_and_Ledger.md` in the same commit to satisfy repository documentation governance.

Architecture documentation changes are not required for a presentation-only implementation. If a code change alters decision ownership, review policy, sizing, execution precheck, paper-broker semantics, scheduler authority, or introduces a new backend read/write contract, stop and scope that change separately before implementation.

## 9. Acceptance boundary

The code slice is repository-accepted when:

- the three existing Strategy capabilities are reachable from the Strategy primary destination;
- `模拟执行` remains the default section;
- current server/API facts and mutation behavior are unchanged;
- no wording implies real-broker execution or N5/#96 AI-agent authority;
- screenshot rendering and approved hashes pass;
- Debug and optimized Release APK verification pass;
- repository `ci-gate` passes.

`PRODUCT_DONE` still requires the physical-device walkthrough tracked in #133.