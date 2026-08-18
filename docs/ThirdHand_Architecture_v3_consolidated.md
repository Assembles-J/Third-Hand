# ThirdHand Backend Architecture v3

## 0. Status
This is the single authoritative v3 architecture document. It defines both the
target authority boundaries and the current implementation conformance; it
supersedes all earlier v1/v2 designs, amendments and duplicate v3 documents.

The paired `ThirdHand_v3_Roadmap_and_Ledger.md` is the authoritative delivery
ledger. A production observation is not considered a design change until both
documents are updated with the evidence, the intended authority boundary, and
acceptance tests. If a README, code comment, UI label, or deployment variable
conflicts with these two documents, these two documents win and the conflicting
text must be corrected in the same change.

The current repository already has strong production invariants around DataHub quality, provider lineage, DecisionPackage hashing, AI isolation, and unified freeze. v3 extends those mechanisms; it does not replace them with a parallel stack.

## 0.1 Current implementation conformance

| Area | Status | Code truth |
|---|---|---|
| Data, identity, events and canonical price/time | Complete | Instrument metadata, market-scoped regime, canonical snapshot and event gates are formal inputs. |
| Atomic evidence and deterministic aggregation | Complete | Fact/availability/conflict provenance, point-in-time Company Intelligence, versioned aggregation and semantic validation are persisted. |
| Decision semantics | Partial | Entry/Position actions and formal action authority exist. High-confidence deterministic adverse research may veto new BUY/ADD risk only; it never upgrades an action or creates REDUCE/EXIT. A traceable weekly snapshot is aggregated from completed daily bars; 60m/15m/5m inputs remain explicitly unavailable and ActionPolicy remains daily-only. |
| Market/execution adapters | Partial at the CNY-only scope | CN lot/T+1/fee and PositionLot FIFO are enforced at the ledger boundary. Sellable/locked quantity and read-only lot evidence feed the formal Context and execution precheck. HK Stock Connect retains HKD trading-price metadata and actual RMB broker-settlement receipts as audit facts. HK/US have no paper-execution path. |
| Decision continuity | Complete | Prior decision, entry-bound position episode, full-input audit change, versioned material fingerprint, cooldown/review fields and position age are persisted. Only a strategic fingerprint transition or a hard gate/position-state transition may replace the prior formal action. ExecutionPrecheck rejects fills before `cooldown_until`; the deterministic runtime promotes `review_after` into a separately audited decision-refresh obligation. |
| Model policy and audit | Complete for configured-provider bounded recovery | Atomic prompt projection, Flash/Pro routing, schema/semantic checks, hashes, usage and retry traces are persisted. The finite recovery graph is Flash -> Pro thinking -> Pro non-thinking structured: a schema/semantic failure promotes the next tier, while exhausted empty-content or truncation failures use the structured tier. A generic multi-provider capability registry and a provider-specific maximum-reasoning capability tier are deliberately not implemented. |
| Feedback | Complete as an audit dataset | Frozen decision/execution lineage, actual-vs-hypothetical outcomes and read-only policy-version export exist; there is no automatic tuning. |

The target diagram below is deliberately broader than the current formal action
path. The current path is `DecisionContext -> EvidenceEngine -> ActionPolicy ->
Atomic Evidence -> ResearchAssessment -> DecisionArbiter -> DecisionContinuity
-> formal_action`. Candidates are frozen before Atomic Evidence is built;
the snapshot has no direct sizing or execution authority. `ResearchAssessment`
has one explicit, bounded authority: sufficiently
evidenced ADVERSE research can veto a new BUY/ADD risk. It cannot upgrade an
action, create REDUCE/EXIT, or bypass a hard gate; AI has no formal action path.

## 0.2 Production verification record and current execution gap

On 2026-08-18, an isolated SQLite test was executed inside the deployed API
container for artifact `GIT_COMMIT=1b7bc47b3a49a5f4e5eaed1a5c8cb17d94299592`.
It proved the ledger contract: a same-day CN BUY creates a `PENDING_T1` lot with
zero sellable quantity; a same-day SELL is rejected with
`paper_t1_unsellable_quantity`; the same SELL succeeds on the next trading day.
This is a verification of the deployed artifact, not a production-account write.

