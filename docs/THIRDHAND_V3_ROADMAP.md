# ThirdHand v3 Redesign Ledger and Roadmap

## 1. Disposition rules

- **KEEP**: required v3 capability.
- **MERGE**: valid concern implemented inside another v3 component.
- **DEFER**: useful, but not P0/P1 or not sufficiently specified.
- **CLOSE**: benchmark/runtime observation; retain as evidence, not a product subsystem.

## 2. Consolidated ledger

| Item | Disposition | v3 owner / decision |
|---|---|---|
| TH-DATA-001 quote vs daily time mismatch | KEEP | CanonicalInputSnapshot + consistency gate |
| TH-DATA-002 stale quote mixed with fresh indicators | KEEP | execution/display authority separation |
| TH-DATA-003 mismatch must be formal evidence | MERGE | Evidence conflicts + quality summary |
| TH-EVENT-001 corporate event missing | KEEP | CorporateEventAdapter |
| TH-EVENT-003 pre-event new-risk gate | KEEP | EventRiskPolicy + DecisionArbiter |
| TH-HK-001 HK metadata missing | KEEP | MarketAdapter / InstrumentMetadata |
| TH-HK-002 HK regime contaminated by CN | KEEP | market-specific regime adapter |
| TH-MARKET-002 HK context source failure | KEEP | provider redundancy + data quality |
| TH-FX-001 account/instrument currency mismatch | KEEP | execution/currency adapter |
| TH-EXPECT-002 consensus/valuation missing | KEEP optional | expectation evidence, optional by default |
| TH-RESEARCH-001 Xiaomi research DB empty | CLOSE | data-coverage incident represented by availability |
| TH-RESEARCH-002 research bias mixed with action | KEEP | ResearchAssessment vs DecisionArbiter |
| TH-AI-001 only one WATCH candidate | CLOSE | historical benchmark observation |
| TH-AI-002 schema violation | MERGE | AIOutputValidator/runtime protocol |
| TH-AI-003 missing-evidence detection weak | CLOSE as AI duty | deterministic availability owns truth |
| TH-AI-004/005 reasoning budget / empty JSON | MERGE | ModelRuntimePolicy |
| TH-AI-006 semantic contradiction despite valid schema | KEEP | SemanticInvariantValidator |
| TH-AI-007 UNKNOWN vs NONE drift | KEEP | deterministic availability/event semantics |
| TH-AI-008 event present but model says missing | MERGE | semantic invariant |
| TH-AI-009 event contaminates technical label | MERGE | domain-isolated Atomic Evidence |
| TH-AI-014 Flash long-context instability | CLOSE as architecture rule | benchmark evidence only |
| TH-AI-015 Pro stability | CLOSE as permanent default | model routing remains versioned/benchmarked |
| TH-AI-016 missing-data list variance | KEEP | deterministic availability |
| TH-RUNTIME-001/002 retry/truncation | KEEP | ModelRuntimePolicy |
| TH-RUNTIME-003 complexity pre-routing | KEEP | ModelPolicy |
| TH-RUNTIME-004 whole-pipeline metrics | KEEP | runtime audit / evaluation |
| TH-RUNTIME-005 atomic context reduces cost/latency | KEEP | AtomicContextBuilder |
| TH-MODEL-001 deep escalation for complex conflicts | KEEP | ModelPolicy |
| TH-MODEL-003 stronger model cannot repair undefined policy | KEEP principle | deterministic aggregation |
| TH-TECH-001 trend label too coarse | KEEP P1 | TechnicalSnapshot decomposition |
| TH-TECH-002 event contaminates technical state | MERGE | domain isolation |
| technical anchor lifecycle/rebase | DEFER | strategy-specific contract needed |
| explicit multi-timeframe authority | KEEP | strategy/decision policy |
| TH-RISK-001/002 stale risk snapshot | MERGE | freshness/consistency gate |
| TH-TEST-001 failed-run coverage omitted | KEEP | evaluation harness |
| TH-BENCH-002 frozen hash/action exclusion | KEEP | snapshot hashing/audit |
| TH-BENCH-003 semantic/aggregation stability | KEEP | evaluation harness |
| TH-METHOD-001 pre-results event is neutral material | KEEP | EventRiskPolicy |
| TH-EVIDENCE-003 availability deterministic | KEEP | EvidenceSnapshot.availability |
| TH-EVIDENCE-004/005 source-level polarity too coarse | KEEP | AtomicFactRecord + fact polarity |
| TH-EVIDENCE-006 provenance vs semantics | KEEP | Source -> Fact separation |
| TH-EVIDENCE-007 atomic evidence | KEEP | core v3 |
| TH-EVIDENCE-008 materiality/comparison adequacy | KEEP | AtomicFactRecord |
| TH-FUND-001/002 fundamental state too coarse | KEEP | FundamentalVector + aggregate bias |
| TH-FUND-003 aggregation not LLM-owned | KEEP | deterministic DimensionAggregator |
| TH-FUND-004 materiality/importance | KEEP | fact + policy |
| TH-AGG-001/002/003 aggregate drift | KEEP | deterministic aggregation |
| TH-CONF-001 confidence drift | KEEP | evidence/research/decision confidence split |
| EntryDecision vs PositionDecision | KEEP | core decision semantics |
| Position state machine | KEEP | decision phase |
| PositionLot/T+1/sellable qty | KEEP | MarketAdapter + execution |
| DecisionMemory/MaterialChange/cooldown | KEEP | continuity phase |
| FeedbackEvent | KEEP | audit/feedback phase |
| A/HK/US MarketAdapter | KEEP | platform market boundary |
| separate DecisionSnapshot table | MERGE initially | extend existing decision persistence first |
| separate availability truth service | MERGE | keep inside canonical/evidence snapshot |

