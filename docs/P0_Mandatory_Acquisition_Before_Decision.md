# P0 — Mandatory Acquisition Before Formal Decision

Tracks: #38

Status: **Design approved for implementation; draft PR must not merge until code + black-box acceptance are complete.**

## 1. Problem statement

The Xiaomi `01810` black-box test on 2026-08-18 proved that ThirdHand can correctly *describe* missing research requirements, but a formal Decision does not guarantee that the required acquisition runs before evidence is frozen.

Observed sequence:

```text
RAW formal Decision
  -> corporate_event_cache = null
  -> earnings event not present
  -> WAIT for stale/missing market inputs

requirements(L3)
  -> all datasets = LOCAL_MISS
  -> some provider_registered=true
  -> some provider_registered=false

manual build_context(allow_remote=true)
  -> six datasets fetched
  -> three remain missing

manual scheduler acquisition
  -> 2026-08-18 earnings discovered
  -> EventRiskGate blocks OPEN/ADD
```

The Requirement Planner is therefore not the defect. The missing stage is **governed action from requirement state to acquisition attempt**.

## 2. Authority model

The formal pipeline becomes:

```text
Decision Request
  -> Research Requirement Planner
  -> Coverage Inspection
  -> Mandatory Acquisition
  -> Post-fetch Verification
  -> AcquisitionManifest freeze
  -> DecisionContext / Frozen Evidence
  -> Deterministic Research
  -> AI Research Gateway
  -> Arbiter
```

### Non-negotiable boundary

Remote I/O is forbidden inside:

- `DecisionContextBuilder`
- `EvidenceEngine`
- Atomic normalization/aggregation
- AI validation
- Arbiter
- execution policy

Those layers consume persisted/frozen inputs only.

Schedulers remain cache warmers. Correctness must not depend on whether a scheduler happened to run first.

## 3. Requirement-state semantics

`LOCAL_MISS` is a state, not a command. The acquisition orchestrator converts state into a governed action.

```text
LOCAL_FRESH_HIT
  -> REUSE

LOCAL_STALE_HIT + provider_registered=true
  -> REFRESH when currentness is mandatory

LOCAL_MISS + provider_registered=true
  -> FETCH once within the decision acquisition budget

LOCAL_MISS + provider_registered=false
  -> UNAVAILABLE
  -> persist unresolved coverage
  -> do not fabricate success
```

A later optional gap-filling/tool provider may be introduced, but it must be separately governed and may not turn unknown facts into formal PASS conditions.

## 4. Mandatory acquisition set

The exact requirement set is market/action/research-priority aware, but the initial implementation must cover:

### Market / execution facts

- instrument metadata / market identity
- quote when current execution price is required
- daily bars needed for technical/risk state
- benchmark / market regime when the market adapter supports it
- FX / settlement prerequisites where relevant

### Event facts

- corporate event calendar for the decision protection window
- event status and provenance

### Company research facts

Derived from existing Company Intelligence requirements for the selected research priority.

For L3, a provider-backed `LOCAL_MISS` must no longer remain passive merely because the formal Decision path was invoked directly.

## 5. Proposed components

### `ResearchAcquisitionOrchestrator`

Responsibilities:

1. resolve research priority and market identity;
2. obtain requirement list;
3. inspect local state;
4. decide `REUSE / FETCH / REFRESH / UNAVAILABLE`;
5. execute bounded provider calls;
6. verify post-fetch state;
7. persist `AcquisitionManifest`;
8. return only after the acquisition phase is complete or explicitly degraded.

### `AcquisitionManifest`

Minimum audit fields:

```text
manifest_id
symbol
market
requested_at
completed_at
requirement_policy_version
budget_policy_version

items[]:
  requirement_key
  domain
  mandatory_for
  pre_state
  provider_registered
  attempted
  provider
  attempt_status
  error_code
  post_state
  as_of
  available_at
  freshness_status
  provenance_hash
```

The manifest hash must be linkable from the Decision lineage.

### `PostFetchVerifier`

Provider return/no-exception is not success by itself. Verify:

- expected symbol/market
- required payload coverage
- as-of semantics
- freshness/currentness
- provenance
- cross-source consistency

## 6. Entry-point wiring

All production paths that create a **new formal Decision** must invoke the same preflight acquisition service before `DecisionContextBuilder.build(...)`.

At minimum cover:

- user/API formal decision generation
- paper-trading decision preparation
- any scheduler path that creates a formal decision

Do not duplicate acquisition rules separately in those entrypoints; inject/call one application service.

## 7. Budget and failure policy

Acquisition must be bounded:

- one requirement-level attempt per decision preflight unless provider policy explicitly permits retry;
- global time budget;
- provider concurrency limit;
- deterministic fallback to persisted stale data only when policy allows;
- mandatory missing/stale/conflicted evidence cannot increase risk.

If acquisition cannot establish required current evidence, the formal decision proceeds only in degraded/fail-closed mode with explicit missing/unavailable reason codes.

## 8. Tests

### Unit

- `LOCAL_MISS + registered -> FETCH`
- `LOCAL_MISS + unregistered -> UNAVAILABLE`
- fresh local hit -> no remote call
- stale local hit -> refresh when mandatory
- provider error -> explicit degraded item
- provider success but no coverage -> verification failure

### Integration

- formal API generation invokes acquisition exactly once
- paper decision generation invokes the same service
- builder/evidence/AI perform zero remote calls
- manifest linked to saved decision

### Golden black-box

Cold-cache Xiaomi scenario:

```text
01810
2026-08-18
no manual company build
no manual scheduler refresh
```

Expected:

- formal preflight attempts mandatory event/company acquisition;
- earnings event is discovered and OPEN/ADD are gated, **or** event acquisition is explicitly unavailable/unknown and OPEN/ADD fail closed;
- no silent `corporate_event_cache=null` path is accepted as if event coverage were complete.

## 9. Out of scope

- giving AI direct web authority over formal facts;
- allowing AI to override hard gates;
- implementing every currently unregistered company dataset provider in this PR;
- replacing scheduler cache warming.

## 10. Merge gate

The PR may merge only when:

1. implementation is wired to all formal Decision entrypoints;
2. deterministic tests pass;
3. full backend suite passes;
4. Xiaomi cold-cache black-box passes without the manual B/C acquisition steps used in the investigation.
