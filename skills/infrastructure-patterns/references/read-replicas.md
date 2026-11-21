# Read replicas

## Problem

One primary serves every read and write, and reads dominate: listings, search, dashboards.
Replicas replay the primary's changes and answer queries, so reads scale out. The price is lag,
usually milliseconds and sometimes minutes: code that writes on the primary and reads from a
replica can miss its own write. And a replica is not a backup.

## When to use / when NOT to use

- **Use** when measurement shows reads, not writes, saturate the primary (CPU, I/O, connections),
  and those reads tolerate some staleness: listings, search, reports, analytics.
- **Use** a replica for reporting so heavy queries stop competing with writers (step 1 of the
  ladder in [cqrs-and-materialized-views](cqrs-and-materialized-views.md)).
- **Don't** before fixing the query or index, or adding a [cache](cache-aside.md).
- **Don't** when writes are the bottleneck. Every replica replays every write; see [sharding](sharding.md).
- **Don't** treat a replica as a backup: a `DROP TABLE` or a bad `UPDATE` replicates in
  milliseconds. Backups and point-in-time recovery are
  [`data-integrity` backup-and-restore](../../data-integrity/references/backup-and-restore.md).

## How it works

**Postgres streaming replication.** A hot standby replays the primary's WAL and accepts
read-only queries: `SELECT`, `COPY TO`, cursors, `SET`. It rejects writes, DDL,
`SELECT ... FOR UPDATE`, `nextval()`, `LISTEN`/`NOTIFY`, and writes to temporary tables. Its data
is eventually consistent: a commit becomes visible once its record is replayed, so the same
query on primary and replica at the same moment can differ (PostgreSQL docs).

**Query conflicts.** Replay can need to remove rows a standby query still sees (vacuum
cleanup) or take a lock it holds. The standby waits up to `max_standby_streaming_delay`
(default 30 s) and then cancels the query. `hot_standby_feedback` (default off) avoids most
cancellations by telling the primary to keep those rows, at the cost of bloat on the primary.
Long reports on a replica therefore either get cancelled, delay replay (more lag), or bloat the
primary. Pick one deliberately, per replica.

**Read-your-writes.** Options, cheapest first:

| Technique | How | Cost |
|---|---|---|
| Return the new state from the write | The handler that wrote renders the result | None; covers the commonest case |
| Primary for a window | After a write, route that session's reads to the primary for a few seconds | Guesswork if lag spikes past the window |
| Position wait | Store the commit's position in the session; read from a replica once it has replayed that far, else from the primary | One extra query per read |
| Synchronous apply | `synchronous_commit = remote_apply` with `synchronous_standby_names` set | Every commit waits for replay on the synchronous standbys |
| Critical reads on the primary | Balance checks, uniqueness checks, read-then-write | Primary load |

