# ThirdHand v3 N3-N6 Evaluation and AI Lab Implementation Design

> **Status: DRAFT DESIGN — no runtime authority change.**
>
> This document turns the existing N3-N6 roadmap bullets into an implementation
> contract. It does not change Formal Decision, StrategyProfile, RiskPolicy,
> SizingPolicy, ExecutionPrecheck or Paper Broker authority.
>
> Canonical authority remains in `ThirdHand_Architecture_v3_consolidated.md` and
> canonical delivery status remains in `ThirdHand_v3_Roadmap_and_Ledger.md`.
> `ThirdHand_v3_Strategy_AI_Lab_Design.md` and
> `ThirdHand_v3_Fullstack_Technical_Roadmap.md` remain approved higher-level
> subordinate designs. Stable decisions accepted from this draft must be
> synchronized into the canonical pair before an implementation PR claims a new
> delivery state.

## 1. Purpose

ThirdHand already has a Formal Decision System, `SWING_V1`, frozen decision
lineage, Feedback audit data, paper-execution foundations and an Android
Decision Workspace. The next problem is no longer only "can the system make a
decision?" but:

1. was the decision useful after the observation window matured;
2. did execution behavior preserve or destroy the decision's value;
3. did the simulated account make money after costs and risk constraints;
4. can an AI strategy agent make independently testable forecasts;
5. can AI and Formal strategies be compared fairly on the same evidence;
6. are AI probabilities calibrated rather than merely persuasive-looking.

The N3-N6 chain is therefore:

```text
N3 Evaluation System
  -> score Formal SWING_V1 first
  -> establish immutable experiment/outcome contracts

N4 AI Strategy Lab Shadow
  -> AI answers the same frozen-evidence question
  -> paper intent + testable forecast only
  -> no fill

N5 AI Isolated Paper Trading
  -> validated AI intent enters deterministic risk/execution path
  -> one isolated account/ledger per experiment

N6 Calibration and Reliability
  -> evaluate forecast probabilities, sample quality and uncertainty
  -> never auto-promote production policy
```

The governing principle is:

```text
Build the referee before adding more players.
```

## 2. Hard ownership boundaries

### N3 owns evaluation, not trading authority

N3 may read frozen decisions, evidence lineage, outcomes, fills, fees, market
history and regime labels. It may not mutate Formal Action, StrategyProfile,
RiskPolicy, SizingPolicy, ExecutionPrecheck or Paper Broker state.

### N4 owns AI shadow intent, not fills

N4 may persist an AI `BUY/WAIT/HOLD/ADD/REDUCE/EXIT` intent and a forecast
contract. It cannot create a paper fill or mutate the Formal Decision.

### N5 owns experiment orchestration, not execution truth

N5 may route a validated AI intent toward the existing deterministic risk and
paper-execution stack. Paper Broker remains the only simulated fill authority.

### N6 owns probability evaluation, not policy promotion

N6 may compute calibration, sample quality, confidence intervals and regime
breakdowns. It cannot automatically modify a Formal Strategy or an AI agent.

## 3. Clarifications to the existing roadmap

This design intentionally resolves two overlaps in the earlier N3-N6 bullets.

### 3.1 Calibration belongs to N6

N3 defines a forecast-outcome envelope so later forecasts can be evaluated, but
N3 does **not** make Brier score, ECE or reliability UX part of its first product
acceptance. Those become N6 responsibilities after N4 has produced real,
versioned probability forecasts.

N3 acceptance is about Formal strategy evaluation: return, risk, benchmark,
action outcomes, execution attribution and sample integrity.

### 3.2 Isolated paper accounts are created in N5

N3 defines experiment identity and account references so the schema does not
need a redesign later. Actual isolated cash/position ledgers are created only in
N5 when an experiment is permitted to execute paper intents.

N3 `FORMAL_OBSERVATION` and `FORMAL_REPLAY` experiments therefore do not require
an AI paper account.

