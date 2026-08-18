# P1 — Decision AI Runtime Recovery and Audit Hardening

Tracks: #40

Status: **Design approved for implementation; draft PR must not merge until failure-path integration tests pass.**

## 1. Problem statement

The Xiaomi `01810` black-box run on 2026-08-18 reproduced a provider/runtime failure despite the existing bounded ModelPolicy recovery graph:

```text
DeepSeek v4 Pro
  -> empty_content
  -> provider retry
  -> empty_content
  -> provider retry
  -> empty_content
  -> provider failure
  -> later invalid structured output / ValidationError
  -> ai_assessment = null
```

The formal Decision remained fail-closed and deterministic. That safety property must remain unchanged.

The defect is advisory research reliability and insufficient attempt-level observability for compound failures.

## 2. Existing behavior to preserve

Current policy concepts remain valid:

```text
FLASH_DEFAULT
PRO_ESCALATION (thinking)
PRO_STRUCTURED_RECOVERY (non-thinking)
```

Current safety boundaries remain mandatory:

- AI may only choose among policy candidates;
- AI references must resolve to supplied evidence IDs;
- formal action is deterministic when AI fails;
- no raw hidden reasoning persisted.

## 3. Runtime state machine

Make the policy-level attempt graph explicit and auditable.

Suggested bounded graph:

```text
DEFAULT_STRUCTURED
  | schema/semantic invalid
  v
PRO_REASONING
  | empty / truncated / unusable structured result
  v
PRO_STRUCTURED_RECOVERY
  | invalid
  v
FAIL_CLOSED
```

When evidence complexity already selects `PRO_REASONING`, the first transition may start there.

Provider-level retries happen *inside* one policy-level attempt and must not be confused with policy-tier transitions.

## 4. Attempt audit contract

Persist one audit item per policy-level attempt:

```text
attempt_index
policy_tier
model
thinking
max_tokens
started_at
finished_at
provider_attempt_count
provider_retry_codes[]
finish_reason
content_present
content_length
content_hash
reasoning_present
reasoning_length
reasoning_hash
schema_validation_status
schema_error_code/path
semantic_validation_status
semantic_error_code/path
transition_reason
```

Privacy requirements:

- never persist API keys;
- never persist raw hidden reasoning;
- raw failed model content is not required by default;
- hashes/lengths/status are sufficient for normal diagnostics.

If provider response does not expose reasoning metadata, record `unknown`, not fabricated zeros.

## 5. Error classification

Use explicit runtime classes:

```text
TRANSPORT
HTTP_RETRYABLE
HTTP_FATAL
EMPTY_CONTENT
OUTPUT_TRUNCATED
INVALID_RESPONSE_SHAPE
SCHEMA_INVALID
SEMANTIC_INVALID
CIRCUIT_OPEN
LOCAL_RATE_LIMITED
```

Do not collapse a final `ValidationError` into a generic `invalid_ai_output` without preserving the preceding `empty_content` transition history.

## 6. Recovery rules

### Empty content

After bounded provider-level retries for the same configuration:

```text
thinking attempt -> non-thinking structured recovery
```

Do not keep replaying the same thinking configuration across policy tiers.

### Truncation

Switch to non-thinking structured recovery with a larger bounded output budget.

### Schema-invalid output

Use a minimal repair instruction:

- one JSON object only;
- exact schema keys;
- exact candidate action set;
- exact evidence IDs or `[]`;
- concise visible reasoning summaries only;
- no Markdown.

### Semantic-invalid output

Do not relax:

- evidence-ID validation;
- candidate-action restrictions;
- backend-owned fields;
- hard-risk constraints.

A failure to satisfy semantics ends fail-closed.

## 7. Provider capability contract

Do not assume every OpenAI-compatible endpoint supports identical reasoning/JSON features.

Introduce or extend a provider capability profile for:

```text
json_object support
schema-enforced response support (if any)
thinking toggle support
reasoning metadata exposure
max output behavior
```

Use capabilities to shape payloads; unsupported provider options must not be guessed.

## 8. Tests

Use deterministic fake-provider sequences rather than depending on live DeepSeek in CI.

Required fixtures:

1. default success;
2. empty -> structured recovery success;
3. reasoning empty after provider retries -> structured recovery success;
4. reasoning truncated -> structured recovery success;
5. schema invalid -> repair success;
6. semantic invalid -> fail closed;
7. empty -> recovery schema invalid -> fail closed with full audit path;
8. timeout / transport retries;
9. circuit open;
10. AI failure leaves formal Decision unchanged.

## 9. Xiaomi reproduction acceptance

Re-run the same `01810` black-box input that produced repeated `empty_content`.

Acceptance is either:

```text
AI succeeds through a bounded documented recovery path
```

or:

```text
AI fails closed, with the exact compound failure path visible in audit metadata
```

It is not acceptable for the final record to expose only `invalid_ai_output` while losing the preceding provider/runtime failure sequence.

## 10. Out of scope

- giving AI formal trading authority;
- unlimited retries;
- persisting hidden chain-of-thought;
- introducing provider-specific “max reasoning” tiers without a tested capability contract.

## 11. Merge gate

Merge only after:

1. attempt-level audit implemented;
2. compound failure sequence covered by tests;
3. bounded recovery graph remains finite;
4. formal fail-closed behavior is proven;
5. full backend suite passes.
