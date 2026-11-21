# Stateful services and messaging

Checked 2026-11-20. Footprints marked *(estimate)* are judgements, not vendor figures.

## Start from what you already run

Every stateful system is another backup, restore drill, upgrade path, monitoring stack and failover
procedure. Add one only for a capability you can name, not for "reliability" in general:
reliability comes from fewer durability domains, not more.

## CloudNativePG (Postgres)

CloudNativePG (CNCF incubating, v1.30) is the default Postgres operator. It manages Pods and PVCs
directly (no StatefulSet), with streaming replicas, failover, rolling updates, a PgBouncer `Pooler`,
replica clusters and point-in-time recovery.

- **Backups:** use the **Barman Cloud plugin**: an `ObjectStore` resource (`barmancloud.cnpg.io`)
  plus `spec.plugins: [{name: barman-cloud.cloudnative-pg.io, isWALArchiver: true, parameters:
  {barmanObjectName: …}}]` on the `Cluster`. The in-tree `barmanObjectStore` is deprecated and is
  removed in 1.32.
- **Volume snapshots** (`method: volumeSnapshot`) need a CSI driver with snapshot support.
- **PITR** always creates a **new** cluster (`bootstrap.recovery` with a `recoveryTarget`); you
  never rewind an existing one. Rehearse it: a backup never restored is a hope, not a backup.
- **Images:**
  - **`minimal` and `standard`:** use these; `system` is deprecated. `standard` includes
    pgvector, PGAudit and all locales.
  - **Image-volume extensions:** separate OCI images mounted via `ImageVolume` (GA 1.36). They
    need PG 18 or later.
  - **Pinning:** pin by digest or with an `ImageCatalog`.
- **Pooler:**
  - **Transaction mode breaks session features:** `LISTEN/NOTIFY` and session advisory locks
    don't work through it.
  - **Prepared statements** need PgBouncer's `max_prepared_statements`.
  - **Bypass it** for consumers that rely on session features.
- **Storage:**
  - **Local NVMe** with several instances on different nodes is the classic recommendation.
    Network volumes cost IOPS and latency.
  - **WAL:** put it on its own volume (`walStorage`).
- **Kubernetes support:** check `supported_releases.md` before upgrading Kubernetes. A CNPG minor
  supports a range and only *tests* the newest.

## Postgres as the queue

| Technique | What it gives | Limits |
|---|---|---|
| A **work table with `FOR UPDATE SKIP LOCKED`** | Competing consumers. Enqueue in the **same transaction** as the business write, so there's no dual-write. Retries via `attempts` / `run_after`; a dead-letter queue is a status | Vacuum churn at high rates: keep queue tables small, partition, or truncate |
| **pgmq** (SQL-only install) | SQS-like visibility timeouts, archive tables for replay, FIFO groups | Same storage limits |
| **Transactional outbox** | Write the event row with the state change, then relay it (poll or logical decoding) to consumers or a broker | The relay must not skip rows (below) |
| **LISTEN/NOTIFY** | A wake-up signal to cut polling latency | Not a queue: payloads under 8000 bytes, lost while nobody listens, not through transaction pooling. Always keep polling as the fallback |

**The cursor trap.** A consumer that reads `WHERE id > :last_seen ORDER BY id` **skips rows**,
because sequence and identity values are assigned at insert but **commit out of order**:
transaction A takes id 101, B takes 102, B commits first, the consumer advances past 102, and 101
is never read. This is the most common bug in home-grown outbox relays. Fix it with any one of
these:

1. **Claim rows** (`SKIP LOCKED` or pgmq: mark or delete them as done) instead of keeping a cursor.
2. **Read only below the oldest in-flight transaction:** store `pg_current_xact_id()` in an `xid8`
   column and read rows whose xid is below `pg_snapshot_xmin(pg_current_snapshot())`.
3. **Re-scan a trailing window** and deduplicate idempotently.
4. **Use logical decoding,** which emits rows in commit order.

The outbox pattern itself (polling publisher versus CDC, relay failure modes, cleanup) is
[`../../infrastructure-patterns/references/transactional-outbox.md`](../../infrastructure-patterns/references/transactional-outbox.md).

A Postgres queue serves hundreds to low thousands of messages a second alongside normal
traffic. Above that, or for long replay or many independent consumers, look at a broker. Spread
backfills over time and claim in batches: a broker doesn't remove the load if every stage still
writes to the same database.

## Brokers

