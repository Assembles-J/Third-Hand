# ThirdHand v3 Full-Stack Technical Roadmap

> Status: delivery design for the Strategy / AI Lab direction.
> This roadmap complements, but does not replace,
> `ThirdHand_v3_Roadmap_and_Ledger.md`. Accepted milestones must be promoted into
> the canonical ledger as they become implementation commitments.

## 0. Why this roadmap exists

ThirdHand already contains substantial backend capability. The next phase must
avoid a recurring failure mode: backend work is technically complete but the
user cannot see, understand, verify or operate it from Android.

From now on, a user-facing capability is not considered delivered merely because
its domain/service code exists.

### Full-stack Definition of Done

For any user-facing milestone, completion requires all applicable layers:

```text
Domain Contract
  -> Persistence / Migration
  -> Application Service
  -> API / DTO
  -> Android Repository
  -> ViewModel / State
  -> User-visible Screen
  -> Audit / Explanation
  -> Tests / Acceptance
```

A backend-only feature may be marked `BACKEND_READY`, but not `PRODUCT_DONE`.

Every roadmap item therefore records **Backend**, **API**, **Android**,
**Visibility**, and **Acceptance** deliverables.

## 1. Delivery status vocabulary

Use one of these states:

- `DESIGN` — contract agreed, no runtime claim.
- `BACKEND_READY` — backend implemented/tested, not necessarily visible.
- `API_READY` — stable read/write contract available.
- `ANDROID_READY` — app consumes and renders the capability.
- `OBSERVABLE` — user can inspect reasons, quality and runtime state.
- `ACCEPTED` — end-to-end acceptance passed.
- `PRODUCT_DONE` — accepted and visible in the intended UX.

Do not label a feature complete if the only evidence is a backend unit test.

## 2. Cross-cutting frontend/back-end contract

Every new user-visible capability must define:

```text
backend owner
API endpoint / DTO
Android owner screen
loading state
missing state
stale state
conflicted state
blocked state
error state
source / as-of visibility
reason codes
version fields
```

No Android screen may infer authority from presentation text. It consumes typed
states and reason codes from the backend.

## 3. Phase 0 — Close current correctness gaps

### Goal

Trust the existing platform before using it to score AI strategies.

### Backend

