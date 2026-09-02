# ThirdHand Current Implementation Status and Mobile Entry Roadmap

> Snapshot: **2026-09-02**
>
> Purpose: provide a short, current navigation/status map for implementation work.
>
> Canonical authority remains `ThirdHand_Architecture_v3_consolidated.md` plus
> `ThirdHand_v3_Roadmap_and_Ledger.md`. This file is intentionally a current
> implementation index, not a historical delivery ledger.

---

# 1. Current repository snapshot

Current `main` reviewed for this snapshot:

`013b73a446581135419387ca2d583c84c10061be`

Current primary Android shell:

```text
首页 | 行情 | 组合 | 策略 | 自选
```

The former primary-shell labels such as `资讯 | 行情 | 持仓 | 交易 | 自选` and
older roadmap targets that placed `Strategy Lab` directly in bottom navigation
are historical implementation directions. They are not the current shell.

Current Strategy workspace selector:

```text
模拟执行 | 收益复盘 | 策略评估
```

`模拟执行` remains the existing simulated-account / Formal-Decision execution
path. It must not be relabelled as real-broker execution or unsupported N5 AI
paper trading.

---

# 2. Current user-facing mobile entries

## 首页

Purpose:

- low-effort attention / status surface assembled from supported facts;
- links into the deeper Portfolio, Strategy and Watchlist paths where relevant.

Do not fabricate a daily AI brief or unsupported portfolio analytics merely to
fill the screen.

---

## 行情

Current entry:

```text
底部导航 -> 行情 -> 股票详情
```

Owns factual market/search/detail presentation, including the current K-line
path. Decision/research authority remains separate from raw market facts.

---

## 组合

Current entry:

```text
底部导航 -> 组合 -> Holding Detail
```

The compact factual portfolio surface is the primary holdings path.

Holding Detail should remain fact-first:

- current price / freshness;
- quantity;
- average cost;
- market value;
- P/L;
- holding days;
- sellable / locked quantity where authoritative;
- K-line and transaction history.

Decision/research content remains behind its separate secondary route rather
than being mixed into every holding row.

---

## 策略

Current entry:

```text
底部导航 -> 策略
             -> 模拟执行
             -> 收益复盘
             -> 策略评估
```

### 模拟执行

Current supported capability includes:

- simulated-account equity / cash / position facts;
- automatic execution enabled / paused state;
- guarded manual decision-rotation action;
- execution-chain / paper-fill history;
- decision-audit drill-down;
- explicit no-real-broker boundary;
- server-owned paper-runtime state explaining recent work, pending work and
  no-trade reasons;
- explicit user-owned archive/restart flow for paper simulation epochs.

Paper restart/runtime repository implementation merged from #177 as
`013b73a446581135419387ca2d583c84c10061be`. Issue #175 remains open for the
required deployed/physical-device restart and quiet no-trade walkthrough before
that slice can be `PRODUCT_DONE`.

### 收益复盘

Reuses the existing Execution Review capability.

### 策略评估

Reuses the existing read-only Strategy Lab / Evaluation capability. Evaluation
must not rewrite Formal Decision, production policy or execution history.

---

## 自选

Current entry:

```text
底部导航 -> 自选
```

Owns the first-class Personal Universe / Watchlist path. Held symbols continue
to route to factual holding detail; watchlist-only symbols route to stock detail.
ReviewPolicy facts remain server-owned.

---

# 3. Decision Workspace boundary

Decision Workspace remains separate from factual Holding Detail.

Typical route:

```text
组合 / 股票详情
  -> secondary Decision entry
  -> Decision Workspace
```

Decision Workspace may display authoritative decision/research facts such as:

- Formal Decision;
- what changed;
- Decision Memory / continuity;
- risk and blocking reasons;
- financial currentness / CorporateEvent state where supplied;
- research evidence and lineage.

Android remains a renderer. It must not locally recalculate ReviewPolicy,
execution eligibility, T+1, sizing, strategy actions or market authority.

---

# 4. Current acceptance-only and parent issues

The following issue states are important so implementation work is not reopened
accidentally.

## #133 — UIX5 Strategy console

Status:

`DEVICE ACCEPTANCE ONLY`

Repository implementation is already accepted. The issue is open only because
the required physical-device Strategy walkthrough was never recorded as a full
PASS. Do not rewrite accepted repository implementation unless that device pass
finds a concrete regression.

## #164 — Strategy shell chrome / workspace tabs

Status:

`DEVICE ACCEPTANCE ONLY`

Repository implementation was merged via #166. Remaining work is physical-device
verification of the merged `模拟执行 | 收益复盘 | 策略评估` chrome.

## #159 / #161 — UI-gap parents

Use these as umbrella/status issues. New implementation must be owned by a
specific current child slice and start from current `main`.

## #167 — Strategy dashboard composition

The old implementation head carried by #168/#169 is historical only. PR #169
was closed unmerged on 2026-09-02 because it is stale against current `main`.
Reassess the actual current-main delta before writing any replacement code; do
not replay the stale branch.

---

# 5. Current P0 paper-runtime acceptance

## #175 — restart epochs and visible runtime state

Repository status:

`MERGED / DEPLOYED_DEVICE_ACCEPTANCE_PENDING`

Merged implementation:

`#177 -> 013b73a446581135419387ca2d583c84c10061be`

The merged contract:

- preserves historical fills, Formal Decisions, runs and equity evidence;
- archives the active paper-simulation epoch instead of fabricating SELL fills;
- starts a new epoch with user-selected CNY cash and isolated new positions/lots;
- prevents pre-epoch execution/review obligations from leaking into the new
  round;
- exposes server-owned runtime/no-trade/next-work facts to Android;
- serializes paper-ledger mutations;
- keeps HK paper fills fail-closed and does not widen trading authority.

Remaining acceptance belongs to #175: verify one real restart and a quiet
no-trade interval on deployed/physical-device runtime before `PRODUCT_DONE`.

---

# 6. Strategy / AI roadmap boundaries

The following distinctions remain mandatory:

- current `模拟执行` is not N5 isolated AI-agent paper trading;
- Strategy Lab / Evaluation is read-only;
- unsupported confidence, target-price or recommendation fields must not be
  fabricated in Android;
- no real-broker order ticket exists unless separately designed, implemented and
  accepted;
- foreign-market research visibility does not silently create multi-currency
  execution authority.

When future N4/N5/N6 work is implemented, update this current status map from the
accepted repository state rather than preserving old roadmap tense.

---

# 7. Development and governance rule

Every product change should still be traceable through:

```text
Issue / accepted scope
 ↓
authoritative backend/API contract when needed
 ↓
Android entry when user-visible
 ↓
Test / screenshot / APK acceptance as applicable
 ↓
canonical roadmap/ledger synchronization
 ↓
physical-device or deployed acceptance when required
```

Repository governance currently requires every commit that changes product
implementation under `backend/app/` or `android/app/src/main/` to update
`docs/ThirdHand_v3_Roadmap_and_Ledger.md` in the **same commit**. Authority-
sensitive backend changes must also synchronize the canonical architecture.

A backend-only capability is not automatically `PRODUCT_DONE`.
A visual mock without authoritative facts is not `PRODUCT_DONE`.
A green screenshot hash alone is not physical-device acceptance.