The production paper ledger from the same session also showed the gap that this
document now governs: after morning CN buys, the scheduler repeatedly generated
REDUCE/EXIT execution attempts during the same day and the ledger rejected them
at the final boundary. The final ledger result is correct, but the preceding
decision, sizing, scheduling and UI behavior is not conformant with this
architecture. A historical after-session paper fill was also observed. Until
the requirements in section 6.1 are met, paper execution is an active safety
gap, not a completed Phase 5 capability.

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

### Post-entry coherence

A static risk fact already present when an entry is accepted cannot become a
standalone `REDUCE` merely because the account changes from FLAT to HOLDING.
For an unchanged policy EvidenceSnapshot `E`, a successful `BUY` may transition
to `HOLD`, but not directly to `REDUCE` or `EXIT`. Position reduction requires
an explicit position-cap breach, hard invalidation, or a separately versioned
post-entry deterioration/threshold-crossing fact. Baseline risk remains a
deterministic sizing input and audit fact.

### Confidence
Split:
- evidence confidence
- research conviction
- decision confidence

### Decision memory
Store:
`prior_decision_id`, `episode_id`, `last_action`, `position_age`,
`input_changed`, `material_fingerprint`, `material_change_components`,
`material_change`, `material_change_reason`, `cooldown_until`, `review_after`,
and invalidation conditions.

`input_changed` records a complete frozen-input hash difference for audit; it is
not itself permission to replace an existing formal action. The versioned
`material_fingerprint` contains only strategic state: hard action gates,
position state/quantity, enabled plan contract, invalidation threshold crossing,
daily technical state, risk and market-regime state, policy-eligible events and
the bounded adverse-research veto. Quote refresh timestamps and price movement
within the same threshold state therefore preserve continuity. The precise
changed fingerprint components are persisted whenever a new episode is allowed.

`cooldown_until` is enforced at `ExecutionPrecheck` against the independently
observed fill quote. `review_after` is not a trade: when due, it authorizes a
new formal decision generation with the lineage reason `decision_review_due`.
The runtime keeps review obligations distinct from unexecuted decision fills so
an expired review cannot be mistaken for an executable order.

### Position episode binding

The first executed BUY of an open paper position creates an immutable
`paper_position_episodes` record. It binds `entry_decision_id`, the Atomic
Evidence snapshot hash, the ResearchAssessment hash, frozen risk/technical/
market/event state and the observed entry price to `episode_id`. ADD orders
cannot replace that record; a full EXIT closes it. `paper_account()` projects
the active record into `PositionSnapshot`, and DecisionContinuity reuses that
entry `episode_id` after FLAT becomes HOLDING. This makes the position's origin
an explicit, durable policy input rather than an inference from the latest
report.

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

### 6.1 Paper-execution safety contract (active remediation)

The paper ledger is the final, transactional enforcement boundary. It is not the
first place at which an impossible order may be discovered. For every executable
CN position decision, the following rules are mandatory:

1. `DecisionContext.PositionSnapshot` must contain total quantity,
   `sellable_quantity`, `locked_quantity`, and the earliest next eligible sell
   time derived from `PositionLot`. These values are deterministic ledger facts;
   they are never LLM inputs with authority.
2. `ExecutionPrecheck` runs before sizing and returns structured reason codes.
   It must validate instrument market, exchange calendar, market session,
   independently observed quote timestamp, quote freshness, cooldown and
   sellability. `execute_paper_trade` repeats the essential checks
   transactionally as defence in depth.
3. For `REDUCE` and `EXIT`, sizing may propose no more than sellable quantity.
   If sellable quantity is zero, the report is non-executable with a T+1 reason
   and `next_eligible_sell_at`; it must not create a zero-quantity SELL attempt.
4. A T+1-deferred decision is a scheduled deferral, not a skipped execution. It
   may be reconsidered at the next eligible CN session, after a fresh decision
   and a fresh in-session quote. It must not write duplicate skip logs each
   scheduler interval.