### 3.3 Personal Universe is not the Experiment Universe

The mutable daily-use Personal Universe introduced by the approved PUX design is
owned by positions, explicit Watchlist membership and optional Discovery. It may
change at any time as the user follows or removes symbols. Evaluation must never
read that mutable set dynamically as experiment membership.

Every experiment version therefore owns an immutable `ExperimentUniverseSnapshot`
that freezes the exact `(market, symbol)` members used by that experiment. The
experiment definition binds both the universe policy version and the snapshot
identity/hash. A later Watchlist add/remove, position close, Discovery promotion,
quote refresh or PersonalUniverse priority edit cannot change historical samples.

This is a selection-bias boundary, not trading authority:

```text
Personal Universe (mutable daily attention)
        X never used dynamically by Evaluation
ExperimentUniverseSnapshot (immutable experiment membership)
        -> OutcomeResolver
        -> StrategyEvaluation
        -> BenchmarkPolicy
```

For an equal-weight universe benchmark, the benchmark must use the same frozen
experiment snapshot (or another separately frozen, explicitly versioned benchmark
constituent snapshot). It may not query today's Watchlist or holdings.

## 4. Shared experiment identity

Every evaluation must resolve to one immutable experiment version.

Suggested model:

```text
ExperimentDefinition
  experiment_id
  experiment_version
  experiment_type
  status

  strategy_id
  strategy_version

  agent_id?                 # N4/N5 only
  agent_version?            # N4/N5 only
  model_provider?           # N4/N5 only
  model_name?               # N4/N5 only
  model_version?            # N4/N5 only
  prompt_version?           # N4/N5 only
  prompt_hash?              # N4/N5 only

  evidence_schema_version
  universe_policy_version
  universe_snapshot_id
  universe_snapshot_hash
  point_in_time_policy_version

  action_policy_version?
  timeframe_policy_version?
  risk_policy_version
  sizing_policy_version
  execution_policy_version

  outcome_policy_version
  benchmark_policy_version
  sample_quality_policy_version
  evaluation_policy_version

  initial_capital?
  started_at
  ended_at?
  created_at
```

`experiment_type` starts with:

```text
FORMAL_OBSERVATION
FORMAL_REPLAY
AI_SHADOW
AI_PAPER
```

Any material change to strategy, model, prompt, evidence schema, universe,
risk, sizing, execution assumptions, outcome rules or evaluation rules creates a
new experiment version. Results from different versions must never be silently
pooled.

The frozen membership record is a separate immutable object:

```text
ExperimentUniverseSnapshot
  universe_snapshot_id
  experiment_id
  experiment_version
  universe_policy_version
  captured_at
  members[]               # canonical (market, symbol), sorted + unique
  source_kind
  source_reference_hash?
  snapshot_hash
```

`ExperimentDefinition` cannot be persisted as a valid runnable experiment unless
its referenced universe snapshot exists, belongs to the same experiment/version,
matches `universe_policy_version`, and its deterministic hash matches
`universe_snapshot_hash`.

## 5. Point-in-time integrity

Evaluation is invalid if it consumes information that did not exist at the
simulated decision time.

The point-in-time contract forbids:

- revised financial data not yet available at decision time;
- later announcements or CorporateEvent lifecycle knowledge;
- future intraday/daily bars;
- later universe membership;
- future benchmark constituents where membership matters;
- later AI prompt/model versions being attributed to an older experiment.

Evidence quality priority remains:

```text
live forward observation / paper
  > historical point-in-time replay
  > ordinary retrospective backtest
```

Every resolved outcome must retain enough lineage to prove the observation
window and source timestamps used.

# Part I — N3 Strategy Evaluation System

## 6. N3 product question

N3 must let the user answer, without reading SQL or logs:

> How has `SWING_V1` actually performed, on how much valid evidence, against what
> benchmark, with what drawdown, and which kinds of actions are helping or
> hurting?

N3 must work **before any Trader AI exists**.

