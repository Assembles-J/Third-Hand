# ThirdHand v3 PUX1 Implementation Design

> Status: IMPLEMENTATION DESIGN READY
>
> This document is subordinate to `ThirdHand_Architecture_v3_consolidated.md`,
> `ThirdHand_v3_Roadmap_and_Ledger.md`, and
> `ThirdHand_v3_Personal_Universe_Review_Watchlist_UX_Design.md`.
>
> Scope: PUX1 only — Personal Universe + first-class Watchlist. PUX2 ReviewPolicy
> and PUX3 Discovery remain separate follow-up slices. No Formal Action, Risk,
> Sizing, T+1, or Paper Broker authority changes are introduced here.

## 1. Why PUX1 is a vertical slice

PUX1 must ship as one understandable product path:

```text
SQLite Watchlist + Paper Positions
  -> PersonalUniverseService
  -> stable API DTO
  -> Android repository/controller
  -> first-class Watchlist tab
  -> dense Watchlist / Positions list
  -> add/edit/delete/priority/note
  -> explicit loading/empty/stale/error states
```

A backend-only table migration is not PUX1. A decorative Android list backed by
mock state is not PUX1. The delivery target is `PRODUCT_DONE` only after the
whole path is visible and accepted.

## 2. Existing code to reuse

Current repository already has the minimal Watchlist substrate:

- SQLite table `watchlist(symbol, name, created_at, updated_at)` in
  `backend/app/storage.py`.
- `PortfolioStore.watchlist()`, `save_watchlist_item()`, and
  `delete_watchlist_item()`.
- legacy API `GET /v1/watchlist`, `POST /v1/watchlist`,
  `DELETE /v1/watchlist/{symbol}`.
- Android DTOs `WatchlistInputDto`, `WatchlistItemDto` and Retrofit calls
  `watchlist()`, `saveWatchlistItem()`, `deleteWatchlistItem()`.
- Android bottom navigation currently `News | Market | Trading | Admin` in
  `MainActivity.kt`.
- Paper positions already expose symbol/name/current account state and remain the
  authoritative source for held-symbol membership.

PUX1 extends this substrate; it does not create `watchlist_v2`, duplicate
portfolio tables, or a second security identity cache.

## 3. Domain contracts

### 3.1 WatchlistPriority

```text
NORMAL
FOCUS
CORE
```

Semantics:

- `NORMAL`: ordinary durable follow-up.
- `FOCUS`: user wants this symbol easier to find / earlier in the list.
- `CORE`: highest personal attention priority.

Priority is attention metadata only. It cannot alter Formal Action, Evidence,
Risk, PositionSizing, ExecutionPrecheck, DecisionContinuity, or experiment
membership.

### 3.2 WatchlistEntry

Target server model:

```text
WatchlistEntry
  symbol: canonical string
  name: non-empty display name
  enabled: bool = true
  priority: NORMAL | FOCUS | CORE = NORMAL
  note: string = ""
  created_at: aware timestamp
  updated_at: aware timestamp
```

Do not persist quote price, action, review mode, freshness, or position quantity
inside the watchlist row. Those are joined read-model facts with independent
owners.

### 3.3 PersonalUniverseItem

Read-only DTO:

```text
PersonalUniverseItem
  symbol
  name
  market?
  membership: POSITION | WATCHLIST | POSITION_AND_WATCHLIST
  watchlist_priority?
  watchlist_note?
  watchlist_enabled?
  position_quantity?
  position_market_value?
  sellable_quantity?
  locked_quantity?
  last_price?
  change_percent?
  quote_display_state: live | refreshing | session_close | stale | unavailable
  quote_as_of?
  formal_action?
  decision_id?
  decision_updated_at?
  review_mode?          # null until PUX2 owns it
  next_review_at?       # null until PUX2 owns it
```

PUX1 may serialize `review_mode=null` and `next_review_at=null`; Android must not
invent ReviewPolicy locally.

### 3.4 Membership invariant

For every open paper position:

```text
position.symbol in PersonalUniverse
```

regardless of Watchlist size, enabled state, priority, quote state, or future
Discovery settings.

Deleting a Watchlist entry for an owned symbol changes membership from
`POSITION_AND_WATCHLIST` to `POSITION`; it never hides the position.

## 4. Persistence design

### 4.1 Additive watchlist migration

Use the migration framework rather than ad-hoc destructive schema replacement.
Suggested migration name:

```text
00xx_pux1_watchlist_metadata
```

Add:

```sql
ALTER TABLE watchlist ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1;
ALTER TABLE watchlist ADD COLUMN priority TEXT NOT NULL DEFAULT 'NORMAL';
ALTER TABLE watchlist ADD COLUMN note TEXT NOT NULL DEFAULT '';
```

Migration/backfill rules:

- existing rows => `enabled=1`, `priority='NORMAL'`, `note=''`;
- no symbol/name/timestamp rewrite;
- migration is idempotent through the existing migration runner;
- do not add quote/action/review fields to the table.

Add an index only if measured query plans justify it. The table is small and
`priority, updated_at` ordering does not justify speculative indexing yet.

### 4.2 Store methods

Prefer additive methods on `PortfolioStore` for PUX1 to minimize architectural
churn while root-level storage remains current authority:

```text
watchlist(include_disabled: bool = false)
watchlist_item(symbol)
upsert_watchlist_item(symbol, name, enabled, priority, note)
update_watchlist_item(symbol, enabled?, priority?, note?, name?)
delete_watchlist_item(symbol)
```

Compatibility:

- existing `save_watchlist_item(symbol, name)` remains as a compatibility wrapper
  that writes defaults and delegates to the new upsert.
- existing callers of `watchlist()` continue receiving enabled rows by default.
- no caller may infer BUY permission from a returned row.

## 5. Backend application design

### 5.1 New feature boundary

Do not add another large block to `legacy/application_legacy.py` beyond thin
compatibility routing. Create:

```text
backend/app/domain/personal_universe/
  __init__.py
  models.py

backend/app/application_services/personal_universe/
  __init__.py
  service.py

backend/app/api/v1/personal_universe/
  __init__.py
  schemas.py
  router.py
```

The existing v2 bootstrap/router registration pattern should own the new route.
Legacy `/v1/watchlist` routes remain backward compatible until callers migrate.

### 5.2 PersonalUniverseService

Dependencies are read-only except explicit Watchlist mutation:

```text
PortfolioStore
Market quote display read model / cached quote access
Instrument metadata read access
Latest persisted Formal Decision read access
```

Do not run:

- Mandatory Acquisition;
- DecisionOrchestrator;
- DeepSeek / Decision AI;
- Company Intelligence refresh;
- CorporateEvent acquisition;
- Paper Broker.

`GET /v1/personal-universe` is a read model, not a research trigger.

Pseudo-flow:

```text
positions = paper position projection
watchlist = enabled watchlist entries
symbols = stable union(positions, watchlist)
quotes = batch local/cached display quote read
metadata = batch/read existing identity
formal = latest persisted decision per symbol

for symbol:
    merge without changing authority
    classify membership
    classify quote display state with existing display freshness helper
sort
return
```

### 5.3 Sort contract

Default deterministic order:

```text
1. POSITION_AND_WATCHLIST, then POSITION, then WATCHLIST
2. CORE, then FOCUS, then NORMAL for watchlist-bearing rows
3. latest explicit watchlist updated_at descending
4. canonical symbol ascending as tie-breaker
```

Do not sort by today's percentage move by default; that creates attention
chasing. Android may offer a local temporary display sort later, but the server
response retains deterministic default order.

## 6. API contract

### 6.1 Preserve current endpoints

Keep behavior compatible:

```text
GET    /v1/watchlist
POST   /v1/watchlist
DELETE /v1/watchlist/{symbol}
```

Extend returned Watchlist DTO additively with defaults:

```json
{
  "symbol": "01810",
  "name": "小米集团-W",
  "enabled": true,
  "priority": "CORE",
  "note": "",
  "created_at": "...",
  "updated_at": "..."
}
```

Older Android clients ignore additive JSON fields.

### 6.2 New mutation endpoint

```text
PUT /v1/watchlist/{symbol}
```

Request:

```json
{
  "name": "小米集团-W",
  "enabled": true,
  "priority": "CORE",
  "note": "等待财报后重新判断"
}
```

Rules:

- path symbol is canonical mutation key;
- request may be partial if schema is explicitly patch-like;
- priority enum validation is server-owned;
- note length should be bounded, e.g. 500 chars;
- blank `name` may reuse existing/cached identity, but must not force a remote
  provider request inside the mutation transaction;
- if no trustworthy local name exists, return an explicit validation error and
  let the existing cache-first Add flow resolve identity first.

### 6.3 Personal Universe read endpoint

```text
GET /v1/personal-universe
```

Response:

```json
{
  "generated_at": "...",
  "items": [],
  "counts": {
    "positions": 0,
    "watchlist": 0,
    "combined": 0
  },
  "data_state": "ready|partial|degraded",
  "warnings": []
}
```

Partial quote or decision data does not fail the whole list. Per-item unavailable
states are explicit.

### 6.4 Settings endpoint deferral

`GET/PUT /v1/personal-universe/settings` belongs to PUX3 when Discovery settings
become real. PUX1 should not ship a settings endpoint containing fields with no
runtime owner.

## 7. Backend tests

Add focused tests rather than expanding giant legacy API snapshots only.

Suggested files:

```text
backend/tests/test_personal_universe.py
backend/tests/test_watchlist_metadata.py
```

