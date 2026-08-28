# ThirdHand v3 Redesign Ledger and Roadmap

> **Canonical status (2026-08-25):** This is the active implementation ledger.
> `ThirdHand_Architecture_v3_consolidated.md` is the paired authority contract.
> `ThirdHand_v3_Strategy_AI_Lab_Design.md`,
> `ThirdHand_v3_Fullstack_Technical_Roadmap.md`, and
> `ThirdHand_v3_Personal_Universe_Review_Watchlist_UX_Design.md` are approved
> subordinate design specifications; they do not override this ledger or the
> paired architecture.
>
> **Completed:** Phases 1-4 core repository implementation, DecisionContinuity,
> most Phase 5 ledger enforcement, and the governed weekly/daily/60m/15m/5m
> Evidence + asymmetric Multi-Timeframe ActionPolicy path.
>
> **Active correctness/runtime acceptance:**
> - Phase 5 paper-execution deployed acceptance (#46);
> - financial currentness / event-driven financial refresh deployed Xiaomi/HK
>   acceptance (#39);
> - Tier-1 CorporateEvent lifecycle deployed acceptance (#49);
> - configured-provider Decision AI live recovery acceptance (#40).
>
> **Active product implementation track:** Personal Universe + Review Cadence +
> first-class Watchlist. PUX1 backend/API is `BACKEND_READY / API_VISIBLE` via
> #86; Android first-class Watchlist is implemented under #92 and awaits CI /
> device acceptance. PUX2 ReviewPolicy /
> AnalysisBudget is tracked by #93 and PUX3 bounded Discovery by #94. N3 is
> `PRODUCT_DONE`; N4 AI Strategy Lab Shadow is the next Evaluation/AI-Lab
> implementation milestone under #95.
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

Daily-use orchestration is now designed as a separate concern:

```text
PersonalUniversePolicy
  -> ReviewPolicy
  -> AnalysisDepthPolicy
  -> Formal Decision when review is authorized
```

This separates who deserves attention, when review is due, how deep research may
run and whether trading is permitted.

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
| StrategyProfile | KEEP / IMPLEMENTED | `SWING_V1` identity/version shipped end-to-end |
| AI Strategy Lab | KEEP NEXT / #95 | N4 isolated paper-intent/forecast experiment plane; never a production arbiter |
| ExperimentDefinition / StrategyEvaluation | KEEP / N3 PRODUCT_DONE | N3.1-N3.8 are accepted end to end for Formal `SWING_V1`: immutable experiment/universe lineage -> point-in-time outcomes -> strategy/benchmark evaluation -> GET-only Lab API -> Android Lab. Evaluation remains read-only and cannot rewrite Formal Action or production policy. |
| full-stack product observability | KEEP | Backend -> API -> Android -> observable reasons/errors required before `PRODUCT_DONE` |
| PersonalUniversePolicy | KEEP / ANDROID_VISIBLE / #92 | Portfolio + Watchlist remain primary daily universe; PUX1 backend/API accepted in #86 and Android first-class Watchlist awaits CI/device acceptance |
| ReviewPolicy / AnalysisBudget | KEEP / BACKEND_FOUNDATION / #93 | versioned deterministic modes + append-only ReviewPlan persistence implemented; scheduler/API/Android consumption pending |
| Discovery / Candidate demotion | KEEP / DESIGNED / #94 | bounded optional Discovery is research-only and requires explicit Watchlist promotion |
| Personal vs Experiment universe separation | KEEP / DESIGNED | mutable user Watchlist must never silently contaminate frozen Evaluation universe |
| first-class Android Watchlist | KEEP / ANDROID_VISIBLE / #92 | user can manage Watchlist and positions without admin/log access; ReviewPolicy state remains PUX2 |

## B. Current-code conformance findings

1. The former held `NO_TRADE -> REDUCE` behavior is removed from formal semantics; held WATCH resolves to HOLD.
2. Market regime, lot and settlement selection are market-scoped. The formal paper account is CNY-only. HK Stock Connect instruments retain HKD trading-price metadata and broker receipts retain the actual RMB settlement/fee facts, but neither creates an FX quote cache, currency balance, fee formula, nor an execution path. CN remains executable; HK/US are intentionally research/audit-only.
3. Atomic Evidence and ResearchAssessment are deterministic and persisted. The DecisionArbiter consumes only high-confidence ADVERSE research as a new-risk veto; it never lets research upgrade an action or produce REDUCE/EXIT. Completed weekly/daily plus governed 60m/15m/5m state now feed a versioned asymmetric Multi-Timeframe ActionPolicy before DecisionContinuity. Raw intraday timestamp/hash noise is excluded from the continuity material fingerprint.
4. Model policy/audit is repository-complete for the configured provider's bounded recovery graph, while the live provider black-box acceptance remains open under #40. A generic provider-capability registry remains out of scope.
5. Feedback is immutable audit data and has no policy/sizing/model-routing write path. Strategy Evaluation and AI calibration will consume this foundation but also have no automatic production write path.
6. Repository quality, time and freeze invariants remain the migration anchors.
7. Production verification on 2026-08-18 confirmed that the deployed ledger correctly blocks same-day CN sells, but Phase 5 is not closed until the #46 deployed acceptance matrix confirms no impossible order leaks through decision/sizing/scheduler/session/UI behavior.
8. `DECISION_SHADOW_MODE` controls research/decision shadow output; it is not a switch for the simulated ledger. Automatic paper fills are governed by the persisted paper-trading setting and every execution entry point must honor the paper-execution safety contract.
9. Report-period currentness and official CorporateEvent lifecycle reconciliation are implemented in repository code, but deployed Xiaomi/HK acceptance remains active.
10. Android Watchlist is now a first-class bottom-navigation destination backed by Personal Universe, with metadata edit, pause, screenshot coverage and stock-detail routing. CI and device acceptance remain required before `PRODUCT_DONE`.
11. Existing Candidate lifecycle/cooldown remains useful as Discovery research infrastructure; it must no longer be presented as an AI stock-picking authority.
12. Existing adaptive DISCOVERY/HOLDING_FOCUS/FULL_FOCUS scheduling already suppresses new discovery near full allocation, but it still conflates capital occupancy with research cadence. The new design separates universe membership, review permission and analysis depth.
13. PUX1 backend/API is accepted on main-base CI with typed Personal Universe contracts, additive Watchlist metadata migration, local-only composition and explicit v2 routes; the user-visible Android entry is implemented and awaits CI/device acceptance.

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

These are correctness/reliability gates, not reasons to freeze unrelated UI
read-model work. User-visible Personal Universe/Watchlist work may proceed when
it does not weaken or hide these gates.

## E. Next-stage product and technical roadmap

The detailed dependency/endpoint/Android mapping lives in
`ThirdHand_v3_Fullstack_Technical_Roadmap.md`. Personal Universe / Review Cadence
is additionally governed by
`ThirdHand_v3_Personal_Universe_Review_Watchlist_UX_Design.md`.

Execution Issue ownership is now explicit so implementation does not jump from a
design paragraph directly to an untracked PR:

```text
PUX1 Android / product acceptance   -> #92
PUX2 ReviewPolicy / AnalysisBudget  -> #93
PUX3 bounded Discovery              -> #94
N4 AI Strategy Lab Shadow           -> #95
N5 isolated AI Paper Trading        -> #96
N6 calibration / reliability        -> #97
N7 Home + Review                    -> #98
N8 Order Flow evidence              -> #99
N9 incremental modularization       -> #100
```

The expected delivery chain is therefore:

```text
Canonical Architecture/Roadmap
  -> owning Issue
  -> implementation PR(s)
  -> CI / acceptance
  -> same-change canonical status sync
```

### PUX1 — Personal Universe + first-class Watchlist — ANDROID_VISIBLE / ACCEPTANCE_PENDING

Current delivery state: `BACKEND_READY / API_VISIBLE` via #86 and
`ANDROID_VISIBLE` via #92. The Android surface has local JVM, screenshot,
Debug and Release validation, but repository CI and physical-device acceptance
remain open; PUX1 is therefore not `PRODUCT_DONE` yet.

Backend/domain:
- additive Watchlist metadata with priority/note/enabled on the existing table;
- typed Personal Universe membership for POSITION/WATCHLIST/both;
- always include all open positions;
- local-only composition from Portfolio + Watchlist and cached display data;
- no Decision/AI/remote-research invocation from the read model.

API:
- preserve existing GET/POST/DELETE `/v1/watchlist`;
- add `PUT /v1/watchlist/{symbol}` for attention metadata;
- add read-only `GET /v1/personal-universe`;
- defer Personal Universe Discovery/settings endpoints to PUX3 when runtime ownership exists.

Android:
- promote Watchlist to a first-class bottom-navigation destination;
- implement Watchlist/Positions sibling tabs;
- manage add/edit/delete/priority/note from the normal user surface;
- use dense scan-first list layout aligned with the project red-first market tokens.

Acceptance:
- no admin/log screen is required to manage Watchlist;
- positions cannot be dropped by a list limit;
- loading/empty/stale/error states are explicit;
- screenshot/preview states are locked;
- this slice cannot be called PRODUCT_DONE before the real Android path exists.

### PUX2 — ReviewPolicy + AnalysisBudget — DESIGNED (#93)

Backend/domain:
- modes: `NO_REVIEW`, `GUARD_ONLY`, `POSITION_REVIEW`, `FULL_RESEARCH`;
- persist per-symbol review reason, last/next review and routine analysis budget;
- scheduler wake-up does not imply full-analysis permission;
- a full/capped `SWING_V1` position without MaterialChange remains GUARD_ONLY
  during the session;
- routine full research is at most once per symbol/trading day unless a material
  trigger or explicit user request supplies an audited override reason.

API/Android:
- expose ReviewPlan and whether full AI/company research actually ran;
- show skipped-analysis reasons so quiet behavior cannot be mistaken for failure.

Acceptance:
- full position + no material change causes zero routine intraday full-research calls;
- hard invalidation/event/risk/T+1 guards still run;
- material triggers deterministically upgrade the review mode;
- Android shows the reason and next review time.

#### Delivery update — 2026-08-26 — PUX2.1 governed review contracts

- Added policy version `PUX2_REVIEW_V1` with explicit `NO_REVIEW`,
  `GUARD_ONLY`, `POSITION_REVIEW` and `FULL_RESEARCH` modes and separately typed
  permitted analysis depth.
- Stable positions without MaterialChange remain `GUARD_ONLY`; a due position
  review does not automatically grant full company/AI research.
- Routine full research is limited to once per symbol per Beijing-local day.
  MaterialChange and explicit user request are the only first-slice audited
  budget overrides. Hard guard obligations remain active even when the routine
  full-research budget is exhausted.
- ReviewPlan decisions are append-only and content-addressed in the existing
  SQLite owner. They persist policy version, mode/depth, reason codes,
  last/next review, routine budget state and override state.
- Deterministic tests cover stable/due positions, routine budget exhaustion,
  material/user overrides, hard guards, timezone safety and persistence replay.
- **Delivery state:** `BACKEND_FOUNDATION / API_ANDROID_PENDING`. Scheduler
  consumption, explicit user-request lineage, API projection and Android reason
  visibility remain required before #93 can close. No Formal Action, Risk,
  sizing, ExecutionPrecheck or Paper Broker authority changes in this slice.

#### Delivery update — 2026-08-26 — PUX2.2 ReviewPlan visibility

- Personal Universe now projects the latest persisted ReviewPlan per symbol
  without recomputing policy or triggering remote research inside the read API.
- API fields include governed mode, permitted analysis depth, stable reason
  codes, last review and next review. Missing plans remain explicitly absent;
  the API does not fabricate a quiet-state reason.
- Android Watchlist translates the server-owned mode and primary reason into
  concise user-facing text, including the important distinction between
  `GUARD_ONLY`, due position review, full research and an intentionally skipped
  repeat full-research run. Android performs no review-authority calculation.
- Backend projection coverage and Android label tests protect this handoff.
- **Delivery state:** `API_ANDROID_VISIBLE / SCHEDULER_ACCEPTANCE_PENDING`.
  Scheduler consumption/persistence and physical-device review-state acceptance
  remain before #93 can close. Authority semantics remain those documented in
  PUX2.1 and the canonical Architecture.

### PUX3 — Discovery demotion and controls — DESIGNED (#94)

Backend/domain:
- reuse Candidate lifecycle as a research-only Discovery substrate;
- default `discovery_enabled=false`, `discovery_slots=2`, cadence every 3 trading sessions;
- allow zero slots as explicit pause;
- default Basic Screen performs no full DeepSeek Company Research;
- explicit user promotion is required before durable Watchlist membership.

API/Android:
- Discovery list + settings + manual run;
- user controls enable/disable, slots and cadence;
- each item supports Add to Watchlist / Ignore and explains only why it may merit research.

Acceptance:
- Discovery cannot silently become Formal BUY scope;
- Discovery can be fully disabled;
- default Discovery produces no full-model research call;
- promotion is explicit and auditable.

### N1 — StrategyProfile + SWING_V1

Status: `PRODUCT_DONE` via #63.

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
- compute performance with fees/slippage and separate economic vs forecast outcomes;
- use a frozen ExperimentUniversePolicy; do not read mutable Personal Watchlist membership.

API:
- experiment list/detail;
- evaluation summary;
- benchmark comparison;
- sample-quality/calibration summary.

Android:
- Lab shell renders real experiment/evaluation data even before AI autonomous paper fills are enabled.

Acceptance:
- evaluation can score Formal SWING_V1 against a benchmark without any AI agent;
- every metric resolves to an immutable experiment/policy version;
- Personal Watchlist mutations do not alter an existing experiment sample.

### N4 — AI Strategy Lab Shadow (#95)

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

### N5 — Isolated AI Paper Trading (#96)

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

### N6 — Calibration and reliability UX (#97)

Backend:
- confidence buckets, Brier score, calibration error, sample size, uncertainty interval, regime/action breakdown.

Android:
- display historical event rate + interval + `n`;
- show `INSUFFICIENT_SAMPLE` instead of fake precision;
- compare AI, Formal SWING_V1 and benchmark.

Acceptance:
- the UI never shows a naked "reliability X%";
- user can see where an agent is overconfident, underconfident or regime-fragile.

### N7 — Home + Review (#98)

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

### N8 — Order Flow as evaluated timing evidence (#99)

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

### N9 — Modularization tied to vertical slices (#100)

Backend:
- migrate new Strategy/Experiment/Evaluation code into domain/application/infrastructure modules;
- gradually move root-level legacy modules behind stable adapters.

Android:
- extract feature ViewModels/repositories/API services from `MainActivity.kt` and monolithic `ApiClient.kt` as each visible milestone lands;
- Personal Universe/Watchlist must use its own feature boundary rather than growing MainActivity further;
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
| PUX1 Personal Universe | Watchlist metadata + PersonalUniverse membership/read model | personal-universe + watchlist CRUD | first-class Watchlist | user sees/manages positions + chosen symbols |
| PUX2 Review cadence | ReviewPlan / AnalysisBudget | review mode/reasons/last-next review | Watchlist + Position detail | why analysis ran or was deliberately skipped |
| PUX3 Discovery | bounded Discovery/Candidate substrate | discovery/settings/promotion | Watchlist Discovery tab | discovery off/slots/cadence, promote/ignore |
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
`Execution`, `Evaluation`, Personal Universe, or Review cadence must state:

- Authority Impact
- Strategy Impact
- API / Android Visibility Impact
- Backward Compatibility
- Evaluation Impact
- Acceptance Tests
- Delivery State (`BACKEND_READY`, `API_VISIBLE`, etc.)

Every Personal Universe/Review implementation commit that advances delivery must
update this Ledger in the same commit. If it changes current authority or safety
conformance, it must also update the canonical Architecture and the subordinate
Personal Universe design. No backend-only implementation may claim
`PRODUCT_DONE`.

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
- every open position remains in Personal Universe risk monitoring
- mutable Personal Watchlist cannot alter a frozen ExperimentUniverse
- Watchlist/Discovery membership alone cannot grant trading authority
- scheduler wake-up alone cannot authorize a full research rerun

## J. Delivery update — 2026-08-20

- **N1 StrategyProfile / SWING_V1:** `PRODUCT_DONE` via #63. The immutable
  `SWING_V1` identity and policy-version lineage are serialized in DecisionReport
  and rendered in Android stock detail together with structured timeframe
  authority. Formal action semantics were unchanged and full backend + Android
  CI passed before merge.
- **P0 #46 paper-execution visibility:** backend/API sellability and deferral
  facts were already authoritative. Android Trading consumes
  `sellable_quantity`, `locked_quantity`, `next_eligible_sell_at`, runtime
  `state_source`, and active execution deferrals and renders explicit T+1/
  next-review reasons. This slice is `ANDROID_VISIBLE / OBSERVABLE`; **Phase 5
  remains open** until deployed acceptance passes.
- **N2 Decision Workspace:** multiple backend/API/Android slices are merged,
  including continuity, strategy/timeframe, financial/event completeness,
  action-first detail hierarchy, typed route state and screenshot regressions.
  Device-level acceptance remains tracked separately; these slices do not alter
  Formal Decision authority.
- **#75 cache-first symbol search:** local identities resolve without blocking on
  provider I/O and true misses use bounded background enrichment. This is useful
  infrastructure for the Watchlist Add flow and introduces no trading authority.
- **PUX1 Personal Universe / Watchlist:** `BACKEND_READY / API_VISIBLE` via #86;
  `ANDROID_VISIBLE / ACCEPTANCE_PENDING` via #92.
  The accepted backend/API slice adds typed Watchlist/Personal Universe contracts,
  additive `0019_pux1_watchlist_metadata`, local-only Portfolio + Watchlist
  composition, explicit `GET /v1/personal-universe` and
  `PUT /v1/watchlist/{symbol}`, v2 route registration and regression tests.
  Main-base acceptance passed compileall, full backend pytest (**423 passed,
  7 warnings**), Docker build, documentation-governance and `ci-gate`. Android
  first-class Watchlist is implemented under #92; repository CI and physical
  device acceptance remain required before `PRODUCT_DONE`.
- **PUX2 Review Cadence / AnalysisBudget (#93) and PUX3 Discovery controls (#94):**
  remain `DESIGNED`. The approved target makes Portfolio + explicit Watchlist the
  primary personal research universe, demotes Candidate Pool product semantics
  to optional Discovery, separates Personal and Experiment universes, and
  introduces `NO_REVIEW/GUARD_ONLY/POSITION_REVIEW/FULL_RESEARCH` plus an
  observable AnalysisBudget. Implementation order remains PUX1 -> PUX2 -> PUX3.

## Delivery update — 2026-08-20 — N3 universe reconciliation

- **N3.1 ExperimentDefinition:** `BACKEND_READY` for immutable experiment identity,
  policy lineage and exact frozen experiment membership. Each experiment version
  binds `universe_policy_version` plus `universe_snapshot_id/hash`;
  `ExperimentUniverseSnapshot` stores sorted unique `(market, symbol)` members
  append-only, and the definition repository rejects missing, mismatched or
  rewritten universe snapshots. This implements the Personal-vs-Experiment
  universe separation already required by the PUX design: mutable Watchlist,
  position and Discovery changes cannot retroactively alter Evaluation samples.
  No Formal Action, quote freshness, Watchlist storage, Risk, sizing,
  ExecutionPrecheck or Paper Broker authority changes are introduced.
- **N3.2 Outcome contracts:** `BACKEND_READY` for immutable DecisionOutcome,
  ExecutionOutcome and TradeEpisodeOutcome plus versioned OutcomePolicy /
  ActionOutcomePolicy. `PENDING / RESOLVED / INSUFFICIENT_DATA / INVALID` are
  explicit, and BUY/WAIT/HOLD/ADD/REDUCE/EXIT/BLOCKED are evaluated by
  action-specific semantics rather than BUY-only rules. The initial SWING_V1
  observation windows remain 3/5/10/20 trading sessions; no target/stop
  thresholds are invented.
- **N3.3 OutcomeResolver:** `BACKEND_READY` for deterministic local-only
  resolution of 3/5/10/20-session DecisionOutcome metrics, execution attribution
  and closed TradeEpisode economics. Resolution now first validates the source
  `(market, symbol)` against the immutable ExperimentUniverseSnapshot and binds
  its hash into outcome lineage; a later PUX Watchlist/position/Discovery change
  cannot expand an existing experiment. The resolver performs no provider refresh.
- **N3.4 StrategyEvaluation:** `BACKEND_READY` for versioned aggregation over
  terminal outcomes. It computes sample sufficiency, episode win/loss economics,
  expectancy, Profit Factor, holding/fee/slippage/MFE/MAE metrics and action /
  horizon / regime / execution breakdowns. The aggregate snapshot now carries
  `universe_snapshot_id/hash`, revalidates every decision/episode against the
  frozen experiment membership and includes that hash in its source lineage.
  `total_return`, `max_drawdown` and `turnover` remain explicitly unavailable
  until an experiment-level equity curve exists; overlapping episodes are never
  compounded as a fake account return.
- **N3.5 BenchmarkPolicy:** `BACKEND_READY` for immutable, market-aware
  decision-window benchmark comparison. Explicit MARKET_INDEX /
  BUY_AND_HOLD_SYMBOL policies require an explicit market and symbol; the system
  does not guess a CN/HK/US index. EQUAL_WEIGHT_ELIGIBLE_UNIVERSE uses only
  same-market members from the frozen ExperimentUniverseSnapshot and fails closed
  when any required constituent start/end qfq bar is unavailable, rather than
  silently shrinking the benchmark. Benchmark observations align from the last
  officially completed session known at decision time to the Outcome's official
  observation-end session, use local persisted daily history only, and bind both
  policy and universe hashes into append-only lineage. Decision-window strategy,
  benchmark and excess returns are available; account-level benchmark/excess
  return remains explicitly unavailable until aligned experiment and benchmark
  equity curves exist. FORMAL_SWING_V1 reference-experiment comparison remains a
  declared policy type but is intentionally deferred to evaluation-to-evaluation
  compare rather than being misrepresented as a price benchmark.
- These backend slices are integrated into the accepted N3 chain; final end-to-end
  acceptance evidence is recorded in the N3.8 delivery update below.

## Delivery update — 2026-08-20 — N3.6 Lab API

- **N3.6 Lab API:** `BACKEND_READY` for stable read-only HTTP DTOs over the
  immutable N3 experiment/evaluation store. `GET /v1/lab/experiments`, detail,
  summary, outcomes, performance, breakdown and compare are registered through
  the v2 bootstrap boundary rather than the legacy API monolith.
- Lab GETs never call OutcomeResolver, provider refresh, Formal Decision, Risk,
  sizing, ExecutionPrecheck or Paper Broker. They project already-persisted
  ExperimentDefinition/Universe, terminal outcomes, StrategyEvaluation and
  BenchmarkEvaluation snapshots only.
- Experiment responses always expose the resolved experiment/version and frozen
  universe hash. Omitting `version` resolves the latest immutable version by
  `created_at`; callers may pin `?version=` explicitly. Compare accepts explicit
  `experiment_id@version` selectors and does not pool incompatible versions.
- PENDING DecisionOutcomes are still derived rather than persisted, so N3.6 does
  not invent a pending count. The API returns `pending_decision_count = null` with
  reason `pending_outcomes_are_derived_not_materialized_n3_6`. Likewise N3.4/5
  unavailable account-level return/drawdown/benchmark-excess metrics remain null
  with their existing reason codes rather than being presented as zero.
- `/calibration` is intentionally absent; probability calibration remains N6.
- N3.6 is now part of the accepted N3 product chain. The final N3.8 section below
  records the main-base end-to-end acceptance evidence.

## Delivery update — 2026-08-20 — N3.7 Android Lab

- **N3.7 Android Lab:** `ANDROID_READY` for the first user-visible Strategy Lab
  slice consuming the N3.6 read-only API. The Android feature has a dedicated
  Retrofit repository, immutable `Loading / Empty / Ready / Error` StateFlow
  controller and a pure content composable covered by unit/screenshot fixtures.
- The first entry is intentionally **Management -> Strategy Lab**. Current bottom
  navigation still uses the legacy numeric News/Market/Trading/Admin tabs and an
  unrelated hidden Research `tab=4` route remains a separate navigation cleanup;
  N3.7 does not combine Lab delivery with that wider navigation refactor.
- The screen exposes the resolved SWING_V1 experiment/version and frozen universe
  hash, sample sufficiency, win rate/payoff/expectancy/Profit Factor, benchmark
  window/excess returns, horizon/action/regime breakdowns and execution
  attribution. It does not request raw outcome detail for the MVP.
- Android performs display formatting only. It does **not** recompute strategy or
  benchmark metrics, infer missing account-level return/drawdown/turnover, or
  coerce unavailable/null values to zero. Existing N3.4/N3.5 reason codes and the
  N3.6 non-materialized PENDING semantics remain visible.
- Lab reads frozen experiment/evaluation facts only. It does not refresh market
  providers, mutate Watchlist/positions/Discovery, invoke Formal Decision/Risk/
  sizing/ExecutionPrecheck, or write Paper Broker state.
- Repository scan confirms the existing single `:app` Compose/Material3 +
  Retrofit/Coroutines architecture and no Navigation Compose dependency. Local
  Gradle baseline build is unavailable in the current execution container because
  Gradle/Android SDK are absent; the official Android PR CI is therefore the
  compile/unit/build acceptance gate.
- N3.7 Android acceptance is complete via #89: unit tests, Compose screenshot
  render/hash verification, Debug/Release builds, optimized Release verification,
  documentation-governance and repository `ci-gate` passed. N3.8 below closes
  the remaining Formal SWING_V1 end-to-end acceptance matrix.

## Delivery update — 2026-08-24 — N3.8 Formal SWING_V1 acceptance

- **N3 Evaluation:** `PRODUCT_DONE` for Formal `SWING_V1`. The automated N3.8
  acceptance fixture executes the real persisted chain from immutable
  `ExperimentDefinition` + `ExperimentUniverseSnapshot` through OutcomeResolver,
  terminal outcome persistence, StrategyEvaluation, BenchmarkEvaluation and the
  GET-only `/v1/lab` read model consumed by Android.
- **Immutable/versioned lineage:** experiment/version and universe snapshot id/hash
  remain fixed. A membership rewrite is rejected; a later/current attention symbol
  outside the frozen universe cannot enter an existing equal-weight benchmark.
- **Point-in-time integrity:** a deliberately impossible decision-session full-day
  candle is excluded from forward metrics, and benchmark alignment starts from the
  latest officially completed session already observable at decision time. No
  provider refresh or future-session data is used by the acceptance path.
- **Outcome integrity:** PENDING remains derived and is not persisted or counted as
  resolved; missing reference price remains visible as terminal
  `INSUFFICIENT_DATA`. Execution disposition comes from persisted fills, while a
  closed episode keeps realized PnL, fees and slippage as separate facts.
- **Metric integrity:** action/regime/horizon/execution breakdowns are reproducible;
  sample quality is explicit; benchmark identity and frozen constituent lineage are
  visible. Account-level total return/max drawdown/turnover and portfolio benchmark
  excess remain unavailable with reason codes until real aligned equity curves
  exist; N3.8 does not fabricate them. `/v1/lab/calibration` remains absent for N6.
- **Android evidence:** merged #89 already accepted Loading/Empty/Ready/Error,
  insufficient/unavailable presentation, screenshot hashes, unit tests and
  Debug/Release APK builds. Android formats immutable DTOs and does not recompute
  Evaluation or mutate Personal Universe/trading state.
- **Main-base acceptance:** N3.8 passed `python -m compileall app`, full backend
  pytest (**412 passed, 7 warnings**), Docker build, documentation-governance and
  repository `ci-gate`. The warnings are existing Starlette/FastAPI/exchange-calendar
  deprecations, not N3 failures.
- **Authority impact:** none. N3 remains a read/measurement plane and has no write
  path to Formal Action, StrategyProfile, RiskPolicy, SizingPolicy,
  ExecutionPrecheck, Paper Broker or Personal Watchlist/positions. Evaluation
  results cannot auto-promote or rewrite production policy.
- **Next dependency:** N4 AI Strategy Lab Shadow is now tracked by #95 and may
  build on this referee. N4 remains paper-intent/forecast only with no fill
  authority; N5 isolated AI paper execution (#96) and N6 probability calibration
  (#97) remain later phases.


## Product recovery decision — 2026-08-25 — S0 Stabilization

Daily mobile usability is now the immediate product priority. The approved
implementation plan is
`ThirdHand_Stabilization_Sprint_Plan.md`.

The active order is:

1. S0.1 Portfolio Recovery;
2. S0.2 Watchlist Recovery and #92 acceptance;
3. S0.3 Holding Detail fact/interpretation separation;
4. S0.4 K-line progressive disclosure;
5. S0.5 canonical AI/Decision entry;
6. remaining N2/device acceptance;
7. reassess N4 resumption.

N4 AI Strategy Lab Shadow, N5 AI Paper Trading and N8 Order Flow are paused for
new implementation until S0 acceptance is recorded here. Existing correctness
acceptance for #46, #39, #49 and #40 continues and is not weakened.

Every S0 item requires an explicit Android entry and the full
Backend -> API -> Android -> observable states -> screenshot/test -> device
acceptance chain. Backend-only or hidden/admin-only capability is not
`PRODUCT_DONE`. This prioritization changes delivery order only; it does not
change Formal Decision, StrategyProfile, Risk, sizing, ExecutionPrecheck,
Paper Broker or Evaluation authority.

### S0.1 Portfolio Recovery — Issue #107 — IN_PROGRESS

- **Android entry:** Bottom navigation -> Portfolio -> Holding Detail.
- **Implemented slice:** Portfolio cards now expose quote freshness, quantity,
  average cost, market value, P/L amount and percentage, holding duration and
  position weight. A holding opens the fact-oriented Holding Detail rather than
  the mixed Stock Detail route. Holding Detail prioritizes authoritative Holding
  and Quote DTO facts and reads transaction history from the real sale-record
  API; K-line remains available from the detail surface.
- **Authority impact:** none. This is a display/navigation recovery only; it
  does not alter Formal Decision, Risk, sizing, ExecutionPrecheck or Paper
  Broker authority.
- **Acceptance outstanding:** screenshot regression, repository CI and a
  physical-device walkthrough for loading, empty, ready, partial/stale and
  error states. Therefore this item is not `PRODUCT_DONE`.

### Mobile execution-chain detail repair — IN_PROGRESS

- **Android entry:** Bottom navigation -> Trading -> Execution chain records ->
  Chain detail.
- **Implemented slice:** selecting a run now loads the authoritative
  `paperTradingRunDetail(runId)` payload and renders its loading, error, empty,
  symbol-result and stage states. The record list closes before the detail
  dialog opens, preventing stacked dialogs from obscuring the result.
- **Authority impact:** none. This is read-only execution observability and
  does not add or change execution authority.
- **Acceptance outstanding:** repository CI, screenshot regression and a
  physical-device walkthrough. It is not `PRODUCT_DONE`.

### S0.4 K-line progressive disclosure — IN_PROGRESS

- **Android entry:** Portfolio -> Holding Detail -> K-line.
- **Implemented slice:** the K-line panel is rendered directly inside the
  detail surface rather than through nested cards. Daily history is requested
  as the complete available series; weekly and monthly candles aggregate that
  complete daily series without a trailing-window cutoff. Intraday data is
  constrained to its latest trading date only.
- **Acceptance outstanding:** screenshot regression, repository CI and a
  physical-device check of monthly, weekly, daily and intraday periods. It is
  not `PRODUCT_DONE`.
## Delivery update — 2026-08-25 — S0.2 Watchlist Recovery

- **Android entry:** Bottom navigation -> Watchlist remains first-class and opens
  the selected Stock Detail without requiring an admin/log surface.
- **404 recovery:** Android first requests the authoritative
  `GET /v1/personal-universe`; an explicit HTTP 404 falls back to the existing
  `GET /v1/watchlist` + `GET /v1/holdings` contracts, merges overlap without
  duplicates and visibly labels the compatibility state. Other HTTP failures
  still fail closed and remain observable.
- **Daily management:** edit and remove actions are both reachable for Watchlist
  rows; priority/note/enabled metadata, deterministic priority/name sorting and
  review status are visible. Position-only rows cannot be removed as Watchlist.
- **Observable states:** compatibility warning, mutation success, transient
  failure with retry, initial error with retry, loading and empty states are
  explicit. Mutations reload authoritative server state.
- **Tests:** controller coverage now includes deterministic ordering and legacy
  overlap reconciliation in addition to mutation/refresh behavior.
- **Delivery state:** `ANDROID_READY / ACCEPTANCE_PENDING`; official CI and a
  physical-device add/edit/remove/restart walkthrough remain required before
  `PRODUCT_DONE`.
- **Authority impact:** none. Personal Universe affects attention/display only;
  it does not alter Formal Decision or execution authority.

## Delivery update — 2026-08-25 — S0.3 Holding Detail separation

- **Canonical fact route:** both Portfolio holdings and Watchlist rows carrying
  `active_holding` now open `PositionDetailRoute`. Watchlist-only symbols retain
  the non-position Stock Detail route.
- **Screen responsibility:** Holding Detail remains limited to quote/position
  facts, K-line and transaction history. Its explicit Decision icon opens the
  secondary Decision Workspace, which in turn owns What Changed, research and
  explanatory content.
- **Regression protection:** route-selection JVM tests prevent a held symbol
  from silently returning to the mixed decision-first surface.
- **Delivery state:** `ANDROID_READY / ACCEPTANCE_PENDING`; repository CI and a
  physical-device walkthrough from both Portfolio and Watchlist remain required
  before `PRODUCT_DONE`.
- **Authority impact:** none. This is navigation and information architecture;
  Formal Decision and execution contracts are unchanged.

## Delivery update — 2026-08-25 — S0.4 K-line UX completion slice

- **Progressive hierarchy:** Holding Detail renders position facts first, then
  the technical chart; Decision/AI, financial and event interpretation remain
  behind the separate Decision entry rather than continuing below the chart.
- **Deterministic periods:** symbol changes reset the chart to Daily. Intraday,
  Daily, Weekly and Monthly select explicit datasets; Weekly/Monthly aggregation
  retains chronological OHLCV semantics over the complete persisted daily
  history.
- **Observable states:** loading, empty and error are distinct; chart failure has
  an in-place retry and does not hide the position facts above it.
- **Tests:** JVM coverage protects period selection and monthly OHLCV aggregation.
- **Delivery state:** `ANDROID_READY / ACCEPTANCE_PENDING`; CI and physical-device
  period switching remain required before `PRODUCT_DONE`.
- **Authority impact:** none. K-line remains read-only timing evidence.

## Delivery update — 2026-08-25 — S0.5 canonical AI entry

- **Stock facts first:** Stock Detail now defaults to quote/market facts and
  K-line only. Formal Decision, company research and paper audit history no
  longer continue as long-form content on the basic facts surface.
- **Canonical secondary entry:** the top-bar `决策与 AI` action opens the
  dedicated Decision Workspace. From there, `AI Research` remains an explicit
  deeper action; Back returns to unchanged stock facts.
- **Holding path:** Holding Detail keeps its existing Decision icon and the same
  Decision -> AI Research hierarchy, so held and Watchlist-only symbols no
  longer expose competing AI destinations.
- **Failure isolation:** AI/research availability cannot blank or block the
  quote/K-line facts screen.
- **Delivery state:** `ANDROID_READY / ACCEPTANCE_PENDING`; CI and a
  physical-device Stock Detail -> Decision -> AI Research -> Back walkthrough
  remain required before `PRODUCT_DONE`.
- **Authority impact:** none. AI remains explanation/research only and cannot
  override Formal Decision or execution gates.

## Delivery update — 2026-08-28 — HiThink official A-share provider PoC

- **Scope:** added an optional official HiThink acquisition layer for three
  bounded A-share capabilities only: `/api/meta/tickers/search`, explicit
  `/api/a-share/prices/snapshot?thscodes=...`, and single-symbol daily
  `/api/a-share/prices/historical` with forward adjustment. Search results are
  capped at five and quote batches are capped by `HITHINK_FINANCE_MAX_BATCH`
  (default 20). The PoC never omits `thscodes`, so it cannot silently switch the
  snapshot endpoint into full-market pagination.
- **Configuration/security:** `HITHINK_FINANCE_ENABLED=false` by default. The
  API key is read only from server environment configuration and is sent only in
  the `X-api-key` header; it is not stored in Android, Git, request URLs or logs.
- **Fallback/currentness:** when disabled, unconfigured, ambiguous, empty,
  unauthorized, capability-denied, rate-limited beyond bounded retries, or
  otherwise unavailable, acquisition falls back to the existing governed
  AKShare/Tencent/Tushare chain. HiThink explicit snapshot mode does not provide
  a unified quote timestamp, so Third-Hand does not invent one; existing
  freshness/quality policy remains authoritative.
- **History lineage:** successful HiThink daily history writes the existing
  normalized daily-price store with `qfq` semantics and provider lineage;
  provider attempt audit records request id/error code without logging secrets.
  Existing missing-range collection, circuit-breaker behavior and closing-bar
  repair remain in force.
- **Tests:** mocked contract coverage verifies default-off/key gating, max-five
  search, header-only credential transport, explicit `thscodes`, `2003`
  fail-fast behavior, bounded `4001` retry, daily/forward historical parameters,
  and fallback to the existing provider chain. Live black-box acceptance is not
  claimed until an operator configures a real server-side API key.
- **Delivery state:** `BACKEND_POC / LIVE_KEY_ACCEPTANCE_PENDING`. No new Android
  surface is required for this provider-only slice; existing user-visible quote,
  symbol-search and K-line surfaces continue to consume the same contracts.
- **Authority impact:** none. This changes acquisition redundancy only and does
  not modify Formal Action, StrategyProfile, Evidence authority, Risk, sizing,
  ExecutionPrecheck, Paper Broker or Evaluation authority.

## Delivery update — 2026-08-28 — Android update recovery and K-line density

- **Android update recovery:** restored foreground/resume update discovery through
  the existing `resumeSignal` and `AppUpdateManager` contract. Release builds
  check the existing `/v1/app-update` endpoint; Debug remains intentionally
  excluded. When the persisted preference is enabled, an available release may
  enqueue automatically on Wi-Fi without blocking normal app startup.
- **Stable update controls:** Profile -> Application Settings exposes a manual
  `检查更新` action and a persisted `Wi-Fi 自动下载更新` switch. Download,
  SHA-256 verification, signature verification, install-permission handling and
  system-installer ownership remain in the existing update manager.
- **K-line density:** Holding Detail removes the duplicated English section label,
  the outer nested chart Card and the extra fixed-height wrapper. One chart
  surface owns identity, equal-width period controls, OHLC/selected-bar facts,
  price canvas and volume; the transaction-history empty state is also tightened.
- **Backend:** unchanged. No backend route, DTO, provider or persistence contract
  changes in this slice.
- **Accepted:** implementation is repository-ready but not yet device-accepted;
  official Android CI and a physical-device update/K-line walkthrough remain the
  acceptance gates.
- **Delivery status:** `ANDROID_READY / CI_DEVICE_ACCEPTANCE_PENDING`.
- **Authority impact:** none. This is Android presentation/update-delivery work
  only and does not modify Formal Decision, StrategyProfile, Evidence, Risk,
  sizing, ExecutionPrecheck, Paper Broker or Evaluation authority.

## Delivery update — 2026-08-28 — PUX2.3 scheduler research governance

- **Scheduler consumption:** the existing adaptive paper scheduler now consults
  the server-owned `PUX2_REVIEW_V1` ReviewPlan before expensive Personal Universe
  research. A scheduler wake-up alone no longer grants a new research run.
- **Stable-position behavior:** `NO_REVIEW` and `GUARD_ONLY` symbols remain in
  the existing quote/daily/risk acquisition and paper-execution obligation path,
  but routine news research, Company Intelligence and fresh Decision/AI report
  generation are skipped. This keeps cheap safety/currentness work alive without
  repeating DeepSeek work simply because the scheduler is awake.
- **Bounded review depth:** `POSITION_REVIEW` may enter the existing bounded
  Decision/AI path against cached/governed evidence but does not rebuild slow
  Company Intelligence. `FULL_RESEARCH` permits both the existing Decision/AI
  path and Company Intelligence. PUX2 does not change candidate membership or
  any Formal Action/Risk/Sizing/Execution authority.
- **Budget/persistence:** routine `FULL_RESEARCH` permission remains at most once
  per symbol per Beijing-local day. ReviewPlan persistence now deduplicates
  semantically unchanged scheduler ticks, and a persisted full-research
  permission is conservatively counted even when a downstream provider/model
  fails so dependency failure cannot create an automatic retry storm.
- **Explicit user request:** added local-only `GET /v1/review-plan/{symbol}` and
  `POST /v1/review-plan/{symbol}/request`. The POST persists an audited
  `explicit_user_request` override for an active Portfolio/Watchlist symbol; it
  does not inject formal candidate membership, call the model synchronously or
  execute a paper trade. Existing manual `force=true` cycles are treated as an
  explicit review permission while retaining all old scope/execution gates.
- **Material change handoff:** a newly persisted formal Decision whose
  `DecisionMemory.material_change` is newer than the last ReviewPlan upgrades the
  next scheduler review deterministically. Once a newer review/decision consumes
  it, ordinary stable-position behavior returns to the governed cadence.
- **Compatibility:** ReviewPolicy applies only to active Personal Universe
  symbols. Non-Personal formal candidate behavior is intentionally unchanged;
  PUX3/#94 still owns Discovery/candidate demotion rather than receiving a hidden
  behavior change in this slice.
- **Tests:** deterministic coverage protects stable-position GUARD_ONLY
  deduplication, once-per-day Watchlist full-research budget, persisted explicit
  request lineage, one-shot MaterialChange upgrade, scheduler filtering of
  news/Company/Decision research and force-cycle explicit permission.
- **Delivery state:** `SCHEDULER_GOVERNED / CI_DEVICE_ACCEPTANCE_PENDING` for
  #93. Existing Android Watchlist ReviewPlan labels remain the visible surface;
  repository CI and physical-device validation remain required. A dedicated
  typed hard-guard transition adapter/metric can be added separately without
  reopening routine full-research permission.
- **Authority impact:** none. Formal candidate selection, Decision authority,
  StrategyProfile, Evidence authority, Risk, sizing, ExecutionPrecheck, Paper
  Broker and Evaluation remain unchanged.

## Delivery update — 2026-08-28 — simulated-account auto-execution control recovery

- **Android entry:** Bottom navigation -> Trading now keeps a `模拟账户自动执行`
  switch visible inside the execution-control panel even when automatic paper
  trading is paused. The user can explicitly resume or pause the existing
  simulated-account scheduler instead of reaching a dead-end `已暂停` state.
- **Existing configuration contract:** Android reads the current
  `GET /v1/admin/config` payload and writes the same complete configuration back
  through `PUT /v1/admin/config`, changing only `paper_trading_enabled`; update
  checking and the configured paper interval are preserved.
- **Guarded manual run:** `立即运行决策轮换` is disabled while the scheduler is
  paused, while its enabled state is being changed, or while a run is already in
  progress. Toggle/run failures are surfaced through the screen Snackbar instead
  of silently leaving the user unsure whether the action succeeded.
- **Boundary:** this restores the existing governed paper-account scheduler; it
  does **not** resume or implement N5 isolated AI-agent paper trading (#96), and
  it does not give an LLM direct ledger or fill authority. The UI explicitly
  states that no real broker order is submitted.
- **Backend:** unchanged. The persisted paper-trading setting and Paper Broker
  safety contracts already exist; this slice restores their Android control
  surface and gives it an authority-accurate product label.
- **Accepted:** repository CI and a physical-device off -> on -> manual run -> off
  walkthrough remain required before this recovery is device-accepted.
- **Delivery status:** `ANDROID_READY / CI_DEVICE_ACCEPTANCE_PENDING`.
- **Authority impact:** none. Formal Decision, Risk, sizing, ExecutionPrecheck,
  Paper Broker rules and Evaluation authority are unchanged.

## Delivery update — 2026-08-28 — UIX1 compact Android UI foundation

- **Issue / implementation:** #129 / draft PR #136 starts the approved compact
  UI/UX rebuild after the design baseline in #135. This slice establishes shared
  density primitives before any screen-specific rewrite.
- **Typography / spacing:** existing Material typography and legacy spacing
  remain compatible, while scan-heavy financial surfaces gain an explicit
  10-18sp compact scale, 16dp content insets, 8dp row rhythm, thin separators
  and a minimum 44dp interactive target.
- **Shared Android primitives:** compact page/section headers, right-aligned value
  rows, text-first state tags and dense dividers are available for the later
  News/Market, Watchlist, Holdings, simulated-account Trading and detail slices.
  Existing Trading page wrappers keep their call-site contracts while adopting
  the dense presentation layer.
- **Navigation:** the current `资讯 | 行情 | 持仓 | 交易 | 自选` information
  architecture is unchanged. A low-chrome compact bottom-navigation component is
  introduced for later shell wiring; no route or business action changes here.
- **Design-system sync:** `.superdesign/design-system.md` now records the
  light-first, high-density financial rules and explicitly preserves the current
  simulated-account Trading boundary instead of inventing broker order-entry UI.
- **Backend/API:** unchanged. No DTO, endpoint, persistence or provider contract
  changes.
- **Delivery status:** `ANDROID_FOUNDATION_IN_PROGRESS / CI_DEVICE_ACCEPTANCE_PENDING`.
  Compile, screenshot impact, Debug/Release, repository governance/ci-gate and
  physical-device readability remain acceptance gates before #129 can close.
- **Authority impact:** none. Formal Decision, StrategyProfile, ReviewPolicy,
  Risk, sizing, ExecutionPrecheck, Paper Broker and Evaluation authority are
  unchanged.

## Delivery update — 2026-08-28 — UIX2 News + Market scan density

- **Issue / implementation:** #130 applies the accepted UIX1 compact primitives to
  the existing News and Market Android surfaces. The slice is presentation-only;
  it does not add providers, endpoints, statistics or navigation destinations.
- **News:** headline rows now lead with 14sp compact titles, source/time metadata
  and text-first announcement/flash tags; explanations are capped at two lines,
  filter controls retain a 44dp touch target, and thin dividers replace excess
  card chrome.
- **Market:** the oversized colored session card is replaced by a compact status
  strip; index, breadth, sector, ranking and quote rows use 16dp insets, 8dp row
  rhythm, right-aligned values and project `MarketColors` for rise/fall semantics.
  Search, tabs, ranking filters and drill-down rows retain at least 44dp targets.
- **Routes / states:** stock-detail routing, loading, empty, error, cached/stale
  display and existing refresh behavior remain intact. Android does not invent
  new market facts or recompute server authority.
- **Screenshot coverage:** dedicated News and Market dense-row preview tests are
  included so CI can render/lock representative scan-heavy states before merge.
- **Backend/API:** unchanged. Existing DTOs and routes are reused exactly.
- **Delivery status:** `ANDROID_IMPLEMENTED / CI_DEVICE_ACCEPTANCE_PENDING`.
  Repository compile/unit/screenshot/Debug/Release/ci-gate plus physical-device
  density/readability remain required before #130 can be `PRODUCT_DONE`.
- **Authority impact:** none. Formal Decision, StrategyProfile, ReviewPolicy,
  Evidence authority, Risk, sizing, ExecutionPrecheck, Paper Broker and
  Evaluation authority are unchanged.

## Delivery update — 2026-08-28 — UIX3 Watchlist / Personal Universe density

- **Issue / implementation:** #131 applies the compact UIX1 language to the
  existing first-class Watchlist / Personal Universe surface without changing
  its membership, review or trading contracts.
- **Scan hierarchy:** the oversized coverage card is replaced by a compact summary
  strip; `自选股 | 持仓股` remain sibling filters; each security row aligns latest
  price and change into fixed right-side columns while keeping symbol, market,
  quote freshness and server-owned review state visible below the name.
- **Attention metadata:** position, CORE/FOCUS priority and paused states use
  text-first compact tags. Review mode, next-review time, first governed reason
  and user note remain visible but are collapsed into one-line scan metadata
  rather than stacked card paragraphs. Android still performs no ReviewPolicy
  calculation.
- **Management:** add remains in the page header. Existing edit/remove flows are
  preserved behind one 44dp row overflow target so dense numeric columns stay
  aligned; position-only rows never gain Watchlist mutation actions.
- **Routes / states:** held symbols still route to Holding Detail and Watchlist-only
  symbols to Stock Detail. Loading, empty, compatibility-warning, transient error
  and retry states remain explicit.
- **Backend/API:** unchanged. `GET /v1/personal-universe` and existing Watchlist
  mutation contracts remain authoritative; no decorative DTO field was added.
- **Delivery status:** `ANDROID_IMPLEMENTED / CI_DEVICE_ACCEPTANCE_PENDING`.
  Repository compile/unit/screenshot/Debug/Release/ci-gate and physical-device
  density/readability plus add/edit/remove routing remain required before #131
  can be `PRODUCT_DONE`.
- **Authority impact:** none. Personal Universe remains an attention/read surface;
  Formal Decision, StrategyProfile, ReviewPolicy authority, Evidence, Risk,
  sizing, ExecutionPrecheck, Paper Broker and Evaluation are unchanged.

## Product UI baseline reset — 2026-08-28 — UIX0 target shell (#140)

- **Approved target shell:** `首页 | 行情 | 组合 | 策略 | 自选` is now the canonical
  Android navigation target. Earlier UIX1-UIX6 delivery notes that preserved
  `资讯 | 行情 | 持仓 | 交易 | 自选` remain implementation history only and no longer
  define visual or information-architecture acceptance.
- **Capability mapping:** Home composes only existing attention/portfolio/review/
  research facts with explicit partial states; Market retains current market/search/
  detail capability; `组合` owns current Holdings/Position Detail facts; `策略`
  organizes current simulated-account execution plus Decision/review/research
  surfaces; `自选` retains Personal Universe/Watchlist capability.
- **Visual contract:** Third-Hand brand red is the primary shell/action role over a
  white/cool-light canvas. Compact Chinese securities density, restrained cards,
  thin dividers, aligned financial values and red-up/green-down market semantics
  are acceptance requirements. Screenshot hashes remain regression protection;
  visual acceptance additionally compares the rendered app against the approved
  reference direction at normal phone scale.
- **Reconciliation:** #129-#134 remain useful implementation history but must be
  reconciled against UIX0. In particular, #132 targets `组合`, #133 targets the
  `策略` simulated-execution/decision surface, and PR #139 remains draft until
  this baseline lands and its factual portfolio work is rebuilt/rebased on the
  new target shell.
- **Safety boundary:** target-reference AI trade/order concepts do not create
  broker authority. No real-broker ticket, transfer, cancel-order or execution
  control is authorized; current automated/manual controls remain simulated-account
  operations governed by existing Paper Broker safety contracts.
- **Backend/API:** unchanged. This baseline changes product-shell and visual
  governance only and does not introduce a new DTO, provider or persistence path.
- **Delivery status:** `DESIGN_BASELINE_READY / IMPLEMENTATION_RECONCILIATION_PENDING`.
  Documentation governance/CI must pass before runtime shell implementation and
  screen reconciliation resume.
- **Authority impact:** none. Formal Decision, StrategyProfile, ReviewPolicy,
  Evidence, Risk, sizing, ExecutionPrecheck, Paper Broker and Evaluation authority
  remain unchanged and server-owned.

## Delivery update — 2026-08-28 — UIX0 runtime shell wiring

- **Android shell:** primary bottom navigation now renders the approved
  `首页 | 行情 | 组合 | 策略 | 自选` destinations and opens on Home. The selected
  shell item uses the Third-Hand brand-red role with a pale-red container while
  unselected destinations remain neutral.
- **Existing-capability mapping:** Market, Holdings, Paper Trading and Personal
  Universe keep their existing runtime owners under `行情`, `组合`, `策略` and
  `自选`. No backend route or authority contract is replaced.
- **Home baseline:** a dedicated Home shell is added without inventing a new
  server summary. It explicitly labels the current aggregation as partial and
  reuses the existing News capability while future attention/review aggregation
  remains pending.
- **Compatibility:** held-symbol detail, Watchlist routing, profile/update flow,
  simulated-account controls and current decision/research drill-down remain
  reachable. `资讯`, `持仓` and `交易` are no longer primary bottom-nav labels.
- **Backend/API:** unchanged.
- **Delivery status:** `ANDROID_SHELL_IMPLEMENTED / CI_DEVICE_ACCEPTANCE_PENDING`.
  Android compile/unit/screenshot/Debug/Release/ci-gate and physical-device
  comparison against the approved target references remain required before UIX0
  runtime shell acceptance.
- **Authority impact:** none. Formal Decision, StrategyProfile, ReviewPolicy,
  Evidence, Risk, sizing, ExecutionPrecheck, Paper Broker and Evaluation authority
  remain unchanged and server-owned.

## Delivery update — 2026-08-28 — UIX0 brand-red Material theme correction

- **Root cause corrected:** the approved shell and design system were red-first,
  but the global Android `MaterialTheme` still used the legacy `#0052D9` blue
  primary palette. Any screen that consumed `MaterialTheme.colorScheme.primary`
  therefore continued to render blue controls even after the bottom navigation
  itself was switched to brand red.
- **Android theme:** light mode now uses Third-Hand brand red `#F52D3A`, pale-red
  `#FFE0E3` containers, cool-light `#F7F8FA` canvas, white surfaces, neutral
  `#1F2329` text and `#667085` secondary text. Dark mode is aligned to the same
  red identity instead of the former blue palette.
- **Market semantics:** rise/fall colors remain owned by the existing
  `MarketColors` abstraction; changing generic Material primary roles does not
  redefine quote direction or trading-state meaning.
- **Scope:** presentation/theme only. Existing routes, DTOs, simulated-account
  controls, Decision Workspace and Paper Broker safety behavior are unchanged.
- **Delivery status:** `ANDROID_THEME_ALIGNED / CI_DEVICE_ACCEPTANCE_PENDING`.
  Repository Android CI and physical-device reference comparison remain required
  before UIX0 visual acceptance is complete.
- **Authority impact:** none. Formal Decision, StrategyProfile, ReviewPolicy,
  Evidence, Risk, sizing, ExecutionPrecheck, Paper Broker and Evaluation remain
  unchanged and server-owned.

## Delivery update — 2026-08-28 — frozen-decision execution polling

- **Root cause / behavior:** market quotes already refresh about once per minute,
  while adaptive full research/decision cycles run at 5–10 minute review
  intervals. Because historical execution was nested inside the full cycle, a
  valid frozen BUY/ADD/REDUCE/EXIT could wait several minutes after a strictly
  later eligible quote existed.
- **Pending queue:** current-version WAIT/HOLD/BLOCKED reports no longer count as
  execution obligations. Only formal actions with a BUY/SELL execution side
  remain pending.
- **Execution cadence:** a 30–60 second execution-only poll checks those frozen
  obligations between full reviews, using only the local quote cache already
  refreshed by the market worker. It does not invoke providers, Company
  Intelligence, DeepSeek/LLM, candidate selection or new decision generation,
  and it does not advance the full analysis clock.
- **Safety / authority:** every fill still runs through existing
  session/calendar, quote freshness, strictly-later-quote, cooldown, action gate,
  sizing, lot/T+1, sellability and idempotency checks. `paper_trading_enabled`
  still gates automatic simulated fills. No ActionPolicy threshold, candidate
  policy, AI authority or real-broker boundary changes.
- **Deployment configuration:** Compose now forwards
  `HITHINK_FINANCE_ENABLED` and `HITHINK_FINANCE_API_KEY` into the API container
  so an operator-enabled optional acquisition provider is actually visible at
  runtime; provider availability does not grant execution authority.
- **Tests:** pending filtering and execution-only cadence are covered, including
  the invariant that a due full analysis review wins over the shortcut and the
  execution poll leaves `last_paper_trading_run_at` unchanged.
- **Android:** unchanged. Existing simulated-account auto-execution controls
  remain the user-facing switch; no broker UI or new execution action is
  introduced.
- **Delivery status:** `BACKEND_READY / CI_ACCEPTANCE_PENDING`. Repository CI is
  the acceptance gate; deployment/live behavior should be verified after merge
  without changing the Formal Decision/risk contract.