## 7. N3 evaluation units

A single "trade result" is insufficient. N3 separates three result layers.

### 7.1 DecisionOutcome

Evaluates the quality of a frozen decision independent of whether a fill
occurred.

Suggested fields:

```text
DecisionOutcome
  outcome_id
  experiment_id
  decision_id
  symbol
  market
  action
  decision_time
  reference_price

  horizon_sessions
  observation_end
  outcome_status

  forward_return
  mfe
  mae
  target_hit?
  stop_hit?
  target_before_stop?

  market_regime
  action_outcome_class
  outcome_reason_codes

  source_lineage_hash
  outcome_policy_version
```

`outcome_status`:

```text
PENDING
RESOLVED
INSUFFICIENT_DATA
INVALID
```

A 10-session outcome may not be marked failed after only 3 sessions. It remains
`PENDING` until the required observation window matures.

### 7.2 ExecutionOutcome

Separates strategy intent from execution consequences.

Suggested fields:

```text
ExecutionOutcome
  execution_outcome_id
  experiment_id
  decision_id
  requested_action
  execution_disposition
  execution_reason_codes
  requested_quantity
  max_executable_quantity
  executed_quantity
  observed_quote_at
  market_session_status
  deferral_id?
  fill_ids[]
  resolved_at
```

Examples:

```text
Decision good + stale quote blocked execution
Decision good + T+1 deferred exit
Decision bad + execution correctly blocked by hard risk
Decision valid + fill completed with measurable slippage
```

### 7.3 TradeEpisodeOutcome

Evaluates the full position episode:

```text
BUY -> ADD -> HOLD -> REDUCE -> EXIT
```

Suggested fields:

```text
TradeEpisodeOutcome
  episode_outcome_id
  experiment_id
  position_episode_id
  symbol

  opened_at
  closed_at
  holding_sessions

  gross_return
  net_return
  realized_pnl
  fees
  slippage

  mfe
  mae
  episode_max_drawdown

  entry_decision_ids[]
  position_decision_ids[]
  fill_ids[]

  outcome_policy_version
```

## 8. Action-specific outcome semantics

The evaluator must not judge every action using BUY semantics.

Introduce `ActionOutcomePolicy`.

```text
BUY / ADD
  -> entry quality
  -> forward return / MFE / MAE
  -> target-before-stop when configured

WAIT
  -> avoided loss
  -> missed opportunity
  -> later valid entry availability

HOLD
  -> continuation quality
  -> post-decision forward return / MFE / MAE

REDUCE
  -> risk-reduction quality
  -> avoided downside vs opportunity cost

EXIT
  -> exit quality
  -> avoided post-exit drawdown vs premature exit opportunity cost

BLOCKED
  -> gate correctness / data-quality attribution
  -> never silently counted as WAIT
```

This is necessary so Review can eventually say "entries are strong but exits
are early" rather than exposing one misleading win-rate number.

## 9. OutcomePolicy

Outcome rules are immutable and versioned.

Suggested contract:

```text
OutcomePolicy
  policy_id
  version
  decision_horizons
  action_outcome_rules
  target_stop_rules
  benchmark_alignment_rule
  trading_calendar_rule
  missing_data_rule
  suspended_symbol_rule
  corporate_action_adjustment_rule
```

Initial `SWING_V1` observation windows should support at least:

```text
3 sessions
5 sessions
10 sessions
20 sessions
```

The exact product default may be selected during N3.2 implementation, but all
persisted results must carry the selected policy version.

## 10. BenchmarkPolicy

Positive return alone does not prove skill.

N3 introduces versioned benchmark definitions.

Initial benchmark classes:

```text
MARKET_INDEX
BUY_AND_HOLD_SYMBOL
EQUAL_WEIGHT_ELIGIBLE_UNIVERSE
FORMAL_SWING_V1
NEUTRAL_DIAGNOSTIC
```

Market benchmarks must be market-aware. An HK experiment must not silently use a
CN benchmark.

