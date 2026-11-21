# CQRS and materialized views

## Problem

One data model serves both writes and reads, and the two pull in different directions. Writes
want normalized rows, short transactions and few indexes. Reads want joins pre-done, totals
pre-summed and whatever indexes the screen needs. The failure that usually forces the issue is
mundane: an admin dashboard or stats endpoint runs a full-table aggregate against the primary,
holds a read lock or snapshot for seconds, and the workers that need to claim and commit stall
behind it. Queue depth climbs, and nothing is "down".

CQRS (Command Query Responsibility Segregation) separates the write model from one or more read
models. A materialized view is a read model kept as stored, precomputed data. They range from a
counter table updated in the write transaction to a separate store fed by events.

## When to use / when NOT to use

- **Use the cheap end first** when reports or dashboards read from the write path: a replica, a
  snapshot, a statement timeout, or counters maintained by the writers.
- **Use** a materialized view when a query is expensive to compute and read far more often than
  its inputs change, and some staleness is acceptable.
- **Use** full CQRS with separate stores when read and write loads scale differently, reads need
  a different technology (search, document store), or several services' data must be joined.
- **Don't** for simple CRUD with simple rules. Azure and microservices.io both list the added
  complexity as the main cost.
- **Don't** put a view in front of reads that must be strongly consistent (a balance check before
  a debit). Read those from the write model.
- **Don't** confuse it with [event-sourcing](event-sourcing.md). CQRS needs no event store, and
  most CQRS systems don't have one.

## How it works

**A ladder, cheapest first.**

| Step | What it is | Staleness | Cost |
|---|---|---|---|
| 1. Read elsewhere | Reports on a read replica or snapshot; statement timeout on the primary | Replica lag | A replica; replica lag to watch |
| 2. Summary maintained by writers | Counter or summary rows updated in the same transaction as the write | None | Write amplification; a hot row if every write touches one counter |
| 3. Database materialized view | `CREATE MATERIALIZED VIEW`, refreshed on a schedule | The refresh interval | Refresh compute; locking during refresh |
| 4. Projection from events | A consumer applies change events to a separate read store | Event lag | Outbox or CDC, idempotent consumer, rebuild tooling |

**Keeping projections updated.** The write side publishes changes reliably through a
[transactional-outbox](transactional-outbox.md) or CDC. The projector is an
[idempotent consumer](idempotent-consumer.md) with a per-entity version guard, and it stores its
position (offset or last event ID) in the same transaction as the view rows.

**Staleness.** Every read model is behind by its refresh interval or its event lag. Azure: define
the acceptable staleness before choosing the refresh method, and watch for a lost refresh
signal, which leaves the view silently stale. Expose the view's age (last applied event time)
and alert when it exceeds the budget. For read-your-own-writes, return the new state from the
command, or read that one entity from the write model.

**Rebuilds.** A view is disposable: it can always be rebuilt from the source or by replaying
events. Build the new version beside the old one, validate it (row counts, totals against the
source), then switch readers over, so a failed rebuild never serves a half-built view (Azure's
advice). Plan rebuild time: replaying a year of events may take hours.

**Postgres materialized views.** `REFRESH MATERIALIZED VIEW` replaces the contents entirely and
can block readers of the view while it runs. `CONCURRENTLY` keeps reads going but requires the
view to be populated and to have a unique index on plain columns covering all rows. Only one
refresh of a given view runs at a time.

## In code / In infrastructure

**In code.** Separate query handlers from command handlers. Summary updates go in the command's
transaction. Projectors are idempotent, versioned and resumable. Queries never write.

**In infrastructure.** A replica or a separate store for reads; a role for reporting with a
statement timeout and read-only access; connection pools per role, so reports can't take the
writers' connections ([bulkheads-and-isolation](bulkheads-and-isolation.md)).

**Agree:** the staleness the product accepts must exceed the refresh interval plus the worst
expected event lag, and the alert threshold sits between them.

## Failure modes and what agents get wrong

- **The stats query on the writer.** On SQLite in rollback-journal mode, a reader in the middle of
  a scan holds a shared lock, and a writer can't commit until it finishes (example). In WAL mode
  readers don't block the writer, but SQLite notes that a long-running reader stops checkpoints,
  so the WAL grows. On Postgres a long report holds a snapshot, which delays vacuum (unverified
  here). Each engine, its own cost; same cure.
