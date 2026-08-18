# P0 — Financial Currentness and Report Freshness

Tracks: #39

Status: **Design approved for implementation; draft PR must not merge until semantic migration + tests are complete.**

## 1. Problem statement

The Xiaomi `01810` black-box test on 2026-08-18 showed that current `freshness_status` can mark a financial dataset as fresh because it was retrieved today even when the underlying report period is historical and a newer report is due now.

Observed:

```text
financial_summary
  provider = AKShare
  report/as_of = 2025-12-31
  retrieved/available = 2026-08-18
  freshness_status = fresh

known corporate event
  earnings_report
  scheduled_at = 2026-08-18
```

Research aggregation then used 2025 annual growth metrics as supportive fundamentals. Those facts are valid historical evidence, but they are not equivalent to current-period confirmation on the day a new interim result is expected.

## 2. Required semantic split

Replace the overloaded idea of `freshness` with separate dimensions.

### Retrieval freshness

Answers:

> Did we recently fetch/validate this snapshot?

Suggested states:

```text
FRESH
STALE
UNKNOWN
```

### Observation/report currentness

Answers:

> Which business/reporting period does the fact describe, and is it still the latest expected period?

Suggested states:

```text
CURRENT
HISTORICAL_VALID
PENDING_EXPECTED_REPORT
STALE_RELATIVE_TO_EXPECTED_REPORT
UNKNOWN
```

### Availability

Answers:

> Is the expected current-period observation actually available yet?

Suggested states:

```text
AVAILABLE
PENDING
MISSING
UNAVAILABLE
UNKNOWN
```

Names may change, meanings must not collapse back into one field.

## 3. Required time fields

Financial snapshots/facts must preserve enough source time semantics to distinguish data age from fetch age:

```text
period_start
period_end
announced_at / published_at
available_at
retrieved_at
source_as_of
```

Where a provider does not expose a field, store `UNKNOWN`; do not derive fictional precision.

## 4. Expected-period policy

Add a deterministic `FinancialCurrentnessPolicy` before fundamental aggregation.

Inputs may include:

- market / fiscal year end
- latest persisted financial report periods
- known `CorporateEvent` earnings/result dates
- event lifecycle (`upcoming`, `released`, etc.)
- current market date/time

Output minimum:

```text
latest_observed_period
expected_latest_period
latest_period_status
current_confirmation_status
reason_codes[]
```

### Example

On 2026-08-18:

```text
latest observed = FY2025 annual
known event = 2026 interim results scheduled today
```

Before new interim data is ingested:

```text
retrieval_freshness = FRESH
historical_validity = VALID
latest_period_status = PENDING_EXPECTED_REPORT
current_confirmation_status = UNKNOWN/PENDING
```

After a verified 2026 interim report is ingested:

```text
latest_period_status = CURRENT
current_confirmation_status = AVAILABLE
```

## 5. Atomic Evidence contract

Historical facts remain immutable historical facts. Add currentness metadata rather than mutating polarity.

For financial `AtomicFactRecord`, add or propagate:

```text
period_start
period_end
report_type
announced_at
retrieval_freshness
observation_currentness
expected_period_status
```

A historical supportive YoY fact remains supportive **for historical trend**, but may not count as current confirmation when the expected latest report is pending.

## 6. Aggregation contract

Fundamental aggregation must distinguish:

```text
historical_fundamental_trend
current_fundamental_confirmation
```

The existing dimension output may remain for compatibility, but the decision/research layer must not interpret historical-only support as proof of current-period confirmation.

Suggested aggregate semantics:

```text
historical trend: SUPPORTIVE / NEUTRAL / ADVERSE / INSUFFICIENT
current confirmation: CONFIRMED / PENDING / UNKNOWN / CONFLICTED
```

A same-day earnings event with no new report ingested should create a pending/unknown current confirmation even if historical trend is strong.

## 7. Interaction with CorporateEvent

Corporate events can constrain **currentness**, not direction.

```text
earnings scheduled today
```

means:

```text
new report expected / pending
```

It does **not** mean bullish or bearish.

Profit warnings/guidance may carry separate evidence polarity according to their own verified facts, but report scheduling itself remains neutral-material.

## 8. Backward compatibility / migration

Do not silently reinterpret existing persisted `freshness_status`.

Migration strategy:

1. keep current retrieval freshness field for compatibility;
2. add explicit currentness fields with a version bump;
3. recompute currentness deterministically at read/build time for old snapshots where possible;
4. use `UNKNOWN` where period semantics are not recoverable;
5. bump Atomic/Fundamental aggregation policy versions when the new semantics become authoritative.

## 9. Tests

### Unit

- fetched today, period last year -> retrieval fresh, observation historical
- known earnings event today + old latest report -> pending expected report
- event tomorrow -> expected report pending, not current
- new verified report ingested -> current
- provider omits period -> unknown, never current by retrieval timestamp alone

### Aggregation

- historical supportive + current pending -> historical supportive, current confirmation pending
- historical adverse + current pending -> historical adverse, current confirmation pending
- missing current report must not become neutral/pass

### Golden Xiaomi

At `2026-08-18` with only FY2025 annual financials and the known 2026 interim event:

```text
historical_fundamental_trend = SUPPORTIVE (if supported by facts)
current_fundamental_confirmation = PENDING/UNKNOWN
```

The system must not present FY2025 as current-period confirmation merely because it was fetched on 2026-08-18.

## 10. Out of scope

- predicting earnings direction;
- changing historical source values;
- adding new financial providers solely to hide currentness gaps;
- allowing AI to infer missing report periods as facts.

## 11. Merge gate

Merge only after:

1. data-model/currentness policy implemented;
2. versioned aggregation updated;
3. migration/compatibility behavior covered;
4. full backend tests pass;
5. Xiaomi same-day earnings black-box reports historical support separately from current confirmation.