Suggested model:

```text
BenchmarkPolicy
  benchmark_policy_id
  version
  benchmark_type
  market
  benchmark_symbol?
  universe_policy_version?
  universe_snapshot_id?
  universe_snapshot_hash?
  rebalance_rule?
  cost_assumptions
```

## 11. SampleQualityPolicy

Metrics without sample context are unsafe.

Suggested states:

```text
INSUFFICIENT
LOW
USABLE
STRONG
```

The policy may consider:

- resolved decision count;
- completed episode count;
- number of distinct symbols;
- observation duration;
- regime coverage;
- invalid/missing-data ratio;
- concentration in a small number of outlier trades.

N3 does not need to expose one universal threshold as a product truth. The
thresholds themselves must be versioned.

## 12. StrategyEvaluation

N3 aggregates immutable outcomes into an evaluation snapshot.

Suggested fields:

```text
StrategyEvaluation
  evaluation_id
  experiment_id
  evaluation_version
  period_start
  period_end

  resolved_decision_count
  completed_trade_count
  sample_quality

  total_return
  benchmark_return
  excess_return
  max_drawdown

  win_rate
  average_win
  average_loss
  payoff_ratio
  expectancy
  profit_factor
  max_consecutive_losses

  average_holding_sessions
  turnover
  fees
  slippage

  mfe_summary
  mae_summary

  regime_breakdown
  action_breakdown
  horizon_breakdown
  execution_attribution

  computed_at
  source_hash
```

Calibration metrics are intentionally not required for N3 `PRODUCT_DONE`.

## 13. N3 first API contract

Suggested read APIs:

```text
GET /v1/lab/experiments
GET /v1/lab/experiments/{id}
GET /v1/lab/experiments/{id}/summary
GET /v1/lab/experiments/{id}/outcomes
GET /v1/lab/experiments/{id}/performance
GET /v1/lab/experiments/{id}/breakdown
GET /v1/lab/compare?ids=...
```

Do not add `/calibration` as an N3 product requirement. Reserve it for N6.

API responses must expose:

```text
experiment/version
strategy/version
policy versions
sample count/quality
period/as-of
benchmark identity
metric provenance
pending/invalid outcome counts
```

## 14. N3 Android Lab MVP

Add one **实验 / Lab** product area. Do not create separate tabs for Evaluation,
AI Paper and Calibration as each phase lands.

N3 MVP may show only:

```text
Formal SWING_V1
Benchmark
```

Suggested information hierarchy:

```text
实验概览
  SWING_V1 v1.0.0
  evaluation period
  sample quality

表现
  total return
  benchmark return
  excess return
  max drawdown

交易质量
  win rate
  payoff ratio
  expectancy
  holding duration

动作表现
  BUY / WAIT / HOLD / REDUCE / EXIT breakdown

市场环境
  regime breakdown

执行归因
  executed / blocked / deferred / stale / T+1
```

The UI must distinguish:

```text
PENDING outcome
INSUFFICIENT sample
INVALID/insufficient data
no completed trades
zero return
```

These states must not collapse into one generic empty/error state.

## 15. N3 implementation slices

Implementation must proceed in this order unless a later PR explicitly changes
the dependency graph.

### N3.1 — ExperimentDefinition

Deliver:

- `domain/experiment` identity models;
- experiment/version/policy lineage;
- immutable `ExperimentUniverseSnapshot` membership + deterministic hash;
- definition-to-universe referential/hash validation;
- persistence and deterministic serialization;
- no scoring yet;
- no AI code.

Exit criterion:

> a Formal `SWING_V1` observation can be identified immutably with all relevant
> policy versions and an exact frozen experiment membership snapshot independent
> from mutable Personal Watchlist/positions state.

### N3.2 — Outcome contracts

Deliver:

- `DecisionOutcome`;
- `ExecutionOutcome`;
- `TradeEpisodeOutcome`;
- `OutcomePolicy` and `ActionOutcomePolicy`;
- pending/resolved/invalid semantics.

