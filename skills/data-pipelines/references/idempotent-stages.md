# Idempotent stages

Every stage of a pipeline will run some input twice: a retried request, a broker redelivery, a
worker killed after writing but before acknowledging, a rerun after a fix. The stage is correct
only if running it twice has the same effect as running it once. This reference covers
idempotent writes, dedupe of messages, checkpoint and resume, two-phase (staged) mutations, and
leases on work. Request-level idempotency keys for a single API call are in
[reliability](../../engineering-practices/references/reliability.md). Anchor sources: the
[SRE Workbook](https://sre.google/workbook/data-processing/) (idempotent and two-phase
mutations, checkpointing), the [SRE book](https://sre.google/sre-book/data-processing-pipelines/)
(leases, unique output names, versioned tasks), microservices.io
[Idempotent Consumer](https://microservices.io/patterns/communication-style/idempotent-consumer.html),
and the Azure [Pipes and Filters](https://learn.microsoft.com/en-us/azure/architecture/patterns/pipes-and-filters)
and [Competing Consumers](https://learn.microsoft.com/en-us/azure/architecture/patterns/competing-consumers)
patterns.

## What agents typically get wrong

- **`INSERT` where `UPSERT` belongs.** A rerun duplicates every row, or fails halfway on a
  unique key and leaves a partial batch.
- **Relative updates.** `count = count + 1` or `balance = balance - amount` on each delivery.
  microservices.io's example is a debit consumer that subtracts twice on a duplicate. Write the
  resulting value, or dedupe the message first.
- **Dedupe record and effect in separate transactions.** Mark-then-apply loses the effect on a
  crash; apply-then-mark repeats it. They commit together or the dedupe is decoration.
- **Trusting the broker to dedupe.** Azure notes that even with broker duplicate detection,
  filters still need idempotent processing. A worker can finish the work and die before
  acknowledging.
- **Surrogate keys from the pipeline.** A new UUID per run makes every rerun a new record. Key
  on the source's stable identity (source + source item ID), or a content hash where there is
  none.
- **Checkpoints saved apart from the output.** The checkpoint says page 40 while the store has
  page 38, or the other way round. Save the checkpoint in the same transaction as the output it
  describes, or make the output idempotent so re-doing a page is harmless.
- **Side effects that can't be repeated** (an email, a webhook, a charge) issued inline in a
  retried stage. Put them behind their own dedupe, or emit them from the committed state.
- **A long task with a fixed lock.** The lock or visibility timeout expires while the worker is
  still busy, a second worker starts, and both write. AWS calls out redelivery during slow
  processing as a cause of duplicate work under overload.

## Procedure

1. **Name each stage's identity key**: what makes two inputs "the same item" (source plus
   source ID, or a hash of normalised content). Make it the primary or unique key of the output.
2. **Make writes absolute.** Upsert to the new state with `ON CONFLICT ... DO UPDATE`, or
   write a whole partition and swap it in. Use `max()` or version checks so an older message
   can't overwrite a newer one.
3. **Dedupe deliveries** where the effect isn't naturally idempotent: record
   `(consumer, message_id)` with a unique key in the same transaction as the effect.
4. **Checkpoint long runs** at natural boundaries (a page, a partition, a time range), in the
   same transaction as that unit's output. Resume from the checkpoint; don't start over.
5. **Stage risky mutations** (two-phase): write proposed changes to a staging table or prefix,
   validate them (counts, diffs, invariants), then apply in one step. Discard on failure.
6. **Lease work** with an expiry and a holder ID, renewed by a heartbeat. A write is accepted
   only from the current lease holder. Stop work when the lease is lost.
7. **Name outputs uniquely per attempt** (run ID, attempt ID) and publish by an atomic rename or
   pointer swap, so a straggler from an old attempt can't overwrite the winner.
8. **Test by running twice.** Every stage's test feeds the same input twice and kills the
   worker mid-batch; the output must be identical to one clean run.

## Techniques

| Technique | Use when | Cost |
|---|---|---|
| Upsert on natural key | Item state from a source | Needs a stable key |
| Absolute values, version or `max()` guard | Out-of-order delivery | Need a version or timestamp per message |
| Processed-messages table | Effects that aren't idempotent (counters, events emitted) | One row per message; prune by age past the redelivery window |
| Partition overwrite (write new, swap) | Batch outputs by day or source | Whole-partition rewrite |
| Staging + validate + apply | Risky or bulk changes; canaries | Extra storage and a step |
| Checkpoint in the output transaction | Long walks and backfills | A row per job |
| Lease with heartbeat and holder check | Work handed to competing workers | Renewal traffic; a clock |
| Unique attempt names + atomic publish | File or object outputs | Cleanup of losers |

- **Versioned tasks** (SRE book). In Google's Workflow, a change to a task makes a new task with a
  new ID, and a commit must name the current ID, so work done under an old configuration is
  thrown away. The same idea works with a generation number on a job row.
- **Exactly-once is an effect, not a delivery.** At-least-once delivery plus an idempotent stage
  gives exactly-once results. The workbook notes that exactly-once semantics may be unnecessary
  when work units are idempotent.
- **Ordering.** Competing consumers don't preserve order. Either make the stage order-free
  (absolute writes with version guards) or partition by key so one consumer sees one key.

## Example

A consumer that applies each message once by committing the dedupe record with the effect,
and a walk that resumes from a checkpoint saved with each page (SQLite, standard library):

```python
import sqlite3

def handle(db, consumer, msg):
    """Apply one message at most once: dedupe record and effect in one transaction."""
    db.execute("BEGIN IMMEDIATE")
    try:
        cur = db.execute("INSERT OR IGNORE INTO processed VALUES (?, ?)", (consumer, msg["id"]))
        if cur.rowcount == 0:                       # already applied: drop the duplicate
            db.execute("ROLLBACK"); return False
        db.execute("""INSERT INTO items VALUES (?, ?, ?, ?)
                      ON CONFLICT(source, item_id) DO UPDATE SET
                        title = excluded.title, seen_run = excluded.seen_run
                      WHERE excluded.seen_run >= items.seen_run""",   # older can't win
                   (msg["source"], msg["item_id"], msg["title"], msg["run"]))
        db.execute("COMMIT"); return True
    except BaseException:
        db.execute("ROLLBACK"); raise

def run(db, job, pages, crash_at=None):
    """Resume from the checkpoint; the checkpoint moves in the same transaction as the page."""
    row = db.execute("SELECT next_page FROM checkpoint WHERE job=?", (job,)).fetchone()
    start = row[0] if row else 0
    for n in range(start, len(pages)):
        if n == crash_at:
            raise RuntimeError("worker killed")
        db.execute("BEGIN IMMEDIATE")
        for it in pages[n]:
            db.execute("INSERT INTO items VALUES ('s', ?, ?, 1) "
                       "ON CONFLICT DO UPDATE SET title=excluded.title", (it, it))
        db.execute("INSERT INTO checkpoint VALUES (?, ?) ON CONFLICT(job) "
                   "DO UPDATE SET next_page=excluded.next_page", (job, n + 1))
        db.execute("COMMIT")
    return start
```

With the tables `items(source, item_id, title, seen_run, PRIMARY KEY(source, item_id))`,
`processed(consumer, msg_id, PRIMARY KEY(consumer, msg_id))` and
`checkpoint(job PRIMARY KEY, next_page)` in an in-memory database (`isolation_level=None`), one
message delivered three times returned `[True, False, False]` and left one row. A later message
from run 5 with a different title was applied as a new message but left run 7's title in place. A five-page walk
killed at page 3 resumed from page 3 on the second run and ended with exactly 50 rows.

## Gotchas and contested points

- **Pruning the dedupe table** too early reopens the door: keep message IDs for longer than the
  broker's longest redelivery or retention window.
- **Content hashes as keys** change when a source edits an item, turning an edit into a new item
  plus a stale one. Prefer the source's own ID when it is stable.
- **Two-phase costs latency.** Use it for bulk, risky or canaried changes, not every write.
- **Heartbeats under overload.** Renewal calls compete with the work for the same threads. Give
  them their own budget, or the lease lapses exactly when the system is slowest.
- **Compensation is not rollback.** When later steps fail after earlier ones had side effects,
  Azure's Pipes and Filters points to compensating actions, recorded so recovery can resume.
  They undo business effects, not the whole pipeline as one transaction.

## Review checklist

1. Does every stage's output have a unique key based on the source's stable identity?
2. Are writes absolute (upsert, partition swap) rather than relative, with version guards
   against out-of-order messages?
3. Where effects aren't naturally idempotent, is the dedupe record committed in the same
   transaction as the effect?
4. Is the checkpoint saved with the output it describes, and does a restart resume from it?
5. Are risky or bulk changes staged, validated, then applied in one step?
6. Is handed-out work leased with an expiry, heartbeat and holder check on commit?
7. Are file or object outputs named per attempt and published atomically?
8. Do non-repeatable side effects (email, webhook, charge) have their own dedupe?
9. Is there a test that runs the same input twice and kills the worker mid-batch?

## Related

[completeness-and-absence](completeness-and-absence.md) (diff only after a complete read),
[backfills-and-reprocessing](backfills-and-reprocessing.md) (reruns at scale),
[failure-isolation](failure-isolation.md) (redelivery limits),
[reliability](../../engineering-practices/references/reliability.md) (idempotency keys on API
calls), [database-migrations](../../engineering-practices/references/database-migrations.md)
(adding the unique key to a live table).

## Sources

Google SRE Workbook, [Data Processing Pipelines](https://sre.google/workbook/data-processing/)
(idempotent and two-phase mutations, checkpointing, exactly-once versus idempotent units).
Google SRE book, [Data Processing Pipelines](https://sre.google/sre-book/data-processing-pipelines/)
(leases, unique output names, versioned task IDs, lack of checkpointing forcing restarts).
microservices.io, [Idempotent Consumer](https://microservices.io/patterns/communication-style/idempotent-consumer.html)
(recording processed message IDs; the debit example). The page shows the ID insert inside the
handler's transaction but doesn't state the same-transaction rule outright; that rule is this
skill's. Azure Architecture Center,
[Pipes and Filters](https://learn.microsoft.com/en-us/azure/architecture/patterns/pipes-and-filters)
and [Competing Consumers](https://learn.microsoft.com/en-us/azure/architecture/patterns/competing-consumers).
AWS Builders' Library,
[Avoiding insurmountable queue backlogs](https://builder.aws.com/content/3EuRcgkTP1MI0c7zM8W6HL3WIqA/avoiding-insurmountable-queue-backlogs)
(redelivery during slow processing, heartbeats).
