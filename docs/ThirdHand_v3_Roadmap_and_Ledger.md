# ThirdHand v3 Redesign Ledger and Roadmap

> **Canonical status (2026-08-18):** This is the only active implementation
> ledger. `ThirdHand_Architecture_v3_consolidated.md` is the paired authority
> contract. All other files formerly under `docs/` are historical and removed.
>
> **Completed:** Phases 1–3 and most Phase 5 ledger enforcement. **Active gaps:**
> Phase 4 intraday 60m/15m/5m ingestion and a versioned multi-timeframe action
> policy; and the Phase 5 paper-execution remediation defined in the paired
> architecture section 6.1. A final ledger T+1 rejection is not sufficient
> conformance when decision, sizing, scheduler, UI or session gates allow an
> impossible paper order to reach that final boundary.
> The paper account is intentionally CNY-only: HK/US remain research/audit
> markets, not a deferred multi-currency execution project.
> No gap is hidden behind a fallback or delegated to an LLM.

## Current implementation decision

The formal action path remains intentionally conservative:

```text
DecisionContext -> EvidenceEngine -> ActionPolicy -> DecisionArbiter
                -> DecisionContinuity -> formal_action -> ExecutionPrecheck
```

Atomic Evidence and AI explanations are persisted and audited beside this path.
`ResearchAssessment` is an explicit, asymmetric arbiter input: high-confidence
ADVERSE research can veto only new BUY/ADD risk. It cannot upgrade an action or
create REDUCE/EXIT. AI never receives authority over price/time, quality,
market rules, sellable quantity, hard gates, sizing or formal action.

## A. Consolidated ledger disposition

Legend:
- KEEP = required v3 design item.
- MERGE = valid concern, implemented inside another v3 component rather than a standalone subsystem.
- DEFER = useful but not P0/P1 or insufficiently specified.
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
| TH-RUNTIME-001 empty-content retry | KEEP | ModelRuntimePolicy |
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
| technical anchor lifecycle/rebase | DEFER | strategy-specific |
| multi-timeframe authority | KEEP | strategy/decision policy |
| TH-RISK-001/002 stale risk snapshot | MERGE | quality/freshness; no duplicate risk-quality subsystem |
| TH-TEST-001 stability ignored failed-run coverage | KEEP | benchmark harness coverage + stability |
| TH-BENCH-002 frozen/hash/action exclusion | KEEP | existing DecisionPackage hashing is the base |
| TH-BENCH-003 semantic/aggregation stability metrics | KEEP | evaluation harness |
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
| TH-CONF-001 conviction drift | KEEP | three confidence layers |
| EntryDecision vs PositionDecision | KEEP | core semantics |
| Position state machine | KEEP | decision phase |
| PositionLot/T+1/sellable qty | KEEP | MarketAdapter + execution |
| TH-EXEC-20260818 T+1 observed after morning buys | KEEP P1 | PositionLot ledger enforcement passed deployed-container verification; promote sellable/locked quantity and next eligible sell time into DecisionContext, precheck, sizing, API and scheduler deferral state. |
| TH-EXEC-20260818 repeated T+1 retry logs | KEEP P1 | A T+1 deferral is one scheduled state, not a zero-quantity SELL attempt or a new skip row every review interval. |
| TH-EXEC-20260818 after-session paper fill | KEEP P1 | Require instrument calendar/session plus an in-session fresh observed quote before every paper fill; closed-market manual runs are analysis-only. |
| TH-OPS-20260818 volatile paper runtime status | KEEP P2 | Rebuild API status from persisted simulation runs after restart; do not report `never_run` while run audit exists. |
| TH-DOC-20260818 paper-vs-real boundary | KEEP P2 | README, UI and deployment comments must distinguish no real broker order from optional simulated paper-ledger fills. |
| DecisionMemory/MaterialChange/cooldown | KEEP | continuity phase |
| FeedbackEvent | KEEP | feedback phase; no auto-tune first |
| A/HK/US MarketAdapter | KEEP | platform boundary |
| legacy DecisionSnapshot/calibration/impact graph | CLOSE | removed; DecisionContext/DecisionPackage and FeedbackEvent are the only v3 authority boundaries |
| separate EvidenceAvailabilitySnapshot service | MERGE | keep inside EvidenceSnapshot/quality snapshot |

## B. Current-code conformance findings

1. The former held `NO_TRADE -> REDUCE` behavior is removed from formal semantics; held WATCH resolves to HOLD.
2. Market regime, lot and settlement selection are market-scoped. The formal paper account is CNY-only. HK Stock Connect instruments retain HKD trading-price metadata and broker receipts retain the actual RMB settlement/fee facts, but neither creates an FX quote cache, currency balance, fee formula, nor an execution path. CN remains executable; HK/US are intentionally research/audit-only.
3. Atomic Evidence and ResearchAssessment are deterministic and persisted. The DecisionArbiter consumes only high-confidence ADVERSE research as a new-risk veto; it never lets research upgrade an action or produce REDUCE/EXIT. Completed daily bars also create a frozen weekly technical snapshot; intraday 60m/15m/5m ingestion and its action policy remain the Phase 4 gap.
4. Model policy/audit is complete for the configured DeepSeek client, while a generic provider-capability registry remains out of scope.
5. Feedback is immutable audit data and has no policy/sizing/model-routing write path.
6. Repository quality, time and freeze invariants remain the migration anchors.
7. Production verification on 2026-08-18 confirmed that the deployed ledger
   correctly blocks same-day CN sells, but also exposed repeated same-day
   REDUCE/EXIT attempts after morning buys and a historical after-session paper
   fill. These are active Phase 5 remediation items, not accepted behavior.