Exit criterion:

> future observation windows cannot be accidentally scored early, and action
> types have explicit outcome semantics.

### N3.3 — OutcomeResolver

Deliver:

- deterministic point-in-time resolver;
- market-calendar aware observation windows;
- MFE/MAE and forward-return resolution;
- execution attribution from existing audit/ledger facts;
- reject decisions/episodes outside the frozen ExperimentUniverseSnapshot;
- no remote look-ahead I/O inside evaluation.

Exit criterion:

> same frozen inputs + same outcome policy produce the same resolved outcome.

### N3.4 — StrategyEvaluation

Deliver:

- economic metrics;
- risk/drawdown metrics;
- action/regime/horizon breakdown;
- sample-quality integration;
- source lineage bound to the frozen universe snapshot hash.

Exit criterion:

> Formal SWING_V1 produces a reproducible evaluation snapshot.

### N3.5 — BenchmarkPolicy

Deliver:

- market-aware benchmark contract;
- benchmark-relative return;
- equal-weight/buy-and-hold baselines where valid;
- equal-weight universe benchmarks consume frozen experiment/benchmark membership,
  never today's Personal Universe.

Exit criterion:

> absolute return is always interpretable against an explicit baseline.

### N3.6 — Lab API

Deliver stable read DTOs and comparison endpoint.

Exit criterion:

> Android does not calculate evaluation metrics itself.

### N3.7 — Android Lab MVP

Deliver repository/ViewModel-or-controller/immutable-state/UI feature boundary.

Exit criterion:

> user can inspect Formal SWING_V1 performance, benchmark, drawdown, sample
> quality and breakdowns without admin/log access.

### N3.8 — Formal SWING_V1 acceptance

Acceptance matrix must prove:

- immutable version lineage;
- frozen ExperimentUniverseSnapshot membership/hash and independence from mutable
  Personal Watchlist/positions/Discovery state;
- point-in-time integrity;
- pending outcomes excluded from resolved metrics;
- invalid/missing observations visible;
- fees/slippage separated where applicable;
- benchmark identity visible;
- action/regime breakdown reproducible;
- Android loading/empty/error/insufficient-sample states;
- documentation synchronized.

`N3 PRODUCT_DONE` means Formal SWING_V1 is fully evaluable end to end. It does
**not** require Trader AI.

# Part II — N4 AI Strategy Lab Shadow

## 16. N4 entry gate

Do not begin N4 product implementation until N3 can evaluate a Formal
`SWING_V1` experiment end to end. N4 may be designed in parallel but must not
become the critical path before the scoreboard exists.

## 17. AiStrategyAgentDefinition

Suggested model:

```text
AiStrategyAgentDefinition
  agent_id
  agent_version
  strategy_id
  strategy_version

  model_provider
  model_name
  model_version
  prompt_version
  prompt_hash

  evidence_schema_version
  forecast_policy_version

  status
  created_at
```

Research AI and Trader AI remain separate roles. N4 introduces Trader AI only in
Lab.

## 18. Fair-comparison input contract

Formal and AI comparison must use the same frozen EvidenceSnapshot.

Forbidden:

```text
Formal -> frozen evidence
AI -> hidden internet/provider research
```

Required:

```text
                 Frozen EvidenceSnapshot
                       /          \
                      /            \
             Formal Engine      AI Agent
```

Every AI shadow decision stores `evidence_snapshot_id` and hash.

## 19. ForecastContract

A probability is invalid without a testable event definition.

Initial template:

```text
ForecastContract
  contract_type = TARGET_BEFORE_STOP
  horizon_sessions
  target_return
  stop_return
  contract_version
```

Example:

```text
action = BUY
horizon_sessions = 10
target_return = +0.06
stop_return = -0.03
probability = 0.72
```

Meaning:

> within 10 trading sessions, the target is reached before the stop with 72%
> predicted probability.

