---
name: data-integrity
description: Protecting stored data against loss and corruption - project-agnostic. Covers choosing RPO and RTO as numbers; backup design (logical dumps, snapshots, base backups, incrementals, continuous WAL archiving, Litestream-style SQLite streaming); retention and immutability; restore drills; where state lives (container layers, emptyDir, persistent volumes); volume sizing, WAL and checkpoint growth, Kubernetes ephemeral-storage evictions and time-to-full alerts; silent corruption, integrity checks, soft delete and recovery from bad writes; backing up credentials and keys; disaster recovery plans; and safe deletion. Use when a database or volume is created, moved, resized or deleted, before going to production, when designing or reviewing backups, when a disk fills or a pod is evicted, or after data was lost or corrupted. Not for schema changes or backfills (see engineering-practices), reprocessing data in a pipeline (see data-pipelines), or choosing an infrastructure pattern (see infrastructure-patterns).
---

# Data Integrity

Keeping stored data recoverable: not losing it, not corrupting it, and being able to get it
back to a known point within an agreed time. The references are grounded in Google's SRE book
(Data Integrity) and *Building Secure and Reliable Systems*, the PostgreSQL and SQLite manuals,
Litestream, and the Kubernetes storage docs. Each leads with what agents get wrong, then gives
a procedure, a tested example and a numbered review checklist.

The skill covers the **data**, not the service. For timeouts, retries, SLOs and postmortems, use
[`engineering-practices`](../engineering-practices/SKILL.md) (reliability). For changing a schema
or backfilling, use its database-migrations reference.

## How to use this skill

1. Find the task or symptom in the tables below and read that one reference. Don't load all four.
2. When a database or volume is about to be created, moved, resized or deleted, run the review
   checklists of [state-and-storage](references/state-and-storage.md) and
   [backup-and-restore](references/backup-and-restore.md) before calling it done.
3. After data loss, start with [corruption-and-bad-writes](references/corruption-and-bad-writes.md)
   (bad writes) or [disaster-recovery](references/disaster-recovery.md) (a lost store or site).
   Stop the damage before repairing it.

## The catalog

| Topic | Read when | Reference |
|---|---|---|
| Backup and restore | Choosing RPO/RTO; picking dumps, snapshots, base backups or WAL streaming; retention; protecting backup copies; checking a backup is real | [backup-and-restore](references/backup-and-restore.md) |
| State and storage | Deciding where a database or files live; sizing a volume; WAL or checkpoint growth; ephemeral-storage requests and evictions; disk-fill alerts | [state-and-storage](references/state-and-storage.md) |
| Corruption and bad writes | A bug deleted or overwrote data; adding soft delete; guarding bulk deletes; checksums, integrity checks and validators; point-in-time repair | [corruption-and-bad-writes](references/corruption-and-bad-writes.md) |
| Disaster recovery | Writing or drilling a DR plan; the order of recovery; recovering credentials and keys; deleting a volume, bucket or account safely | [disaster-recovery](references/disaster-recovery.md) |

## Symptom to reference

| Symptom or situation | Look at |
|---|---|
| Data vanished after a container restart or OOM kill | [state-and-storage](references/state-and-storage.md): the writable layer is wiped on restart |
| Pod evicted for ephemeral storage; `DiskPressure` on the node; container set no `ephemeral-storage` request | [state-and-storage](references/state-and-storage.md) |
| `-wal` file or `pg_wal` bigger than the database; disk filling while health checks pass | [state-and-storage](references/state-and-storage.md): a pinned checkpoint, slot or archiver |
| Postgres down with PANIC on a full disk | [state-and-storage](references/state-and-storage.md), then [backup-and-restore](references/backup-and-restore.md) (archiving) |
| "We have nightly backups" but nobody has restored one | [backup-and-restore](references/backup-and-restore.md), drill in [disaster-recovery](references/disaster-recovery.md) |
| Asked for RPO/RTO, or "how often should we back up?" | [backup-and-restore](references/backup-and-restore.md) |
| A replica is offered as the backup | [backup-and-restore](references/backup-and-restore.md), [corruption-and-bad-writes](references/corruption-and-bad-writes.md) |
| A job deleted or overwrote many rows; bad data found weeks later | [corruption-and-bad-writes](references/corruption-and-bad-writes.md) |
| Adding a delete endpoint, cleanup job or purge | [corruption-and-bad-writes](references/corruption-and-bad-writes.md) |
| A token, key or kubeconfig lived only on a deleted workspace or volume | [disaster-recovery](references/disaster-recovery.md): credentials are data |
| About to delete a volume, bucket, snapshot, namespace or account | [disaster-recovery](references/disaster-recovery.md): safe deletion |
| Moving a database to a new host, cluster or provider | [state-and-storage](references/state-and-storage.md), then a restore drill from [disaster-recovery](references/disaster-recovery.md) |

## Working rules

A synthesis across the references:

1. **An untested backup counts as none.** Only a restore that was checked and timed proves a
   backup. Automate the drill and alert when its success heartbeat stops.
2. **Numbers first.** Write RPO and RTO per store before choosing a mechanism, and check the
   mechanism against them in arithmetic.
3. **State on durable storage only.** No database on a container's writable layer or in an
   `emptyDir`. Keep the WAL with its database.
4. **Watch the rate of fill, not only the level.** Alert on time-to-full and on WAL size relative
   to data size. A green health check says nothing about the disk.
5. **Copies apart from the original**: another failure domain, and credentials the workload can't
   use to delete them. Replication is not a backup.
6. **Make bad writes reversible**: soft delete with a purge window, caps on bulk destruction, and
   point-in-time recovery for longer than detection takes.
7. **Credentials and keys are data.** Each has a recovery copy somewhere other than where it is
   used.
8. **Look before deleting.** Check a volume or bucket for unique data, and keep a final
   snapshot, before it goes.

## Gotchas

- `cp` of a live SQLite file, or a snapshot of Postgres data without its WAL, may not open.
  Use the database's backup tool, or an atomic snapshot of every volume it uses at once.
- SQLite's `-wal` file is part of the database. Copying or deleting the main file alone loses
  committed transactions. WAL mode doesn't work on network filesystems.
- One open read transaction can stop SQLite checkpoints indefinitely. One abandoned Postgres
  replication slot can keep unlimited WAL by default.
- Kubernetes QoS class doesn't apply to ephemeral storage. Eviction order under disk pressure
  depends on usage against the request.
- A VolumeSnapshotClass with `deletionPolicy: Delete` removes the underlying snapshot when its
  content object is deleted.
- Restores can bring back data that was deleted after the restore point. Re-apply deletions.

## Related

- [`engineering-practices`](../engineering-practices/SKILL.md): database-migrations (schema
  changes, backfills), reliability (SLOs, alerting, postmortems), security-practices (leaked
  credentials).
- [`core-principles`](../core-principles/SKILL.md): defensive programming, fail fast.
- `data-pipelines`: reprocessing or re-driving data through a pipeline.
- `infrastructure-patterns`: choosing managed versus self-hosted stores and deployment shapes.
- `architecture-review`: its provider crosswalk lists each cloud's backup and DR services.
- `production-operations`, `secure-reliable-systems`: incident response; rollback, revocation and
  break-glass design.
- [`helm-charts`](../helm-charts/SKILL.md): where PVC, StatefulSet and resource settings are
  templated.
