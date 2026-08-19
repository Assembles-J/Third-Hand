# ThirdHand v3 Strategy and AI Lab Design

> Status: design extension for the existing v3 architecture. This document does
> not supersede `ThirdHand_Architecture_v3_consolidated.md` or
> `ThirdHand_v3_Roadmap_and_Ledger.md`; when they conflict, the paired canonical
> documents win. After this design is accepted, its stable authority rules must
> be promoted into those canonical files together with implementation changes.

## 1. Product direction

ThirdHand is evolving from an information assistant into an auditable personal
investment decision-support and strategy-experiment system.

The product has three first-class systems:

1. **Formal Decision System** — deterministic, versioned, explainable and
   fail-closed. AI does not own final BUY/ADD/REDUCE/EXIT authority.
2. **AI Strategy Lab** — an isolated paper-trading environment where an AI agent
   may form its own simulated BUY/WAIT/HOLD/ADD/REDUCE/EXIT intents.
3. **Evaluation System** — measures whether a strategy or AI agent is actually
   reliable, in which regimes, and with what uncertainty.

The long-term axis is:

```text
Strategy -> Evidence -> Decision -> Risk -> Execution -> Evaluation
```

ThirdHand does not connect to a real broker, store broker credentials, submit
real orders, or promise returns. Paper fills remain simulated ledger activity.

## 2. Why Strategy must become first-class

The repository now has weekly/daily/60m/15m/5m technical state, fundamental and
financial evidence, CorporateEvent lifecycle, market regime, position state,
risk, paper execution and AI research. These inputs cannot all have the same
meaning for every investment style.

A 5-minute order-flow observation can matter for short-term entry timing but
should not overrule a long-horizon fundamental thesis. Conversely, long-horizon
financial quality should not silently become an intraday execution trigger.

Introduce a first-class `StrategyProfile` so every evidence type has an explicit
role and authority.

Suggested domain model:

```text
StrategyProfile
  strategy_id
  strategy_version
  name
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

Every frozen formal decision and every experiment must record `strategy_id`,
`strategy_version` and the relevant policy versions.

## 3. First production strategy: SWING_V1

Do not implement VALUE, POSITION, SWING, SHORT and INTRADAY simultaneously.
The first explicit production profile should be `SWING_V1`, targeting roughly
3-20 trading-session holding episodes.

Recommended authority:

| Input | SWING_V1 role |
| --- | --- |
| weekly | strategic structure |
| daily | primary trend / setup |
| 60m | setup maturity / position management |
| 15m | execution timing |
| 5m | execution timing |
| realtime | hard risk and execution safety only |
| fundamentals | quality/risk context |
| financial currentness | quality/current confirmation |
| CorporateEvent | deterministic risk gate |
| market regime | strategic context |
| news | research context |
| order flow | timing evidence only |
| LLM interpretation | research/explanation only |

The already merged asymmetric multi-timeframe policy is the correct starting
point: lower timeframes may confirm, delay or downgrade new risk but may not
manufacture BUY/ADD and may not create REDUCE/EXIT by themselves.

## 4. Formal Decision System

The formal path remains conservative:

```text
Canonical Input
  -> Evidence
  -> StrategyProfile
  -> Base ActionPolicy
  -> ResearchAssessment
  -> DecisionArbiter
  -> TimeframePolicy
  -> DecisionContinuity
  -> Formal Action
  -> RiskPolicy
  -> ExecutionPrecheck
  -> Sizing
  -> DecisionPackage / Paper Execution
```

Formal AI authority remains bounded to interpretation and explanation. It may
surface counter-evidence and ambiguity, but it cannot own canonical price/time,
quality, market rules, sellability, sizing, hard risk, or final formal action.

## 5. AI Strategy Lab

The AI Strategy Lab is deliberately parallel to the Formal Decision System.
It is not a hidden extension of Formal ActionPolicy.

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

An AI agent may propose `BUY`, `WAIT`, `HOLD`, `ADD`, `REDUCE`, or `EXIT`, but
only inside its own experiment account. AI never writes the ledger directly.

## 6. AI output contract: probability must be testable

Do not store ungrounded values such as `confidence=87%` without defining what
87% means.

An AI paper decision must bind probability to a forecast contract, for example:

```text
action = BUY
forecast_contract:
  horizon_sessions = 10
  event = TARGET_BEFORE_STOP
  target_return = +0.06
  stop_return = -0.03