Postgres positions: `pg_current_wal_lsn()` on the primary after commit, `pg_last_wal_replay_lsn()`
on the standby, `pg_wal_lsn_diff()` for bytes of lag. `remote_apply` makes a commit visible on
the *synchronous* standbys only; asynchronous replicas still lag. MySQL: capture the GTID of the
write and call `WAIT_FOR_EXECUTED_GTID_SET(gtid_set, timeout)` on the replica (0 = applied,
1 = timed out). (Combining these into a session router is this skill's design.)

**Routing.** Make the split explicit in code: two pools, and each query chooses. A proxy that
routes by parsing SQL misses side-effecting functions and read-then-write transactions (this
skill's reasoning).

**Failover and promotion.** Postgres itself doesn't detect a failed primary; external tooling
must, then promote a standby (`pg_ctl promote` or `SELECT pg_promote()`), and fence the old
primary (STONITH) so two primaries never accept writes. Afterwards the old primary is rebuilt
as a standby, faster with `pg_rewind`, and the cluster runs without a spare until then. With
asynchronous replication, commits not yet shipped are lost on failover. Practise switchovers
regularly (PostgreSQL docs). Split brain and fencing in general:
[redundancy-and-failover](redundancy-and-failover.md).

**Connection pooling.** Each replica adds a pool, and each app pod opens connections to every
pool. PgBouncer multiplexes clients onto fewer server connections. Session mode supports every
feature. Transaction mode assigns a server connection per transaction and breaks `SET`/`RESET`,
`LISTEN`, `WITH HOLD` cursors, SQL `PREPARE`/`DEALLOCATE`, session advisory locks, `LOAD` and
`PRESERVE`/`DELETE ROWS` temp tables; protocol-level prepared statements work if
`max_prepared_statements` is non-zero (PgBouncer docs).

## In code / In infrastructure

**In code.** Two pools, a per-call choice of primary or replica, a session position for
read-your-writes, and a fallback to the primary when the replica is too far behind.

**In infrastructure.** Replicas in other zones; a lag metric and alert per replica; a separate
replica for heavy reporting with its own conflict settings; failover tooling with fencing; a
pooler in front of each node. Size the primary to carry all reads if every replica is lost.

**Agree:** the code's lag tolerance must be larger than the lag the alert allows.

## Failure modes and what agents get wrong

- **Write, then redirect to a page read from a replica:** the user doesn't see the save.
- **Read-then-write on a replica:** a uniqueness or balance check passes on stale data.
- **A replica as backup** or as recovery from logical errors. **No lag alert:** hours-old reads.
- **Lag measured by `now() - pg_last_xact_replay_timestamp()` on a quiet primary** grows with no
  writes; compare LSNs instead (this skill's reasoning).
- **Long analytics queries on the HA standby,** with `hot_standby_feedback` on: primary bloat.
- **Transaction pooling with session features** (`SET search_path`, advisory locks, `LISTEN`).
- **No fencing:** the old primary returns and accepts writes.

## Implementation notes

- **Postgres:** streaming replication with hot standby; `max_standby_streaming_delay`,
  `hot_standby_feedback`; `pg_stat_database_conflicts` on the standby counts cancellations.
- **MySQL:** GTID-based replication; `WAIT_FOR_EXECUTED_GTID_SET` for position waits.
- **Managed:** managed read replicas and reader endpoints; check how lag is exposed and whether
  the reader endpoint balances per connection.

## Example

A session router that sends reads to a replica only after it has replayed the session's last
write, with LSNs as plain numbers (run on Python 3.13):

```python
import time

class Router:  # reads go to the replica only once it has replayed the session's last write
    def __init__(self, primary_lsn, replica_lsn, max_wait=0.05):
        self.primary_lsn, self.replica_lsn, self.max_wait = primary_lsn, replica_lsn, max_wait

    def write(self, session):
        session["lsn"] = self.primary_lsn()          # pg_current_wal_lsn() after COMMIT

    def read(self, session, critical=False):
        if critical:
            return "primary"                         # e.g. balance check before a debit
        need, deadline = session.get("lsn", 0), time.monotonic() + self.max_wait
        while self.replica_lsn() < need:             # pg_last_wal_replay_lsn() on the replica
            if time.monotonic() >= deadline:
                return "primary"                     # lag too high: fall back, don't serve stale
            time.sleep(0.005)
        return "replica"

state = {"primary": 100, "replica": 100}
r = Router(lambda: state["primary"], lambda: state["replica"])
alice, bob = {}, {}
print("bob, no writes:          ", r.read(bob))
state["primary"] = 180; r.write(alice)               # alice commits at LSN 180
print("alice right after write: ", r.read(alice))    # replica still at 100
state["replica"] = 180
print("alice after replay:      ", r.read(alice))
print("alice, critical read:    ", r.read(alice, critical=True))
```

Output: `replica`, `primary`, `replica`, `primary`. Checked: no-write sessions use the replica,
a fresh write forces the primary until replay catches up, critical reads stay on the primary. In
Postgres the test is `pg_last_wal_replay_lsn() >= '0/3000060'::pg_lsn` (not run here).

## Review checklist

1. Did measurement show reads saturating the primary, after query and index fixes?
2. Is every read explicitly routed to primary or replica, with critical reads on the primary?
3. Does a session read its own writes (returned state, position wait, or primary window)?
4. Is there a lag metric and alert per replica, and a fallback when lag exceeds the tolerance?
5. Are standby conflict settings chosen per replica (cancel, delay, or feedback and bloat)?
6. Is failover automated with fencing, and practised?
7. Are backups and PITR separate from replicas?
8. Does the pooler mode match the session features the app uses?
9. Can the primary carry all reads if the replicas are gone?

## Related

[cqrs-and-materialized-views](cqrs-and-materialized-views.md), [cache-aside](cache-aside.md),
[sharding](sharding.md), [redundancy-and-failover](redundancy-and-failover.md),
[`data-integrity` backup-and-restore](../../data-integrity/references/backup-and-restore.md),
[`system-design` capacity-planning](../../system-design/references/capacity-planning.md) (connections).

## Sources

PostgreSQL: [Hot Standby](https://www.postgresql.org/docs/current/hot-standby.html),
[High availability solutions](https://www.postgresql.org/docs/current/different-replication-solutions.html),
[Failover](https://www.postgresql.org/docs/current/warm-standby-failover.html),
[replication settings](https://www.postgresql.org/docs/current/runtime-config-replication.html),
[WAL settings](https://www.postgresql.org/docs/current/runtime-config-wal.html) (`synchronous_commit`),
[admin functions](https://www.postgresql.org/docs/current/functions-admin.html).
PgBouncer, [features](https://www.pgbouncer.org/features.html). MySQL,
[GTID functions](https://dev.mysql.com/doc/refman/8.4/en/gtid-functions.html).
