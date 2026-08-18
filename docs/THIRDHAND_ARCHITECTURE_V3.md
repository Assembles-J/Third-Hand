# ThirdHand Backend Architecture v3

Status: implementation baseline after the Xiaomi T4-E benchmark and audit of the current `pengpengno/Third-Hand` backend.

## 1. Purpose

ThirdHand v3 keeps the current deterministic decision pipeline, data-quality checks, persistence, and audit trail, but separates four responsibilities that are currently too easy to mix:

1. source facts and freshness;
2. research interpretation;
3. deterministic aggregation and hard gates;
4. entry/position action and execution constraints.

The redesign is evolutionary, not a rewrite. Existing `DecisionContext`, deterministic policy, execution precheck, evidence audit, and saved decision reports remain the migration anchors.

## 2. Target pipeline

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
                  Freshness + Consistency Gate
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
        (default / escalation)       (availability, price/time,
                 |                    event, instrument rules)
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
                   Sizing / Lot / FX / Fees
                               |
                               v
                        Decision Report
                               |
                               v
                    Feedback / Review
```

## 3. Authority boundaries

### Deterministic authority

LLMs must never own:

- canonical price or authoritative market timestamp;
- whether a required fact is present, missing, stale, or conflicted;
- market, exchange, currency, lot, tick, fee, settlement or sellability rules;
- event date and event distance;
- hard execution gates;
- formal dimension/fundamental/research aggregation;
- final entry/position action;
- position sizing, cash checks, sellable quantity or hard stops;
- hashes, persistence identity or audit lineage.

### AI authority

AI may:

- interpret compact atomic evidence;
- classify ambiguous qualitative disclosures;
- summarize management guidance and non-standard events;
- identify counter-evidence, conflicts and unresolved ambiguity;
- produce cited narrative research.

AI output is always advisory and validator-gated.

## 4. Canonical data model

### 4.1 CanonicalInputSnapshot

One coherent analysis-time view built before formal rules run:

- `analysis_started_at`;
- instrument identity and market;
- canonical completed daily bar;
- executable quote when valid;
- display-only latest close when realtime is unavailable;
- market-specific regime/benchmark;
- corporate-event snapshot;
- account and position snapshot;
- freshness, conflicts and missing capabilities.

A display fallback must never silently become an execution quote.

### 4.2 AtomicFactRecord

Minimum fields:

```text
fact_id
symbol
market
domain
dimension
metric
value
unit
period_start / period_end
comparison_type
source_evidence_id
source_timestamp
observed_at
freshness_status
polarity
materiality
comparison_adequacy
confidence
provenance_hash
```

A source document may yield multiple facts with different polarity.

### 4.3 EvidenceSnapshot

Contains atomic facts plus deterministic availability, conflict, technical, event, instrument and market-context snapshots. It is hashed and versioned.

### 4.4 ResearchAssessment

```text
fundamental_dimensions
aggregate_fundamental_bias
technical_state
event_state
expectation_state
market_context
research_bias
evidence_confidence
research_conviction
supportive_fact_ids
adverse_fact_ids
neutral_material_fact_ids
unresolved_fact_ids
invalidation_conditions
aggregation_policy_versions
model_run_ids
```

### 4.5 Decision semantics

Research bias is not an action.

Entry actions:

- `BUY`
- `WAIT`
- `BLOCKED`

Position actions:

- `HOLD`
- `ADD`
- `REDUCE`
- `EXIT`
- `BLOCKED`

The system must not map a generic no-entry state into `REDUCE` merely because a position exists.

### 4.6 Confidence

Keep three independent fields:

- `evidence_confidence`: source quality/completeness/freshness;
- `research_conviction`: directional strength of the evidence;
- `decision_confidence`: certainty of the actual action after hard gates.

A valid result can be `research_bias=NEGATIVE`, `research_conviction=LOW`, `entry_decision=WAIT`, `decision_confidence=HIGH`.

## 5. MarketAdapter

Market-specific behavior must be explicit, not inferred ad hoc throughout the codebase.

Minimum contract:

```text
market
exchange
timezone
trading_currency
lot rule
price tick rule
fee schedule
settlement rule
sellability rule
calendar/session rules
benchmark/regime universe
```

Initial adapters: `CN_A`, `HK`, `US`.

Current symbol-shape detection may remain as a compatibility resolver, but formal decisions should consume an `InstrumentSnapshot`/adapter result instead of re-inferring the market in every service.

## 6. Corporate events

Corporate events become first-class deterministic evidence. At minimum:

- earnings/results and result-board-meeting dates;
- dividend/ex-date;
- placement/rights issue;
- suspension/resumption;
- major capital transaction;
- material legal/regulatory event.

Before disclosure, a scheduled result event is `NEUTRAL_MATERIAL` directionally but may have `HIGH` event risk. A deterministic pre-event gate may block new risk without claiming the event is bearish.

## 7. Deterministic aggregation

The following policies are versioned code, not free-form LLM decisions:

- `FactPolarityPolicy`
- `DimensionAggregationPolicy`
- `FundamentalAggregationPolicy`
- `ResearchAggregationPolicy`
- `EventRiskPolicy`
- `DecisionArbiterPolicy`

The Xiaomi benchmark weights are benchmark-only. They demonstrate reproducibility; they are not production weights.

## 8. Technical authority

Technical state is decomposed into:

- trend structure;
- price location;
- momentum;
- volume state;
- support/resistance.

Timeframe authority:

- weekly/daily: strategic structure;
- 60m: position management;
- 15m/5m: execution timing;
- realtime: hard risk/execution trigger only.

Anchor lifecycle/rebase remains deferred until a strategy-specific contract is defined.

## 9. Decision memory

Formal continuity metadata:

```text
prior_decision_id
episode_id
last_action
position_age
material_change
material_change_reason
cooldown_until
review_after
invalidation_conditions
```

A changed recommendation must explain what changed.

## 10. Position lots and settlement

Use lot-level state for market-specific sellability:

```text
lot_id
symbol
market
currency
quantity
acquired_at
cost_basis
sellable_quantity
settlement_state
```

A-share T+1 rules must never be applied to HK/US instruments.

## 11. Model policy

- Fast/non-thinking model: explain already deterministic conclusions.
- Default reasoning model: compact Atomic Evidence interpretation.
- Deep reasoning escalation: complex source documents, material source conflicts, ambiguous accounting/guidance, or validator failure.
- Maximum reasoning: exceptional/manual escalation only.

Persist only observable runtime metadata: provider/model/settings, prompt/evidence hashes, latency, usage, final-content hash, validator result, retry/fallback path, and reasoning-content presence/length/hash if exposed. Never persist API keys or raw hidden reasoning.

## 12. Feedback

Feedback is auditable data before it is an optimization signal. Link each feedback event to the exact frozen decision/report and store user action, execution, actual outcome, hypothetical outcome, explicit feedback and review label. No automatic policy tuning in the first v3 release.

## 13. Explicitly rejected designs

1. `LLM -> BUY/WAIT/SELL` as formal authority.
2. Generic `NO_TRADE -> REDUCE` for held positions.
3. One generic confidence field.
4. Source-level polarity when a source contains opposing atomic facts.
5. A second independent quality truth system.
6. Market rules inferred only from symbol format at every call site.
7. Global A-share lot/T+1 assumptions.
8. Auto-tuning from one Xiaomi benchmark.
9. Persisting raw hidden reasoning.
