# ThirdHand Stabilization Sprint Plan

> Status: approved product-recovery plan.
>
> This document is subordinate to `ThirdHand_Architecture_v3_consolidated.md`
> and `ThirdHand_v3_Roadmap_and_Ledger.md`. The ledger remains authoritative
> for delivery status. This plan defines the immediate S0 implementation order
> and the required Android entry for every slice.

## 1. Why S0 exists

ThirdHand is not blocked by missing backend depth. The current imbalance is:

```text
Backend capability
        >
Daily product usability
```

The system already has substantial Decision, Evaluation and AI design, while the
daily mobile path still needs stabilization: portfolio facts must be dependable,
Watchlist must be reachable, chart information must be layered, and AI must have
one clear secondary entry.

S0 therefore takes priority over expanding N4 AI Shadow, N5 AI Paper Trading and
N8 Order Flow. Existing safety and authority contracts do not change.

## 2. Definition of done

Every S0 slice must deliver the complete vertical path:

```text
Issue
  -> Backend
  -> API
  -> Android entry
  -> observable loading/empty/error states
  -> screenshot and automated tests
  -> device acceptance
  -> Roadmap update
```

Backend-only work is not `PRODUCT_DONE`. Android code without an obvious
user-facing entry is not `PRODUCT_DONE`. Repository CI is not a substitute for
physical-device acceptance.

## 3. S0.1 Portfolio Recovery

Goal: make Portfolio useful every day before adding more research surfaces.

Mobile entry:

```text
Bottom navigation
  -> Portfolio
  -> Holding Detail
```

The Portfolio and Holding Detail fact layer must expose:

- stock name and symbol;
- current price and quote freshness;
- quantity, average cost and market value;
- profit/loss amount and percentage;
- holding days and position weight;
- a route to transaction history;
- a route to the K-line surface.

AI explanations, financial research and event narratives do not belong in the
basic holding list.

Acceptance:

- loading, empty, ready, partial/stale and error states are understandable;
- tapping a holding opens the correct symbol;
- calculations and currency formatting match authoritative API facts;
- screenshots and a physical-device walkthrough are recorded.

## 4. S0.2 Watchlist Recovery

Goal: eliminate the broken or hidden Watchlist path and make Personal Universe
management first-class.

Mobile entry:

```text
Bottom navigation
  -> Watchlist
  -> Stock Detail
```

Required behavior:

- list Watchlist symbols;
- add and remove a symbol;
- edit priority, note and enabled/paused state;
- sort deterministically;
- open Stock Detail;
- expose review status without requiring an admin/log page.

This slice must build on the existing PUX1 backend/API and Android work tracked by
#92. It must not create a second Watchlist model.

Acceptance:

- no 404 on the normal Android path;
- mutations survive refresh/restart;
- loading, empty, partial and error states are covered;
- repository CI and device acceptance pass.

## 5. S0.3 Holding Detail UX

Goal: separate facts from interpretation.

Holding Detail owns:

- price and freshness;
- quantity, cost, market value and profit/loss;
- position weight and holding duration;
- K-line and transaction history.

Decision Workspace owns:

- why buy, hold, wait, reduce or exit;
- What Changed and Decision Memory;
- AI research;
- financial and CorporateEvent evidence;
- risk and blocked-action explanations.

Mobile transition:

```text
Portfolio -> Holding Detail
Holding Detail -> AI/Decision icon -> Decision Workspace
```

The two screens may share the same symbol identity, but must not merge their
responsibilities into one long page.

## 6. S0.4 K-line UX

Goal: reduce information overload with progressive disclosure.

Layer 1 — trading facts:

- price and daily change;
- cost and profit/loss;
- current holding state.

Layer 2 — chart evidence:

- K-line;
- timeframe;
- volume;
- selected indicators.

Layer 3 — research:

- Decision/AI;
- financials;
- events;
- strategy and timing evidence.

The default view must not render all three layers as one uninterrupted feed.

## 7. S0.5 AI Entry Refactor

Goal: make AI discoverable without letting it dominate the daily facts page.

Canonical entry:

```text
Holding Detail or Stock Detail
  -> AI/Decision icon
  -> Decision Workspace
  -> AI Research
```

Rules:

- no AI long-form narrative in the Portfolio list;
- no AI trading authority;
- AI output cannot override Formal Decision, Risk, sizing, ExecutionPrecheck or
  Paper Broker;
- failures, missing evidence and stale results remain explicit.

## 8. Work paused during S0

Do not begin new implementation for the following until S0 acceptance is
recorded in the canonical ledger:

- N4 AI Strategy Lab Shadow;
- N5 AI Paper Trading;
- N8 Order Flow;
- additional scoring or confidence models.

Existing correctness/runtime acceptance for #46, #39, #49 and #40 may continue;
S0 does not weaken those gates.

## 9. Ordered recovery route

1. S0.1 Portfolio Recovery.
2. S0.2 Watchlist Recovery and #92 acceptance.
3. S0.3 Holding Detail separation.
4. S0.4 K-line layering.
5. S0.5 AI entry refactor.
6. Complete remaining N2/device acceptance.
7. Reassess and resume N4 only after the canonical ledger records S0 acceptance.

## 10. Codex desktop implementation handoff

Before coding, read:

1. `ThirdHand_Architecture_v3_consolidated.md`;
2. `ThirdHand_v3_Roadmap_and_Ledger.md`;
3. `ThirdHand_Current_Implementation_Status_and_Mobile_Entry_Roadmap.md`;
4. this plan;
5. the selected S0 Issue.

Each implementation PR must use the delivery matrix required by
`ThirdHand_v3_Documentation_and_Delivery_Governance.md` and synchronize the
canonical documents in the same commit when product code changes.

## 11. Post-S0 visual fidelity handoff — 2026-08-30

The completed UIX0-UIX6 device walkthrough proved routing, readability and the
current authority boundaries, but the supplied AI-trading reference still shows
a material product-level visual and information-architecture gap. That follow-up
is tracked separately by parent #159 and must not reopen already accepted S0/UIX
correctness work.

The first implementation slice is #164 under Strategy parent #161. It is limited
to Strategy shell chrome and workspace-selector fidelity:

- the visible Strategy root title becomes the product destination `策略` rather
  than the implementation label `策略执行`;
- the subtitle remains capability-accurate (`AI决策 · 模拟执行 · 风险控制`);
- the existing `模拟执行 | 收益复盘 | 策略评估` routes remain authoritative and
  reachable while their selector styling moves closer to the supplied reference;
- no unsupported `研究计划`, real-broker action, new Decision authority, API or
  DTO is introduced merely to match the mockup;
- intentional Strategy/Lab screenshot changes require visual review before their
  hashes are accepted, followed by normal Android CI and device acceptance.

This is a presentation reconciliation track, not permission to resume paused N5
AI paper-account authority or to treat reference-only order controls as shipped
capability.
