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

`ThirdHand_v3_Strategy_AI_Lab_Design.md`,
`ThirdHand_v3_Fullstack_Technical_Roadmap.md`, and
`ThirdHand_v3_Personal_Universe_Review_Watchlist_UX_Design.md` are approved
subordinate design specifications for the next v3 delivery stages. They may add
implementation clarity, but they may not override the authority, safety or
status contracts in this document and the paired ledger. Stable decisions from
those documents are promoted here before runtime authority changes are accepted.

The current repository already has strong production invariants around DataHub quality, provider lineage, DecisionPackage hashing, AI isolation, and unified freeze. v3 extends those mechanisms; it does not replace them with a parallel stack.

## 0.1 Current implementation conformance

| Area | Status | Code truth |
|---|---|---|
| Data, identity, events and canonical price/time | Complete, with live acceptance still active for the newest financial/event wiring | Instrument metadata, market-scoped regime, canonical snapshot and event gates are formal inputs. Report-period currentness and persistent event lifecycle are implemented, while the latest deployed Xiaomi/HK acceptance remains tracked separately. |
| Atomic evidence and deterministic aggregation | Complete | Fact/availability/conflict provenance, point-in-time Company Intelligence, versioned aggregation and semantic validation are persisted. |
| Decision semantics | Complete for the current versioned multi-timeframe authority; StrategyProfile / `SWING_V1` is implemented and product-visible | Entry/Position actions and formal action authority exist. High-confidence deterministic adverse research may veto new BUY/ADD risk only; it never upgrades an action or creates REDUCE/EXIT. Weekly/daily plus governed 60m/15m/5m Evidence feed a versioned asymmetric Multi-Timeframe ActionPolicy. Lower timeframes may preserve, delay or downgrade new risk but may not manufacture BUY/ADD or create REDUCE/EXIT by themselves. |
| Market/execution adapters | Partial at the CNY-only scope | CN lot/T+1/fee and PositionLot FIFO are enforced at the ledger boundary. Sellable/locked quantity and read-only lot evidence feed the formal Context and execution precheck. HK Stock Connect retains HKD trading-price metadata and actual RMB broker-settlement receipts as audit facts. HK/US have no paper-execution path. Deployed Phase 5 acceptance remains open. |
| Decision continuity | Complete | Prior decision, entry-bound position episode, full-input audit change, versioned material fingerprint, cooldown/review fields and position age are persisted. Only a strategic fingerprint transition or a hard gate/position-state transition may replace the prior formal action. Approved timeframe states participate in the material fingerprint while raw timestamp/hash noise does not. ExecutionPrecheck rejects fills before `cooldown_until`; the deterministic runtime promotes `review_after` into a separately audited decision-refresh obligation. |
| Model policy and audit | Complete for configured-provider bounded recovery; live provider acceptance remains open | Atomic prompt projection, Flash/Pro routing, schema/semantic checks, hashes, usage and retry traces are persisted. The finite recovery graph is Flash -> Pro thinking -> Pro non-thinking structured. A generic multi-provider capability registry and a provider-specific maximum-reasoning capability tier are deliberately not implemented. |
| Feedback | Complete as an audit dataset | Frozen decision/execution lineage, actual-vs-hypothetical outcomes and read-only policy-version export exist; there is no automatic tuning. N3 Evaluation consumes this foundation through a read/measurement plane; AI calibration remains N6. |
| Evaluation | N3.1-N3.6 are `BACKEND_READY`; N3.7 is `ANDROID_READY`; end-to-end acceptance pending | Immutable experiment identity remains bound to an exact `ExperimentUniverseSnapshot`; OutcomeResolver, StrategyEvaluation and BenchmarkPolicy enforce frozen membership and point-in-time market history. N3.6 exposes the GET-only `/v1/lab` API, and N3.7 adds an Android Strategy Lab that reads those immutable DTOs through a dedicated repository/state/screen boundary. The first visible entry is intentionally incremental under Management rather than a numeric-tab navigation rewrite. Android renders loading/empty/error/insufficient/unavailable states and reason codes without recomputing Evaluation metrics, refreshing providers, mutating Personal Universe membership or changing trading authority. |
| Personal universe / review cadence | Designed; implementation pending | Positions and existing Watchlist data become the primary daily-use universe; Discovery is optional and bounded. Universe membership, review permission, analysis depth and trading authority are separate policy owners. |

