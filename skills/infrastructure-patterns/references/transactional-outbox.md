# Transactional outbox

## Problem

A service must change its database and tell others: insert the order, publish `order.placed`.
Two systems, no shared transaction. Publish inside the transaction and it can still roll back
after the message is out; publish after commit and the process can die in between. This is the
dual-write problem. microservices.io's requirement: send if and only if the transaction commits,
in the order sent, without two-phase commit across database and broker.

## When to use / when NOT to use

- **Use** whenever a state change and a message must agree: domain events, saga steps, index or
  read-model updates ([cqrs-and-materialized-views](cqrs-and-materialized-views.md)), webhooks.
- **Don't** if consumers can read the source of truth directly, or if losing an occasional
  notification is acceptable and a periodic full sweep repairs it.
- **Don't** add it when the state *is* the event log: with [event-sourcing](event-sourcing.md)
  the append is the publish (microservices.io lists it as the alternative).
- **Not** exactly-once: the relay can publish a row twice; consumers must be [idempotent](idempotent-consumer.md).

## How it works

1. **In the business transaction,** insert the event into an `outbox` table in the same
   database: event ID, aggregate type and ID, event type, payload.
2. **A relay** reads committed outbox rows and publishes them to the broker.
3. **The relay records progress** (mark the row, delete it, or store a log position).
4. **Cleanup** removes published rows.

Two ways to build the relay:

| | Polling publisher | Transaction log tailing (CDC) |
|---|---|---|
| How | Query `WHERE published_at IS NULL ORDER BY seq` on an interval | Read the database's change log (Postgres WAL, MySQL binlog) for outbox inserts |
| Works with | Any SQL database (microservices.io) | Database-specific (microservices.io) |
| Latency | The poll interval | Near the commit |
| Load | A query per poll; an index on unpublished rows | Replication slot or binlog reader |
| Ordering | Tricky (microservices.io); see below | Log order is commit order (unverified) |
| Duplicates | After a crash between publish and mark | Tricky to avoid too (microservices.io) |
| Tooling | A loop in the service, or a sidecar | Debezium with the outbox event router |

**Debezium's outbox event router** expects columns `id`, `aggregatetype`, `aggregateid`, `type`
and `payload` by default. `aggregatetype` picks the topic (`outbox.event.<aggregatetype>`),
`aggregateid` becomes the message key, which keeps one aggregate's events in order within a Kafka
partition, and `id` goes into a header that consumers can dedupe on. It expects only `INSERT`s:
it filters out `DELETE`s and warns on `UPDATE`s by default. So cleanup can delete captured rows
without emitting events. How soon after insert that is safe was not stated (unverified).

