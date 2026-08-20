# ThirdHand v3 Personal Universe / Review Cadence / Watchlist UX Design

> **Status: DESIGN — no runtime trading-authority change.**
>
> This document defines the product and implementation contract for ThirdHand's
> personal daily universe, review cadence, discovery demotion and first-class
> Android watchlist experience. It is subordinate to
> `ThirdHand_Architecture_v3_consolidated.md` and
> `ThirdHand_v3_Roadmap_and_Ledger.md`.
>
> The visual language is informed by user-provided screenshots of a dense
> Chinese-market self-selected/holdings workflow. We adopt the useful interaction
> principles — scan density, table alignment, sibling tabs, compact market
> context and red-up/green-down semantics — but do not copy third-party brand
> assets, logos, proprietary graphics or exact trade dress.

## 1. Product problem

ThirdHand currently has three partially overlapping concepts:

1. deterministic candidate rotation used by the formal paper runtime;
2. persisted/manual Candidate lifecycle used to schedule research;
3. an existing Watchlist API and Android watchlist surface that is not a
   first-class navigation destination.

The result is a poor daily-use contract. A user can receive repeated analysis on
stocks they did not explicitly care about, while a fully allocated holding can
still be reconsidered too frequently simply because the scheduler is alive.
This is especially mismatched with `SWING_V1`, whose normal holding horizon is
roughly 3-20 trading sessions rather than intraday scalping.

The new product principle is:

```text
Portfolio > Watchlist >>> Discovery
```

ThirdHand primarily studies what the user owns and what the user explicitly
chooses to follow. Discovery is optional, low-frequency and bounded. AI is a
research/interpreting tool, not an automatic stock-selection authority.

## 2. Non-negotiable ownership split

### 2.1 PersonalUniversePolicy

Daily product use owns a Personal Universe:

```text
PersonalUniverse
  +-- Portfolio   # all current positions, mandatory
  +-- Watchlist   # user-owned durable attention set
  +-- Discovery   # optional bounded research suggestions
```

Target policy contract:

```text
PersonalUniversePolicy
  policy_version
  include_all_positions = true
  watchlist_enabled = true
  discovery_enabled = false
  discovery_slots = 2
  discovery_interval_sessions = 3
  discovery_requires_manual_promotion = true
```

`include_all_positions=true` is a safety invariant, not a user preference. No
watchlist size or discovery limit may hide an open position from risk monitoring.

### 2.2 ExperimentUniversePolicy

Evaluation / AI Lab experiments retain a separate frozen universe contract.
Personal watchlist membership must never silently change an experiment sample.
This prevents user preference / survivor / attention bias from contaminating
Formal-vs-AI comparisons.

`ExperimentDefinition.universe_policy_version` therefore belongs to the
experiment/evaluation plane. A later implementation may rename or type the
ownership more explicitly, but PersonalUniverse and ExperimentUniverse must not
share mutable membership state.

### 2.3 Watchlist membership is not BUY authority

Adding a symbol to Watchlist means:

> spend governed research attention on this symbol.

It does not mean:

> permit BUY.

A Watchlist symbol still needs the complete Formal chain before any actionable
paper decision exists:

```text
Evidence
 -> ActionPolicy
 -> ResearchAssessment / DecisionArbiter
 -> Multi-Timeframe ActionPolicy
 -> DecisionContinuity
 -> Risk / Sizing / ExecutionPrecheck
```

## 3. Watchlist domain model

Reuse the existing Watchlist persistence/API rather than creating a competing
`watchlist_v2` store. Extend it additively with personal-attention metadata.

Target fields:

```text
WatchlistEntry
  symbol
  name
  enabled
  priority       # NORMAL | FOCUS | CORE
  note?
  created_at
  updated_at
  last_review_at?
  next_review_at?
```

Watchlist priority and Candidate research depth are intentionally different:

```text
Watchlist priority = how much the user cares about the symbol
Candidate L0-L4    = how deep a particular research task should go
```

Do not overload one enum with both meanings.

## 4. Discovery replaces candidate-pool product semantics

The existing Candidate lifecycle remains useful infrastructure, but the user-
facing meaning changes from "stocks the system selected" to "research-only
Discovery".

Discovery contract:

```text
DiscoveryCandidate
  -> BASIC_SCREEN
  -> user sees why it may deserve attention
  -> [Add to Watchlist] or [Ignore]
```

Default settings:

