---
name: data-pipelines
description: Designing and operating batch or continuous data pipelines (ingestion, crawler and scraper fleets, ETL, enrichment, change feeds) - project-agnostic. Covers freshness, coverage, correctness and per-field completeness SLIs measured end to end; proving a read was complete before treating unseen items as deleted (stated totals, page-walk stop rules, short pages); telling our-side failures from source failures; idempotent, checkpointed and two-phase stages; backfills, reprocessing and shadow comparison; poison records, dead-letter queues and redrive; per-source rate limits, hotspots, backlogs and dashboards. Use when building or reviewing a pipeline, backfill, scraper or crawler fleet, or when data is stale, missing or wrong, or items vanished after a run. Not for backups, restores or lost volumes (see data-integrity), schema migrations (see engineering-practices), choosing a broker or pattern (see infrastructure-patterns), or one service's request retries and timeouts (see engineering-practices).
---

# Data Pipelines

Moving data from sources through stages into stores that others read: list and fetch, parse,
transform, enrich, diff, write, publish. Pipelines fail quietly. A run that read half the
source still exits 0, a stage that drops a field still reports success, and the dashboard stays
green while the data goes stale. The references are grounded in Google's SRE book and SRE
Workbook chapters on data processing pipelines, the Azure Architecture Center messaging
patterns, microservices.io, and the AWS Builders' Library on queue backlogs. Each leads with
what agents get wrong, then gives a procedure, a tested example and a numbered review
checklist.

The skill covers the **flow of data**. For the stored copy (backups, restores, corruption,
safe deletion) use [`data-integrity`](../data-integrity/SKILL.md). For one service's timeouts,
retries, idempotency keys and burn-rate alerts use
[`engineering-practices`](../engineering-practices/SKILL.md) (reliability).

## How to use this skill

1. Find the task or symptom in the tables below and read that one reference. Don't load all
   five.
2. Before shipping any stage that **closes, deletes or marks items gone** because they were not
   seen, run the checklist in [completeness-and-absence](references/completeness-and-absence.md).
3. Before shipping any change to a running pipeline, or a backfill, run the checklist in
   [backfills-and-reprocessing](references/backfills-and-reprocessing.md).
4. When data is stale, missing or wrong, first check the SLIs in
   [pipeline-slos](references/pipeline-slos.md): they say which stage and which sources.

## The catalog

| Topic | Read when | Reference |
|---|---|---|
| Pipeline SLOs | Defining freshness, coverage, completeness or correctness; per-field completeness; end-to-end measurement; pipeline dashboards and alerts | [pipeline-slos](references/pipeline-slos.md) |
| Completeness and absence | A diff that closes or deletes what was not seen; paginated walks; stated totals; empty results; telling our failures from the source's | [completeness-and-absence](references/completeness-and-absence.md) |
| Idempotent stages | Reruns, retries and at-least-once delivery; dedupe; checkpoint and resume; two-phase or staged writes; leases on work | [idempotent-stages](references/idempotent-stages.md) |
| Backfills and reprocessing | Releasing a pipeline change; dry runs, canaries and ramps; throttled backfills; shadow comparison; reprocessing after bad output | [backfills-and-reprocessing](references/backfills-and-reprocessing.md) |
| Failure isolation | Poison records, dead-letter queues and redrive; per-source rate limits and cooldowns; hotspots and partitioning; queue backlogs | [failure-isolation](references/failure-isolation.md) |

## Symptom to reference

