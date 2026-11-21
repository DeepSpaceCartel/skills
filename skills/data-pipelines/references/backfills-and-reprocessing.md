# Backfills and reprocessing

Changing a pipeline that is already writing data people use: a new parser, a fixed transform,
a new enrichment, a matching rule, or a rerun over history after a bug. Code can be rolled
back; data written by bad code stays written and flows downstream. This reference covers the
release path for pipeline changes, shadow comparison, throttled backfills, and reprocessing
after bad output. Schema changes and column backfills inside one database are in
[database-migrations](../../engineering-practices/references/database-migrations.md); flags,
canaries and rollback in general are in
[release-engineering](../../engineering-practices/references/release-engineering.md). Anchor
sources: the [SRE Workbook](https://sre.google/workbook/data-processing/) (development
lifecycle, two-phase mutation, corrupt-data response) and the
[SRE book](https://sre.google/sre-book/data-processing-pipelines/) (thundering herds, overlapping
runs).

## What agents typically get wrong

- **Shipping a transform change straight to the full dataset.** A unit test on five records
  passes; the change then rewrites ten million records, a tenth of them wrongly.
- **Comparing only counts.** Old and new runs both produce 1,000 rows, so the change "matches".
  The diff that matters is per field: which values changed, and which went from filled to empty.
- **A canary that writes to production.** A canary meant to test the change then becomes the
  incident. The workbook's canary runs on real input but holds writes back (for example with
  two-phase mutation) and compares outputs.
- **A random sample that changes each run.** Ramping 1% then 10% with fresh random picks moves
  different items in and out. Bucket by a stable hash of the key so the 1% stays inside the 10%.
- **Backfilling at full speed.** The backfill competes with live traffic for the source's rate
  limit, the store's write capacity and the workers, and live freshness falls. The SRE book's
  warning about adding workers to a late job applies: it often makes things worse.
- **No marker on what each run wrote.** Without a run or code version on each record, nobody can
  find which rows a bad release touched, so the repair becomes "reprocess everything".
- **Repairing while the bad writer still runs.** Stop the damage first.
- **Reprocessing from the output.** Re-deriving from already-transformed data repeats the bug's
  effects. Reprocess from raw input that was kept.

## Procedure

**Releasing a pipeline change** (the workbook's lifecycle, in this skill's words)

1. **Prototype and unit-test** the change on fixtures, including the awkward cases from
   production (missing fields, odd encodings, empty sources).
2. **Dry run on a small share** of real input in a non-production environment, writing to a
   scratch store. Watch for errors and throughput limits; scale up the share.
3. **Shadow compare.** Run old and new on the same input, write nothing, and diff field by
   field (example below). Every changed field is either expected and explained, or a bug.
4. **Canary on production input** without production writes: stage the canary's output, compare
   it with the live output, and check the SLIs on the staged output.
5. **Ramp behind a flag** keyed on a stable bucket: about 1%, 10%, 50%, then 100%, checking SLIs
   and the shadow diff at each step. Pause on any unexpected change.
6. **Keep the way back ready:** the old code deployable, raw input retained, and each record
   tagged with the run and code version that wrote it.

**Running a backfill or reprocessing**

1. **State the scope:** which sources, which time range, which fields. Estimate rows and time.
2. **Set a budget** below the headroom of the tightest resource: the source's rate limit, the
   store's write rate, the worker pool. Leave live traffic its share; give the backfill its own
   queue or priority tier so live work goes first.
3. **Checkpoint** by partition so it can stop and resume (see
   [idempotent-stages](idempotent-stages.md)). Make every write idempotent.
4. **Start small** (one partition), validate the output, then widen.
5. **Watch live SLIs** during the run. Pause automatically if live freshness or error rate moves.
6. **Validate at the end**: counts and per-field completeness against the expected result, and
   a sample checked by hand.

**After bad output reached the store**

1. **Stop the writer**: roll back the binary or flip the flag, and pause downstream jobs that
   read the bad data.
2. **Bound the damage** by the run and version tags: which records, since when.
3. **Mark bad data** so readers skip it, then **reprocess selectively** from raw input for only
   the affected records. Restore from backup only if raw input is gone; use
   [`data-integrity`](../../data-integrity/SKILL.md) for that.
4. **Tell downstream consumers** what was wrong and what was re-sent.

## Techniques

- **Stable ramp buckets.** Hash the item key into 10,000 buckets and include buckets below the
  ramp percentage. Widening the ramp only adds items.
- **Field-level diff report.** For each field: changed count, filled-to-empty count, and a few
  examples. Gate on filled-to-empty being zero unless expected.
- **Golden set.** Keep inputs with known outputs per source type and run them on every change
  (see [pipeline-slos](pipeline-slos.md)).
- **Run and version tags** on every output row: `run_id`, `code_version`, `written_at`. They turn
  a repair from a guess into a query.