| | NATS JetStream | RabbitMQ | Kafka (Strimzi) / Redpanda |
|---|---|---|---|
| Best at | Light pub/sub, fan-out, work queues, request/reply, replayable streams, KV | Task queues with routing (exchanges), priorities, TTL, delays, dead-lettering; AMQP/MQTT clients | High sustained throughput, many consumer groups over long retention, the Kafka ecosystem (Connect, Debezium CDC, Flink, Streams) |
| Ordering | Per stream / subject | Per queue with one consumer | Per partition |
| Replay | Yes (by sequence or time) | Streams only; queues delete on ack | Yes: its core strength |
| DLQ / retries | `MaxDeliver`, `BackOff`, `Nak` with a delay. No built-in DLQ: subscribe to the max-deliveries advisory | **Built in:** quorum-queue `delivery-limit` with at-least-once dead-lettering; 4.4 adds delayed and deferred messages | Your own retry and DLQ topics (Connect has a DLQ) |
| Smallest replicated setup | 3 servers, a few hundred MB each *(estimate)* | 3 nodes. Operator default 1 CPU / 2 Gi each; the official production example uses 4 CPU / 10 Gi | Kafka: 3 KRaft nodes, roughly 8–12 Gi in total *(estimate)*. Redpanda: dedicated nodes at 2 GiB per core |
| Operator | Helm chart (JetStream **off** by default) + NACK for streams and consumers as CRDs | Cluster Operator + Messaging Topology Operator | Strimzi 1.x (`kafka.strimzi.io/v1`, KRaft only) / Redpanda operator |
| Licence, project | Apache-2.0, CNCF graduated (2026) | MPL; Broadcom | Kafka Apache-2.0 (Strimzi CNCF incubating); Redpanda BSL with paid enterprise features (tiered storage) |
| Ops load | Low | Medium (Erlang, memory and disk alarms that block publishers, feature flags before upgrades) | High (partitions, rebalancing, JVM, two-step upgrades) |

None of them joins the database transaction, so each needs an outbox to stay consistent with the
data. Partitions, consumer groups, retention and replay semantics are in
[`../../infrastructure-patterns/references/publish-subscribe.md`](../../infrastructure-patterns/references/publish-subscribe.md);
dead-letter handling in its
[`dead-letter-queues`](../../infrastructure-patterns/references/dead-letter-queues.md).

Gotchas:

- **NATS:**
  - JetStream must be enabled and sized; publishes fail when file-store limits are hit.
  - R3 streams need 3 servers; R1 streams die with their volume.
  - Deduplicate with the `Nats-Msg-Id` header.
- **RabbitMQ:**
  - 4.x removed classic mirrored queues: use quorum queues for work and streams for replay.
  - Very long queues hurt: it isn't a database.
- **Kafka:** consumers own retries. Plan partition counts up front. Upgrades go operator first,
  then the Kafka and metadata versions.

## Documents and caches

- **Postgres JSONB versus MongoDB:**
  - **JSONB:** `jsonb` columns next to relational ones, GIN indexes, ACID, joins, one backup, and
    pgvector for embeddings. Choose MongoDB only when documents are the product, built-in sharding
    is needed from day one, or the team is Mongo-native.
  - **MongoDB:** the Community Operator is deprecated in favour of **MCK** (MongoDB Controllers for
    Kubernetes). The Percona Operator bundles backups (PBM). The server is SSPL.
- **Valkey / Redis** are caches, rate limiters and ephemeral locks, **not a durable queue of
  record**.
  - **Operators:** the official Valkey operator is marked "not ready for production". A single
    instance from the official Helm chart is enough for a cache.
  - **Bitnami images:** charts that pull `bitnami/*` images need a new source (free images moved
    to `bitnamilegacy`).

## Object storage

| Option | Status | Fit |
|---|---|---|
| Managed S3 (cloud or provider) | — | Backups belong **outside** the cluster they protect. Check object-lock support before relying on it for immutable copies |
| **MinIO** community | Repo archived 2026-04-25, unmaintained | Don't start new deployments |
| **Garage** | Active, light, replication-based | No versioning, no object lock, no bucket policies |
| **SeaweedFS** | Active | Richer S3, more components |
| **Rook-Ceph** (CNCF graduated) | Active | Block, file and object; the heaviest; wants raw disks and at least 3 nodes |

## Velero

Velero (`velero-io/velero`, CNCF sandbox) backs up API objects and volumes to object storage and
restores them, also into another cluster.

| Path | What it is | Off-site? |
|---|---|---|
| CSI snapshots | Storage-backend snapshots | No: they stay on the backend |
| **CSI snapshot data movement** | Snapshot, then Kopia copies it to object storage | Yes: the recommended path |
| File-system backup | Kopia reads the volume through the node agent | Yes: the fallback when the CSI driver has no snapshots |

- **Restic:** restic backups were removed in 1.17; old restic backups can be restored until 1.19.
- **Databases:** don't back them up with Velero when they have WAL archiving. Exclude their PVCs
  to avoid inconsistent double copies.
- **With GitOps,** Git already holds the manifests, so Velero mostly covers volumes and state that
  isn't in Git.
- **Back up the CRDs, and test restores.**