| Symptom or situation | Look at |
|---|---|
| Thousands of items marked removed after one run that reported `ok` | [completeness-and-absence](references/completeness-and-absence.md): the walk stopped early (a short page mid-list, a cursor that ended, a truncated response) |
| A source returned zero items and every known item was closed | [completeness-and-absence](references/completeness-and-absence.md): an empty result is not the source saying "zero" |
| Many records stored without a field (location, price, date) and nobody noticed | [pipeline-slos](references/pipeline-slos.md): per-field completeness SLI against a baseline |
| Every target in a run timed out at once and was recorded dead or gone | [completeness-and-absence](references/completeness-and-absence.md): our pool, deadline or DNS failed; canaries and error classes |
| One tenant's 429 paused every tenant on the same provider; freshness for the provider fell to zero | [failure-isolation](references/failure-isolation.md): key cooldowns by the unit the source limits |
| Freshness looks fine but users see old data | [pipeline-slos](references/pipeline-slos.md): the denominator dropped paused or failing sources, or the SLI is per stage |
| Each stage reports success but the output is missing data | [pipeline-slos](references/pipeline-slos.md): measure end to end, with golden data |
| A rerun or redelivery created duplicates or double-counted | [idempotent-stages](references/idempotent-stages.md) |
| A crash forced a restart from the beginning | [idempotent-stages](references/idempotent-stages.md): checkpoint and resume |
| One record crashes the worker on every retry; the queue stops moving | [failure-isolation](references/failure-isolation.md): poison record, dead-letter, redrive |
| Backlog keeps growing after an outage ended | [failure-isolation](references/failure-isolation.md): recovery needs spare capacity; serve fresh work first |
| An admin stats or report query stalls every worker | [failure-isolation](references/failure-isolation.md): keep reads off the coordinator's write path |
| About to change a parser, transform or matching rule on live data | [backfills-and-reprocessing](references/backfills-and-reprocessing.md) |
| Need to reprocess months of history | [backfills-and-reprocessing](references/backfills-and-reprocessing.md) |
| A bad run already wrote wrong data to the store | [backfills-and-reprocessing](references/backfills-and-reprocessing.md), then [`data-integrity`](../data-integrity/SKILL.md) corruption-and-bad-writes for the repair |

## Working rules

A synthesis across the references:

1. **Absence needs proof.** "Not seen in this run" means "gone" only when the run proved it
   read everything. Otherwise fail the run and change nothing.
2. **Fail the run, not the data.** On unexpected input (a count that doesn't add up, a page
   bigger than its size, markup or schema the parser doesn't know) stop and report. Stale data
   beats wrong data.
3. **Our failures are not the source's.** Class every error by whose side it is on. Only a
   source-side answer may change what we believe about the source.
4. **Measure what users get, end to end.** Freshness and completeness over every source that
   should be read, and per field, not per stage or per successful run.
5. **Every stage safe to run twice.** Idempotent writes keyed on stable identity, checkpoints
   for long runs, staged writes for anything risky.
6. **Isolate by the unit that fails.** Rate limits, cooldowns, queues and pools per source or
   tenant, so one bad source costs only itself.
7. **Release data changes like code, with more care.** Dry run, canary on real input without
   writing, ramp, and a way to put the old output back.
8. **Every failure path has a place to land:** a dead-letter store, a review queue, an alert.
   Nothing retries forever or vanishes.

## Gotchas

This skill's synthesis from practice, not from one source:

- Many list APIs return fewer items than the page size in the middle of a list (filtered rows,
  deleted items, per-page caps). "Short page means last page" is a guess, not a rule.
- Stated totals can be approximate, capped ("10,000+") or computed before filtering. Learn what
  a source's total means before comparing against it.
- A cursor that comes back empty or repeated can mean "done" or "the server lost your place".
  Check the item count and the cursor sequence together.
- Exit code 0 is not a complete run. A run is complete when its own evidence says so.
- Autoscaling consumers without capping their total rate to the downstream only moves the
  overload downstream.
- Most brokers deliver at least once. A broker's duplicate detection doesn't make the consumer's
  side effects happen once; the consumer still has to be idempotent.
- Excluding "not due" or "paused" sources from a freshness denominator makes the SLI read 100%
  while a whole provider is dark.

## Related

- [`data-integrity`](../data-integrity/SKILL.md): backups, restores, soft delete, caps on bulk
  deletes, repairing bad writes in the store.
- [`engineering-practices`](../engineering-practices/SKILL.md): reliability (timeouts, retry
  budgets, idempotency keys, burn-rate alerts, postmortems), database-migrations (schema changes
  and column backfills), release-engineering (flags, canaries, rollback), testing (fakes for
  source APIs).
- [`core-principles`](../core-principles/SKILL.md): fail fast, defensive programming.
- [`structured-logging`](../structured-logging/SKILL.md): per-item tracking IDs and error
  classes in logs.
- [`cloudevents`](../cloudevents/SKILL.md): envelopes for change feeds between services.
- [`infrastructure-patterns`](../infrastructure-patterns/SKILL.md): choosing a broker, queue or workflow engine; keeping reads off the
  write path.
- [`production-operations`](../production-operations/SKILL.md): incident response when a pipeline is down.