Do not accept a naked `confidence=0.87` as a forecast probability.

## 20. AiShadowDecision

Suggested fields:

```text
AiShadowDecision
  shadow_decision_id
  experiment_id
  symbol
  decision_time

  evidence_snapshot_id
  evidence_snapshot_hash
  formal_decision_id

  agent_id
  agent_version
  paper_intent

  forecast_contract
  probability
  reason_summary
  supporting_evidence_ids
  opposing_evidence_ids

  validation_status
  model_run_id
  latency_ms
  token_usage
  estimated_cost?
```

Schema and semantic validation must reject:

- action outside the allowed action set;
- missing/invalid forecast contract;
- probability outside `[0,1]`;
- evidence references absent from the frozen snapshot;
- model output that tries to mutate deterministic risk/execution fields.

## 21. N4 API / Android

The Decision Workspace may show:

```text
Formal: WAIT
AI Lab: BUY
10 sessions: target +6% before stop -3%
Predicted probability: 72%
LAB — does not affect formal decision
```

Formal and AI opinions must never be merged into an implicit "combined" action.

N4 Lab detail should also show:

- agent/model/prompt version;
- evidence snapshot identity;
- validation status;
- run latency/cost metadata where available;
- disagreement with Formal;
- forecast outcome once matured.

## 22. N4 acceptance

N4 is complete only when:

- same frozen evidence reaches Formal and AI;
- no hidden remote research path exists;
- AI failure cannot change Formal Action;
- every AI percentage maps to a ForecastContract;
- invalid output fails closed;
- shadow records are immutable and replayable;
- Android clearly marks the output as experiment-only.

# Part III — N5 Isolated AI Paper Trading

## 23. N5 entry gates

Before AI paper performance is trusted:

1. N3 evaluation must be end-to-end functional;
2. N4 shadow agent must have validated immutable output contracts;
3. Phase 5 / Issue #46 paper-execution acceptance must be complete or explicitly
   re-scoped with equivalent safety evidence.

N5 must not become a workaround for unfinished Paper Broker safety.

## 24. Execution authority

The only allowed path is:

```text
AI Paper Intent
  -> deterministic RiskPolicy
  -> deterministic SizingPolicy
  -> ExecutionPrecheck
  -> Paper Broker
  -> isolated experiment ledger
```

AI never calls the ledger directly and does not decide T+1, session validity,
quote freshness, lot/tick rules, fees, slippage or maximum executable quantity.

## 25. ExperimentAccount

Actual isolated accounts are introduced in N5.

Suggested model:

```text
ExperimentAccount
  experiment_account_id
  experiment_id
  ledger_id
  initial_capital
  cash
  equity
  status
  risk_policy_version
  created_at
```

Each AI agent/version receives a separate account and ledger. Two experiments
must never consume the same cash or sellable inventory.

## 26. AiPaperIntent lifecycle

Suggested lifecycle:

```text
PROPOSED
VALIDATED
BLOCKED
DEFERRED
ACCEPTED
EXECUTED
EXPIRED
CANCELLED
```

Persist:

```text
intent_id
shadow_decision_id / ai_decision_id
experiment_id
requested_action
requested_at
status
reason_codes
requested_quantity?
max_executable_quantity?
execution_precheck_id?
deferral_id?
fill_ids[]
```

A deferred T+1 EXIT may not execute blindly on the next session. A fresh decision
or explicitly governed revalidation plus a fresh in-session quote is required by
the authoritative paper-execution contract.

## 27. N5 experiment risk controls

Introduce deterministic experiment controls, for example:

```text
experiment_enabled
max_portfolio_drawdown
max_single_position_exposure
max_daily_turnover
max_simultaneous_positions
```

These values belong to a versioned `ExperimentRiskPolicy`, not to the AI prompt.

An experiment-level kill switch must be able to stop new intents without
mutating historical records.

## 28. N5 API / Android

Per experiment account expose:

```text
cash
positions
equity
realized/unrealized PnL
max drawdown
fills
fees
active risk
blocked/deferred intents
last AI decision
```

Lab comparison should support:

```text
Formal SWING_V1
AI Agent A
AI Agent B
market benchmark
```

The user must be able to distinguish:

```text
AI decision failure
risk-policy block
execution block/deferral
slippage/cost effect
market outcome
```

## 29. N5 acceptance

N5 is complete only when:

- experiment cash/positions are isolated;
- AI cannot write a fill directly;
- T+1/session/freshness behavior matches the authoritative Paper Broker;
- blocked/deferred intents remain visible;
- kill switch and drawdown guard are deterministic;
- every fill links back to the frozen AI decision and evidence;
- Evaluation can attribute resulting PnL correctly.

# Part IV — N6 Calibration and Reliability

## 30. N6 entry gate

N6 requires a sufficient population of resolved N4/N5 forecasts. Calibration
must not be invented from a tiny sample.

## 31. ForecastOutcome

N3 reserves the generic outcome envelope; N6 consumes resolved testable
ForecastContracts.

Suggested fields:

```text
ForecastOutcome
  forecast_outcome_id
  shadow_decision_id
  experiment_id
  forecast_contract
  predicted_probability
  event_occurred
  resolved_at
  outcome_status
  source_lineage_hash
```

## 32. CalibrationEvaluation

Suggested fields:

```text
CalibrationEvaluation
  calibration_evaluation_id
  experiment_id
  evaluation_version

  forecast_contract_type
  horizon_sessions

  sample_count
  sample_quality
  brier_score
  expected_calibration_error

  bucket_breakdown
  regime_breakdown
  action_breakdown

  computed_at
  source_hash
```

### CalibrationBucket

```text
probability_low
probability_high
sample_count
mean_predicted_probability
realized_event_rate
confidence_interval_low
confidence_interval_high
```

## 33. Reliability UX

Never show:

```text
AI reliability: 82%
```

without a defined event and sample context.

Prefer:

```text
Prediction bucket: 70-80%
Mean prediction: 74%
Realized event rate: 72%
Sample: n=126
95% interval: 64-79%
Status: calibrated
```

For small samples:

```text
INSUFFICIENT_SAMPLE
Not enough evidence to estimate reliability yet.
```

N6 should surface overconfidence/underconfidence and regime fragility rather
than compressing all reliability into one number.

## 34. N6 promotion states

Keep the bounded maturity model:

```text
LAB -> OBSERVED -> VALIDATED -> ADVISORY
```

`ADVISORY` remains the production ceiling for AI opinion in this v3 design. It
may be visible beside Formal Decision but cannot mutate Formal ActionPolicy.

Promotion requires a versioned EvaluationPolicy and evidence such as:

- sufficient sample quality;
- acceptable drawdown;
- positive expectancy after costs where economic performance applies;
- benchmark-relative value;
- acceptable calibration;
- no catastrophic regime failure;
- no point-in-time leakage;
- no domination by a few outliers;
- stable results for the frozen version.

No automatic production tuning is permitted.

# Part V — Module and storage boundaries

## 35. Backend target layout

New code should enter target modules instead of adding more root-level runtime
files.

```text
backend/app/
  domain/
    experiment/
      definition.py
      policies.py
      status.py
    evaluation/
      decision_outcome.py
      execution_outcome.py
      trade_episode_outcome.py
      forecast_outcome.py
      strategy_evaluation.py
      calibration.py
      benchmark.py
      sample_quality.py

  application/
    experiment/
      experiment_service.py
    evaluation/
      outcome_resolver.py
      evaluation_service.py
      benchmark_service.py
      calibration_service.py

  api/v1/
    lab/
      experiments.py
      performance.py
      comparison.py
      calibration.py
```

Naming may adapt to the repository's current target-module conventions, but the
domain ownership boundary should remain explicit.

## 36. Android target layout