5. A BUY/ADD may fill later in the same CN session only when all execution
   checks pass. T+1 limits the newly acquired lot's sellability; it does not
   impose a universal next-day BUY rule. Existing settled lots remain sellable.
6. Closed-market manual runs may generate research, reports and snapshots, but
   may not create a paper fill. A fill requires a trading day, the instrument's
   open session and an in-session, fresh observed quote.
7. Account and API output must expose aggregate sellable/locked quantity and
   read-only PositionLot details. A date rollover must be reflected in the
   derived display without requiring a failed or successful SELL to mutate the
   lot first.
8. Scheduler status is operational audit data and must be recoverable from
   persisted runs after process restart. `paper_trading_enabled` gates every
   automatic paper fill; `DECISION_SHADOW_MODE` is a research-report setting and
   is not a paper-trading safety switch.

The product boundary is equally explicit: ThirdHand does not connect to a
broker, submit a real order, hold broker credentials, or promise returns.
Paper execution is a simulated CNY ledger only. Any UI, README or deployment
text that says "no automatic order" must state whether it refers to real orders,
paper fills, or both.

Release acceptance for this contract requires:

- a same-day BUY followed by REDUCE/EXIT produces one explainable T+1 deferral,
  no paper SELL attempt and no duplicate skip logs;
- a mixed inventory sells only its already-settled lots on the same day;
- the next eligible session recalculates sellability before the UI, sizing and
  scheduler read it;
- closed-session, stale-quote and out-of-session-quote executions are blocked;
- restart recovery reports the latest persisted paper run instead of `never_run`;
- deployed-container tests cover all of the above without touching production
  account data.

### 6.2 Approved implementation design for the paper-execution remediation

This section is the coding contract for the active remediation. Implementations
may refactor internal names, but may not change the data ownership, state
transitions or externally visible semantics below without first amending this
document and the paired ledger.

#### Read models and ownership

`PortfolioStore` remains the owner of the transactional paper ledger. Add a
read-only `PaperPositionState` projection, built from `paper_trading_positions`,
`paper_position_lots`, `InstrumentMetadata` and the market calendar:

```text
symbol, market, total_quantity, sellable_quantity, locked_quantity,
next_eligible_sell_at, lots[], calculated_at
```

`PositionLot` gains a persisted `sellable_at` timestamp. A CN BUY writes it as
the next CN trading session open after `acquired_at`; non-CN values remain
unsupported for paper execution. The projection derives current sellability
from `sellable_at <= calculated_at`; a GET request must never need to mutate a
lot merely to display the next-day state. Migration/backfill derives
`sellable_at` from each existing CN lot's `acquired_at` and `market`; an
unreconcilable historical lot remains explicitly non-sellable.

`DecisionContext.PositionSnapshot` adds nullable, backward-compatible fields:
`sellable_quantity`, `locked_quantity` and `next_eligible_sell_at`. The context
builder obtains them only from `PaperPositionState`; generic research contexts
without a paper account retain `None`. `PositionSizingResult` adds
`execution_disposition` (`ready`, `deferred_t1`, `blocked`, or
`not_applicable`) and `max_executable_quantity`. Existing `status` remains for
wire compatibility during the migration.

#### Precheck and sizing interfaces

Split the present boolean precheck into two deterministic calls:

```text
preflight_for_sizing(context, action, position_state, now)
    -> ExecutionConstraint(disposition, reason_codes, max_quantity,
                           next_eligible_at)

precheck_fill(report, action, quote, live_position_state, now, calendar)
    -> ExecutionConstraint(disposition, reason_codes, max_quantity,
                           next_eligible_at, quote_observed_at)
```

`ExecutionConstraint` is the single typed result used by sizing, scheduler
audit and API serialization. `allowed` is represented by `disposition=ready`;
T+1 is represented by `deferred_t1`, not by an exception. `blocked` is reserved
for a permanent or currently non-deferrable failure (metadata, currency, lot,
missing/stale quote, cooldown, closed session, or action gate). The old
`validate_daily_execution` becomes a compatibility wrapper over
`precheck_fill` and is removed only after all callers migrate.

