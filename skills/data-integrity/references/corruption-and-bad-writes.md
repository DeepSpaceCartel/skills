# Corruption and bad writes

Most lost data is not lost to a dead disk. A program wrote the wrong thing or deleted the
right thing, and nobody noticed for weeks. This reference covers silent corruption, checksums
and integrity checks, out-of-band validators, soft delete and delayed purge, guards against
runaway deletes, and recovering to just before a bad write. Anchor sources: Google's
[SRE book, Data Integrity](https://sre.google/sre-book/data-integrity/),
[BSRS ch. 9](https://google.github.io/building-secure-and-reliable-systems/raw/ch09.html),
PostgreSQL [data checksums](https://www.postgresql.org/docs/current/checksums.html) and
[PITR](https://www.postgresql.org/docs/current/continuous-archiving.html), SQLite
[PRAGMA](https://www.sqlite.org/pragma.html), and the AWS
[resilience analysis framework](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/mitigation-strategies.html).

## What agents typically get wrong

- **Planning only for hardware loss.** The SRE book reviewed recovery efforts and found that
  user-visible loss most often came from software bugs: deletions and broken references. The
  hardest cases were slow corruption found weeks or months later.
- **Hard `DELETE` on the user path.** Once the row is gone, the only way back is a restore. That
  is slow, coarse, and loses every good write since the backup.
- **No brake on bulk deletes.** A batch job or cleanup script with a bad filter removes half the
  table at full speed. Nothing checks whether the volume is normal.
- **Trusting that a store which reports success wrote the right thing.** Checksums catch flipped
  bits on disk, not a correct write of wrong data. Only invariants checked by something outside
  the write path catch that.
- **Validators so strict they get turned off.** The SRE book warns that noisy checks are
  disabled. Check the invariants whose violation would really hurt users.
- **Restoring the whole database to fix a few rows.** That throws away every good write since the
  backup. Restore to a side copy and repair only what is wrong.
- **Cleaning up before understanding.** Running a "fix" before the bug is found, or while the
  bad writer still runs, adds a second round of damage.
- **Turning off checksums or integrity errors to get the service up**, then forgetting to turn
  them back on.

## Procedure

**Before it happens**

1. **List the failure modes** by what caused the damage (a person, a program, the platform or a
   whole site), how much it touched, and how fast it spread. The SRE book crosses these three.
   Say which defence covers each combination.
2. **Soft-delete user-facing data.** Add a `deleted_at` column, read through a filter or view, and
   purge in a separate job after a recovery window. Windows of 15 to 60 days are common in the
   SRE book's account.
3. **Rate-limit destruction.** Cap rows deleted per batch or per hour relative to the normal
   rate. Over the cap, stop and ask a human. The SRE book suggests alerting when deletions reach
   an extreme multiple of normal, for example 10x the 95th percentile.
4. **Turn on storage-level checks.** Postgres data checksums (on by default in the current docs;
   older clusters may predate that, so run `SHOW data_checksums`). SQLite `PRAGMA quick_check` or `integrity_check`. Object-store or
   filesystem checksums where offered.
5. **Run out-of-band validators** on a schedule against a replica or a restored copy: referential
   integrity, counts against an independent source, files against their listings. Alert on new
   violations and keep a history.
6. **Keep point-in-time recovery** (base backup plus WAL) for as long as detection can take, so
   you can stop just before a bad write.

**When it happens**

1. **Stop the writer.** Pause the job, disable the feature flag, or stop intake (AWS calls this an
   andon cord). Don't start repairs while the damage is still growing.
2. **Preserve evidence.** Keep the current state, logs, and the WAL or binlog. Postgres's recovery
   steps start by saving the current data directory and `pg_wal`.
3. **Bound the damage.** Find the first bad write (time or LSN), which keys it touched, and
   whether later good writes touched the same keys.
4. **Recover to a side copy.** Restore the last good point next to production, for example with
   PITR and a recovery target time (`recovery_target_time`, unverified) just before the first bad write.
5. **Repair surgically.** Diff the side copy against production for the affected keys. Write back
   only those rows, through the application's own rules, and keep good later writes.
6. **Validate**, then turn the guard that should have caught it into a permanent check.

## Techniques

- **Layers, each catching what the last missed** (SRE book):

| Layer | Catches | Misses | Recovery speed |
|---|---|---|---|
| Soft delete / trash | User and app deletions inside the window | Corruption in place, anything past the window | Seconds (undelete) |
| Rate guard on destructive jobs | Runaway bulk deletes and updates | Slow, small damage | Prevents it |
| Storage checksums, integrity pragmas | Torn or flipped pages, broken b-trees | Valid-looking wrong data | Find it, then restore |
| Out-of-band validators | Broken invariants, orphans, drift between stores | Invariants nobody wrote down | Hours to days, if alerted |
| PITR (base + log) | Any bad write after the base | Damage older than the oldest base | Restore time + repair |
| Offline / offsite copies | Site loss, compromised production credentials | Recent writes | Slowest |

- **Replication is not a layer here.** It copies the bad write everywhere within seconds.
- **Revision history** helps only if deleting an object doesn't also delete its history (SRE book).
- **Scaling validators.** Run cheap checks often and thorough ones rarely. Shard by key or time.
  Verify data once it stops changing, then trust it (SRE book "trust points").
- **SQLite checks.** `integrity_check` finds out-of-order entries, malformed records, missing
  pages, index mismatches, and UNIQUE/CHECK/NOT NULL violations, and returns `ok` when clean. It
  does not check foreign keys (use `PRAGMA foreign_key_check`). `quick_check` skips UNIQUE and
  index-content checks and runs in O(N), not O(N log N).
- **Postgres checksums** cover data pages only, not internal structures or temp files.
  `pg_checksums` enables or verifies them on a stopped cluster, and every node of a replicated
  cluster needs the same setting. `ignore_checksum_failure` exists for salvage. Set it only for
  the recovery session.
- **Protect backups like primary data.** Integrity-protect them and check signatures or checksums
  when restoring (BSRS ch. 9).
- **Assume people will make mistakes.** The AWS framework treats "a human made a mistake" as a
  missing guardrail: confirmation steps, dry runs, scoped credentials, per-batch caps.

## Example

Soft delete with a runaway-delete guard, delayed purge, and an out-of-band validator, using the
standard-library `sqlite3`:

```python
import sqlite3, time

SCHEMA = """
CREATE TABLE accounts(id INTEGER PRIMARY KEY, name TEXT NOT NULL, deleted_at REAL);
CREATE TABLE documents(id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, deleted_at REAL);
CREATE VIEW live_documents AS SELECT * FROM documents WHERE deleted_at IS NULL;
"""

class RunawayDelete(Exception):
    pass

def soft_delete(db, ids, *, max_fraction=0.01, max_rows=1000):
    """Mark rows deleted; refuse a batch far larger than normal (a bug, not a user)."""
    live = db.execute("SELECT count(*) FROM documents WHERE deleted_at IS NULL").fetchone()[0]
    if len(ids) > max_rows or len(ids) > max_fraction * max(live, 1):
        raise RunawayDelete(f"{len(ids)} of {live} live rows in one batch; needs a human")
    db.executemany("UPDATE documents SET deleted_at=? WHERE id=? AND deleted_at IS NULL",
                   [(time.time(), i) for i in ids])

def purge(db, *, retention_s=30 * 86400):
    """Hard-delete only after the recovery window has passed."""
    return db.execute("DELETE FROM documents WHERE deleted_at < ?",
                      (time.time() - retention_s,)).rowcount

def validate(db):
    """Out-of-band invariants: run on a schedule against a replica or restored copy."""
    problems = []
    if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        problems.append("quick_check failed")
    orphans = db.execute("""SELECT count(*) FROM live_documents d
        LEFT JOIN accounts a ON a.id = d.account_id AND a.deleted_at IS NULL
        WHERE a.id IS NULL""").fetchone()[0]
    if orphans:
        problems.append(f"{orphans} live documents point at missing or deleted accounts")
    return problems
```

Checked with 10,000 documents. Soft-deleting 3 left 9,997 live. A 5,000-row batch was refused.
`purge` removed nothing until a row's `deleted_at` was 31 days old, then removed that row only.
`validate` was clean until an account was soft-deleted, then it reported 4,999 orphaned
documents: a cascade the application forgot.

## Gotchas and contested points

- **Soft delete is not deletion.** It conflicts with erasure duties and with uniqueness (a
  deleted row still holds its unique key). Purge on a schedule, and scope unique indexes to live
  rows (a partial index).
- **Every read must filter.** One query that forgets `deleted_at IS NULL` shows deleted data.
  Read through a view or a default scope, and test for it.
- **Thresholds must follow the data.** A fixed row cap blocks a legitimate migration and passes a
  slow leak. Base it on the normal rate, and give a reviewed override.
- **Repairs can do damage too.** A bulk repair is itself a bulk write: run it with the same
  guard, a dry run and a diff first.

## Review checklist

1. Is user-facing data soft-deleted, with a purge job and a stated recovery window?
2. Do destructive jobs stop when their volume exceeds a multiple of normal, and alert someone?
3. Are storage checksums or integrity checks on, and run on a schedule?
4. Does an out-of-band validator check the invariants that matter, alert on new violations, and
   stay quiet enough that nobody turns it off?
5. Can you recover to a point just before a bad write, for as far back as detection can take?
6. Is there a written path for repairing rows from a side copy without rolling back good writes?
7. During an incident, is the bad writer stopped and evidence kept before any repair runs?

## Related

[backup-and-restore](backup-and-restore.md) (PITR and retention),
[disaster-recovery](disaster-recovery.md) (incident order),
[`engineering-practices`](../../engineering-practices/SKILL.md) (database-migrations for
backfills; reliability for postmortems), `data-pipelines` (re-running a pipeline over bad data).

## Sources

[SRE book ch. 26, Data Integrity](https://sre.google/sre-book/data-integrity/);
[BSRS ch. 9](https://google.github.io/building-secure-and-reliable-systems/raw/ch09.html);
PostgreSQL [Data Checksums](https://www.postgresql.org/docs/current/checksums.html),
[Continuous Archiving and PITR](https://www.postgresql.org/docs/current/continuous-archiving.html);
SQLite [PRAGMA](https://www.sqlite.org/pragma.html);
AWS [resilience analysis framework, mitigation strategies](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/mitigation-strategies.html).
`PRAGMA foreign_key_check` and partial unique indexes are stated from general knowledge
(unverified against a fetched page).
