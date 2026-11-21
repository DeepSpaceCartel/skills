# Event sourcing

## Problem

A table holds only the current state. It can't say how the record got there, what it looked
like last Tuesday, or why it changed. Event sourcing stores the changes instead: every
state-changing event for an entity is appended to that entity's stream, and current state is
whatever replaying the stream produces. The audit trail, temporal queries and reliable
publishing come for free. Everything else gets harder: querying, schema changes, deletion,
testing, and operating a store no one on the team has run before.

**Usually it doesn't pay for itself.** Azure's page now opens with that warning: it is costly to
adopt and to leave, it constrains later design, and for most systems and most parts of a system
ordinary current-state storage is enough. Treat it as a choice for one bounded part (a ledger,
an order lifecycle), not an architecture.

## When to use / when NOT to use

- **Use** when the history is the product: ledgers, bookings, regulated workflows where you
  must show what happened, in order, and why.
- **Use** when you need temporal questions ("state as of date X") and replays that rebuild new
  read models from old facts.
- **Use** when the domain already thinks in events and intent matters ("moved home", "closed
  account") more than resulting values.
- **Don't** for CRUD with no audit or replay need, prototypes, short-lived systems, or mostly
  static reference data (Azure lists each).
- **Don't** when every read must be immediately consistent with every write across views.
  Projections lag.
- **Don't** as the first event-driven system a team builds. Azure names inexperience as a reason
  not to; the antipatterns are expensive to undo.
- **Only want an audit log?** An audit table in the same transaction. **Reliable publishing?**
  A [transactional-outbox](transactional-outbox.md).

## How it works

| Piece | What it does | Watch for |
|---|---|---|
| Event stream per entity | Ordered, append-only events with a per-stream version | Events named for intent (`SeatsReserved`), not state (`FreeSeatsChanged`) |
| Append with expected version | Rejects an append if the stream moved since it was read (optimistic concurrency) | Retry by reloading and re-deciding, not by re-appending |
| Rehydration | Load the stream, apply each event to rebuild state | Long streams get slow |
| Snapshot | Saved state at version N; load it, replay only later events | An optimization; always rebuildable from events |
| Projections | Read models built from events ([cqrs-and-materialized-views](cqrs-and-materialized-views.md)) | Eventually consistent; idempotent; rebuildable |
| Publishing | Subscribers receive appended events | At least once; events stored are often too low-level for other teams |

**An event store is not a broker.** Azure warns that log brokers such as Kafka usually lack
per-entity stream reads and optimistic concurrency, so they work as the distribution layer, not
as the store. A relational table with a `(stream, version)` primary key is a workable store.

**Snapshots.** Take one every N events or on a schedule, sized by how long rehydration may take.
A snapshot's schema evolves too: version it, and discard and rebuild snapshots on a breaking
change rather than upcasting them.

**Schema evolution.** Stored events are never edited, so every version ever written must stay
readable. In order of preference:

| Approach | Handles | Cost |
|---|---|---|
| Additive change, tolerant readers | New optional fields | Readers ignore unknown fields and default missing ones |
| Version on each event | Any change | A handler per version; old handlers live forever |
| Upcaster on read | Renames, reshapes | A chain of transforms from old to current shape; stored events unchanged |
| New event type | Changed meaning | Old and new coexist; projections handle both |
| Rewrite stored events | Last resort | Breaks immutability and the audit trail |

**Corrections and deletion.** A wrong event is fixed by a compensating event, not an edit. A bug
that wrote bad events leaves them in the store; replay must handle them. Personal data conflicts
with immutability: keep it outside the events, referenced by ID, or encrypt it per subject and
delete the key (crypto-shredding), both from Azure.

## In code / In infrastructure

**In code.** Command handler: load, decide, append with the expected version, retry on
conflict. Events carry type, schema version, stream, version and time, in the
[`cloudevents`](../../cloudevents/SKILL.md) envelope or equivalent. Tests in given (past events),
when (command), then (new events) form.

**In infrastructure.** The event store's backups and restore drills: it is the only source of
truth ([`data-integrity`](../../data-integrity/SKILL.md)). Distribution to projections through an
outbox or CDC from the store, consumer lag alerts, and rebuild capacity.

**Agree:** the event store's retention is forever; the broker's is days. Projections that need
full history rebuild from the store, not the topic.

## Failure modes and what agents get wrong

- **State-shaped events** (`OrderUpdated {all fields}`): the history says nothing a CRUD table
  plus triggers wouldn't.
- **Kafka as the event store.** No append-if-version check, so two handlers both reserve the last
  seat.
- **Breaking event schemas** with no upcaster: old streams no longer load.
- **Querying the store directly** for lists and searches. Build projections.
- **Side effects on replay.** Rebuilding a projection resends every email. Keep side effects out
  of projection code, or gate them on "live" mode.
- **Event loops.** A handler whose event triggers itself (Azure flags circular logic).
- **Assuming a single global order.** Order holds within a stream; across streams, use
  timestamps only as a hint.

## Implementation notes

- **Postgres / SQLite:** `events(stream, version, type, schema, data, recorded_at)` with
  `PRIMARY KEY (stream, version)`; a snapshots table; an outbox or CDC to publish.
- **Purpose-built event stores** add stream reads, expected-version appends, subscriptions and
  snapshots out of the box (Azure).
- **Kafka / NATS JetStream:** distribution to projections and other services. JetStream subjects
  per stream can serve small event-sourced aggregates (unverified for optimistic concurrency).
- **Managed:** document databases with a change feed are a common store-plus-feed choice;
  check that the store offers a conditional append.

## Example

A seat-reservation stream in SQLite with an expected-version append, an upcaster for an old
schema, and a snapshot. Excerpt: the imports and the `db` connection are omitted, so it doesn't
run on its own:

```python
db.executescript("""
CREATE TABLE events (stream TEXT NOT NULL, version INTEGER NOT NULL, type TEXT NOT NULL,
                     schema INTEGER NOT NULL, data TEXT NOT NULL, PRIMARY KEY (stream, version));
CREATE TABLE snapshots (stream TEXT PRIMARY KEY, version INTEGER NOT NULL, state TEXT NOT NULL);""")

def upcast(etype, schema, data):                 # v1 stored "n"; v2 calls it "seats"
    return {"seats": data["n"]} if etype == "SeatsReserved" and schema == 1 else data

def load(stream, capacity=100):
    snap = db.execute("SELECT version, state FROM snapshots WHERE stream=?", (stream,)).fetchone()
    version, state = (snap[0], json.loads(snap[1])) if snap else (0, {"free": capacity})
    rows = db.execute("SELECT version, type, schema, data FROM events WHERE stream=? AND version>?"
                      " ORDER BY version", (stream, version)).fetchall()
    for version, etype, schema, data in rows:
        state = apply(state, etype, upcast(etype, schema, json.loads(data)))
    return version, state, len(rows)

def append(stream, expected_version, etype, data, schema=2):
    try:                                         # the primary key rejects a stale writer
        db.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?)",
                   (stream, expected_version + 1, etype, schema, json.dumps(data)))
        return True
    except sqlite3.IntegrityError:
        return False
```

`apply` subtracts seats on `SeatsReserved` and adds them on `ReservationCancelled`. Starting from
one schema-1 event (`{"n": 3}`): a reservation of 2 succeeded; two handlers that both read
version 2 tried to append 90 seats and only the first succeeded; a cancellation, a snapshot and
one more reservation left `free = 6` with 1 event replayed after the snapshot, and all 5 events
in the history.

## Review checklist

1. Is there a requirement (audit, temporal queries, replay) that a current-state table plus an audit table can't meet?
2. Is event sourcing limited to the bounded part that needs it?
3. Do appends check the expected stream version, and do handlers reload and re-decide on conflict?
4. Are events named for intent and versioned, with tolerant readers or upcasters for old versions?
5. Is there a snapshot policy, and are snapshots rebuildable and versioned?
6. Are reads served by projections, with lag monitored and rebuilds rehearsed?
7. Are side effects kept out of replays?
8. Is personal data outside the events or crypto-shredded?
9. Is the event store backed up and restore-tested as the single source of truth?

## Related

[cqrs-and-materialized-views](cqrs-and-materialized-views.md),
[transactional-outbox](transactional-outbox.md), [idempotent-consumer](idempotent-consumer.md),
[sagas](sagas.md), [`cloudevents`](../../cloudevents/SKILL.md),
[`engineering-practices` api-evolution](../../engineering-practices/references/api-evolution.md)
(evolving schemas), [`data-integrity` backup-and-restore](../../data-integrity/references/backup-and-restore.md).

## Sources

Azure Architecture Center, [Event Sourcing](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)
and [CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs) (combining the
two, snapshots). microservices.io, [Event sourcing](https://microservices.io/patterns/data/event-sourcing.html).