The orchestrator invokes `preflight_for_sizing` before `PositionSizingEngine`.
For `REDUCE` and `EXIT`, the sizing engine uses
`min(total_quantity, constraint.max_quantity)` as its only sellable inventory.
Zero sellable inventory returns `deferred_t1` with a zero suggested quantity;
it does not create an executable operation item. Immediately before a fill, the
scheduler obtains a fresh live projection and re-runs `precheck_fill`; the
storage transaction independently enforces the same maximum as defence in
depth. This protects against a stale report, concurrent scheduler cycle or
position change.

#### Calendar and quote gate

`TradingCalendarService` is injected into `precheck_fill` using the instrument
market, not a global CN assumption. A paper fill requires all of:

1. the current instant is an open exchange trading minute;
2. the quote has an aware observed timestamp inside that same session;
3. the quote is strictly later than the report's input quote and no older than
   the configured execution freshness limit;
4. cooldown, action gate, lot, currency, fee and live sellability checks pass.

The manual endpoint may still force analysis and report generation when closed,
but it passes `execution_enabled=False` to the runtime. It must not use
`active or symbols` to bypass the fill gate. The scheduler cannot bypass this
gate, regardless of trigger or `allow_when_disabled` compatibility arguments.

#### Deferral persistence and idempotency

Add migration `0017_paper_execution_safety_contract` with:

```text
paper_position_lots.sellable_at TEXT NULL

paper_execution_deferrals(
  decision_id TEXT PRIMARY KEY,
  symbol TEXT NOT NULL,
  action TEXT NOT NULL,
  requested_quantity REAL NOT NULL,
  max_executable_quantity REAL NOT NULL,
  reason_code TEXT NOT NULL,
  next_eligible_at TEXT NOT NULL,
  state TEXT NOT NULL,              -- active | released | superseded | cancelled
  created_at TEXT NOT NULL,
  resolved_at TEXT NULL,
  detail TEXT NOT NULL
)
```

Creation is idempotent by `decision_id`. A scheduler records one simulation
stage with terminal state `deferred_t1` and upserts this table; it does not call
`record_paper_skip`. The pending-execution query selects only transaction
actions and excludes active deferrals until `next_eligible_at`. A newer formal
decision for the same symbol marks an older active deferral `superseded`.
Successful fills mark it `released`; an explicit cancellation marks it
`cancelled`. Existing `paper_trading_logs` preserve immutable historical skip
records and are not rewritten.

#### API and operational state

Extend the existing account response position with `sellable_quantity`,
`locked_quantity` and `next_eligible_sell_at`; add read-only endpoints:

```text
GET /v1/paper-trading/positions/{symbol}/lots
GET /v1/paper-trading/execution-deferrals?symbol=&state=
```

The paper status endpoint reads the newest persisted `simulation_runs` record
at startup and whenever its in-memory state is empty. It may expose
`state_source` (`memory` or `persisted`) so a restart cannot appear as
`never_run` when the audit database contains prior runs.

#### Delivery order and tests

1. Add pure calendar/lot projection helpers and their tests; do not change
   runtime behavior yet.
2. Add the additive migration, API response fields and read-only lots/deferral
   routes; verify legacy database backfill and no GET-side writes.
3. Add `ExecutionConstraint`, preflight-before-sizing and report serialization;
   keep the old runtime precheck as a wrapper.
4. Migrate scheduler and manual execution to live fill precheck plus idempotent
   deferral persistence; remove the closed-market fill fallback.
5. Enable the new path only after a deployed-container test confirms no
   production database mutation outside an intentional paper run.

Required regression cases include: same-day full lock, mixed old/new lots,
Friday-to-next-session settlement, closed market, lunch break, stale quote,
quote outside session, restart status recovery, repeated scheduler cycles,
superseded deferral, legacy lot backfill and concurrent fill attempts.

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