- **Keep raw input** for as long as you might need to reprocess, priced against storage.
- **Throttle arithmetic.** Rows divided by the budget gives the duration; check it fits the
  window. 12 million rows at 400 writes per second is about 8.3 hours. If the store has 2,000
  writes per second of headroom, 400 leaves live traffic most of it.
- **Spread start times.** Many backfill workers starting together hit the source and shared
  services at once (the SRE book's thundering herd). Stagger starts and cap concurrency.

## Example

A shadow comparison that runs both transforms on the same input, writes nothing, and gates the
ramp on field-level diffs, plus stable ramp buckets:

```python
import hashlib
from collections import Counter

def in_ramp(key: str, percent: float) -> bool:
    """Stable bucket per key, so the same items stay in the ramp as it widens."""
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % 10_000 < percent * 100

def shadow_compare(records, old, new, fields):
    """Run both transforms on the same input; write nothing; report field-level diffs."""
    changed, lost, errors = Counter(), Counter(), 0
    for r in records:
        a = old(r)
        try:
            b = new(r)
        except Exception:
            errors += 1; continue
        for f in fields:
            if a.get(f) != b.get(f):
                changed[f] += 1
                if a.get(f) not in (None, "") and b.get(f) in (None, ""):
                    lost[f] += 1
    return {"n": len(records), "errors": errors, "changed": dict(changed), "lost": dict(lost)}

def gate(report, *, max_error=0.001, max_lost=0.0, expected_changes=()):
    n = report["n"]
    problems = [f"errors {report['errors']}/{n}"] if report["errors"] / n > max_error else []
    problems += [f"'{f}' emptied on {c}" for f, c in report["lost"].items() if c / n > max_lost]
    problems += [f"unexpected change in '{f}' ({c})" for f, c in report["changed"].items()
                 if f not in expected_changes]
    return problems
```

On 1,000 synthetic records where one in ten has a location without a comma (`"Remote"`), a new
transform that returns no city for those records produced
`{'n': 1000, 'errors': 0, 'changed': {'city': 100}, 'lost': {'city': 100}}`, and the gate
returned two problems (`'city' emptied on 100`, an unexpected change in `city`), so the ramp
stops. The record counts matched exactly, which is why counts alone would have passed it. The
ramp check put 7 records in the 1% bucket and 117 in the 10% bucket, and every 1% record was
also in the 10% bucket.

## Gotchas and contested points

- **Shadow runs cost double** for their duration. Run them on a sample, not the whole stream,
  unless the change is high risk.
- **Replicated or multihomed pipelines** can't always be canaried one region at a time, the
  workbook notes. Canary by data share or in dry-run mode instead.
- **Expected changes hide unexpected ones.** If a change is meant to alter `title`, a separate bug
  in `title` passes the gate. Look at examples, not just counts, for expected fields.
- **Backfills and live runs race.** A backfill writing an old version of an item can overwrite a
  live update. Guard writes with a version or timestamp so the newer value wins.
- **Downstream reprocessing is not free.** Re-sending corrected data makes consumers reprocess
  too. Send only what changed, and say so.

## Review checklist

1. Did the change go through dry run, shadow comparison, canary without production writes, and
   a ramp on stable buckets?
2. Does the shadow diff report changes and filled-to-empty counts per field, not only row counts?
3. Is every changed field either expected and explained, or treated as a blocker?
4. Is each output row tagged with the run and code version that wrote it?
5. Is raw input retained long enough to reprocess from it?
6. Does the backfill have a rate budget below the tightest resource's headroom, its own queue or
   priority, and checkpoints?
7. Does the backfill pause automatically when live SLIs move?
8. Are backfill writes guarded so an older version can't overwrite a newer live one?
9. After bad output: was the writer stopped first, the damage bounded by tags, and only affected
   records reprocessed?
10. Were downstream consumers told what was wrong and what was re-sent?

## Related

[pipeline-slos](pipeline-slos.md) (golden data, SLIs to watch during a ramp),
[idempotent-stages](idempotent-stages.md) (checkpoints, version guards),
[failure-isolation](failure-isolation.md) (separate queues for backfill traffic),
[release-engineering](../../engineering-practices/references/release-engineering.md) (flags,
canaries, rollback), [database-migrations](../../engineering-practices/references/database-migrations.md)
(schema changes, column backfills),
[corruption-and-bad-writes](../../data-integrity/references/corruption-and-bad-writes.md)
(repairing bad writes in the store).

## Sources

Google SRE Workbook, [Data Processing Pipelines](https://sre.google/workbook/data-processing/)
(lifecycle: prototype, small dry run, staging with output comparison, canary without production
writes via two-phase mutation, gradual ramp, rollback and reprocessing; corrupt-data response;
regions that can't be canaried one at a time). Google SRE book,
[Data Processing Pipelines](https://sre.google/sre-book/data-processing-pipelines/) (thundering
herd, adding workers to a late job). The field-level diff gate, stable ramp buckets and run tags
are this skill's synthesis.