Required cases:

1. old database row migrates to enabled/NORMAL/empty note;
2. legacy POST creates a NORMAL enabled row;
3. PUT changes priority/note without changing symbol identity;
4. deleting held symbol's Watchlist row leaves it in Personal Universe as POSITION;
5. every open paper position appears even with zero Watchlist rows;
6. duplicate symbol in position + Watchlist appears exactly once as POSITION_AND_WATCHLIST;
7. quote unavailable => item remains present with `unavailable` state;
8. stale/session-close display uses existing display-freshness semantics and never
   implies executable quote freshness;
9. GET Personal Universe performs no remote provider/model call;
10. Watchlist priority never appears in DecisionContext/formal action inputs.

## 8. Android feature boundary

Do not grow `MainActivity.kt` and `ApiClient.kt` with the full feature.

Create:

```text
android/app/src/main/java/com/thirdhand/app/personaluniverse/
  PersonalUniverseModels.kt
  PersonalUniverseRepository.kt
  PersonalUniverseController.kt
  PersonalUniverseScreen.kt
  WatchlistEditorDialog.kt
  PersonalUniverseRow.kt
```

`MainActivity.kt` changes should be limited to navigation wiring and detail
callbacks.

`ApiClient.kt` may temporarily retain Retrofit interface declarations for
compatibility, but PUX1 DTO mapping belongs in the feature package. A later API
modularization can split the Retrofit service without blocking PUX1.

## 9. Android navigation

Current shell:

```text
News | Market | Trading | Admin
```

PUX1 shell:

```text
News | Market | Watchlist | Trading | Admin
```

Use a dedicated tab id; do not reuse hidden Research Chat id or encode navigation
meaning in array position arithmetic.

Recommended sealed/enum destination introduced incrementally:

```text
AppDestination.News
AppDestination.Market
AppDestination.Watchlist
AppDestination.Trading
AppDestination.Admin
```

If replacing current integer navigation creates too large a conflict surface for
other agents, PUX1 may first add one dedicated integer constant and move to the
typed destination in a later isolated cleanup. Product behavior is more
important than a big-bang navigation refactor.

## 10. Screen information architecture

Top-level Watchlist destination:

```text
compact red app bar
  title: 自选
  search/add action

segment row
  自选股 | 持仓股

column header
  股票             最新         涨幅

high-density rows

optional bottom status strip
  最后刷新 / degraded state
```

Discovery tab is not rendered in PUX1; add it only when PUX3 has real backend
settings/data.

### 10.1 Watchlist row

```text
小米集团-W            28.440       +3.64%
01810 · HK · CORE
HOLD · 数据收盘态
```

PUX1 may show Formal Action when locally available from the Personal Universe DTO.
It must not show a fabricated Review mode. Until PUX2, review line is omitted or
rendered as a neutral placeholder such as `复核策略：待 PUX2` only in debug,
not in production UI.

### 10.2 Positions row

```text
云南铜业              16.16        +1.38%
000878 · CN
持仓 1200 · 可卖 800 · 锁定 400
```

Selecting a row reuses the existing stock/holding detail path; PUX1 should not
create a second competing detail screen.

## 11. Visual tokens

Reuse ThirdHand market semantics:

```text
brand/rise: #F52D3A
fall:       #16A05D
canvas:     cool white
surface:    white
primary text: near black
secondary text: muted gray
```

Rules:

- scan list screen uses no gradient hero;
- 1dp/thin separators instead of elevated cards per row;
- price and change columns use stable widths and right alignment;
- security name may use 1-2 lines; code/market stays secondary;
- market state always includes text, never color only;
- touch target >= 44dp;
- red/green semantics use the existing configurable market color tokens rather
  than hardcoding per component.

## 12. UI state machine

`PersonalUniverseUiState` is immutable:

```text
Initial
Loading
Content(data, isRefreshing=false, transientError=null)
Empty
Error(message, retryable)
```

Refresh behavior:

```text
Content -> refresh -> Content(lastGood, isRefreshing=true)
  success -> Content(new)
  failure -> Content(lastGood, transientError=...)
```

Do not blank the whole screen on a recoverable refresh error.

Per-item states remain independent:

```text
quote = live/session_close/stale/unavailable
formal_action = value/null
position sellability = value/null
```

## 13. Add/Edit flow

Add:

```text
Watchlist -> +
  -> existing cache-first Stock Search
  -> choose canonical security
  -> optional priority/note
  -> POST/PUT Watchlist
  -> refresh Personal Universe
```

Never duplicate symbol resolution logic inside the Watchlist screen.

Edit existing row:

```text
long press / row menu
  -> priority
  -> note
  -> remove from Watchlist
```

For a held symbol, removal confirmation text must say that the symbol remains
visible under Positions because an open paper position still exists.

## 14. Android tests

