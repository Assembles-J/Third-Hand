# ThirdHand Backend Architecture v3

## 0. Status
This is the single authoritative v3 architecture document. It defines both the
target authority boundaries and the current implementation conformance; it
supersedes all earlier v1/v2 designs, amendments and duplicate v3 documents.

The current repository already has strong production invariants around DataHub quality, provider lineage, DecisionPackage hashing, AI isolation, and unified freeze. v3 extends those mechanisms; it does not replace them with a parallel stack.

## 0.1 Current implementation conformance

| Area | Status | Code truth |
|---|---|---|
| Data, identity, events and canonical price/time | Complete | Instrument metadata, market-scoped regime, canonical snapshot and event gates are formal inputs. |
| Atomic evidence and deterministic aggregation | Complete | Fact/availability/conflict provenance, point-in-time Company Intelligence, versioned aggregation and semantic validation are persisted. |
| Decision semantics | Partial | Entry/Position actions and formal action authority exist. High-confidence deterministic adverse research may veto new BUY/ADD risk only; it never upgrades an action or creates REDUCE/EXIT. A traceable weekly snapshot is aggregated from completed daily bars; 60m/15m/5m inputs remain explicitly unavailable and ActionPolicy remains daily-only. |
| Market/execution adapters | Complete at the CNY-only scope | CN lot/T+1/fee and PositionLot FIFO are formal in the CNY-only paper account. HK Stock Connect retains HKD trading-price metadata and actual RMB broker-settlement receipts as audit facts. HK/US have no paper-execution path; a generic FX cache, multi-currency cash ledger and inferred broker-fee schedule are deliberately out of scope. |
| Decision continuity | Complete | Prior decision, episode, material change, cooldown/review fields and position age are persisted. ExecutionPrecheck rejects fills before `cooldown_until`; the deterministic runtime promotes `review_after` into a separately audited decision-refresh obligation. |
| Model policy and audit | Complete for the configured DeepSeek provider | Atomic prompt projection, Flash/Pro routing, schema/semantic checks, hashes, usage and retry traces are persisted. A generic multi-provider capability registry is not implemented. |
| Feedback | Complete as an audit dataset | Frozen decision/execution lineage, actual-vs-hypothetical outcomes and read-only policy-version export exist; there is no automatic tuning. |

The target diagram below is deliberately broader than the current formal action
path. The current path is `DecisionContext -> EvidenceEngine -> ActionPolicy ->
DecisionArbiter -> DecisionContinuity -> formal_action`; Atomic Evidence,
ResearchAssessment and AI are deterministic/auditable research inputs beside
that path. `ResearchAssessment` has one explicit, bounded authority: sufficiently
evidenced ADVERSE research can veto a new BUY/ADD risk. It cannot upgrade an
action, create REDUCE/EXIT, or bypass a hard gate; AI has no formal action path.

## 1. Existing foundations to preserve

Keep and build on:
- `DataHubRouter` and provider lineage.
- capability/subject-scoped quality.
- freshness recomputation and cache monotonicity.
- required vs optional Evidence.
- `DecisionPackage` evidence/package hashes.
- deterministic rule status separated from executable status.
- `freeze_trade_plan` as the single formal freeze boundary.
- AI forbidden from changing deterministic rule status, buy zone, position quantity, hard stop, and execution permission.
- one analysis authority time (`analysis_started_at`).

## 2. Target architecture

```text
Raw Providers
    |
    +--> Market Adapter --------+
    +--> Research Adapter ------+
    +--> Corporate Event Adapter|
    +--> Account/Position Adapter
                               |
                               v
                    Canonical Input Snapshot
                               |
                     Freshness / Consistency
                               |
                               v
                         Fact Extractor
                               |
                               v
                     Atomic Evidence Snapshot
                               |
                 +-------------+-------------+
                 |                           |
                 v                           v
        AI Research Interpreter      Deterministic Facts
        (Flash default / Pro         (quality, availability,
         escalation)                 event dates, price/time,
                 |                    settlement, metadata)
                 +-------------+-------------+
                               |
                               v
                Deterministic Dimension Aggregator
                               |
                               v
                 Deterministic Research Aggregator
                               |
                               v
                       ResearchAssessment
                               |
               +---------------+----------------+
               |                                |
               v                                v
        Hard Gates / Policy             Decision Memory
        event, market, risk,            material change,
        settlement, instrument          cooldown, episode
               |                                |
               +---------------+----------------+
                               |
                               v
                        Decision Arbiter
                        /              \
                       v                v
                EntryDecision     PositionDecision
                       \                /
                        +--------------+
                               |
                               v
                      Execution Precheck
                               |
                               v
                     Sizing / Lot / Fees
                               |
                               v
                        DecisionPackage
                               |
                               v
                    Unified Freeze / Confirm
                               |
                               v
                 Decision Memory / Feedback
```

