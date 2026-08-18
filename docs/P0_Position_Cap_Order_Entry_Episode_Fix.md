# P0 Fix Design — Position Cap Authority, Order Quantity, Entry Episode Continuity

Status: proposed implementation contract
Issue: #36
Base: `main@d042a59fc4be26edf359aab9d9788faac61e0ef2`

## 1. Problem statement

Three integration defects can combine into an invalid paper-trading lifecycle:

```text
FLAT
  -> OPEN sizing under hard-coded 20% cap
  -> BUY
  -> HOLDING above PersonalRule cap
  -> position.above_max
  -> REDUCE
  -> zero suggested reduction falls back to target/current position quantity
  -> SELL intent
  -> T+1 blocks the order
```

T+1 is the final safety boundary and is not the root cause. The root cause is disagreement between policy/sizing authorities plus ambiguous sizing/execution quantity semantics.

A separate continuity defect drops the frozen entry contract while projecting `paper_account()` positions into the next paper `DecisionContext`.

## 2. Authority contract

### 2.1 Single effective position cap

ThirdHand must have one deterministic position-cap authority for formal paper decisions.

For this fix:

```text
system_hard_cap_percent = 20.0
personal_cap_percent = PersonalRule.max_position_percent when an enabled rule exists

effective_position_cap_percent = min(system_hard_cap_percent, personal_cap_percent)
```

If no personal rule is available, the system hard cap remains 20%.

`TradePlan.max_position_percent` is **not promoted to sizing authority in this PR**. It remains part of the plan/audit contract. Promoting it later requires an explicit precedence/version change because existing sizing is deliberately system-policy based rather than free-form per-plan text.

The same helper must be used by:

- `EvidenceEngine` when emitting `position.above_max` / `position.near_max`;
- `PositionSizingEngine` for OPEN/ADD concentration limits;
- `PositionSizingEngine` for REDUCE target quantity.

No duplicate cap formula is allowed.

## 3. Sizing/execution quantity contract

`target_quantity` and executable order quantity are different concepts.

The formal sizing result gains:

```text
order_quantity
    Quantity to submit for the current action.

target_quantity
    Resulting position quantity after the proposed order.

max_executable_quantity
    Market/settlement maximum currently executable.
```

Compatibility:

- `suggested_quantity` remains populated during migration as an alias for `order_quantity`.
- new runtime code reads `order_quantity` first, then `suggested_quantity` only for compatible historical/current reports;
- runtime never falls back from a missing/zero order quantity to `target_quantity`.
- numeric zero is a valid value and must remain zero.

Execution invariant:

```text
order_quantity == 0
=> no paper order
```

For SELL actions:

```text
order_quantity <= sellable_quantity
```

## 4. Entry episode continuity contract

The first executed OPEN of a paper-position episode freezes:

```text
entry_episode_id
entry_decision_id
entry_evidence_snapshot_hash
entry_research_assessment_hash
entry_risk_state
entry_technical_state
entry_market_regime
entry_event_state
entry_price
entry_opened_at
```

The projection path must preserve those facts end to end:

```text
paper_position_episodes
  -> paper_account()
  -> prepare_paper_decisions().paper_holdings
  -> DecisionContextBuilder
  -> PositionSnapshot
  -> DecisionContinuity
```

ADD may change aggregate quantity/average cost but must not overwrite the frozen entry contract or reset position age.

Full EXIT closes the episode.

`PositionSnapshot.opened_at` must use the frozen episode open time when available, not mutable position `updated_at`.

## 5. Versioning

This changes formal sizing semantics, so bump `SIZING_VERSION`.

The ActionPolicy REDUCE/OPEN precedence does not need a new semantic rule in this fix; it consumes corrected evidence generated from the shared cap authority. If implementation changes the action-policy contract itself, bump `ACTION_POLICY_VERSION` as well.

## 6. Non-goals

This PR does not:

- weaken T+1 enforcement;
- add HK/US paper execution;
- add a general FX ledger;
- change ModelPolicy routing;
- grant AI formal action authority;
- implement 60m/15m/5m multi-timeframe policy;
- implement risk-deterioration-since-entry signals.

## 7. Acceptance tests

### 7.1 Effective cap

Given:

```text
system hard cap = 20%
personal max = 10%
```

OPEN/ADD sizing must target no more than 10%.

A held position above 10% must emit `position.above_max`; REDUCE sizing must target the same 10% cap.

### 7.2 Zero order quantity

Given:

```text
formal action = REDUCE
order_quantity = 0
target_quantity = current position quantity
```

Runtime must produce no SELL order.

### 7.3 T+1 mixed lots

Given:

```text
total = 1000
sellable = 800
locked = 200
```

EXIT/REDUCE must never submit more than 800.

### 7.4 Entry episode integration

After first BUY:

```text
paper_account -> prepare_paper_decisions -> DecisionContext
```

must preserve all entry provenance fields and original `opened_at`.

After ADD, those fields and position age remain tied to the first entry episode.

### 7.5 Post-entry coherence golden case

With identical market/evidence state:

```text
FLAT -> BUY -> HOLDING
```

must not produce REDUCE/SELL solely because OPEN sizing used a looser cap than held-position evidence.

## 8. Rollout / verification

1. focused unit tests for shared cap helper, evidence and sizing;
2. paper-runtime regression for zero order quantity;
3. paper episode end-to-end projection test;
4. existing T+1 tests must remain green;
5. full backend test suite;
6. deployed-container golden scenario before considering the issue closed.
