# State and storage

Where data physically lives, and how it outgrows its disk. This covers container writable
layers versus persistent volumes, `emptyDir` and node-local storage, volume sizing, WAL and
checkpoint growth in Postgres and SQLite, Kubernetes ephemeral-storage requests and evictions,
and alerting on how fast a disk fills. Anchor sources: Kubernetes
[volumes](https://kubernetes.io/docs/concepts/storage/volumes/),
[ephemeral storage](https://kubernetes.io/docs/concepts/storage/ephemeral-storage/),
[resource management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/#local-ephemeral-storage)
and [node-pressure eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/);
[SQLite WAL](https://www.sqlite.org/wal.html); PostgreSQL
[continuous archiving](https://www.postgresql.org/docs/current/continuous-archiving.html) and
[replication settings](https://www.postgresql.org/docs/current/runtime-config-replication.html).

## What agents typically get wrong

- **A database on the container's writable layer.** Kubernetes says files a container creates
  are lost when it crashes or stops, and the kubelet restarts it with a clean state. An OOM kill
  is a crash. A SQLite file at `/app/data.db` with no volume mounted is gone on the first restart.
- **`emptyDir` treated as durable.** It is scratch space tied to the pod on that node. It is
  deleted when the pod leaves the node: eviction, rescheduling, a node drain.
- **No `ephemeral-storage` request.** Under disk pressure the kubelet evicts first the pods whose
  usage exceeds their requests. A pod that requested nothing exceeds its request with its first
  byte, so it should expect to be near the front of the queue (an inference from the ranking
  rule). QoS class doesn't protect it: QoS doesn't apply to ephemeral-storage requests.
- **"Healthy" while the disk fills.** Liveness probes check that the process answers, not that
  the volume has room. A WAL can grow to many times the database's size while every probe stays
  green.
- **Assuming checkpoints just happen.** SQLite can't finish a checkpoint while any reader is
  using the WAL. With overlapping readers that never pause, the WAL grows without bound. A
  long-running read transaction, an idle connection left inside `BEGIN`, or a backup tool
  holding a read lock all do this.
- **Assuming Postgres cleans `pg_wal`.** WAL that hasn't been archived stays. Replication slots
  can keep unlimited WAL (`max_slot_wal_keep_size=-1` is the default). An abandoned slot or a
  broken `archive_command` fills the disk. When the disk is full, Postgres does a PANIC shutdown
  and stays down until space is freed.
- **A fixed "% used" alert as the only alert.** 80% is fine on a static 2 TB volume and an hour
  from death on a small one filling at 1 GB/min.
- **SQLite in WAL mode on a network filesystem.** The wal-index uses shared memory, so every
  process must be on the same host. NFS and similar shares break this.

## Procedure

1. **Locate every write.** For each process, list the paths it writes: database files, WAL,
   uploads, caches, temp files, logs. Check each one is on a volume whose lifetime matches the
   data's (table below).
2. **Pick the volume type.** Data you must keep goes on a persistent volume: a PVC, a block
   device, a managed disk, or managed database storage. On Kubernetes, use a StatefulSet or a PVC
   per instance; a `hostPath` or `emptyDir` is not a substitute.
3. **Size it from growth, not from today.** Size = data x growth over the planning horizon + WAL
   peak + space for maintenance (VACUUM, a backup or restore copy, reindex) + headroom. Measure
   the growth rate, then pick the horizon.
4. **Bound the logs.** Postgres: alert on archive failures and slot lag, and set
   `max_slot_wal_keep_size` unless losing a replica is worse than filling the disk. SQLite: keep
   reader gaps, or run `PRAGMA wal_checkpoint(RESTART|TRUNCATE)` from one place. Set
   `journal_size_limit` so a reset WAL shrinks back.
5. **Request ephemeral storage** for every container that writes scratch data, logs or layers:
   `resources.requests.ephemeral-storage`, plus a limit and an `emptyDir.sizeLimit`.
6. **Alert on time-to-full**, and separately on WAL size relative to data size, and on archive or
   checkpoint progress stalling.
7. **Test the failure.** Kill the container (`kill -9`), delete the pod, drain the node. Confirm
   the data survives each one.

## Techniques

| Storage | Survives container restart | Survives pod deletion or eviction | Survives node loss | Use for |
|---|---|---|---|---|
| Container writable layer | No | No | No | Nothing you keep |
| `emptyDir` (disk or memory) | Yes | No | No | Scratch, caches; memory-backed counts against memory |
| `hostPath` / node-local PV | Yes | Yes, if rescheduled to the same node | No | Node agents; local-disk databases that replicate elsewhere |
| Network or cloud block PV | Yes | Yes | Usually (zone-scoped) | Single-writer databases |
| Managed database / object store | Yes | Yes | Yes | The default for durable data |

The first two rows are from the Kubernetes volume docs. The `hostPath`, PV and managed rows are
general practice, not checked against a fetched page (unverified). Check your storage class.

- **Ephemeral-storage accounting.** The kubelet counts the container's writable layer, its logs,
  and non-tmpfs `emptyDir` volumes. If a container's writable layer and logs exceed its limit,
  the pod is evicted. Limits are summed across containers to give a pod limit, and `emptyDir`
  usage counts against it. Watch the units: `400m` is 0.4 bytes, not 400 MB.
- **Eviction is abrupt.** Hard thresholds evict with no grace period and ignore
  PodDisruptionBudgets. The Linux defaults are `nodefs.available<10%`, `imagefs.available<15%`,
  and inodes below 5%. Changing one hard threshold zeroes the others unless
  `MergeDefaultEvictionSettings` is set. Before evicting, the kubelet first reclaims dead
  containers and unused images.
- **Deleted-but-open files.** By default the kubelet scans directories, so a deleted file a
  process still holds open doesn't show in its numbers, but it still fills the disk. Project
  quotas (beta, off by default) count it.
- **SQLite checkpoint facts.** The automatic checkpoint runs at 1000 WAL pages and is PASSIVE, so
  it gives way to readers. `PRAGMA wal_checkpoint(TRUNCATE)` returns three columns. The first is
  1 if it was blocked, the second is the number of pages in the WAL, and the third is the number of pages
  copied back. Alert when the first stays 1, or the second keeps rising.
- **Under a WAL-streaming replicator** (Litestream) the tool owns checkpointing. Under heavy
  writes, set `PRAGMA wal_autocheckpoint=0` in the app and `busy_timeout` (5 s suggested).
- **Postgres WAL retention.** Things that pin WAL: unarchived segments, replication slots, and
  `wal_keep_size`. `pg_replication_slots` shows each slot's WAL availability. An inactive slot
  is the usual cause.
- **Disk-fill alerts are the exception to symptom-only paging.** The
  [reliability](../../engineering-practices/references/reliability.md) reference says page on
  user symptoms. A filling disk is the case where the cause is imminent, certain to become an
  outage, and invisible to symptom checks until it hits. Page on time-to-full.

## Example

A time-to-full alert (Prometheus). `predict_linear(v, t)` extrapolates a series `t` seconds
ahead by linear regression over the range `v`. The metric and label names are from the common
node exporter and are **illustrative**: check your exporter's actual names.

```yaml
groups:
- name: disk-fill
  rules:
  - alert: VolumeFullIn4h          # page: fast fill, hours left
    expr: |
      predict_linear(node_filesystem_avail_bytes{mountpoint="/var/lib/db"}[1h], 4*3600) < 0
      and node_filesystem_avail_bytes{mountpoint="/var/lib/db"}
          / node_filesystem_size_bytes{mountpoint="/var/lib/db"} < 0.4
    for: 10m
    labels: {severity: page}
  - alert: VolumeFullIn4d          # ticket: slow growth, days left
    expr: predict_linear(node_filesystem_avail_bytes{mountpoint="/var/lib/db"}[1d], 4*86400) < 0
    for: 1h
    labels: {severity: ticket}
```

The short range catches a runaway WAL. The long range catches steady growth before it becomes
urgent. The `< 0.4` guard stops a brief burst on an empty disk from paging. Pair it with a
direct check on the log itself. This SQLite demo shows checkpoint starvation:

```python
import os, sqlite3
w = sqlite3.connect("s.db", isolation_level=None); w.execute("PRAGMA journal_mode=WAL")
w.execute("CREATE TABLE t(x BLOB)")
r = sqlite3.connect("s.db", isolation_level=None)
r.execute("BEGIN"); r.execute("SELECT count(*) FROM t").fetchone()   # long-lived reader
for _ in range(3000):
    w.execute("INSERT INTO t VALUES (randomblob(4000))")
print("db", os.path.getsize("s.db"), "wal", os.path.getsize("s.db-wal"))
print(w.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())      # while reader open
r.execute("COMMIT")
print(w.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())      # after reader ends
```

Its output, run on the standard-library `sqlite3`:

```text
db 4096 bytes   wal 37,595,032 bytes             # WAL ~9,000x the main file
wal_checkpoint(TRUNCATE) while reader open: (1, 9125, 2)   # blocked; 2 of 9125 pages copied
after the reader committed:                 (0, 0, 0)       # completed; WAL truncated to 0
```

The database answered queries the whole time. Only the WAL-size check and the blocked
checkpoint showed the problem.

## Gotchas and contested points

- **`hostPath` and local PVs tie the data to one node.** They survive restarts, but losing the
  node loses the data. That is acceptable only with replication or backups elsewhere.
- **Bigger disks delay the problem but don't fix it.** If the WAL is pinned, it grows until any
  size is full. Fix the reader, the slot or the archiver.
- **`max_slot_wal_keep_size` trades one failure for another.** Setting it breaks a lagging
  replica (it must be rebuilt) to save the primary. Usually right, but decide it deliberately.
- **Node-level and pod-level pressure differ.** A pod can be evicted for its own limit while the
  node has room, or for node pressure while it stays within its limit.

## Review checklist

1. Is every file the service must keep on a persistent volume? Does any database, upload or
   state file sit on the container's writable layer or in an `emptyDir`?
2. Would the data survive `kill -9` of the container, deletion of the pod, and a drain of the
   node? Was each one tried?
3. Does every container that writes scratch data or logs set `requests.ephemeral-storage`, a
   limit, and an `emptyDir.sizeLimit`?
4. Is the volume sized from measured growth plus WAL peak and maintenance space, with headroom?
5. Is there a time-to-full alert (fast and slow) as well as any percentage threshold?
6. Is WAL size watched relative to data size, with an alert when checkpoints (SQLite) or
   archiving and slots (Postgres) stop making progress?
7. Can any long-lived reader, idle transaction, backup or abandoned replication slot pin the log?
8. Is SQLite kept off network filesystems, with its `-wal` and `-shm` files beside the database?

## Related

[backup-and-restore](backup-and-restore.md) (WAL streaming as a backup),
[disaster-recovery](disaster-recovery.md) (safe deletion of volumes),
[`engineering-practices` reliability](../../engineering-practices/references/reliability.md)
(SLOs and alerting); [`infrastructure-patterns`](../../infrastructure-patterns/SKILL.md) (choosing StatefulSets and managed stores).

## Sources

Kubernetes [Volumes](https://kubernetes.io/docs/concepts/storage/volumes/),
[Ephemeral Storage](https://kubernetes.io/docs/concepts/storage/ephemeral-storage/),
[Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/#local-ephemeral-storage),
[Node-pressure Eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/);
SQLite [WAL](https://www.sqlite.org/wal.html), [PRAGMA](https://www.sqlite.org/pragma.html);
PostgreSQL [Continuous Archiving](https://www.postgresql.org/docs/current/continuous-archiving.html),
[Replication settings](https://www.postgresql.org/docs/current/runtime-config-replication.html);
Prometheus [query functions](https://prometheus.io/docs/prometheus/latest/querying/functions/);
Litestream [Tips](https://litestream.io/tips/). The node exporter metric names are not verified
against its docs.
