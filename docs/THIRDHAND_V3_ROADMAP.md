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

### Phase 1 — Data correctness and market identity

Implement explicit instrument/market identity, canonical snapshot semantics, cross-source consistency, first-class corporate events, market-specific regime selection and stale-risk quarantine.

Acceptance:
- quote and bars cannot silently represent different authority times;
- display fallback cannot act as execution price;
- HK decisions never consume CN market regime;
- event date is explicit evidence;
- existing CN behavior remains compatible.

### Phase 2 — Atomic Evidence shadow mode

Add `AtomicFactRecord`, FactExtractor, compact evidence snapshot, deterministic availability/conflicts, provenance, materiality and comparison adequacy. Run beside current evidence; no action changes.

### Phase 3 — Deterministic research aggregation

Move formal dimension/fundamental/research aggregation out of the LLM. Add three confidence layers and semantic validation.

### Phase 4 — Decision semantics/state machine

Split EntryDecision from PositionDecision, remove generic no-entry-to-reduce mappings, introduce hard event gates and explicit timeframe authority.

### Phase 5 — Market/execution adapters

Formalize CN/HK/US lot, tick, fee, currency, settlement and sellability rules; add PositionLot and FX boundaries.

### Phase 6 — Decision continuity

Add DecisionMemory, episode id, material-change detector, cooldown/review-after and prior-decision references.

### Phase 7 — Model policy and audit

Use compact evidence by default, deep-model escalation only when justified, and persist observable runtime audit metadata with schema + semantic validation.

### Phase 8 — Feedback

Link user actions and outcomes to exact frozen decisions. Do not auto-tune production policy until offline labels/evaluation are trustworthy.

## 4. First implementation slice

The first PR deliberately stays narrow:

1. add a single `MarketAdapter`/instrument identity boundary;
2. preserve current CN/HK symbol compatibility;
3. add US identity/calendar capability without changing strategy logic;
4. make `TradingCalendarService.market_for_symbol` delegate to the new resolver;
5. add focused unit tests;
6. do not change sizing, strategy thresholds, AI authority or final decisions.

The next PR will build CanonicalInputSnapshot consistency on top of this boundary.