## 3. Authority boundaries

### Deterministic authority
The LLM must never own:
- canonical price or authoritative market time;
- missing/stale/conflicted truth;
- event date or event distance;
- market/exchange/currency/lot/tick/fee/settlement rules;
- sellable quantity;
- hard risk/execution gates;
- formal dimension/fundamental/research aggregation;
- final entry/position action;
- sizing/hard-stop arithmetic;
- evidence/package hashes and freeze validity.

### AI authority
AI may:
- interpret atomic facts;
- classify ambiguous qualitative text;
- identify counter-evidence and unresolved ambiguity;
- summarize complex disclosures and management guidance;
- produce cited narrative research.

## 4. Core v3 domain models

### CanonicalInputSnapshot
One coherent analysis-time view:
- aware `analysis_started_at`;
- instrument identity + market;
- canonical completed daily bar;
- executable realtime quote, when required and valid;
- display-only fallback close;
- market-specific benchmark/regime;
- event snapshot;
- account/position snapshot;
- quality bindings;
- conflicts/missing capabilities.

### AtomicFactRecord
Fields:
`fact_id`, `symbol`, `market`, `domain`, `dimension`, `metric`, `value`, `unit`,
`period_start`, `period_end`, `comparison_type`, `source_evidence_id`,
`source_timestamp`, `observed_at`, `freshness_status`, `polarity`, `materiality`,
`comparison_adequacy`, `confidence`, `provenance_hash`.

One source can produce many facts with different polarity.

### EvidenceSnapshot
Fields:
`evidence_snapshot_id`, `symbol`, `analysis_started_at`, `canonical_market_time`,
`facts`, `event_snapshot`, `technical_snapshot`, `market_context`,
`instrument_metadata`, `availability`, `conflicts`, `missing`, `snapshot_hash`,
`schema_version`.

### ResearchAssessment
Fields:
`fundamental_dimensions`, `aggregate_fundamental_bias`, `technical_state`,
`event_state`, `expectation_state`, `market_context`, `research_bias`,
`evidence_confidence`, `research_conviction`, fact-id buckets,
`invalidation_conditions`, `aggregation_policy_versions`, `model_run_ids`.

### Decision semantics
Research bias is not an action.

The DecisionArbiter consumes deterministic research only as an asymmetric
new-risk veto: ADVERSE research at the configured evidence-confidence threshold
may turn BUY into WAIT or ADD into HOLD. SUPPORTIVE research never creates or
upgrades an action, and research never creates REDUCE or EXIT.

Entry actions:
- BUY
- WAIT
- BLOCKED

Position actions:
- HOLD
- ADD
- REDUCE
- EXIT
- BLOCKED

No generic `NO_TRADE -> REDUCE` translation.

### Confidence
Split:
- evidence confidence
- research conviction
- decision confidence

### Decision memory
Store:
`prior_decision_id`, `episode_id`, `last_action`, `position_age`,
`material_change`, `material_change_reason`, `cooldown_until`, `review_after`,
and invalidation conditions.

`cooldown_until` is enforced at `ExecutionPrecheck` against the independently
observed fill quote. `review_after` is not a trade: when due, it authorizes a
new formal decision generation with the lineage reason `decision_review_due`.
The runtime keeps review obligations distinct from unexecuted decision fills so
an expired review cannot be mistaken for an executable order.

### PositionLot
Lot-level settlement/sellability:
`lot_id`, `symbol`, `market`, `currency`, `quantity`, `acquired_at`, `cost_basis`,
`sellable_quantity`, `settlement_state`.