## 3. Roadmap

### Phase 1 — Data correctness and market identity — COMPLETE

Implemented in PRs #30-#33. The production decision path now has explicit instrument/market identity, canonical quote/daily authority, cross-source consistency, first-class scheduled earnings, market-scoped regime selection, stale-risk quarantine, and migration handling for the legacy synthetic paper-market instrument placeholder.

Acceptance met:
- quote and bars cannot silently represent different authority times;
- display fallback cannot act as execution price;
- HK decisions never consume CN market regime;
- scheduled earnings date is explicit neutral-material evidence and can conservatively block only new risk near disclosure;
- the formal paper-decision path remains Local-First;
- legacy CN behavior remains compatible while HK/US no longer inherit CN lot/currency defaults.

### Phase 2 — Atomic Evidence shadow mode — COMPLETE

Add `AtomicFactRecord`, `FactExtractor`, compact evidence snapshots, deterministic availability/conflicts, provenance, materiality and comparison adequacy. Run beside current evidence with no action changes.

Current first slice:
- add strict atomic fact / availability / conflict schemas;
- derive source-level facts from the already-authoritative `DecisionContext` and current deterministic `EvidenceItem`s;
- keep supportive and adverse facts separate even when they come from the same source document;
- mirror existing `DecisionQualitySummary` availability/conflict semantics rather than create a second quality authority;
- hash the compact evidence content against the frozen `context.input_hash`;
- attach the full atomic snapshot to `DecisionReport` for existing JSON persistence;
- construct Atomic Evidence only **after** current `ActionPolicyEngine` candidates are frozen;
- do not pass Atomic Evidence to ActionPolicy, AI, sizing, execution or final action selection during Phase 2.

Completed acceptance:
- identical frozen inputs produce identical atomic snapshot hashes;
- source provenance survives fact extraction;
- mixed-polarity facts from one source remain separate;
- missing/stale/conflicted capabilities agree with existing deterministic quality state;
- scheduled earnings remains `NEUTRAL_MATERIAL` rather than support/opposition;
- Company Intelligence is point-in-time bounded by both CompanyContext and its
  underlying ResearchDataSnapshot `available_at` values;
- the Xiaomi frozen-shadow benchmark proves that adding Company Research changes
  only the shadow snapshot, never formal candidates or action;
- full regression suite proves no formal action behavior changes.

Promotion boundary: Phase 3 may consume Atomic Evidence only through versioned,
deterministic aggregation policies. It must not promote the Xiaomi fixture's
weights or a model-produced research label into formal action authority.

