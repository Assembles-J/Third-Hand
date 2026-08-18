# ThirdHand v3 Redesign Ledger and Roadmap

> **Canonical status (2026-08-18):** This is the only active implementation
> ledger. `ThirdHand_Architecture_v3_consolidated.md` is the paired authority
> contract. All other files formerly under `docs/` are historical and removed.
>
> **Completed:** Phases 1–3, Phase 6, Phase 7 and Phase 8. **Active gaps:** Phase 4
> additional timeframe ingestion; Phase 5 HK/US fee + multi-currency FX cash
> ledger and broker fee schedules.
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
| TH-FX-001 account/instrument currency mismatch | KEEP | execution/currency adapter |
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
| DecisionMemory/MaterialChange/cooldown | KEEP | continuity phase |
| FeedbackEvent | KEEP | feedback phase; no auto-tune first |
| A/HK/US MarketAdapter | KEEP | platform boundary |
| DecisionSnapshot | MERGE initially | extend DecisionPackage/PlanAnalysisRun first; add table when memory requires it |
| separate EvidenceAvailabilitySnapshot service | MERGE | keep inside EvidenceSnapshot/quality snapshot |

## B. Current-code conformance findings

1. The former held `NO_TRADE -> REDUCE` behavior is removed from formal semantics; held WATCH resolves to HOLD.
2. Market regime, lot and settlement selection are market-scoped. HK Stock Connect explicitly uses HKD trading and CNY settlement, with a directed observed HKD→CNY context quote; CN remains executable, while HK/US stay blocked until their broker fee and multi-currency cash-ledger rules are configured.
3. Atomic Evidence and ResearchAssessment are deterministic and persisted. The DecisionArbiter consumes only high-confidence ADVERSE research as a new-risk veto; it never lets research upgrade an action or produce REDUCE/EXIT. Additional technical timeframe ingestion remains the Phase 4 gap.
4. Model policy/audit is complete for the configured DeepSeek client, while a generic provider-capability registry remains out of scope.
5. Feedback is immutable audit data and has no policy/sizing/model-routing write path.
6. Repository quality, time and freeze invariants remain the migration anchors.

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

### Phase 2 — Atomic Evidence shadow mode
Implement:
- AtomicFactRecord
- FactExtractor
- compact EvidenceSnapshot
- deterministic availability/conflict list
- fact-level provenance/materiality/comparison adequacy

Run beside legacy Evidence; do not change action yet.

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

### Phase 5 — Market/execution adapters
Implement:
- CN_A/HK/US market adapter interface
- lot/tick/fees/currency/settlement
- PositionLot and sellable quantity
- FX boundary
- execution precheck before sizing

Acceptance:
- no global 100-share rule
- no global A-share T+1 rule
- HK/US rules are selected by instrument market
- Stock Connect HKD→CNY conversion is explicit and directed; no reciprocal or
  implicit FX conversion may enable a trade

### Phase 6 — Decision continuity
Implement:
- DecisionMemory
- episode id
- material-change detector
- cooldown/review-after
- prior decision reference

Acceptance:
- changed recommendation states what changed
- repeated analyses cannot flip without material change unless a hard gate changed
- execution rejects a fill before `cooldown_until`
- due `review_after` produces a separately auditable decision-refresh obligation,
  never an implied trade

### Phase 7 — Model policy and audit
Implement:
- compact atomic research prompt
- configured-provider ModelPolicy (generic capability registry deferred)
- Flash/default vs Pro/escalation
- schema + semantic validation
- observable runtime audit

Acceptance:
- every model run auditable by hashes/settings/usage
- invalid output never mutates formal decision
- retry/fallback path recorded

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