```text
discovery_enabled = false
discovery_slots = 2
discovery_interval_sessions = 3
```

Supported user controls should include:

```text
Automatic discovery: off / on
Slots per discovery: 0 / 1 / 2 / 3 / 5 / 10
Cadence: manual / every 3 trading sessions / weekly
```

`discovery_slots=0` is a valid explicit pause state.

### Discovery authority firewall

Default Discovery may use local-first deterministic screening such as:

- market identity and liquidity/data availability;
- completed daily structure;
- market regime;
- basic risk state;
- existence of material CorporateEvent;
- data completeness/freshness.

Default Discovery does **not**:

- call full DeepSeek Company Research for every candidate;
- create Formal BUY/ADD authority;
- auto-promote a symbol into Watchlist;
- auto-execute.

Full/focused research becomes eligible only after explicit promotion or another
separately governed research trigger.

## 5. ReviewPolicy: scheduler wake-up is not analysis permission

Separate five different frequencies:

```text
market-data collection frequency
!= risk-guard frequency
!= research frequency
!= formal-decision frequency
!= execution frequency
```

The scheduler asks whether work is due. It must not imply that every wake-up
creates a new full analysis.

Target Review modes:

```text
NO_REVIEW
GUARD_ONLY
POSITION_REVIEW
FULL_RESEARCH
```

### NO_REVIEW

No material change, no due review and no explicit user request. Persist an
explainable skip reason; do not call the model.

### GUARD_ONLY

Cheap deterministic monitoring only:

- hard invalidation / stop threshold crossing;
- material CorporateEvent lifecycle change;
- data-quality failure affecting safety;
- risk-level transition;
- execution/T+1 obligation state.

No full Company Research and no routine DeepSeek call.

### POSITION_REVIEW

A bounded position-management review, normally at a daily/strategy cadence.
It may evaluate whether a holding thesis remains valid without rebuilding every
slow-moving company dataset.

### FULL_RESEARCH

Reserved for genuinely material research change or explicit user request, such
as:

- new financial report / material announcement;
- strategic daily state transition;
- thesis-level CorporateEvent;
- material evidence conflict;
- explicit user "analyze now" action.

## 6. Position-aware review rules

For a position at its target/capped exposure:

```text
FULL POSITION
+ no strategic MaterialChange
= GUARD_ONLY during the session
```

Consequences:

- no BUY/ADD research loop;
- no routine full DeepSeek research;
- no repeated same-day thesis regeneration;
- hard risk/event/T+1 monitoring remains active.

A normal held position may receive at most one routine `POSITION_REVIEW` after
the relevant daily review point. A material trigger can upgrade it.

The existing adaptive `DISCOVERY / HOLDING_FOCUS / FULL_FOCUS` scheduling work
may remain as an intensity/input hint, but it must stop owning both membership
and analysis permission. Ownership becomes:

```text
UniversePolicy      -> who is in scope
ReviewPolicy        -> whether review is due
AnalysisDepthPolicy -> how deep the review may go
ActionPolicy        -> whether a trading action is permitted
```

## 7. AnalysisBudget

Introduce observable per-symbol review budget/state. Suggested contract:

```text
ReviewBudget
  symbol
  trading_date
  last_full_research_at?
  last_position_review_at?
  next_review_at?
  full_research_count_today
  position_review_count_today
  ai_call_count_today
  last_trigger?
  last_skip_reason?
```

Initial normal rule:

```text
routine FULL_RESEARCH <= 1 / symbol / trading day
```

Only a material trigger or explicit user request may exceed the routine budget.
The override reason must be persisted.

## 8. API contract

Preserve existing compatibility:

```text
GET    /v1/watchlist
POST   /v1/watchlist
DELETE /v1/watchlist/{symbol}
```

Additively extend:

```text
PUT /v1/watchlist/{symbol}
```

for `priority`, `note`, and `enabled` metadata.

Personal-universe read/settings APIs:

```text
GET /v1/personal-universe
GET /v1/personal-universe/settings
PUT /v1/personal-universe/settings
```

Discovery APIs:

```text
GET    /v1/discovery
POST   /v1/discovery/run
POST   /v1/discovery/{symbol}/promote
DELETE /v1/discovery/{symbol}
```

Review observability may be a focused endpoint or included in the personal-
universe read model:

```text
GET /v1/review-plan/{symbol}
```

Minimum ReviewPlan DTO:

```text
symbol
review_mode
reason_codes[]
last_review_at?
next_review_at?
material_change
ai_call_allowed
budget
```

Android must consume the authoritative DTO. It must not reproduce scheduling or
material-change calculations locally.

## 9. Android information architecture

### 9.1 First-class entry is mandatory

A backend Watchlist capability without an obvious app entry is incomplete.
The first implementation slice must promote Watchlist into the primary bottom
navigation.

Incremental target for the existing app shell:

```text
News | Market | Watchlist | Trading | Admin
```

This is a safe transition from today's four-item navigation. The broader v3
product target may later converge to:

```text
Home | Watchlist | Portfolio | Lab | Review
```

without blocking the first usable Watchlist slice.

### 9.2 Watchlist feature hierarchy

Inside the first-class Watchlist area, use sibling tabs:

```text
Watchlist | Positions | Discovery
```

The first two mirror the user's mental model: "what I chose to follow" and
"what I already own". Discovery is deliberately tertiary.

Primary user paths:

```text
Watchlist -> Add -> cache-first symbol search -> choose priority -> Save
Watchlist row -> Decision Workspace / stock detail
Discovery row -> Add to Watchlist / Ignore
Position row -> position-first detail / risk guard / decision workspace
```

Adding, editing priority/note, disabling and deleting a Watchlist symbol must be
possible from Android. No admin/log screen is required for normal management.

## 10. UI design language: dense trading utility, not decorative dashboard

The user-provided reference screenshots demonstrate a useful high-density
Chinese-market utility layout. ThirdHand adopts the principles below while
keeping its own Material 3 tokens and identity.

### 10.1 Visual hierarchy

Use:

- compact solid brand-red app bar;
- cool-white/white surfaces;
- thin neutral separators instead of card stacks;
- aligned numeric columns for scan speed;
- short active-tab underline;
- low/no elevation for list rows;
- small market/code/priority tags beneath or beside security name;
- fixed left identity column and right-aligned quote/status columns;
- red-up / green-down semantics through the existing configurable MarketColors;
- text labels in addition to color for decision/review states.

Avoid on Watchlist/Positions list surfaces:

- orange/red gradient hero cards;
- large rounded cards around every stock;
- oversized marketing headings;
- animation that moves numeric columns;
- AI-first visual hierarchy.

### 10.2 ThirdHand token alignment

Use existing project tokens rather than hard-coding a screenshot palette:

```text
Brand / rise: #F52D3A
Fall:         #16A05D
Neutral:      #7A8492
Canvas:       #F7F8FA
Surface:      #FFFFFF
Text:         #1F2329
Subdued:      #667085
```

Spacing should remain aligned with `AppSpacing` (2/4/8/12/16/20/24dp). List
rows may use a dense 8-12dp vertical rhythm while preserving a minimum 44dp
touch target.

The screenshot reference is a density/layout reference, not permission to copy
third-party exact colors, iconography, logos, typography metrics or branded
header composition.

### 10.3 Watchlist row anatomy

Target row:

```text
Security name                Price       Change%
CODE · market · CORE         review/action state
Formal: HOLD · no change     next review / freshness
```

The second/third line is where ThirdHand differs from a quote app. It should
answer "why should I care now?" without opening the detail screen.

Suggested compact state labels:

```text
No review due
Risk guard
Review due today
Material change
Data stale
Research unavailable
```

### 10.4 Full-position visibility

A full/capped position with no material change should explicitly render:

```text
Review mode: Risk guard
No full AI analysis was rerun today
Reason: target exposure reached; no strategic material change
Monitoring: invalidation / material event / T+1 / risk transition
```

This makes a skipped model call observable rather than indistinguishable from a
broken worker.

### 10.5 Discovery UI

Discovery lives under the Watchlist feature, not as a louder home feed.

Header controls:

```text
Automatic discovery    Off
Per run                2
Cadence                Every 3 sessions
[Run discovery now]
```

Each row explains why the symbol may deserve further research and offers:

```text
[Add to Watchlist] [Ignore]
```

Do not label Discovery items as recommendations to buy.

## 11. Android architecture requirement

Do not grow `MainActivity.kt` or generic `ApiClient.kt` into larger monoliths for
this feature. Implement an incremental feature boundary such as:

```text
feature/watchlist/
  PersonalUniverseRepository
  WatchlistController / ViewModel
  WatchlistUiState
  WatchlistScreen
  WatchlistRow
  DiscoverySettingsSheet
```