The current formal action path is:

```text
DecisionContext
  -> EvidenceEngine
  -> ActionPolicy
  -> Atomic Evidence
  -> ResearchAssessment
  -> DecisionArbiter
  -> Multi-Timeframe ActionPolicy
  -> DecisionContinuity
  -> formal_action
  -> ExecutionPrecheck
```

Candidates are frozen before Atomic Evidence is built; the snapshot has no
direct sizing or execution authority. `ResearchAssessment` has one explicit,
bounded authority: sufficiently evidenced ADVERSE research can veto a new
BUY/ADD risk. It cannot upgrade an action, create REDUCE/EXIT, or bypass a hard
gate; AI has no formal action path.

The daily product scope is governed separately from this formal action chain:

```text
PersonalUniversePolicy -> ReviewPolicy -> AnalysisDepthPolicy -> Formal Decision
```

The first three layers decide who deserves attention, whether a review is due,
and how much research may run. They do not grant BUY/ADD/REDUCE/EXIT authority.

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
- AI forbidden from changing deterministic rule status, buy zone, position quantity, hard stop, and execution permission in the Formal Decision System.
- one analysis authority time (`analysis_started_at`).
- versioned multi-timeframe authority that is asymmetric toward new risk.
- DecisionContinuity that excludes raw refresh noise from material-change permission.
- all open positions remain in the personal risk-monitoring universe regardless of watchlist/discovery limits.
- Personal Watchlist membership is user-owned attention metadata, not trading authority.
- Experiment/Evaluation universe membership remains frozen and independent from mutable Personal Watchlist state.

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
        (bounded advisory)           (quality, availability,
                 |                    event dates, price/time,
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
                               |
                               v
                  Multi-Timeframe ActionPolicy
                        /              \
                       v                v
                EntryDecision     PositionDecision
                       \                /
                        +--------------+
                               |
                               v
                     Decision Continuity
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

`StrategyProfile` / `SWING_V1` is already first-class. The next v3 extension is the
read-only Evaluation plane, beginning with immutable experiment identity and a
frozen ExperimentUniverseSnapshot; the later AI Strategy Lab consumes frozen
Evidence but cannot mutate the Formal Decision System. Section 12 defines that
boundary.

The personal-workflow orchestration that decides whether the formal chain should
run is deliberately outside formal action authority:

```text
Portfolio + Watchlist + optional Discovery
                  |
                  v
        PersonalUniversePolicy
                  |
                  v
             ReviewPolicy
                  |
                  v
        AnalysisDepthPolicy
                  |
          only when authorized
                  v
        Formal Decision System
```

## 3. Authority boundaries

### Deterministic authority
The LLM must never own in the Formal Decision System:
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

A separately isolated AI Strategy Lab may own **paper intent** inside its own
experiment account, but never canonical facts, RiskPolicy, Paper Broker
execution truth, or the production Formal ActionPolicy. Lab authority is
specified in section 13.

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

These formal confidence layers are not equivalent to the AI Strategy Lab's
probability calibration. A Lab probability must bind to a testable forecast
contract as defined in section 13.

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
approved weekly/daily/60m/15m/5m timeframe states, risk and market-regime state,
policy-eligible events and the bounded adverse-research veto. Quote refresh
timestamps, raw bar timestamps, raw prices and source hashes therefore do not
by themselves create permission for an action flip. The precise changed
fingerprint components are persisted whenever a new episode is allowed.

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
- MultiTimeframeActionPolicy

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
  state TEXT NOT NULL,
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

Current formal timeframe authority is versioned and asymmetric:
- weekly/daily = strategic structure;
- 60m = position/setup management;
- 15m/5m = execution timing;
- realtime = hard risk/execution trigger only.

Completed bars now feed a governed 60m/15m/5m Evidence plane. The approved
Multi-Timeframe ActionPolicy runs after deterministic research/DecisionArbiter
and before DecisionContinuity. Its rules are:

- lower timeframes may preserve an already-permitted BUY/ADD when confirmation is present;
- missing/stale/conflicted lower-timeframe state cannot fabricate PASS and may delay new risk;
- 60m weakness, or joint 15m+5m weakness, may delay/downgrade new risk;
- lower-timeframe strength cannot upgrade WAIT/BLOCKED/HOLD into BUY/ADD;
- lower-timeframe weakness alone cannot create REDUCE/EXIT;
- bullish intraday state cannot override higher-timeframe structural conflict;
- only discrete approved timeframe states participate in DecisionContinuity material fingerprints; raw bar timestamps, prices, retrieval times and source hashes do not.

Technical anchor lifecycle/rebase remains strategy-specific and is deferred to
an explicit StrategyProfile contract rather than being added as another global rule.

## 9. Model policy
- Fast/non-thinking model: explain already deterministic conclusions.
- Default reasoning model: compact Atomic Evidence interpretation.
- Deep model escalation: complex unstructured disclosures, material conflicts, ambiguous accounting/guidance, or validator failure.
- Maximum reasoning/capability tiers remain bounded and provider-contract dependent rather than assumed globally.

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

No automatic production policy tuning until labels and offline/forward evaluation
are reliable. Feedback is the raw substrate for the Evaluation System, not a
write path back into ActionPolicy.

## 11. Explicitly rejected v3 designs
1. LLM as final BUY/WAIT/SELL authority in the Formal Decision System.
2. `NO_TRADE -> REDUCE` because a holding exists.
3. One generic confidence field.
4. Source-level polarity for mixed source documents.
5. A second independent quality truth store beside DataHub.
6. A second freeze path outside unified freeze.
7. Market rules inferred only from symbol shape.
8. Global A-share T+1/100-share assumptions.
9. Auto-tuning from one Xiaomi benchmark or one profitable experiment.
10. Persisting raw hidden reasoning.
11. A generic backtest or Stock Connect fee formula inside the CNY-only paper ledger; actual broker receipts remain audit facts.
12. Legacy portfolio decision snapshots, future-close calibration, or impact graphs as alternate evidence/freeze/feedback authority.
13. A naked AI "reliability 72%" without a defined forecast event, sample size and uncertainty.
14. Shared cash/positions between independent AI experiments.
15. Letting an AI Strategy Lab agent write the paper ledger directly or bypass RiskPolicy/ExecutionPrecheck/Paper Broker.
16. Automatically promoting LAB performance into Formal ActionPolicy authority.
17. Marking a user-facing capability `PRODUCT_DONE` when only backend/domain code exists and the required API/Android observability surface is absent.
18. Treating mutable Personal Watchlist membership as an Experiment/Evaluation universe.
19. Treating scheduler wake-up as permission to rerun full research.
20. Dropping an open position from monitoring because a watchlist/discovery limit was reached.
21. Treating Discovery membership as BUY permission or automatically promoting Discovery into Watchlist.

## 12. StrategyProfile architecture

Strategy becomes a first-class policy composition boundary instead of letting
all Evidence compete in one global scoring system.

Target model:

```text
StrategyProfile
  strategy_id
  strategy_version
  holding_horizon
  strategic_timeframes
  setup_timeframes
  timing_timeframes
  risk_timeframes
  allowed_evidence
  authority_matrix
  entry_policy
  position_policy
  exit_policy
  risk_policy
  review_policy
  universe_policy
  sizing_policy
  evaluation_policy
  outcome_policy
```

Every frozen formal decision must eventually persist `strategy_id`,
`strategy_version` and the policy versions that composed it.

The first explicit production profile is `SWING_V1`, targeting roughly 3-20
trading-session episodes. Its starting authority contract is:

| Evidence | SWING_V1 role |
| --- | --- |
| weekly | strategic structure |
| daily | primary trend/setup |
| 60m | setup maturity / position management |
| 15m/5m | execution timing |
| realtime | hard risk/execution only |
| fundamentals | quality/risk context |
| financial currentness | historical trend + current confirmation |
| CorporateEvent | deterministic risk gate |
| market regime | strategic context |
| news | research context |
| order flow | timing evidence only until separately evaluated |
| AI interpretation | research/explanation only in Formal System |

Do not implement VALUE/POSITION/SWING/SHORT/INTRADAY simultaneously and do not
collapse them into a universal weighted score. Additional strategies require
separate StrategyProfile versions.

## 13. AI Strategy Lab authority

The AI Strategy Lab is a parallel experiment system, not an alternate production
arbiter.

```text
Frozen EvidenceSnapshot
        |                         |
        v                         v
 Formal Decision Engine      AI Strategy Agent
        |                         |
 Formal Decision             AI Paper Intent
        |                         |
        +-----------+-------------+
                    v
                RiskPolicy
                    v
                Paper Broker
                    v
                  Ledger
                    v
                Evaluation
```

Inside an isolated experiment account, an AI agent may form simulated
`BUY/WAIT/HOLD/ADD/REDUCE/EXIT` intents. The following remain deterministic and
outside AI authority:

- experiment account cash/position truth;
- market session/calendar;
- quote freshness and observed time;
- lot/tick/T+1/sellability;
- fees/slippage and maximum executable quantity;
- RiskPolicy and default SizingPolicy;
- final Paper Broker fill.

Every AI probability must bind to a testable `ForecastContract`, for example a
10-session `TARGET_BEFORE_STOP` event. A naked model confidence percentage is
not an evaluation contract.

Each experiment has an isolated ledger and immutable identity including model,
prompt, Evidence schema, StrategyProfile, ExperimentUniversePolicy, RiskPolicy,
SizingPolicy and execution-policy versions. Personal Watchlist membership is not
an experiment input unless an experiment definition explicitly freezes a
versioned copy as its declared sample universe; no silent linkage is allowed.
A material version change starts a new experiment result set rather than
silently pooling history.

Historical replay must be point-in-time correct. Live forward paper trading is
the preferred reliability evidence because the agent cannot observe future data.

AI maturity is explicit and non-automatic:

```text
LAB -> OBSERVED -> VALIDATED -> ADVISORY
```

`ADVISORY` is the first production ceiling. It may display an opinion beside the
Formal Decision but may not mutate Formal ActionPolicy.

## 14. Evaluation and calibration

The Evaluation System measures both economic performance and forecast quality.
It must not equate win rate with reliability.

Minimum economic metrics:
- total and benchmark-relative return;
- max drawdown;
- win rate;
- average win/loss and payoff ratio;
- expectancy;
- Profit Factor;
- max consecutive losses;
- holding duration;
- turnover;
- fees/slippage;
- MFE/MAE;
- regime and action-type breakdowns.

Minimum forecast/calibration metrics:
- confidence bucket event rate;
- Brier score;
- Expected Calibration Error or a versioned equivalent;
- sample size and sample-quality state;
- uncertainty/confidence interval.

The UI must not display a single reliability percentage without its event
contract, sample count and uncertainty. Insufficient samples must be labeled
explicitly rather than rendered with false precision.

Benchmarks should include, where applicable, buy-and-hold, equal-weight eligible
universe, `FORMAL_SWING_V1`, and a neutral/random diagnostic baseline.

Evaluation has no automatic write path back into production policy. Promotion
requires an explicit version change, acceptance tests and review.

## 15. Full-stack delivery and product observability

A user-facing milestone is not complete merely because backend/domain code
exists. Delivery states are:

```text
DESIGNED
  -> BACKEND_READY
  -> API_VISIBLE
  -> ANDROID_VISIBLE
  -> OBSERVABLE
  -> PRODUCT_DONE
```

For every user-facing capability, `PRODUCT_DONE` requires the complete path when
applicable:

```text
Domain/Persistence
  -> Application Service
  -> API/DTO
  -> Android Repository
  -> ViewModel immutable UiState
  -> Screen/component
  -> loading/empty/error/stale/degraded states
  -> audit/reason visibility
  -> end-to-end acceptance
```

Backend-only work may be marked `BACKEND_READY`, but not `PRODUCT_DONE`.
Likewise, a decorative Android card disconnected from authoritative data is not
complete.

The next-stage full-stack sequence is governed by
`ThirdHand_v3_Fullstack_Technical_Roadmap.md`. The core visible surfaces are:

- Decision Workspace: Formal Decision, SWING_V1, timeframe authority, company/event state, risk/T+1, AI research, later AI Lab opinion, What Changed;
- Watchlist: positions + user-selected symbols as the primary personal research universe, with review state and optional Discovery;
- Lab: experiment state, PnL, benchmark, drawdown, sample quality and calibration;
- Review: good/bad entries/exits, missed opportunities, over/under-confidence, regime/data/execution failures;
- Home: only the day's material changes, review obligations, risk changes, events and Formal-vs-AI disagreements.

The Android and backend codebases should be modularized incrementally around
these vertical slices rather than through a big-bang rewrite.

## 16. Personal Universe and Review authority

The daily-use research scope is explicitly different from the Evaluation
experiment universe.

### PersonalUniversePolicy

The personal universe is composed from:

```text
Portfolio + Watchlist + optional Discovery
```

Rules:

1. Every open position is always included for risk monitoring.
2. Watchlist is durable user-owned attention state and may carry priority/note
   metadata. It never grants BUY/ADD permission.
3. Discovery is optional, bounded and disabled by default. A zero-slot setting is
   valid. Discovery remains research-only until explicit user promotion.
4. Personal Watchlist membership must not silently mutate an ExperimentUniverse.
5. Existing deterministic candidate rotation may remain for experiments and may
   be reused as a Discovery mechanism, but it is not the user's primary daily
   research universe.

### ReviewPolicy

Scheduler cadence and analysis permission are different concepts. The governed
review modes are:

```text
NO_REVIEW
GUARD_ONLY
POSITION_REVIEW
FULL_RESEARCH
```

`GUARD_ONLY` is deterministic, cheap monitoring for hard invalidation,
CorporateEvent change, safety-relevant data-quality change, risk transition and
execution/T+1 obligations. It does not imply a full AI/company-research call.

For `SWING_V1`, a position at target/capped exposure with no strategic
MaterialChange remains `GUARD_ONLY` during the session. Routine full research is
budgeted to at most once per symbol per trading day; material events or explicit
user requests may override the routine budget only with an audited reason.

The authority split is canonical:

```text
UniversePolicy      -> who deserves attention
ReviewPolicy        -> whether a review is due
AnalysisDepthPolicy -> how deep research may run
ActionPolicy        -> whether a trading action is permitted
```

### Android/product requirement

Watchlist is a first-class user-facing surface, not an admin-only or buried
backend feature. The first implementation slice must expose add/edit/delete,
priority and current review status from Android and must include loading, empty,
stale/degraded and error states. Discovery on/off, slot count and cadence must
also be user-configurable when the Discovery slice ships.

The detailed API, Android information architecture and dense trading-utility UI
contract are defined in
`ThirdHand_v3_Personal_Universe_Review_Watchlist_UX_Design.md`.
