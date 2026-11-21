# Sharding

## Problem

One database node runs out of write throughput or storage that no bigger node fixes, or data
must live in different regions by law. Sharding splits rows across databases with one schema,
each owning a subset chosen by a shard key. It scales writes and storage, and adds permanent
complexity to every query, migration, backup and incident (Azure). Most systems that think they
need it need an index, a replica, a cache or table partitioning first.

This reference is about splitting *data*. Splitting a whole stack into independent copies to
limit blast radius is [cells-and-shuffle-sharding](cells-and-shuffle-sharding.md).

## When to use / when NOT to use

- **Use** when data volume or write throughput exceeds one instance with no vertical option
  left, and replicas don't help because writes are the load (Azure).
- **Use** for data residency (geographic shards) or contractual tenant isolation (Azure).
- **Don't** when it fits one instance with projected growth: vertical scaling keeps joins and
  transactions simple (Azure). Size it first with [`system-design`](../../system-design/SKILL.md).
- **Don't** when reads are the bottleneck: [read-replicas](read-replicas.md) and
  [cache-aside](cache-aside.md) (Azure).
- **Don't** when partitioning on one instance suffices, or the dominant queries join across
  entities, need multi-entity transactions or aggregate everything (Azure).

## How it works

**The ladder.** Tune and index → vertical scaling → read replicas and caches → table
partitioning on one node → functional split (separate databases per service) → sharding.

**Shard key.** The most important decision, and expensive to change: it usually means migrating
every row (Azure). A good key is immutable, high-cardinality, spreads data *and* load evenly,
and matches the dominant queries so most requests touch one shard. Avoid auto-increment IDs and
timestamps (all new writes hit one shard), low-cardinality fields, and values that change
(Azure). For multi-tenant SaaS the tenant ID is the usual key; Citus says the same, and says
don't distribute by timestamp: use an entity key and partition by time within it.

**Strategies.**

| Strategy | Maps by | Good | Bad |
|---|---|---|---|
| Range | Key ranges (dates, IDs) | Range scans stay on one shard | Hotspots on recent or adjacent keys; splitting may not fix them (Azure) |
| Hash | Hash of the key | Even spread, no map to keep (Azure) | `hash mod N` moves most keys when N changes; range scans fan out |
| Directory (lookup) | A map from key (or virtual shard) to node | Move one tenant at a time; isolate a big tenant | The map is a dependency to cache and keep available (Azure) |
| Geographic | Region of the data | Residency, latency | Uneven regions; global queries cross regions (Azure) |

**Virtual shards.** Map keys to many logical shards (say 256), and logical shards to a few
nodes. Rebalancing then moves whole logical shards and updates the map, without rehashing.
Prefer many small shards to few large ones: they move faster and balance better (Azure).
Consistent hashing (a ring with virtual nodes) gives the same property without a map.

**Resharding.** Copy the data to the new layout while the old shards keep serving, keep it in
sync, verify, then switch routing. Vitess does this online, with a few seconds of read-only
time at switchover. Without tooling, Azure's lookup procedure is: pause the affected keys,
move, update the map, invalidate caches, resume.

**Cross-shard work.**
- **Queries:** fan out in parallel and merge; the slowest shard sets the latency (Azure). Keep
  a secondary index or search index for lookups by non-key attributes.
- **Joins:** co-locate related tables on the same key (customers and orders by `tenant_id`) so
  the join stays on one shard; replicate small reference tables to every shard (Azure; Citus).
- **Transactions:** avoid them. Two-phase commit adds latency and failure modes; most sharded
  systems use per-shard transactions plus eventual consistency (Azure), via
  [sagas](sagas.md) or the [transactional-outbox](transactional-outbox.md).
- **IDs:** per-shard auto-increment produces duplicates across shards (Azure). Use UUIDs or IDs
  that embed the shard.

**Operations multiply** (Azure): monitoring aggregated across shards, a backup per shard with
cross-shard consistency on restore, and DDL rolled out to every shard.

## In code / In infrastructure

**In code.** One routing layer maps key to shard; nothing else knows the layout. Every query
carries the shard key; queries without it are explicit fan-outs.

**In infrastructure.** Shards as separate databases or clusters, each with its own replicas
and backups; a shard map service or a sharding proxy; per-shard dashboards.

**Agree:** the router's map, its caches and the data placement change together during a move.

## Failure modes and what agents get wrong