Network DTOs remain outside composables. Business calculations and review rules
remain backend-owned.

Required UI states:

```text
Loading
Ready
Empty Watchlist
Partial/Stale data
Refresh with last-good data
Section error
Discovery disabled
Discovery empty
Review-plan unavailable
```

The screen must remain useful when one section fails.

## 12. Observability and metrics

Measure the effect instead of promising an invented percentage.

At minimum expose/record:

```text
full_research_count_per_symbol_day
position_review_count_per_symbol_day
ai_call_count_per_symbol_day
review_skipped_count
review_mode_counts
discovery_basic_screen_count
discovery_promoted_count
provider_call_count where already observable
```

Expected qualitative effect:

- full/capped holdings with no MaterialChange have zero routine intraday full
  research calls;
- Discovery creates no default full DeepSeek call;
- user attention concentrates on positions + explicit Watchlist;
- repeated same-day thesis regeneration and decision chatter decline;
- provider/model work falls, with actual reduction measured after deployment;
- experiment evaluation remains unbiased by Personal Watchlist membership.

## 13. Delivery plan

### Slice A — Personal Universe + first-class Watchlist

Backend:
- additive Watchlist metadata;
- `PersonalUniversePolicy` and composed read model.

API:
- Watchlist update endpoint;
- Personal Universe read/settings endpoints.

Android:
- first-class Watchlist bottom-nav destination;
- Watchlist/Positions tabs;
- add/edit/delete/priority/note workflow;
- dense scan-first list language.

Acceptance:
- a user can manage the full Watchlist without admin tools;
- all positions remain visible regardless of user limits;
- loading/empty/stale/error states are visible;
- screenshot/preview tests lock representative states.

### Slice B — ReviewPolicy + AnalysisBudget

Backend:
- ReviewPlan/ReviewBudget persistence/read model;
- NO_REVIEW/GUARD_ONLY/POSITION_REVIEW/FULL_RESEARCH planner;
- scheduler integration;
- full-position guard behavior.

API/Android:
- show review mode, reason, last/next review and whether AI/full research ran.

Acceptance:
- scheduler wake-up without a due trigger does not run full analysis;
- capped position + no material change stays GUARD_ONLY;
- explicit material trigger upgrades deterministically;
- routine full research is budgeted and override reasons are audited.

### Slice C — Discovery demotion/productization

Backend:
- reuse Candidate lifecycle as research-only Discovery substrate;
- settings, bounded slots/cadence and manual promotion.

Android:
- Discovery tab/settings;
- run now;
- add-to-watchlist / ignore.

Acceptance:
- discovery can be fully disabled or set to zero slots;
- no default full model research for Discovery;
- Discovery cannot silently become Formal BUY scope;
- promotion is an explicit user action.

## 14. Full-stack delivery state rule

Every implementation slice must update this document and the canonical Ledger
in the same product commit as progress changes. Authority/current-conformance
changes must also update the canonical Architecture in that same commit.

Use the existing delivery states:

```text
DESIGNED
 -> BACKEND_READY
 -> API_VISIBLE
 -> ANDROID_VISIBLE
 -> OBSERVABLE
 -> PRODUCT_DONE
```

No slice is `PRODUCT_DONE` unless its Android entry, authoritative API state,
failure/degraded states and acceptance evidence all exist.

## 15. Explicitly rejected designs

1. Removing position monitoring because Watchlist/Discovery limits are reached.
2. Treating Watchlist membership as BUY permission.
3. Letting Personal Watchlist silently become an Evaluation experiment universe.
4. Running full AI research whenever a market-data scheduler wakes.
5. Re-running full research for a full position with no material change.
6. Treating 5m/15m changes as a reason to redo company research.
7. Auto-promoting Discovery items into Watchlist or Formal trading scope.
8. Calling all Candidate/Discovery items "recommended stocks".
9. Backend-only Watchlist configuration with no Android entry.
10. An Android-only fake review state calculated in Compose.
11. Copying third-party visual assets/trade dress instead of adapting generic
    density/layout principles into ThirdHand tokens.

## 16. Product acceptance question

After these slices are complete, opening ThirdHand should answer:

```text
What changed in what I own?
What changed in what I explicitly follow?
Which symbols actually need review now?
Why did the system deliberately skip analysis?
Are there any optional new discoveries worth promoting?
```

The intended end state is a governed swing-trading assistant centered on the
user's positions and durable interests, not an always-on AI stock-picking feed.