Add JVM controller tests:

```text
PersonalUniverseControllerTest.kt
```

Cover:

- initial load -> content;
- initial load -> retryable error;
- refresh keeps last good data;
- delete held Watchlist membership does not locally delete server-returned POSITION row;
- priority update round-trip state;
- empty Watchlist but non-empty positions -> Positions content, not global Empty;
- quote unavailable row remains selectable.

Add screenshot tests:

```text
PersonalUniverseScreenshotTest.kt
```

Reference states:

1. mixed Watchlist red/green/flat rows;
2. positions tab with sellable/locked quantities;
3. empty Watchlist;
4. loading;
5. stale/degraded quote rows;
6. refresh failure with last-good data;
7. long name truncation / HK symbol.

## 15. File ownership plan for parallel agents

To reduce merge conflicts, PUX1 implementation should reserve these files:

Primary PUX1 ownership:

```text
backend/app/domain/personal_universe/**
backend/app/application_services/personal_universe/**
backend/app/api/v1/personal_universe/**
backend/tests/test_personal_universe.py
backend/tests/test_watchlist_metadata.py
android/app/src/main/java/com/thirdhand/app/personaluniverse/**
android/app/src/test/java/com/thirdhand/app/personaluniverse/**
android/app/src/screenshotTest/kotlin/com/thirdhand/app/personaluniverse/**
```

Shared files — keep edits minimal and rebase immediately before modification:

```text
backend/app/storage.py
backend/app/migrations.py
backend/app/bootstrap/v2_routes.py
backend/app/legacy/application_legacy.py
android/app/src/main/java/com/thirdhand/app/ApiClient.kt
android/app/src/main/java/com/thirdhand/app/MainActivity.kt
docs/ThirdHand_v3_Roadmap_and_Ledger.md
```

Avoid touching unless required:

```text
DecisionOrchestrator
ActionPolicy
DecisionContinuity
Decision AI
Paper Broker / execution contract
CorporateEvent / financial currentness
```

This split is intentional so correctness agents can continue #39/#40/#46/#49
with minimal overlap.

## 16. Implementation commit sequence

### PUX1-A — persistence + server models

Touch:

- migration;
- storage compatibility wrappers;
- domain models;
- focused backend tests.

Delivery state: `BACKEND_READY_CORE` only.

### PUX1-B — read model + API

Touch:

- PersonalUniverseService;
- `/v1/personal-universe`;
- Watchlist PUT/update contract;
- API tests;
- bootstrap route registration.

Delivery state: `API_VISIBLE`.

### PUX1-C — Android repository/controller

Touch:

- feature models/repository/controller;
- Retrofit declarations only as needed;
- JVM tests.

Delivery state remains `API_VISIBLE` until the real screen ships.

### PUX1-D — Android screen/navigation

Touch:

- first-class bottom nav Watchlist;
- dense list + Watchlist/Positions tabs;
- add/edit/delete/priority/note;
- explicit UI states;
- existing detail/search integration.

Delivery state: `ANDROID_VISIBLE`.

### PUX1-E — screenshot/device acceptance

Touch:

- screenshot references/tests;
- device acceptance fixes;
- canonical Ledger update.

Only after end-to-end acceptance may PUX1 become `PRODUCT_DONE`.

## 17. Documentation synchronization rule

Every PUX1 code PR must update `ThirdHand_v3_Roadmap_and_Ledger.md` in the same
accepted change with the achieved state. Do not edit the canonical Architecture
for ordinary implementation progress unless an authority/invariant changes.

If implementation discovers that this contract is wrong, change the subordinate
PUX1 design and, when authority is affected, Architecture before merging the
behavior change.

## 18. Explicit non-goals

PUX1 does not implement:

- ReviewPolicy or AnalysisBudget (PUX2);
- Discovery settings/candidates (PUX3);
- experiment universe UI;
- a new formal decision engine;
- automatic DeepSeek analysis on Watchlist load;
- quote polling beyond existing governed market refresh;
- broker execution;
- a big-bang MainActivity/ApiClient rewrite.

## 19. PUX1 acceptance checklist

PUX1 is complete only when all are true:

- existing Watchlist rows migrate without loss;
- old Android/client POST/GET/DELETE remains compatible;
- user can add, edit priority/note, and remove Watchlist entries;
- all open positions always appear in Personal Universe;
- Watchlist + Position duplicate is one row with combined membership;
- Watchlist has a first-class bottom navigation entry;
- Watchlist/Positions are sibling tabs;
- screen uses dense scan-first trading-utility visual language;
- partial/stale/unavailable quote states remain visible and truthful;
- Personal Universe GET causes no remote research/model call;
- priority/watchlist membership cannot affect Formal Action;
- controller + backend + screenshot acceptance passes;
- Ledger is synchronized in the same completion PR.
