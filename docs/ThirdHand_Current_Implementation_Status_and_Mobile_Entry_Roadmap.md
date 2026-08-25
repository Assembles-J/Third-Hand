# ThirdHand Current Implementation Status and Mobile Entry Roadmap

> Purpose: provide Codex implementation guidance.
>
> This document answers two questions before any new development:
>
> 1. What has already been implemented?
> 2. Where is the user-facing mobile entry for each capability?
>
> This document does not replace the canonical Architecture and Roadmap documents. It is an implementation navigation map.

---

# 1. Current Project Status

## Completed

## N1 — StrategyProfile / SWING_V1

Status:

`PRODUCT_DONE`

Implemented:

- StrategyProfile
- SWING_V1 identity
- strategy version lineage
- timeframe authority
- DecisionReport strategy display
- Android strategy visibility

Mobile entry:

```
Stock Detail
  -> Strategy Card
  -> Timeframe Authority
```

---

## N2 — Decision Workspace

Status:

`IMPLEMENTED BUT DEVICE ACCEPTANCE OPEN`

Implemented:

- Formal Decision display
- What Changed
- Decision Memory
- Financial currentness
- CorporateEvent status
- T+1 / sellable / locked quantity
- Decision Workspace API
- immutable UiState
- screenshot regression tests

Mobile entry:

```
Portfolio
  -> Holding Detail
  -> AI / Decision icon
  -> Decision Workspace
```

Important:

Holding Detail and Decision Workspace must remain separate.

Holding Detail:

- price
- K line
- quantity
- cost
- profit/loss
- holding days
- market value

Decision Workspace:

- AI explanation
- why hold/buy/wait
- what changed
- risk reason
- research evidence

---

## N3 — Evaluation Infrastructure

Status:

`PRODUCT_DONE`

Implemented:

- ExperimentDefinition
- frozen experiment universe
- OutcomeResolver
- StrategyEvaluation
- BenchmarkEvaluation
- Lab API
- Android Strategy Lab

Mobile entry:

```
Management
  -> Strategy Lab
```

Not implemented:

- AI autonomous trading
- AI calibration

These belong to N4/N5/N6.

---

# 2. Current Pending Runtime Acceptance

## Paper Execution Acceptance

Issue:

#46

Need verify:

- T+1
- mixed inventory
- stale quote block
- closed session block
- restart recovery

Mobile entry:

```
Portfolio
  -> Paper Position
  -> Execution Status
```

---

## Financial Currentness

Issue:

#39

Need:

- deployed Xiaomi/HK acceptance
- official release refresh verification

Mobile entry:

```
Stock Detail
  -> Financial Status
```

---

## CorporateEvent Lifecycle

Issue:

#49

Need:

- deployed lifecycle verification

Mobile entry:

```
Stock Detail
  -> Events
```

---

# 3. Current Product Development Queue

## PUX1 — Android Watchlist

Issue:

#92

Status:

`ANDROID_VISIBLE / ACCEPTANCE_PENDING`

Backend/API is complete. Android implementation now provides the first-class
entry and local JVM/screenshot/Debug/Release validation. It is not
`PRODUCT_DONE` until repository CI and physical-device acceptance pass.

Goal:

Create a first-class user universe.

Mobile entry:

```
Bottom Navigation
  -> Watchlist
```

Must support:

- add stock
- remove stock
- priority
- notes
- enabled/disabled
- review status

Implemented Android surface:

- authoritative Personal Universe read model (Watchlist and Positions tabs);
- add, edit, remove, priority, note and enabled/paused state;
- stock-detail routing while preserving holding facts;
- loading, empty, partial, error and screenshot fixtures/baselines.

Do not use admin/log pages.

---

## PUX2 — ReviewPolicy / AnalysisBudget

Issue:

#93

Goal:

Control when AI/company research runs.

Mobile entry:

```
Watchlist
  -> Review Status
```

Display:

- why analyzed
- why skipped
- next review time

---

## PUX3 — Discovery

Issue:

#94

Goal:

Turn Candidate Pool into optional discovery.

Mobile entry:

```
Watchlist
  -> Discovery
```

Rules:

- no BUY authority
- no automatic watchlist addition
- explicit user promotion

---

# 4. AI Roadmap

## N4 — AI Strategy Lab Shadow

Issue:

#95

Status:

Not implemented.

Goal:

AI generates paper opinions only.

Mobile entry:

```
Stock Detail
  -> AI Opinion

or

Strategy Lab
  -> AI Shadow
```

Display:

- Formal Decision
- AI Opinion
- difference
- forecast contract

No trading authority.

---

## N5 — AI Paper Trading

Issue:

#96

Status:

Not implemented.

Goal:

Independent AI paper accounts.

Mobile entry:

```
Strategy Lab
  -> AI Accounts
```

Display:

- equity
- positions
- fills
- blocked actions
- execution reasons

---

## N6 — AI Calibration

Issue:

#97

Status:

Not implemented.

Goal:

Measure whether AI confidence is reliable.

Mobile entry:

```
Strategy Lab
  -> Reliability
```

Display:

- confidence bucket
- actual success rate
- sample size
- uncertainty interval

---

## N7 — Home / Review

Issue:

#98

Status:

Not implemented.

Goal:

Daily low-effort dashboard.

Mobile entry:

```
Home
Review
```

Display:

- what changed
- decisions requiring attention
- AI/formal disagreement
- failures

---

## N8 — Order Flow

Issue:

#99

Status:

Design only.

Goal:

Read-only timing evidence.

Mobile entry:

```
Stock Detail
  -> Timing Evidence
```

Rules:

- no direct BUY
- no direct SELL
- no override of Strategy

---

## N9 — Modularization

Issue:

#100

Goal:

Incremental architecture cleanup.

Rules:

No big rewrite.

Each refactor must protect or deliver a user-visible vertical slice.

---

# 5. Mobile Information Architecture Target

Final navigation:

```
Home
Watchlist
Portfolio
Strategy Lab
Review
```

Stock Detail:

```
Price
K Line
Position Data

AI / Decision icon

Decision Workspace
Research
Events
Financials
Timing Evidence
```

Portfolio:

```
Stock Name
Market Value
Quantity
Cost
Profit/Loss
Holding Days
```

Do not put:

- AI reasoning
- review time
- execution explanation

inside the basic holding table.

---

# 6. Development Rule

Every new feature must have:

```
Issue
 ↓
Backend
 ↓
API
 ↓
Android Entry
 ↓
Screenshot/Test
 ↓
Roadmap Update
```

A backend-only feature is not PRODUCT_DONE.

A UI mock without authoritative data is not PRODUCT_DONE.