Do not add another monolithic Lab implementation to `MainActivity.kt` or generic
`ApiClient.kt`.

Suggested incremental boundary:

```text
feature/lab/
  LabRepository
  LabController or LabViewModel
  LabUiState
  LabScreen
  ExperimentDetailScreen
  PerformanceSection
  DecisionComparisonSection
  PaperAccountSection      # N5
  ReliabilitySection       # N6
```

Network DTOs and endpoint clients should remain outside composables.

# Part VI — Testing and observability

## 37. Determinism

For every versioned evaluator:

```text
same frozen source lineage
+ same policy versions
= same outcome/evaluation
```

Tests must lock deterministic serialization and source hashes where practical.

## 38. Data-quality handling

Evaluation must not silently interpret missing data as neutral performance.

Expose at least:

```text
pending_count
invalid_count
insufficient_data_count
resolved_count
coverage_ratio
```

Where a metric cannot be computed, return an explicit availability/status field.

## 39. Audit lineage

Every metric displayed to the user should resolve back to:

```text
ExperimentDefinition
OutcomePolicy
source frozen decision/evidence
resolved outcomes
benchmark definition
EvaluationPolicy
```

N4-N6 additionally resolve to model/prompt/forecast versions.

# Part VII — Delivery and documentation governance

## 40. Implementation PR rule

This draft is a design PR only. Runtime implementation must be split into
reviewable vertical slices.

Required sequence:

```text
N3.1 ExperimentDefinition
N3.2 Outcome contracts
N3.3 OutcomeResolver
N3.4 StrategyEvaluation
N3.5 BenchmarkPolicy
N3.6 Lab API
N3.7 Android Lab MVP
N3.8 Formal SWING_V1 acceptance

then

N4 Shadow Agent
N5 Isolated AI Paper
N6 Calibration
```

Each implementation PR must follow repository documentation governance:

- update `ThirdHand_v3_Roadmap_and_Ledger.md` in the same product commit;
- update `ThirdHand_Architecture_v3_consolidated.md` in the same commit when an
  authority/safety/current-conformance contract changes;
- state exact Backend/API/Android/Observable/Accepted delivery status;
- never mark a backend-only slice `PRODUCT_DONE`;
- keep this detailed design synchronized when an accepted implementation changes
  its contract.

## 41. Current design delivery status

At the time this draft is opened:

```text
N3 Evaluation              DESIGN
N4 AI Shadow               DESIGN / blocked by N3 product acceptance
N5 AI Paper                DESIGN / blocked by N3 + N4 + paper safety acceptance
N6 Calibration             DESIGN / blocked by resolved N4/N5 forecast samples
```

No runtime implementation is claimed by this document.

## 42. Design acceptance checklist

Before this design PR is ready for merge, confirm:

- [ ] N3 evaluates Formal SWING_V1 before AI exists;
- [ ] DecisionOutcome / ExecutionOutcome / TradeEpisodeOutcome stay separate;
- [ ] action-specific outcome semantics are accepted;
- [ ] pending/invalid outcomes cannot contaminate resolved metrics;
- [ ] benchmark and sample-quality policies are versioned;
- [ ] calibration ownership is N6, not N3 product acceptance;
- [ ] actual isolated experiment accounts begin in N5;
- [ ] Formal and AI use the same frozen EvidenceSnapshot for comparisons;
- [ ] AI probabilities require ForecastContract;
- [ ] AI cannot write ledgers directly;
- [ ] no automatic production policy promotion exists;
- [ ] backend/API/Android module boundaries avoid new monoliths;
- [ ] implementation PR sequence and documentation synchronization are explicit.

## 43. Final design principle

The N3-N6 system is not an AI feature bundle. It is an evidence loop:

```text
Strategy / Agent
  -> Frozen Decision
  -> Outcome
  -> Evaluation
  -> Human review
  -> new explicit version, if justified
```

A good result may justify designing a new version. It never silently rewrites the
old one.