- **Sharding before measuring,** when a missing index or a replica would do.
- **Timestamp or sequential ID as the shard key:** every write on one shard (example).
- **`hash mod N`:** adding one shard moves 80% of the data (example).
- **A key that doesn't match the queries:** every request fans out to every shard.
- **One giant tenant on a shared shard.** Give whales their own shard via a directory.
- **Cross-shard transactions designed in** instead of designed out.
- **Restoring one shard to a point in time** that no longer matches the others.
- **Unique constraints assumed global.** They hold per shard only.

## Implementation notes

- **Postgres declarative partitioning** (one node): `PARTITION BY RANGE | LIST | HASH`; worth it
  when the table is larger than memory; pruning by bounds (`enable_partition_pruning` on); a
  primary or unique key must include the partition columns; indexes are per partition; dropping
  or `DETACH PARTITION CONCURRENTLY` replaces bulk deletes; a few thousand partitions are fine if
  pruning leaves few per query (PostgreSQL docs).
- **Citus** (Postgres extension): distributed tables by a distribution column, co-location,
  reference tables. **Vitess** (MySQL): keyspaces split into key-range shards, routed by a
  primary vindex, online split and merge. How each handles cross-shard transactions was not on
  the pages read (unverified).
- **Managed:** distributed SQL and NoSQL services that shard internally still need a good
  partition key; check what they handle (splits, routing) and what remains yours (Azure).

## Example

Moving from 4 to 5 shards with `hash mod N` and with a ring of 100 virtual nodes per shard,
then range sharding on a sequential ID (run on Python 3.13):

```python
import bisect, collections, hashlib

def h(s):
    return int.from_bytes(hashlib.sha256(s.encode()).digest()[:8], "big")

def mod_n(key, shards):
    return shards[h(key) % len(shards)]

class Ring:
    def __init__(self, shards, vnodes=100):
        self.points = sorted((h(f"{s}#{v}"), s) for s in shards for v in range(vnodes))
        self.hashes = [p for p, _ in self.points]
    def __call__(self, key, _=None):
        i = bisect.bisect(self.hashes, h(key)) % len(self.points)
        return self.points[i][1]

keys = [f"tenant-{i}" for i in range(100_000)]
old, new = ["s0", "s1", "s2", "s3"], ["s0", "s1", "s2", "s3", "s4"]
for name, before, after in [("hash mod N", lambda k: mod_n(k, old), lambda k: mod_n(k, new)),
                            ("ring, 100 vnodes", Ring(old), Ring(new))]:
    moved = sum(before(k) != after(k) for k in keys) / len(keys)
    sizes = collections.Counter(after(k) for k in keys).values()
    print(f"{name:17} moved {moved:6.1%}  largest shard {max(sizes) / (len(keys) / 5):.2f}x average")

# Range sharding on a monotonic key: every new write lands on the last shard.
bounds = [25_000, 50_000, 75_000]                     # order_id ranges for s0..s3
new_ids = range(100_000, 101_000)
print("range on order_id, new writes per shard:",
      collections.Counter(f"s{bisect.bisect(bounds, i)}" for i in new_ids))
```

Output: `hash mod N` moved 80.1% of 100,000 keys, the ring 22.4% (ideal 20%) with the largest
shard at 1.13x average; range on a sequential ID sent all 1000 new writes to `s3`.

## Review checklist

1. Was the single node measured at its limit, after indexes, vertical scaling, replicas and partitioning?
2. Is the shard key immutable, high-cardinality, evenly loaded, and present in the dominant queries?
3. Is the strategy (range, hash, directory, geographic) chosen for the queries and the hotspots?
4. Can shards be added by moving virtual shards or ring segments, not by rehashing everything?
5. Are cross-shard queries explicit fan-outs, with an index for non-key lookups?
6. Are cross-shard transactions designed out (co-location, sagas, outbox)?
7. Are IDs unique across shards?
8. Are backups, restores, monitoring and migrations defined per shard and for all shards together?

## Related

[cells-and-shuffle-sharding](cells-and-shuffle-sharding.md), [read-replicas](read-replicas.md),
[load-balancing](load-balancing.md) (consistent hashing for traffic), [sagas](sagas.md),
[transactional-outbox](transactional-outbox.md), [`system-design`](../../system-design/SKILL.md),
[`data-integrity` backup-and-restore](../../data-integrity/references/backup-and-restore.md).

## Sources

Azure Architecture Center, [Sharding pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/sharding).
PostgreSQL, [Table partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html).
Citus, [Choosing the distribution column](https://docs.citusdata.com/en/stable/sharding/data_modeling.html).
Vitess, [Sharding](https://vitess.io/docs/reference/features/sharding/).
Envoy, [load balancers](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/load_balancing/load_balancers) (ring hash remapping).