probability = 0.72
```

This allows long-run calibration: among all predictions in the 70-80% bucket,
did the target event occur approximately 70-80% of the time?

Keep two evaluation layers separate:

- **Economic outcome:** PnL, return, drawdown, risk, fees and slippage.
- **Forecast outcome:** whether the explicitly predicted event occurred.

## 7. Experiment isolation

Every strategy/agent must have an isolated account and ledger. Never let one AI
agent's BUY consume another agent's cash or alter its sellable inventory.

Suggested identifiers:

```text
experiment_id
experiment_account_id
ledger_id
strategy_id
agent_id
```

For fair AI/model comparisons, keep these controls equal unless the experiment
is explicitly testing them:

- frozen EvidenceSnapshot;
- candidate universe;
- initial capital;
- RiskPolicy;
- SizingPolicy;
- fees/slippage;
- Paper Broker;
- market/session rules.

Default rule: AI chooses **directional intent**; deterministic RiskPolicy and
SizingPolicy own capital-at-risk. AI-controlled sizing should be a separate
experiment class.

## 8. ExperimentDefinition and immutable versioning

Suggested model:

```text
ExperimentDefinition
  experiment_id
  strategy_id
  strategy_version
  agent_id
  model_provider
  model_name
  model_version
  prompt_version
  prompt_hash
  evidence_schema_version
  universe_policy_version
  risk_policy_version
  sizing_policy_version
  execution_policy_version
  initial_capital
  started_at
  ended_at
  status
```

Any change in model, prompt, tools, evidence schema, strategy, risk or sizing
creates a new experiment version. Performance from changed versions must not be
silently pooled into the old result set.

## 9. Point-in-time integrity

Historical replay must use only information available at the simulated decision
time. It must not consume revised financials, later announcements, future bars,
future event outcomes, future universe membership or other look-ahead data.

Priority of evidence quality for strategy validation:

1. live forward paper trading;
2. historical point-in-time replay;
3. ordinary backtest.

Forward paper is especially valuable because the agent genuinely has not seen
the future.

## 10. UniversePolicy

Candidate selection is part of the experiment and must be versioned. A user
watchlist or a hindsight-picked set of winners must not silently become the test
universe.

The current deterministic candidate rotation is a strong foundation because it
is independent from same-day heat, price ranking, fund flow and LLM output while
always retaining held positions for risk monitoring. Promote this concept into
an explicit `UniversePolicy` and record it in every experiment.

## 11. Paper Broker is the only execution authority

AI may say "I want to BUY". The broker decides whether the simulated fill is
possible and at what executable quantity/price.

Paper Broker owns:

- exchange calendar and market session;
- quote freshness and observed time;
- tick and lot rules;
- T+1 and sellability;
- price-limit behavior;
- fees/slippage;
- execution delay;
- maximum executable quantity.

The active Phase 5 paper-execution acceptance contract must be complete before
AI Strategy Lab performance is treated as meaningful.

## 12. Evaluation System

Reliability is not one win-rate number. At minimum evaluate:

- total and benchmark-relative return;
- max drawdown;
- win rate;
- average win / average loss;
- payoff ratio;
- expectancy;
- Profit Factor;
- max consecutive losses;
- holding duration;
- turnover;
- fees/slippage;
- MFE/MAE;
- regime breakdown;
- action-type breakdown;
- confidence-bucket calibration.

Suggested model:

```text
StrategyEvaluation
  evaluation_id
  experiment_id
  period_start
  period_end
  trade_count
  total_return
  benchmark_return
  excess_return
  win_rate
  payoff_ratio
  expectancy
  profit_factor
  max_drawdown
  mfe
  mae
  turnover
  fees
  slippage
  calibration_score
  brier_score
  regime_breakdown
  sample_quality
  evaluation_version