- complete Issue #46 deployed paper-execution acceptance;
- complete financial currentness production acceptance (#39);
- complete CorporateEvent lifecycle production acceptance (#49);
- complete Decision AI real-provider recovery acceptance (#40);
- merge/fix current event-driven financial-refresh wiring;
- synchronize merged 60m/15m/5m multi-timeframe policy status into canonical docs.

### API

Ensure paper account/status APIs expose:

- sellable quantity;
- locked quantity;
- next eligible sell time;
- execution disposition / reason;
- active deferral;
- observed quote time;
- market-session status;
- persisted runtime status source.

### Android

Paper/position UI must visibly distinguish:

```text
可卖
T+1 锁定
下次可卖时间
等待复核
行情过期
休市不可执行
模拟交易已关闭
```

No generic "失败" label for deterministic safety blocks.

### Visibility acceptance

A same-day BUY followed by an EXIT intent should be understandable from the app
without reading server logs: the user sees the locked lot, T+1 reason and next
eligible review time.

### Exit criteria

`PRODUCT_DONE` only after deployed-container acceptance plus Android rendering of
all critical execution states.

## 4. Phase 1 — StrategyProfile and SWING_V1

### Goal

Make "what strategy is this decision using?" explicit everywhere.

### Backend

Create target modules:

```text
domain/strategy/
application/strategy/
```

Implement:

- `StrategyProfile`;
- `SWING_V1`;
- `EvidenceAuthorityMatrix`;
- `TimeframeAuthorityPolicy` integration;
- `UniversePolicy` reference;
- `RiskPolicy` reference;
- strategy version in DecisionContext / DecisionPackage / audit.

Do not rewrite the existing Decision Engine. Wrap/version existing semantics.

### API

Decision responses expose:

```text
strategy_id
strategy_version
holding_horizon
strategic_timeframes
setup_timeframes
timing_timeframes
timeframe_authority
policy_versions
```

### Android

Stock detail gains a compact **策略** section:

```text
SWING_V1
预计周期：3-20 个交易日
周线/日线：战略结构
60m：Setup
15m/5m：Timing
```

The current decision card shows which strategy generated it.

### Visibility acceptance

The user can answer from one screen:

> 我现在看到的 BUY/HOLD 到底是什么策略下的判断？

### Exit criteria

Strategy identity is persisted, available by API, shown in stock detail and
included in decision history.

## 5. Phase 2 — Decision Workspace

### Goal

Turn stock detail into the central explanation surface instead of hiding backend
capability in logs/admin endpoints.

### Backend

Provide one read model aggregating already-authoritative states without creating
new decision authority:

```text
DecisionWorkspaceReadModel
  formal_decision
  strategy
  what_changed
  timeframe_authority
  fundamentals
  financial_currentness
  corporate_events
  market_regime
  risk
  position_sellability
  research_summary
  data_quality
```

### API

Prefer one stable read endpoint (or one facade over existing endpoints) so
Android does not reconstruct decision semantics from many unrelated calls.

Suggested:

```text
GET /v1/decisions/{symbol}/workspace
```

### Android

Refactor stock detail into sections:

1. Formal Decision;
2. What Changed;
3. Strategy;
4. Weekly/Daily/60m/15m/5m;
5. Company / Financial / Events;
6. Timing;
7. Risk / Position / T+1;
8. AI Research;
9. Decision History.

### Visibility acceptance

Any formal action must have a visible reason path and visible data-quality state.
The user should not need Admin Dashboard to understand a normal stock decision.

## 6. Phase 3 — Evaluation infrastructure before AI trading

### Goal

Build the scoreboard before creating players.

### Backend

Add target modules:

```text
domain/experiment/
domain/evaluation/
application/experiment/
application/evaluation/
```

Implement:

- `ExperimentDefinition`;
- experiment versioning;
- isolated experiment accounts;
- `OutcomePolicy`;
- `StrategyEvaluation`;
- benchmark definitions;
- confidence buckets;
- Brier score / calibration metrics;
- sample-quality status;
- regime/action/horizon breakdown.

### API

Read APIs:

```text
GET /v1/lab/experiments
GET /v1/lab/experiments/{id}
GET /v1/lab/experiments/{id}/performance
GET /v1/lab/experiments/{id}/calibration
GET /v1/lab/compare?ids=...
```

### Android

Add a minimal **实验** tab before AI auto-paper execution exists.

It may initially show Formal SWING_V1 evaluation and benchmark only. This proves
the UI/data contract before adding AI complexity.

### Visibility acceptance

The app can already answer:

> SWING_V1 最近表现怎么样？样本多少？最大回撤多少？比基准好吗？

## 7. Phase 4 — AI Strategy Lab shadow mode

### Goal

Let AI make paper intents without fills first.

### Backend

Implement:

- `AiStrategyAgent` contract;
- immutable agent/model/prompt versions;
- forecast contract;
- probability output;
- schema/semantic validation;
- evidence hash binding;
- shadow decision persistence;
- run-cost/latency audit.

AI consumes the same frozen EvidenceSnapshot as the comparable formal strategy.
No hidden remote research path is allowed.

### API

Expose:

```text
agent_id
agent_version
paper_intent
forecast_contract
probability
reason_summary
evidence_snapshot_id
validation_status
```

### Android

Stock Decision Workspace gains an **AI 实验观点** card clearly marked:

```text
实验，不影响正式决策
AI-SWING-01: BUY
目标事件: 10日内先 +6% 后 -3%
预测概率: 72%
```

### Visibility acceptance

Formal and AI opinions can disagree and are shown side by side without being
merged:

```text
Formal: WAIT
AI Lab: BUY
```

## 8. Phase 5 — AI isolated paper trading

### Goal

Allow validated shadow agents to manage isolated paper accounts.

### Backend

- one paper account/ledger per experiment;
- AI intent -> deterministic RiskPolicy -> deterministic SizingPolicy -> Paper Broker;
- no direct AI ledger writes;
- identical execution assumptions for comparison experiments;
- experiment-level kill switch;
- portfolio-level drawdown guard;
- all fills linked to frozen AI decision and evidence.

### API

Expose per-agent:

```text
cash
positions
equity
PnL
max_drawdown
fills
fees
active_risk
last_decision
```

### Android

Lab detail page shows:

- current paper account;
- active positions;
- latest AI decisions;
- equity/performance;
- drawdown;
- comparison to Formal SWING_V1 and market benchmark.

### Visibility acceptance

The user can inspect exactly why an AI account gained/lost money and whether the
trade was an AI decision failure, risk block, or execution effect.

## 9. Phase 6 — Calibration and reliability UX

### Goal

Answer "这个 AI 到底有多可靠？" without fake precision.

### Backend

Compute versioned:

- confidence buckets;
- realized event rate;
- sample count;
- confidence interval;
- Brier score;
- Expected Calibration Error;
- regime calibration;
- action calibration.

### API

Return structured reliability rather than a single percentage:

```text
sample_count
sample_quality
historical_event_rate
confidence_interval
brier_score
ece
bucket_breakdown
regime_breakdown
```

### Android

Reliability card examples:

```text
70-80% 预测区间
实际事件率 73%
n = 126
95% 区间 65-80%
```

For small samples:

```text
样本不足，暂不判断可靠率
```

### Visibility acceptance

No naked "AI 可靠率 82%" appears anywhere in the product.

## 10. Phase 7 — Home and Review surfaces

### Goal

Make daily use lazy-friendly: the user should not need to inspect every stock.

### Backend

Create summary read models:

```text
DailyAttentionSummary
ReviewSummary
```

Aggregate only existing authoritative/audit facts.

### API

Suggested:

```text
GET /v1/home/summary
GET /v1/review/summary
```

### Android Home

Show only high-value attention items:

- market regime;
- holdings with material decision changes;
- reviews due;
- major CorporateEvents;
- blocked/stale data warnings;
- AI Lab actions worth inspection.

### Android Review

Show:

- good/bad entry;
- good/bad exit;
- missed opportunity;
- overconfidence/underconfidence;
- regime failure;
- data failure;
- execution failure;
- Formal vs AI disagreement outcomes.

### Visibility acceptance

A user can open ThirdHand once per day and understand what changed without
reading logs or manually comparing historical reports.

## 11. Phase 8 — Order flow as observable evidence

### Goal

Implement the existing active-buying/order-flow design without prematurely
changing strategy authority.

### Backend

Implement read-only `OrderFlowSnapshot`, provenance, freshness, contradiction
state and deterministic score.

### API

```text
GET /v1/market/order-flow/{symbol}
```

### Android

Decision Workspace gains a Timing card:

```text
资金承接
主动买卖
VWAP/价格响应
新鲜度
矛盾提示
```

### Evaluation

Record order-flow state beside decisions, then test whether it improves timing
outcomes.

### Promotion rule

Only a separately versioned future strategy (for example SWING_V2) may grant it
formal timing authority after evaluation.

## 12. Phase 9 — Engineering modularization

This work is continuous, but should be delivered behind product milestones so
refactoring does not make user progress invisible.

### Backend migration target

```text
api/v1/
application/
domain/
infrastructure/
bootstrap/
```

New Strategy/Experiment/Evaluation work starts in target modules. Existing
root-level modules are migrated opportunistically with regression tests; no big-bang
rewrite.

### Android migration target

```text
core/
  network/
  model/
  navigation/
  ui/
feature/
  home/
  watchlist/
  stock/
  portfolio/
  lab/
  review/
  settings/
```

Split the current large `MainActivity.kt` and `ApiClient.kt` incrementally as
features are touched. Do not block product delivery on a complete rewrite.

## 13. Required milestone matrix

Every future roadmap PR should include a table like this:

| Milestone | Backend | API | Android | Observable | Accepted |
| --- | --- | --- | --- | --- | --- |
| StrategyProfile | yes/no | yes/no | yes/no | yes/no | yes/no |
| Decision Workspace | yes/no | yes/no | yes/no | yes/no | yes/no |
| Evaluation | yes/no | yes/no | yes/no | yes/no | yes/no |
| AI Shadow | yes/no | yes/no | yes/no | yes/no | yes/no |
| AI Paper | yes/no | yes/no | yes/no | yes/no | yes/no |
| Calibration | yes/no | yes/no | yes/no | yes/no | yes/no |
| Order Flow | yes/no | yes/no | yes/no | yes/no | yes/no |

This matrix is the anti-"backend finished but invisible" control.

## 14. PR Definition of Done

For a user-visible capability, the PR (or linked PR series) must state:

1. domain/authority change;
2. backend owner;
3. API/DTO change;
4. Android surface;
5. loading/missing/stale/conflicted states;
6. audit/reason-code visibility;
7. tests;
8. deployed or device acceptance evidence.

If Android intentionally comes later, the backend PR must explicitly say:

```text
Delivery status: BACKEND_READY, not PRODUCT_DONE
Follow-up Android milestone: <issue/PR>
```

## 15. Recommended implementation sequence

```text
P0 current correctness closure
        ↓
P1 StrategyProfile + SWING_V1 identity
        ↓
P2 Decision Workspace
        ↓
P3 Evaluation infrastructure
        ↓
P4 AI Lab shadow
        ↓
P5 AI isolated paper trading
        ↓
P6 Calibration / reliability UX
        ↓
P7 Home + Review daily workflow
        ↓
P8 Order-flow read-only evidence
        ↓
P9 evidence-based SWING_V2 decision
```

Do not start SHORT/INTRADAY strategy expansion until this loop has been proven
end to end.

## 16. Final delivery principle

ThirdHand should never again treat hidden backend capability as sufficient
product progress.

A capability becomes real product value only when:

```text
The system can compute it
+ the API can expose it
+ Android can show it
+ the user can understand why
+ the result can be evaluated later
```
