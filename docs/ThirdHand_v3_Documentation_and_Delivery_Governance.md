# ThirdHand v3 Documentation and Delivery Governance

> Status: repository governance contract for v3 delivery.
> This document does not override `ThirdHand_Architecture_v3_consolidated.md`
> or `ThirdHand_v3_Roadmap_and_Ledger.md`. The architecture remains the
> authority/safety contract and the ledger remains the authoritative delivery
> status. This document defines how code, commits and pull requests must keep
> those two sources synchronized.

## 1. Purpose

ThirdHand now evolves across backend domain/runtime code, API contracts, Android
surfaces, strategy definitions, paper execution and evaluation. A recurring
failure mode is unacceptable from this point forward:

```text
implementation changes
  -> code is merged
  -> authoritative status remains stale
  -> later contributors/AI read the wrong project state
```

Documentation synchronization is therefore a merge requirement, not optional
cleanup.

## 2. Sources of truth

The repository has two canonical documents:

1. `docs/ThirdHand_Architecture_v3_consolidated.md`
   - authority boundaries;
   - safety invariants;
   - target/current architecture conformance;
   - formal decision/execution semantics.
2. `docs/ThirdHand_v3_Roadmap_and_Ledger.md`
   - implementation/delivery status;
   - active correctness gaps;
   - milestone layer status;
   - deployed/device acceptance state.

Subordinate design documents may add detail but may not claim status that
conflicts with the canonical pair.

## 3. Mandatory commit-level synchronization

A **product implementation commit** is any non-merge commit that changes code
under one or more of these product surfaces:

```text
backend/app/**
android/app/src/main/**
android/app/build.gradle.kts
```

Every product implementation commit MUST update
`docs/ThirdHand_v3_Roadmap_and_Ledger.md` in the **same commit**.

The ledger update may be small, but it must truthfully record one of:

- milestone/layer advanced;
- implementation partially completed;
- acceptance still pending;
- structural refactor only, delivery status unchanged;
- rollback/regression/status moved backward.

Do not defer the status update to a later cleanup commit.

### Authority-impact commits

If a commit changes formal strategy, action, risk, continuity, sizing,
execution, paper-broker or authority-boundary code, the same commit MUST also
update `docs/ThirdHand_Architecture_v3_consolidated.md`.

Authority-sensitive areas include, but are not limited to:

```text
backend/app/domain/strategy/**
backend/app/application_services/strategy/**
backend/app/action_policy.py
backend/app/decision_*.py
backend/app/timeframe_authority.py
backend/app/research_assessment.py
backend/app/execution_precheck.py
backend/app/position_sizing.py
backend/app/risk.py
backend/app/paper_execution_contract.py
backend/app/paper_runtime*.py
```

A change that only adds identity/audit metadata must explicitly say that formal
action authority is unchanged.

## 4. Mandatory pull-request synchronization

A PR that contains product implementation changes MUST include an updated
`ThirdHand_v3_Roadmap_and_Ledger.md` in its diff.

A PR that contains authority-sensitive implementation changes MUST also include
an updated `ThirdHand_Architecture_v3_consolidated.md` in its diff.

The PR description MUST state:

- authority impact;
- strategy impact;
- Backend/API/Android/Observable/Acceptance layer status;
- exact delivery status;
- documentation files synchronized;
- remaining acceptance or follow-up work.

A PR must never claim a higher delivery state than the implemented layers prove.

## 5. Delivery-state rules

Use the shared vocabulary:

```text
DESIGN
BACKEND_READY
API_READY
ANDROID_READY
OBSERVABLE
ACCEPTED
PRODUCT_DONE
```

Hard rules:

- `BACKEND_READY != PRODUCT_DONE`.
- Android code existing is not automatically `OBSERVABLE`; reasons, missing,
  stale, conflicted, blocked and error states must be understandable.
- Repository tests are not deployed/device acceptance.
- Design-only work cannot claim runtime completion.
- A production observation cannot silently change architecture; update the
  canonical pair with evidence and acceptance consequences.

## 6. Frontend/backend task completion rule

When a designated backend task is completed:

1. update implementation/tests;
2. update the ledger in the same commit;
3. mark only the highest proven layer (`BACKEND_READY` or `API_READY`);
4. keep Android/Observable/Acceptance explicitly pending when applicable.

When the corresponding Android task is completed:

1. consume structured backend/API truth;
2. render required states/reasons;
3. update the ledger in the same commit to `ANDROID_READY` or `OBSERVABLE`;
4. do not mark `PRODUCT_DONE` until acceptance evidence exists.

When acceptance completes:

1. record the deployed/device/black-box evidence;
2. update the ledger immediately;
3. update architecture conformance if the accepted result changes a previously
   partial/gapped architecture claim;
4. only then mark `ACCEPTED` / `PRODUCT_DONE`.

## 7. CI enforcement

`.github/scripts/check_documentation_sync.py` is the enforcement gate.

For pull requests it verifies:

1. every product implementation commit contains a same-commit ledger update;
2. every authority-sensitive commit contains a same-commit architecture update;
3. the aggregate PR diff contains the required canonical documentation changes;
4. the PR body declares Delivery Status and Documentation Sync sections.

The `documentation-governance` job is required by `ci-gate`. A PR that violates
this contract must not merge merely because backend/Android builds pass.

## 8. No silent exceptions

Merge commits and non-product commits (for example docs-only or tests-only
commits) do not trigger the product-code synchronization rule.

Refactors that touch product implementation paths are **not exempt**: record
`status unchanged; structural refactor only` in the ledger so later readers can
distinguish intentional no-op architecture work from forgotten status updates.

If a future exceptional workflow genuinely requires a bypass, that bypass must
be designed as an explicit, audited repository policy change. Do not introduce
an informal label/comment escape hatch.

## 9. Required PR matrix

Every product PR should include this table in its description:

| Layer | Status | Evidence / remaining work |
| --- | --- | --- |
| Backend | yes/no | ... |
| API | yes/no/n-a | ... |
| Android | yes/no/n-a | ... |
| Observable | yes/no/n-a | ... |
| Accepted | yes/no | ... |

The final row of the PR must declare one exact delivery state and must match the
canonical ledger.

## 10. Governing principle

ThirdHand documentation is part of the implementation contract.

```text
Code changes project truth
+ canonical docs record project truth
+ CI proves they changed together
```

A feature is not complete when code alone says it is complete.