```

## 13. Calibration and uncertainty

The UI must never show a naked "reliability 72%" without sample context.
Prefer:

```text
Historical event rate: 72%
95% interval: 64-79%
Sample: n=126
```

If the sample is insufficient, display `INSUFFICIENT_SAMPLE` rather than false
precision.

Evaluate calibration with versioned metrics such as calibration buckets, Brier
score and Expected Calibration Error. A model that says 85% but realizes only
65% in that bucket is overconfident even if its trading PnL is positive.

## 14. Benchmarks

Every experiment should compare against stable baselines where applicable:

- buy-and-hold benchmark;
- equal-weight eligible universe;
- `FORMAL_SWING_V1`;
- a neutral/random baseline for research diagnostics.

Positive absolute return is not proof of skill when the market benchmark rose
more.

## 15. Promotion gates

AI performance must never automatically modify production policy.

Allowed maturity states:

```text
LAB -> OBSERVED -> VALIDATED -> ADVISORY
```

The first production ceiling is `ADVISORY`: AI may display an opinion next to
the formal decision, but it still does not mutate Formal ActionPolicy.

Promotion should require versioned EvaluationPolicy checks such as:

- sufficient sample size;
- acceptable max drawdown;
- positive expectancy after costs;
- benchmark-relative value;
- acceptable calibration;
- no catastrophic regime failure;
- no detectable point-in-time leakage;
- results not dominated by a few outliers;
- stable performance over the frozen version.

No automatic production tuning from Feedback or experiment PnL.

## 16. Research AI vs Trader AI

Keep roles explicit:

- **Research AI:** explains evidence, financials, events and counter-evidence.
- **Trader AI:** exists only in AI Strategy Lab and produces paper intents.

Do not let role boundaries become implicit through prompts.

## 17. Order-flow authority

The order-flow/active-buying design is useful, but the first implementation must
remain read-only evidence. Under `SWING_V1`, order flow may confirm or delay
execution timing; it may not create BUY/ADD/REDUCE/EXIT or override higher-timeframe
structure and hard risk.

Only after offline/forward evaluation may a separately versioned timing policy
promote order-flow evidence into `SWING_V2` or another strategy.

## 18. Backend target modules

Continue the existing modular migration instead of introducing a v4 rewrite:

```text
backend/app/
  bootstrap/
  api/v1/
  application/
    market/
    company/
    research/
    strategy/
    decision/
    portfolio/
    experiment/
    evaluation/
  domain/
    market/
    company/
    evidence/
    strategy/
    decision/
    portfolio/
    execution/
    experiment/
    evaluation/
  infrastructure/
    database/
    providers/
    llm/
    scheduler/
```

New Strategy/Experiment/Evaluation code should enter the target modules rather
than adding more root-level `xxx_policy.py` / `xxx_runtime.py` files.

## 19. Android product structure

The UI should converge on five user-facing areas:

```text
Home | Watchlist | Portfolio | Lab | Review
```

The stock-detail page becomes a `Decision Workspace` showing:

- Formal Decision and why;
- current StrategyProfile;
- weekly/daily/60m/15m/5m authority state;
- financial/fundamental/event state;
- timing/order-flow evidence;
- position, stop, sellable/locked/T+1 risk;
- AI Research explanation;
- AI Strategy Lab opinions;
- Decision Memory / What Changed.

The Lab page compares AI agents, Formal SWING_V1 and benchmark with sample size,
drawdown and calibration. The Review page explains where decisions were right,
wrong, overconfident, regime-sensitive, data-blocked or execution-blocked.

## 20. Engineering priority

The global priority is:

```text
Correctness
  > Strategy Definition
  > Evaluation Infrastructure
  > Reliability
  > UX
  > New Features
```

Current correctness/runtime acceptance (paper execution, financial currentness,
CorporateEvent lifecycle and Decision AI provider recovery) must be closed before
large-scale AI Lab paper performance is trusted.

## 21. Governance rule for every new feature

Before a feature enters formal strategy or the lab, answer five questions:

1. Which StrategyProfile does it belong to?
2. What Evidence does it create?
3. What authority does that evidence have?
4. How will its contribution be evaluated?
5. If it fails, can it break formal safety?

If these questions do not have explicit answers, the feature remains research-only.
