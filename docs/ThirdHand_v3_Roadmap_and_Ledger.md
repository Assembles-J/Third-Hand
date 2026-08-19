# ThirdHand v3 Redesign Ledger and Roadmap

> **Canonical status (2026-08-19):** This is the active implementation ledger.
> `ThirdHand_Architecture_v3_consolidated.md` is the paired authority contract.
> `ThirdHand_v3_Strategy_AI_Lab_Design.md` and
> `ThirdHand_v3_Fullstack_Technical_Roadmap.md` are approved subordinate design
> specifications; they do not override this ledger or the paired architecture.
>
> **Completed:** Phases 1-4 core repository implementation, DecisionContinuity,
> most Phase 5 ledger enforcement, and the governed weekly/daily/60m/15m/5m
> Evidence + asymmetric Multi-Timeframe ActionPolicy path.
>
> **Active correctness/runtime acceptance:**
> - Phase 5 paper-execution deployed acceptance (#46);
> - financial currentness / event-driven financial refresh deployed Xiaomi/HK
>   acceptance (#39, including the current bootstrap wiring follow-up);
> - Tier-1 CorporateEvent lifecycle deployed acceptance (#49);
> - configured-provider Decision AI live recovery acceptance (#40).
>
> **Next product/architecture track:** make Strategy first-class (`SWING_V1`),
> expose the Formal Decision System as an Android Decision Workspace, build the
> Evaluation foundation, then add an isolated AI Strategy Lab. Backend-only
> user-facing work is `BACKEND_READY`, not `PRODUCT_DONE`.
>
> The paper account is intentionally CNY-only: HK/US remain research/audit
> markets, not a deferred multi-currency execution project. No correctness gap
> is hidden behind a fallback or delegated to an LLM.

## Current implementation decision

The formal action path remains intentionally conservative:

```text
DecisionContext
  -> EvidenceEngine
  -> ActionPolicy
  -> Atomic Evidence / ResearchAssessment
  -> DecisionArbiter
  -> Multi-Timeframe ActionPolicy
  -> DecisionContinuity
  -> formal_action
  -> ExecutionPrecheck
```

Atomic Evidence and AI explanations are persisted and audited beside this path.
`ResearchAssessment` is an explicit, asymmetric arbiter input: high-confidence
ADVERSE research can veto only new BUY/ADD risk. It cannot upgrade an action or
create REDUCE/EXIT. Governed 60m/15m/5m state may preserve, delay or downgrade
new risk but cannot manufacture BUY/ADD or create REDUCE/EXIT by itself. AI
never receives authority over price/time, quality, market rules, sellable
quantity, hard gates, sizing or formal action.

The next explicit abstraction is `StrategyProfile`; it composes existing policy
without creating a second action engine.

## A. Consolidated ledger disposition

Legend:
- KEEP = required v3 design item.
- MERGE = valid concern, implemented inside another v3 component rather than a standalone subsystem.
- DEFER = useful but not current P0/P1 or insufficiently specified.
- CLOSE = benchmark/runtime observation; keep as evidence, not a permanent product component.

| Item | Disposition | Owner / decision |
|---|---|---|
| TH-DATA-001 quote vs daily time mismatch | KEEP | CanonicalInputSnapshot + consistency validation |
| TH-DATA-002 stale quote mixed with fresh indicators | KEEP | executable/display authority separation |
| TH-DATA-003 mismatch must be formal evidence | MERGE | Evidence conflicts + quality snapshot |
| TH-DATA-005 old quote vs canonical close | MERGE | same as TH-DATA-001 |
| TH-EVENT-001 corporate event not first-class | KEEP | CorporateEventAdapter |
| TH-EVENT-003 pre-event new-risk gate | KEEP | EventRiskPolicy + DecisionArbiter |
| TH-HK-001 HK metadata missing | KEEP | MarketAdapter/InstrumentMetadata |
| TH-HK-002 HK regime contaminated by CN regime | KEEP | market-specific regime adapter |
| TH-MARKET-002 HK context provider failure | KEEP | provider redundancy + quality, not Yahoo-specific logic |
| TH-FX-001 account/instrument currency mismatch | MERGE | single-CNY execution precheck; foreign-currency quotes are research/audit-only |
| generic backtest/Stock Connect fee formula | CLOSE | removed; actual broker receipts are audit facts, never fee-policy defaults |
| TH-EXPECT-002 consensus/valuation missing | KEEP optional | Expectation Evidence; optional by default |
| TH-RESEARCH-001 Xiaomi research DB empty | CLOSE | data-coverage incident represented by deterministic availability |
| TH-RESEARCH-002 research bias mixed with action | KEEP | ResearchAssessment vs DecisionArbiter |
| TH-AI-001 only one WATCH candidate | CLOSE | not current formal GitHub architecture |
| TH-AI-002 Pro schema violation | MERGE | AIOutputValidator / provider protocol |
| TH-AI-003 missing-evidence detection weak | CLOSE as AI duty | deterministic availability owns truth |
| TH-AI-004 reasoning consumes output budget | MERGE | ModelRuntimePolicy |
| TH-AI-005 thinking/JSON empty content | MERGE | provider protocol/retry |
| TH-AI-006 schema-valid semantic contradiction | KEEP | SemanticInvariantValidator |
| TH-AI-007 UNKNOWN vs NONE drift | KEEP | deterministic event/availability semantics |
| TH-AI-008 event present but model says missing | MERGE | semantic invariant |
| TH-AI-009 event changes technical label | MERGE | domain-isolated Atomic Evidence |
| TH-AI-014 Flash High 50% long-context success | CLOSE as architecture rule | benchmark evidence only |
| TH-AI-015 Pro High stable in T3b | CLOSE as permanent default | model routing remains benchmarked/versioned |
| TH-AI-016 missing-data list varies | KEEP | deterministic availability |
| TH-RUNTIME-001 empty-content retry | KEEP | ModelRuntimePolicy; live provider acceptance remains open under #40 |
| TH-RUNTIME-002 truncation escalation | KEEP | ModelRuntimePolicy |
| TH-RUNTIME-003 pre-route by Evidence complexity | KEEP | ModelPolicy |
| TH-RUNTIME-004 evaluate whole retry pipeline | KEEP | audit/benchmark metrics |
| TH-RUNTIME-005 atomic context cuts latency/tokens | KEEP | AtomicContextBuilder |
| TH-RUNTIME-006 atomic context restored primary success | KEEP as evidence | supports compact context; not an SLA |
| TH-MODEL-001 complex event/conflict escalation | KEEP | ModelPolicy |
| TH-MODEL-002 model difference mostly confidence | MERGE | confidence split + deterministic aggregation |
| TH-MODEL-003 stronger model cannot fix undefined policy | KEEP principle | formal aggregation deterministic |
| TH-TECH-001 coarse trend label | KEEP P1 | TechnicalSnapshot decomposition |
| TH-TECH-002 event contamination of technical state | MERGE | domain isolation |
| technical anchor lifecycle/rebase | DEFER | strategy-specific; define only inside an explicit StrategyProfile |
| multi-timeframe authority | KEEP / IMPLEMENTED | governed 60m/15m/5m Evidence plus versioned asymmetric Multi-Timeframe ActionPolicy merged; lower timeframes delay/downgrade new risk only |
| TH-RISK-001/002 stale risk snapshot | MERGE | quality/freshness; no duplicate risk-quality subsystem |
| TH-TEST-001 stability ignored failed-run coverage | KEEP | benchmark harness coverage + stability |
| TH-BENCH-002 frozen/hash/action exclusion | KEEP | existing DecisionPackage hashing is the base |
| TH-BENCH-003 semantic/aggregation stability metrics | KEEP | Evaluation System foundation |
| TH-METHOD-001 event neutral before disclosure | KEEP | EventRiskPolicy |
| TH-EVIDENCE-003 availability deterministic | KEEP | EvidenceSnapshot.availability |
| TH-EVIDENCE-004 source mixes positive/negative facts | KEEP | AtomicFactRecord |
| TH-EVIDENCE-005 polarity at fact level | KEEP | fact-level polarity |
| TH-EVIDENCE-006 provenance vs semantics | KEEP | Source Evidence -> Atomic Fact |
| TH-EVIDENCE-007 atomic evidence formalization | KEEP | core v3 |
| TH-EVIDENCE-008 materiality/comparison adequacy | KEEP | AtomicFactRecord |
| TH-FUND-001 one fundamental state too coarse | KEEP | FundamentalVector |
| TH-FUND-002 mixed presence vs net direction | KEEP | dimensions + aggregate bias |
| TH-FUND-003 dimension aggregation not LLM-owned | KEEP | deterministic DimensionAggregator |
| TH-FUND-004 materiality/importance | KEEP | fact + policy |
| TH-AGG-001 dimension aggregation drift | KEEP | deterministic aggregation |
| TH-AGG-002 aggregate fundamental drift | KEEP | deterministic aggregation |
| TH-AGG-003 research bias drift | KEEP | deterministic ResearchAggregator |
| TH-CONF-001 conviction drift | KEEP | formal confidence layers remain distinct from AI probability calibration |
| EntryDecision vs PositionDecision | KEEP | core semantics |
| Position state machine | KEEP | decision phase |
| PositionLot/T+1/sellable qty | KEEP | MarketAdapter + execution |
| TH-EXEC-20260818 T+1 observed after morning buys | KEEP P1 | PositionLot ledger enforcement passed deployed-container verification; deployed full acceptance remains #46 |
| TH-EXEC-20260818 repeated T+1 retry logs | KEEP P1 | A T+1 deferral is one scheduled state, not a zero-quantity SELL attempt or a new skip row every review interval |
| TH-EXEC-20260818 after-session paper fill | KEEP P1 | require instrument calendar/session plus an in-session fresh observed quote before every paper fill |
| TH-OPS-20260818 volatile paper runtime status | KEEP P2 | rebuild API status from persisted simulation runs after restart |
| TH-DOC-20260818 paper-vs-real boundary | KEEP P2 | README/UI/deployment comments distinguish no real broker order from optional simulated paper-ledger fills |
| DecisionMemory/MaterialChange/cooldown | KEEP / IMPLEMENTED | continuity phase |
| FeedbackEvent | KEEP / IMPLEMENTED BASE | audit dataset complete; explicit Strategy Evaluation remains next-stage work |
| A/HK/US MarketAdapter | KEEP | platform boundary |
| legacy DecisionSnapshot/calibration/impact graph | CLOSE | removed as alternate authority; new AI calibration belongs only to isolated Evaluation over frozen experiments |
| separate EvidenceAvailabilitySnapshot service | MERGE | keep inside EvidenceSnapshot/quality snapshot |
| StrategyProfile | KEEP NEXT | first-class strategy composition; first production profile `SWING_V1` |
| AI Strategy Lab | KEEP NEXT | isolated paper-intent experiment plane; never a production arbiter |
| ExperimentDefinition / StrategyEvaluation | KEEP NEXT | immutable versioned experiments, benchmarks, calibration and uncertainty |
| full-stack product observability | KEEP NEXT | Backend -> API -> Android -> observable reasons/errors required before `PRODUCT_DONE` |

## B. Current-code conformance findings

1. The former held `NO_TRADE -> REDUCE` behavior is removed from formal semantics; held WATCH resolves to HOLD.
2. Market regime, lot and settlement selection are market-scoped. The formal paper account is CNY-only. HK Stock Connect instruments retain HKD trading-price metadata and broker receipts retain the actual RMB settlement/fee facts, but neither creates an FX quote cache, currency balance, fee formula, nor an execution path. CN remains executable; HK/US are intentionally research/audit-only.
3. Atomic Evidence and ResearchAssessment are deterministic and persisted. The DecisionArbiter consumes only high-confidence ADVERSE research as a new-risk veto; it never lets research upgrade an action or produce REDUCE/EXIT. Completed weekly/daily plus governed 60m/15m/5m state now feed a versioned asymmetric Multi-Timeframe ActionPolicy before DecisionContinuity. Raw intraday timestamp/hash noise is excluded from the continuity material fingerprint.
4. Model policy/audit is repository-complete for the configured provider's bounded recovery graph, while the live provider black-box acceptance remains open under #40. A generic provider-capability registry remains out of scope.
5. Feedback is immutable audit data and has no policy/sizing/model-routing write path. Strategy Evaluation and AI calibration will consume this foundation but also have no automatic production write path.
6. Repository quality, time and freeze invariants remain the migration anchors.
7. Production verification on 2026-08-18 confirmed that the deployed ledger correctly blocks same-day CN sells, but Phase 5 is not closed until the #46 deployed acceptance matrix confirms no impossible order leaks through decision/sizing/scheduler/session/UI behavior.
8. `DECISION_SHADOW_MODE` controls research/decision shadow output; it is not a switch for the simulated ledger. Automatic paper fills are governed by the persisted paper-trading setting and every execution entry point must honor the paper-execution safety contract.
9. Report-period currentness and official CorporateEvent lifecycle reconciliation are implemented in repository code, but deployed Xiaomi/HK acceptance remains active. The newest runtime follow-up is wiring event-driven financial refresh to the authoritative v2 Company Intelligence bootstrap.
10. The Android app contains substantial existing screens, but user-visible delivery is not yet organized around a single Decision Workspace / Lab / Review product model. The next phase treats visibility as a first-class acceptance dimension rather than a post-backend polish step.

Therefore v3 remains an evolution of the present architecture, not a rewrite.

## C. Historical v3 target requirements and acceptance criteria

The following phase descriptions remain the historical/core v3 contract. Status
at the start of this file overrides their tense: an item remains active until
its stated acceptance criteria and any explicitly required deployed acceptance
are met.

### Phase 0 — Architecture/documentation lock
Deliverables:
- consolidated v3 architecture
- ledger disposition
- formal call-chain map
- migration/compatibility rules

Acceptance:
- no duplicate quality system
- no alternate freeze path
- all new components have a clear authority owner

### Phase 1 — Data correctness and market identity — repository complete
Goal: make every formal calculation use coherent market-specific inputs before changing strategy semantics.

Implement:
- InstrumentMetadata / market identity
- CanonicalInputSnapshot
- explicit execution quote vs display close
- CrossSourceConsistency checks
- CorporateEventAdapter
- market-specific benchmark/regime selection
- stale risk quarantine through existing quality machinery

Acceptance:
- stale quote cannot be mixed with newer technical bars as if same-time
- event date is first-class Evidence
- HK symbols no longer use CSI300 regime
- market metadata is explicit
- current A-share golden output is unchanged

### Phase 2 — Atomic Evidence foundation — complete
Implement:
- AtomicFactRecord
- FactExtractor
- compact EvidenceSnapshot
- deterministic availability/conflict list
- fact-level provenance/materiality/comparison adequacy

Build after ActionPolicy candidates freeze. The raw snapshot does not directly
change action, sizing or execution; later deterministic aggregation may only
exercise the explicitly bounded research authority defined in this document.

Acceptance:
- one source can produce multiple facts with different polarity
- every fact has provenance
- atomic snapshot hashes deterministically
- same input creates same facts

### Phase 3 — Deterministic research aggregation — complete
Implement:
- DimensionAggregationPolicy
- FundamentalAggregationPolicy
- ResearchAggregationPolicy
- evidence/research/decision confidence split
- SemanticInvariantValidator

Acceptance:
- same EvidenceSnapshot + policy versions => identical formal ResearchAssessment
- rerunning a model cannot change formal aggregate research bias
- benchmark-only Xiaomi weights are not production defaults

### Phase 4 — Decision semantics and state machine — repository complete
Implement:
- EntryDecision and PositionDecision types
- remove `NO_TRADE -> REDUCE`
- position states
- EventRiskGate
- DecisionArbiter
- governed multi-timeframe authority

Acceptance:
- negative research bias can produce WAIT
- held-position actions use HOLD/ADD/REDUCE/EXIT only
- entry actions use BUY/WAIT/BLOCKED only
- every hard gate has reason codes
- high-confidence ADVERSE research may downgrade BUY to WAIT or ADD to HOLD, but cannot create or upgrade any action
- 60m/15m/5m may only preserve/delay/downgrade already permitted new risk
- lower-timeframe state cannot manufacture BUY/ADD or create REDUCE/EXIT
- higher-timeframe structural conflict cannot be overridden by bullish intraday state
- DecisionContinuity material fingerprint records discrete approved timeframe states but excludes raw timing/hash noise

### Phase 5 — Market/execution adapters — active deployed acceptance
Implement:
- CN_A/HK/US market adapter interface
- lot/tick/fees/currency/settlement
- PositionLot and sellable quantity
- single-CNY paper-execution boundary
- execution precheck before sizing
- T+1 deferral state, calendar/session/freshness gate, and persisted runtime status

Acceptance:
- no global 100-share rule
- no global A-share T+1 rule
- HK/US rules are selected by instrument market
- a foreign-currency quote can never create a paper-execution conversion path
- Stock Connect broker receipts preserve the actual RMB settlement and fee as audit evidence only; no general FX ledger or broker-fee formula is inferred
- `REDUCE`/`EXIT` can never size or submit more than `sellable_quantity`; a same-day lot produces one explainable T+1 deferral with its next eligible sell time, not repeated skipped SELL attempts
- manual or scheduler execution outside the instrument's open session, on a non-trading day, or with stale/out-of-session quotes cannot write a paper fill
- account/API exposes sellable and locked quantity plus read-only lot evidence, and status survives a process restart by reading persisted runs
- deployed-container isolated-SQLite acceptance matrix in #46 passes before Phase 5 is marked complete

### Phase 6 — Decision continuity — complete
Implement:
- DecisionMemory
- entry-bound position episode id and frozen entry snapshot
- material-change detector
- cooldown/review-after
- prior decision reference

Acceptance:
- changed recommendation states what changed
- repeated analyses cannot flip without material change unless a hard gate changed
- an unchanged EvidenceSnapshot that permitted `BUY` when FLAT cannot produce `REDUCE`/`EXIT` solely because the resulting position is now HOLDING
- a full `input_hash` difference is retained for audit, while only a versioned strategic material fingerprint can permit an action flip
- execution rejects a fill before `cooldown_until`
- due `review_after` produces a separately auditable decision-refresh obligation, never an implied trade
- first paper BUY persists decision/evidence/research/state/price provenance; ADD cannot overwrite it and full EXIT closes the episode

### Phase 7 — Model policy and audit — repository complete, live acceptance active
Implement:
- compact atomic research prompt
- configured-provider ModelPolicy
- default vs reasoning escalation plus one bounded structured recovery
- schema + semantic validation
- observable runtime audit

Acceptance:
- every model run auditable by hashes/settings/usage
- invalid output never mutates formal decision
- finite recovery transitions are recorded
- provider-specific maximum-reasoning tiers remain out of scope until a stable tested capability contract exists
- live configured-provider black-box under #40 confirms the persisted compound attempt lineage and bounded fail-closed behavior

### Phase 8 — Feedback — audit foundation complete
Implement:
- FeedbackEvent
- execution/outcome link
- hypothetical-vs-actual review
- policy-version evaluation dataset

Acceptance:
- feedback points to an exact frozen decision/package
- no automatic tuning in first production release

## D. Current correctness closure gate — P0 before new product breadth

Do not treat the next-stage Strategy/AI Lab as permission to bypass open runtime
acceptance. Close or explicitly re-scope these first:

1. **#46 Paper execution safety** — deployed isolated-SQLite acceptance for T+1,
   mixed inventory, fresh later quote, closed/stale session blocks and restart
   recovery.
2. **#39 Financial currentness** — deployed Xiaomi/HK confirms old financials
   remain historical while the newly released report is refreshed/current only
   through bounded official-release-aware acquisition.
3. **#49 CorporateEvent lifecycle** — deployed Tier-1 HKEX ingestion + verified
   financial snapshot closes RELEASED_UNVERIFIED -> VERIFIED without regression.
4. **#40 Decision AI runtime** — live provider acceptance confirms bounded
   recovery/audit while formal action remains deterministic and fail-closed.
5. **Canonical documentation sync** — code, Architecture and this ledger agree on
   the already merged Multi-Timeframe ActionPolicy.

These are correctness/reliability gates, not reasons to freeze unrelated UI
read-model work. User-visible work may proceed when it does not weaken or hide
these gates.

## E. Next-stage product and technical roadmap

The detailed dependency/endpoint/Android mapping lives in
`ThirdHand_v3_Fullstack_Technical_Roadmap.md`. This section is the canonical
status sequence.

### N1 — StrategyProfile + SWING_V1

Backend/domain:
- add `domain/strategy` and immutable `StrategyProfile` contract;
- define `SWING_V1` by composing current weekly/daily/60m/15m/5m authority;
- add `strategy_id` / `strategy_version` to frozen Decision lineage;
- preserve existing thresholds and current multi-timeframe semantics in the first migration.

API:
- expose Strategy identity/version and timeframe authority in decision detail;
- expose structured reason codes, not only prose.

Android:
- stock detail visibly shows `SWING_V1` and weekly/daily/60m/15m/5m roles;
- missing/stale/conflicted state must be visible, not collapsed into neutral.

Acceptance:
- same current frozen inputs produce the same formal action before/after wrapping them in `SWING_V1`;
- strategy version is persisted and visible end-to-end;
- Android can answer "which strategy produced this decision?".

### N2 — Decision Workspace vertical slice

Backend/API:
- provide one read model that joins Formal Decision, Strategy, What Changed,
  financial/event state, timeframe authority and paper-risk state without
  introducing new authority.

Android:
- refactor stock detail incrementally into an action-first Decision Workspace;
- show Formal Action, invalidation/review reason, strategy/timeframe state,
  company/event state, sellable/locked/T+1, AI Research and Decision Memory;
- implement loading, partial error, stale and blocked states.

Acceptance:
- a user does not need admin/log screens to understand why the current formal
  action exists or why it cannot execute;
- backend-only completion is not enough; this milestone ends at `PRODUCT_DONE`.

### N3 — Evaluation Infrastructure

Backend/domain:
- add `ExperimentDefinition`, `OutcomePolicy`, `StrategyEvaluation`, benchmark
  definitions and point-in-time lineage;
- compute performance with fees/slippage and separate economic vs forecast outcomes.

API:
- experiment list/detail;
- evaluation summary;
- benchmark comparison;
- sample-quality/calibration summary.

Android:
- Lab shell renders real experiment/evaluation data even before AI autonomous paper fills are enabled.

Acceptance:
- evaluation can score Formal SWING_V1 against a benchmark without any AI agent;
- every metric resolves to an immutable experiment/policy version.

### N4 — AI Strategy Lab Shadow

Backend:
- define Trader AI output schema with paper intent plus testable ForecastContract;
- consume the same frozen EvidenceSnapshot used by the comparable formal decision;
- persist model/prompt/evidence/strategy/risk/sizing versions;
- no AI paper fill yet.

API/Android:
- show AI shadow opinion beside Formal Decision with explicit `LAB` status;
- show disagreements and confidence event definition;
- never label an uncalibrated probability as historical reliability.

Acceptance:
- AI failure cannot alter Formal Action;
- every AI percentage has an outcome contract;
- shadow records are replayable/auditable.

### N5 — Isolated AI Paper Trading

Backend:
- one experiment account/ledger per AI agent/version;
- AI owns directional intent only by default;
- deterministic RiskPolicy/SizingPolicy/ExecutionPrecheck/Paper Broker own risk and fill;
- experiment agent cannot write ledger directly.

API/Android:
- Lab shows account equity, cash, positions, fills, blocked/deferred intents and execution reasons.

Acceptance:
- two agents cannot share cash/positions;
- T+1/session/freshness rules match the authoritative Paper Broker contract;
- blocked or deferred AI intents remain visible and explainable.

### N6 — Calibration and reliability UX

Backend:
- confidence buckets, Brier score, calibration error, sample size, uncertainty interval, regime/action breakdown.

Android:
- display historical event rate + interval + `n`;
- show `INSUFFICIENT_SAMPLE` instead of fake precision;
- compare AI, Formal SWING_V1 and benchmark.

Acceptance:
- the UI never shows a naked "reliability X%";
- user can see where an agent is overconfident, underconfident or regime-fragile.

### N7 — Home + Review

Backend/API:
- material-change feed and review aggregates from existing immutable history;
- no new trading authority.

Android Home:
- show only actionable material changes: position decision changes, due reviews,
  major events, data failures and Formal-vs-AI disagreement.

Android Review:
- classify good/bad entries/exits, missed opportunities, over/under-confidence,
  regime failure, data failure and execution failure.

Acceptance:
- a low-effort user can open the app once and understand what changed and what needs review.

### N8 — Order Flow as evaluated timing evidence

Backend:
- implement read-only OrderFlowSnapshot/evidence first;
- persist freshness/provenance/degraded state;
- keep it out of formal action authority initially.

API/Android:
- stock detail shows active-buying/support evidence with source/freshness and contradiction state.

Evaluation:
- compare timing with and without OrderFlow under frozen SWING_V1 baseline.

Acceptance:
- only benchmark/forward evidence can justify a separately versioned timing-policy promotion;
- no order-flow score directly creates BUY/ADD/REDUCE/EXIT.

### N9 — Modularization tied to vertical slices

Backend:
- migrate new Strategy/Experiment/Evaluation code into domain/application/infrastructure modules;
- gradually move root-level legacy modules behind stable adapters.

Android:
- extract feature ViewModels/repositories/API services from `MainActivity.kt` and monolithic `ApiClient.kt` as each visible milestone lands;
- do not perform a big-bang rewrite.

Acceptance:
- each extraction is covered by compile/tests and preserves behavior;
- architecture cleanup must deliver or protect a user-visible vertical slice rather than becoming open-ended refactoring.

## F. Full-stack completion states

Every user-facing milestone uses these states:

```text
DESIGNED
  -> BACKEND_READY
  -> API_VISIBLE
  -> ANDROID_VISIBLE
  -> OBSERVABLE
  -> PRODUCT_DONE
```

Definitions:

- `BACKEND_READY`: authoritative domain/persistence/application behavior exists and is tested.
- `API_VISIBLE`: stable DTO/read model exposes the behavior with reason/freshness/degraded states.
- `ANDROID_VISIBLE`: real repository-backed UI renders it.
- `OBSERVABLE`: audit/reason/source/freshness/failure state is diagnosable without server log archaeology.
- `PRODUCT_DONE`: end-to-end acceptance passes, including loading/empty/error/stale/blocked paths where applicable.

A backend feature that the user cannot see is not `PRODUCT_DONE`. A UI mock that
is disconnected from real authoritative data is not `PRODUCT_DONE` either.

## G. Milestone visibility matrix

| Milestone | Backend truth | API surface | Android surface | User-visible proof |
| --- | --- | --- | --- | --- |
| P0 execution safety | PositionLot / ExecutionConstraint / deferral | paper account, lots, deferrals, status | Portfolio / Paper detail | sellable, locked, next eligible time, blocked/deferred reason |
| N1 SWING_V1 | StrategyProfile + version | decision strategy/timeframe fields | Stock detail | strategy name/version and timeframe authority |
| N2 Decision Workspace | decision read model | workspace/detail endpoint or composed stable DTO | Stock detail | action, why, what changed, risk/invalidation |
| N3 Evaluation | experiment/evaluation models | Lab summary/detail | Lab | benchmark, drawdown, expectancy, sample quality |
| N4 AI Shadow | immutable AI paper-intent record | AI shadow opinion | Stock detail + Lab | Formal vs AI and forecast contract |
| N5 AI Paper | isolated experiment ledger | AI account/positions/fills | Lab | AI equity/positions + execution reasons |
| N6 Calibration | calibration metrics | evaluation calibration DTO | Lab/Review | event rate + interval + sample count |
| N7 Home/Review | material-change/review aggregates | feed/review endpoints | Home + Review | what changed, what failed, what needs attention |
| N8 Order Flow | read-only OrderFlowSnapshot | order-flow endpoint | Stock detail timing card | support/active-buying evidence + freshness |

## H. Required PR governance

Any PR that changes `Authority`, `Strategy`, `Evidence`, `Decision`, `Risk`,
`Execution` or `Evaluation` must state:

- Authority Impact
- Strategy Impact
- API / Android Visibility Impact
- Backward Compatibility
- Evaluation Impact
- Acceptance Tests
- Delivery State (`BACKEND_READY`, `API_VISIBLE`, etc.)

A Strategy/Decision/Execution PR that changes the canonical contract must update
code, tests, Architecture and this Roadmap in the same accepted change.

## I. Required regression invariants

Preserve repository-fixed golden results until a later explicitly scoped strategy change:
- READY
- buy zone [10.4209, 10.5391]
- hard stop 9.7023
- final quantity 600
- trial quantity 100
- per-share risk 0.7777
- max loss 77.77

Also preserve:
- one formal plan per analysis
- unique account/symbol/version behavior
- quality blocking
- package hash reproducibility
- unified freeze
- provider lineage
- no automatic production tuning from Feedback or AI experiment performance
- no AI direct write to authoritative paper execution state

## J. Delivery update — 2026-08-19

- **N1 StrategyProfile / SWING_V1:** `PRODUCT_DONE` via #63. The immutable
  `SWING_V1` identity and policy-version lineage are serialized in DecisionReport
  and rendered in Android stock detail together with structured timeframe
  authority. Formal action semantics were unchanged and full backend + Android
  CI passed before merge.
- **P0 #46 paper-execution visibility:** backend/API sellability and deferral
  facts were already authoritative. The Android Trading surface now consumes
  `sellable_quantity`, `locked_quantity`, `next_eligible_sell_at`, runtime
  `state_source`, and active execution deferrals and renders explicit T+1/
  next-review reasons. This advances #46 to `ANDROID_VISIBLE / OBSERVABLE` for
  the user-facing slice; **Phase 5 remains open** until the deployed-container
  acceptance matrix in #46 passes. This UI slice does not change Paper Broker,
  ExecutionPrecheck, sizing, session, freshness or T+1 authority.