## 5. Deterministic aggregation
Versioned policy objects:
- FactPolarityPolicy
- DimensionAggregationPolicy
- FundamentalAggregationPolicy
- ResearchAggregationPolicy
- EventRiskPolicy
- DecisionArbiterPolicy

The Xiaomi T4-E weights are benchmark-only; they are not production defaults.

## 6. MarketAdapter
Required contract:
- market
- exchange
- timezone
- trading currency
- lot rule
- tick rule
- fee schedule
- settlement rule
- sellability rule
- sessions/calendar
- benchmark/regime universe

Initial adapters:
- CN_A
- HK
- US

For mainland-broker Stock Connect, HK securities trade/quote in HKD while cash
settles in CNY. ThirdHand's paper account remains CNY-only and does not model
FX rates, foreign-currency balances or a conversion workflow. A foreign-currency
quote is therefore not paper-executable, even when the broker settles cash in
RMB. This is an intentional scope boundary, not a missing fallback.

Broker settlement receipts preserve the actual foreign-currency price, RMB gross
settlement, total/broken-out fee, net cash impact and implied per-fill settlement
ratio. They are audit evidence, not a formula for later orders and not an
alternate execution path.

Existing A-share quality invariants remain the CN_A contract and must not be weakened while generalizing.

## 7. Corporate events
Corporate events become first-class evidence:
- results/earnings
- board meeting for results
- dividend/ex-date
- placement/rights issue
- suspension/resumption
- major capital transaction
- material legal/regulatory events

Pre-disclosure results event:
- direction = NEUTRAL_MATERIAL
- risk may be HIGH
- deterministic PreEventRiskGate may block new risk without claiming bearish direction.

## 8. Technical authority
Split technical interpretation into:
- trend_structure
- price_location
- momentum
- volume_state
- support/resistance

Timeframe authority:
- weekly/daily = strategic
- 60m = position management
- 15m/5m = execution timing
- realtime = hard risk/execution trigger only

Completed daily bars now produce a deterministic weekly 4/12-SMA snapshot with
its own source hash. It is visible in the frozen context and timeframe audit,
but remains research/strategic input only; the formal ActionPolicy still uses
the daily technical snapshot until an explicit multi-timeframe action policy is
versioned. Accordingly, the weekly snapshot is excluded from the current
daily-only formal `input_hash`; its separate source hash preserves auditability
without allowing asynchronous history maintenance to alter job identity.

Technical anchor lifecycle/rebase is deferred until a strategy-specific contract is defined.

## 9. Model policy
- Fast/non-thinking model: explain already deterministic conclusions.
- Default reasoning model: compact Atomic Evidence interpretation.
- Deep model escalation: complex unstructured disclosures, material conflicts, ambiguous accounting/guidance, or validator failure.
- Max reasoning: rare escalation only.

Persist observable execution audit:
model/provider, reasoning mode/effort, prompt hash, evidence hash, schema version,
latency, tokens, reasoning presence/length/hash if exposed, content hash,
validation, retry/fallback path.

Never persist API keys or raw hidden reasoning.

## 10. Feedback
Feedback is auditable data first, optimization signal later.

FeedbackEvent:
- frozen decision/package reference
- user action
- execution time/qty/price
- actual outcome window
- hypothetical outcome
- explicit feedback
- review label

No automatic production policy tuning until labels and offline evaluation are reliable.

## 11. Explicitly rejected v3 designs
1. LLM as final BUY/WAIT/SELL authority.
2. `NO_TRADE -> REDUCE` because a holding exists.
3. One generic confidence field.
4. Source-level polarity for mixed source documents.
5. A second independent quality truth store beside DataHub.
6. A second freeze path outside unified freeze.
7. Market rules inferred only from symbol shape.
8. Global A-share T+1/100-share assumptions.
9. Auto-tuning from one Xiaomi benchmark.
10. Persisting raw hidden reasoning.
11. A generic backtest or Stock Connect fee formula inside the CNY-only paper
    ledger; actual broker receipts remain audit facts.
12. Legacy portfolio decision snapshots, future-close calibration, or impact
    graphs as alternate evidence/freeze/feedback authority.