- **A view with no age.** Nobody can tell it stopped updating.
- **Rebuilding in place.** Readers see an empty or half-built view during the rebuild.
- **A projector that commits view rows and its position separately.** A crash replays events
  into a view that already has them, or skips some.
- **One global counter row** updated by every write: the hot row becomes the new lock.
- **A view per screen** until storage and refresh cost exceed the original query's (Azure notes
  views are usually tailored to one or a few queries).
- **Forgetting deletions.** Azure: a view must apply the source's retention and deletion rules,
  and its access controls must be at least as strict as the source's.

## Implementation notes

- **Postgres:** read replicas; `CREATE MATERIALIZED VIEW` with a unique index and `REFRESH ...
  CONCURRENTLY`; summary tables updated in the transaction or by triggers;
  `statement_timeout` on the reporting role (unverified).
- **SQLite:** WAL mode so readers don't block the writer; summary tables in the write
  transaction; a periodic copy for heavy reports.
- **Kafka / NATS JetStream / Redis Streams:** the change feed for projections; Kafka's compacted
  topics keep the latest value per key, which suits rebuilding a key-value view.
- **Search or document stores** as read models, fed by a projector.
- **Managed:** managed read replicas, managed materialized views in analytical databases, and
  change-feed triggers into a separate read store.

## Example

A dashboard report scanning the jobs table while a worker commits, in SQLite rollback-journal
mode and WAL mode. The worker also updates a `job_counts` summary in the same transaction
(connections with `timeout=0`, so a lock fails at once instead of waiting):

```python
report = connect(journal)
cur = report.execute("SELECT id, state FROM jobs")       # report walks the table row by row
cur.fetchone()                                           # ...and is still running
try:
    w.execute("BEGIN IMMEDIATE")                         # a worker finishes a job
    w.execute("UPDATE jobs SET state = 'done' WHERE id = 1")
    w.execute("UPDATE job_counts SET n = n + (CASE state WHEN 'done' THEN 1 ELSE -1 END)"
              " WHERE state IN ('queued', 'done')")       # read model kept in the same transaction
    w.execute("COMMIT")
except sqlite3.OperationalError as e:
    w.execute("ROLLBACK"); print(journal, e)
```

Against a file database with 5,000 queued jobs: in `DELETE` (rollback-journal) mode the
worker's commit failed with `database is locked` and the counts stayed at 5,000 queued. In `WAL`
mode the commit succeeded, and `job_counts` read `done 1, queued 4999`, a point lookup instead
of a scan. Either way the dashboard should read `job_counts`, not aggregate `jobs`.

## Review checklist

1. Which reports, dashboards or admin queries run against the write path today, and how long do they hold locks or snapshots?
2. Is there a statement timeout and a separate pool for reporting reads?
3. Could a writer-maintained summary or a replica answer the query before a new store is added?
4. Is the acceptable staleness written down, and is the view's age exposed and alerted on?
5. Are projectors idempotent, version-guarded, and do they commit their position with the view rows?
6. Is the change feed reliable (outbox or CDC), not a dual write?
7. Can each view be rebuilt beside the live one and switched atomically, and is rebuild time known?
8. Do views apply the source's deletions and access controls?
9. Do strongly consistent reads go to the write model?

## Related

[transactional-outbox](transactional-outbox.md), [idempotent-consumer](idempotent-consumer.md),
[event-sourcing](event-sourcing.md), [publish-subscribe](publish-subscribe.md),
[bulkheads-and-isolation](bulkheads-and-isolation.md),
[`data-pipelines` failure-isolation](../../data-pipelines/references/failure-isolation.md)
(admin queries on the coordinator's write path),
[`data-integrity` state-and-storage](../../data-integrity/references/state-and-storage.md) (WAL growth).

## Sources

Azure Architecture Center: [CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs),
[Materialized View](https://learn.microsoft.com/en-us/azure/architecture/patterns/materialized-view).
microservices.io, [CQRS](https://microservices.io/patterns/data/cqrs.html). PostgreSQL,
[REFRESH MATERIALIZED VIEW](https://www.postgresql.org/docs/current/sql-refreshmaterializedview.html).
SQLite, [Write-Ahead Logging](https://www.sqlite.org/wal.html). Kafka 4.4,
[Design: log compaction](https://kafka.apache.org/44/design/design/).