8. `DECISION_SHADOW_MODE` controls research/decision shadow output; it is not a
   switch for the simulated ledger. Automatic paper fills are governed by the
   persisted paper-trading setting and every execution entry point must honor
   the paper-execution safety contract.

Therefore v3 is an evolution of the present architecture, not a rewrite.

## C. Target requirements and acceptance criteria

The following phase descriptions are the target contract. The canonical status
at the start of this file overrides their historical tense: an item remains
active until its stated acceptance criteria are actually met.

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

### Phase 1 — Data correctness and market identity
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

### Phase 2 — Atomic Evidence foundation
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

### Phase 3 — Deterministic research aggregation
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

### Phase 4 — Decision semantics and state machine
Implement:
- EntryDecision and PositionDecision types
- remove `NO_TRADE -> REDUCE`
- position states
- EventRiskGate
- DecisionArbiter
- multi-timeframe authority

Acceptance:
- negative research bias can produce WAIT
- held-position actions use HOLD/ADD/REDUCE/EXIT only
- entry actions use BUY/WAIT/BLOCKED only
- every hard gate has reason codes
- high-confidence ADVERSE research may downgrade BUY to WAIT or ADD to HOLD,
  but cannot create or upgrade any action
- weekly technical state is hash-traceable but cannot alter the daily ActionPolicy
  before a separately versioned multi-timeframe action policy is approved

### Phase 5 — Market/execution adapters
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
- Stock Connect broker receipts preserve the actual RMB settlement and fee as
  audit evidence only; no general FX ledger or broker-fee formula is inferred
- `REDUCE`/`EXIT` can never size or submit more than `sellable_quantity`; a
  same-day lot produces one explainable T+1 deferral with its next eligible
  sell time, not repeated skipped SELL attempts
- manual or scheduler execution outside the instrument's open session, on a
  non-trading day, or with stale/out-of-session quotes cannot write a paper fill
- account/API exposes sellable and locked quantity plus read-only lot evidence,
  and status survives a process restart by reading persisted runs

### Phase 6 — Decision continuity
Implement:
- DecisionMemory
- entry-bound position episode id and frozen entry snapshot
- material-change detector
- cooldown/review-after
- prior decision reference

Acceptance:
- changed recommendation states what changed
- repeated analyses cannot flip without material change unless a hard gate changed
- an unchanged EvidenceSnapshot that permitted `BUY` when FLAT cannot produce
  `REDUCE`/`EXIT` solely because the resulting position is now HOLDING; static
  entry risk is not a post-entry deterioration signal
- a full `input_hash` difference is retained for audit, while only a versioned
  strategic material fingerprint can permit an action flip; ordinary quote
  refreshes inside the same threshold state preserve the prior action
- execution rejects a fill before `cooldown_until`
- due `review_after` produces a separately auditable decision-refresh obligation,
  never an implied trade
- first paper BUY persists decision/evidence/research/state/price provenance;
  ADD cannot overwrite it and full EXIT closes the episode

### Phase 7 — Model policy and audit
Implement:
- compact atomic research prompt
- configured-provider ModelPolicy (generic capability registry deferred)
- Flash/default vs Pro/escalation plus one bounded structured recovery
- schema + semantic validation
- observable runtime audit

Acceptance:
- every model run auditable by hashes/settings/usage
- invalid output never mutates formal decision
- the finite recovery graph is Flash -> Pro thinking -> Pro non-thinking
  structured: schema/semantic failure promotes the next tier, while exhausted
  empty-content or truncation failure uses the structured tier; every tier
  transition is recorded
- provider-specific maximum-reasoning tiers remain out of scope until the
  configured provider exposes a stable, tested capability contract

### Phase 8 — Feedback
Implement:
- FeedbackEvent
- execution/outcome link
- hypothetical-vs-actual review
- policy-version evaluation dataset

Acceptance:
- feedback points to an exact frozen decision/package
- no automatic tuning in first production release

## D. First implementation slice

The safest first code slice is Phase 1 and should remain narrow:
1. add market identity/instrument metadata abstractions;
2. introduce canonical snapshot builder around the existing one-click chain;
3. keep A-share behavior as default compatibility;
4. expose event/consistency results as Evidence;
5. add targeted tests;
6. do not change strategy thresholds, sizing, or freeze semantics in the same commit.

## E. Required regression invariants

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