**Ordering.** Order matters per aggregate, rarely globally. Key the broker message by aggregate
ID. With a polling publisher, ordering by an auto-increment column is safe on a single-writer
database such as SQLite. On Postgres or MySQL, a sequence value is taken at insert, not at
commit, so a transaction holding seq 41 can commit after one holding 42. A poller that remembers
"last seq published" skips 41 for good. One polling `published_at IS NULL` doesn't skip it but
may publish 42 first. (This paragraph is this skill's reasoning, not from the sources.)
Remedies: serialize writes per aggregate (lock the aggregate row in the business transaction),
poll per aggregate in order, or use log tailing.

## In code / In infrastructure

**In code.** The outbox insert goes in the same transaction as the business change, through the
same connection. Make it impossible to forget: write it from the repository or unit-of-work, not
from each handler. microservices.io names forgetting to publish as the drawback. Use a
stable event ID, and wrap the payload in a [`cloudevents`](../../cloudevents/SKILL.md)
envelope or an equivalent.

**In infrastructure.** One active relay per outbox (lease or leader election), or several
partitioned by aggregate. For CDC: a replication slot, connector monitoring, and a slot-lag alert,
since a stalled slot holds WAL on the primary
([`data-integrity` state-and-storage](../../data-integrity/references/state-and-storage.md)).

**Agree:** the relay's at-least-once publish is safe only because consumers dedupe on the event
ID. Both sides must use the same ID.

## Failure modes and what agents get wrong

- **"Publish after commit, it's fine."** An OOM kill or deploy in between loses the event for good.
- **Publishing inside the transaction.** It then rolls back: consumers act on a phantom order.
- **Treating the relay as exactly-once.** A crash after publish and before mark republishes
  (example). Consumers must be idempotent.
- **Polling on `seq > last_seen`** on a database with concurrent writers: rows that commit late
  are skipped forever.
- **Several relays on one outbox** with no lease or partitioning: duplicates, and per-aggregate
  order lost.
- **No cleanup.** The outbox grows and polls slow; delete published rows or drop old partitions.
- **CDC slot left behind** after a connector is removed: WAL piles up until the disk fills.

## Implementation notes

- **Postgres:** a partial index on unpublished rows for polling. **Postgres / MySQL:** WAL / binlog
  CDC into Debezium; `SELECT ... FOR UPDATE` on the aggregate row serializes its events.
- **SQLite:** one writer, so an auto-increment `seq` is commit order; poll from the app.
- **RabbitMQ:** use publisher confirms in the relay, so a row is marked published only after the
  broker accepted it.
- **NATS JetStream:** set `Nats-Msg-Id` to the event ID; the server drops repeats within the
  duplicate window (default 2 minutes), which absorbs quick relay retries.
- **Managed:** managed CDC services, or a database's change feed, play the log-tailing role.

## Example

The business row and the outbox row in one SQLite transaction, a polling relay, a crash
between publish and mark, and cleanup:

```python
import json, sqlite3, uuid
db = sqlite3.connect(":memory:", isolation_level=None)
db.executescript("""
CREATE TABLE orders (id TEXT PRIMARY KEY, customer TEXT NOT NULL, total INTEGER NOT NULL);
CREATE TABLE outbox (seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
  aggregate_type TEXT NOT NULL, aggregate_id TEXT NOT NULL, type TEXT NOT NULL,
  payload TEXT NOT NULL, published_at REAL);""")

def place_order(customer, total, fail_after_insert=False):
    order_id = uuid.uuid4().hex
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute("INSERT INTO orders VALUES (?, ?, ?)", (order_id, customer, total))
        db.execute("INSERT INTO outbox (event_id, aggregate_type, aggregate_id, type, payload)"
                   " VALUES (?, 'order', ?, 'order.placed', ?)", (uuid.uuid4().hex, order_id,
                   json.dumps({"customer": customer, "total": total})))
        if fail_after_insert:
            raise RuntimeError("validation failed after the inserts")
        db.execute("COMMIT"); return order_id
    except BaseException:
        db.execute("ROLLBACK"); raise

def relay(broker, batch=100, crash_before_mark=False):
    rows = db.execute("SELECT seq, event_id, aggregate_id, type, payload FROM outbox"
                      " WHERE published_at IS NULL ORDER BY seq LIMIT ?", (batch,)).fetchall()
    for seq, event_id, key, etype, payload in rows:
        broker.append({"id": event_id, "key": key, "type": etype, "data": json.loads(payload)})
        if crash_before_mark:
            raise RuntimeError("relay killed after publish, before mark")
        db.execute("UPDATE outbox SET published_at = julianday('now') WHERE seq = ?", (seq,))

def cleanup():
    return db.execute("DELETE FROM outbox WHERE published_at IS NOT NULL").rowcount
```

Driven as: one good order, one that fails after both inserts, a relay killed after publishing,
a second relay run, a consumer that skips seen IDs, then cleanup. Result: 1 order and 1 outbox
row (the failed order left neither); 2 messages on the broker with 1 distinct ID; 1 applied by
the deduping consumer; 1 row cleaned up.

## Review checklist

1. Is the outbox row written in the same transaction, on the same connection, as the business change?
2. Is the outbox write centralized so a handler can't forget it?
3. Does every event have a stable ID, used by consumers to dedupe?
4. Is the broker message keyed by aggregate ID, and are one aggregate's events serialized at write time?
5. Does the relay avoid `seq > last_seen` on a database with concurrent writers?
6. Is exactly one relay active per outbox partition (lease or leader election)?
7. Does the relay mark a row only after the broker confirmed it?
8. Is there cleanup, an alert on relay lag (oldest unpublished row), and for CDC on slot lag?

## Related

[idempotent-consumer](idempotent-consumer.md), [publish-subscribe](publish-subscribe.md),
[sagas](sagas.md), [event-sourcing](event-sourcing.md), [`cloudevents`](../../cloudevents/SKILL.md),
[`data-pipelines` idempotent-stages](../../data-pipelines/references/idempotent-stages.md)
(side effects emitted from committed state).

## Sources

microservices.io: [Transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html),
[Polling publisher](https://microservices.io/patterns/data/polling-publisher.html),
[Transaction log tailing](https://microservices.io/patterns/data/transaction-log-tailing.html).
Debezium, [Outbox event router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html).
Azure Architecture Center, [CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)
(outbox plus idempotent read-model consumers). RabbitMQ,
[publisher confirms](https://www.rabbitmq.com/docs/confirms). NATS,
[streams](https://docs.nats.io/nats-concepts/jetstream/streams) (duplicate window).