### Phase 3 — Deterministic research aggregation — COMPLETE

The first aggregation slice is implemented: versioned Fact Polarity, Dimension,
Fundamental and Research policies build a `FundamentalVector` and
`ResearchAssessment` directly from frozen Atomic Evidence. Fundamental,
technical, event, optional expectation and market partitions remain isolated;
mixed polarity, missing capability and source conflict are explicit states. No
LLM output or Xiaomi-specific weighting is consulted. The assessment is
persisted on the decision report for audit, but has no action authority until
Phase 4.

Acceptance is complete: the same snapshot and policy versions reproduce the
same assessment; model output is not an aggregation input; no Xiaomi benchmark
weights exist in production policy; and semantic invariants validate fact
references, mutually exclusive polarity buckets, conflict propagation, snapshot
identity, and the Phase-4 boundary for decision confidence.

### Phase 4 — Decision semantics/state machine — ACTIVE

The semantic action is now the formal execution authority, while the legacy
action remains a compatibility/audit field. A flat `OPEN` maps to BUY, while a
held-position WATCH maps to HOLD rather than REDUCE; paper execution reads the
formal action and maps BUY back to the existing OPEN quality gate. Old frozen
reports safely replay through the same mapping. The arbiter does not consume
ResearchAssessment or model output.

Explicit state transitions (`FLAT`, `ENTRY_PENDING`, `HOLDING`,
`REDUCE_PENDING`, `EXIT_PENDING`, `BLOCKED`) are now emitted with each semantic
decision. Existing deterministic event gates are copied into a blocked entry's
reason codes without changing their scope. A versioned timeframe authority
contract now makes daily the current formal technical input and explicitly
reports missing weekly/60m/15m/5m inputs; it never fabricates an intraday
technical conclusion. Remaining: ingest and validate those additional
timeframes before granting them authority.

### Phase 5 — Market/execution adapters

ACTIVE. Paper execution now resolves lot, settlement and fee rules from
InstrumentMetadata/MarketAdapter. Each executed buy now persists a PositionLot;
CN lots become sellable only after the acquisition date, and sells consume
sellable lots in FIFO order. Sizing runs a market/currency/fee precheck before
deriving a quantity. CN retains its existing T+1 and fee schedule; HK/US are
conservatively blocked until their own fee/FX schedules and account currency
boundary exist, rather than inheriting CN's 100-share lot, T+1 or fees.

Pre-PositionLot aggregate positions are replayed from their immutable execution
logs into lots; any aggregate/log mismatch is explicitly blocked for manual
reconciliation. Remaining: market-specific HK/US fee schedules and a
multi-currency cash/FX ledger before enabling non-CN paper execution.

### Phase 6 — Decision continuity — ACTIVE

The formal decision path now records `DecisionMemory`: the prior decision,
episode, material-change reason, review time and an action cooldown. Identical
inputs and hard gates preserve the prior formal action; an input, position-state
or hard-gate change is an explicit material-change reason. Position age is
derived from the frozen opening timestamp. Remaining: make review/cooldown
scheduling observable in the paper runtime.

Add DecisionMemory, episode id, material-change detector, cooldown/review-after and prior-decision references.

### Phase 7 — Model policy and audit

Use compact evidence by default, deep-model escalation only when justified, and persist observable runtime audit metadata with schema + semantic validation.

### Phase 8 — Feedback

Link user actions and outcomes to exact frozen decisions. Do not auto-tune production policy until offline labels/evaluation are trustworthy.

## 4. Migration guardrails

1. Existing `DecisionContext`, `DecisionQualitySummary`, `EvidenceEngine`, deterministic `ActionPolicyEngine`, `DecisionReport`, and execution audit remain migration anchors.
2. New shadow representations must be additive and auditable before they receive policy authority.
3. Availability and conflict truth stay deterministic; an LLM may explain them but cannot define whether data exists, is stale, or conflicts.
4. Research bias is not an action. Entry/position action semantics remain a later phase.
5. No phase may silently reintroduce cross-market defaults, display-price execution, synchronous remote dependencies on the formal paper-decision path, or AI action override.
