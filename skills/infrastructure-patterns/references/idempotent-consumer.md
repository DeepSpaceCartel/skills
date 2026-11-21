# Idempotent consumer

## Problem

Every broker that doesn't lose messages delivers some of them twice. A worker finishes the
work and dies before acking; a lease expires on a slow worker; an outbox relay crashes between
publish and mark; a producer retries a send that had in fact landed. A consumer that applies
each delivery as new work debits an account twice or sends two emails. The fix is in the
consumer, not the broker: make a repeat delivery have no further effect.

This reference covers the pattern and how it meets each broker's redelivery behaviour. The
pipeline view (upserts on natural keys, checkpoints, two-phase mutations, a worked example) is
in [`data-pipelines` idempotent-stages](../../data-pipelines/references/idempotent-stages.md).

## When to use / when NOT to use

- **Use** on every consumer of an at-least-once channel: RabbitMQ, Kafka outside its
  transactional Kafka-to-Kafka path, SQS, Redis Streams, NATS JetStream, webhooks, outbox relays.
- **Use** on every saga step and compensation: both may be retried
  ([sagas](sagas.md)).
- **Skip the dedupe table** when the effect is already idempotent: an absolute upsert keyed by a
  stable ID, a "set status to shipped" with a version guard. Then the write itself is the guard.
- **Don't** rely on broker deduplication alone. Kafka's idempotent producer only dedupes the
  producer's retried sends; JetStream's `Nats-Msg-Id` only within its duplicate window (default
  2 minutes). Neither covers a consumer that processed and died before acking.

## How it works

**The same-transaction rule.** Record the message ID and apply the effect in one local
transaction. Separately, they fail in both orders: mark first and a crash loses the effect;
apply first and a crash repeats it. microservices.io's example inserts the ID into a
`PROCESSED_MESSAGES` table, keyed by subscriber and message ID, after starting the handler's
transaction, and rolls back on a duplicate. The page shows this without stating the rule; the
rule is this skill's.

**The dedupe key.** A producer-assigned event ID (the CloudEvents `id`, which with `source` is
unique per event), carried unchanged through retries and relays. Never a broker delivery tag or
offset alone: those change on redelivery or differ between brokers. If the producer gives no ID,
derive one from the business identity (order ID plus event type plus version).

**Where the record lives.**

| Store | When | Cost |
|---|---|---|
| Processed-messages table in the consumer's own database | Effect is a database write | One row per message; prune past the redelivery window |
| ID or version column on the entity itself | One message updates one entity | No extra table; needs a version per entity |
| Kafka offset stored with the output | Kafka consumer writing to its own store | Commit offset and output in one transaction; Kafka's docs describe this for outside systems |
| Separate key-value store | Effect is outside any transaction (an email, an API call) | Not atomic with the effect; use the downstream's own idempotency key too |

**External side effects.** An email or a third-party API call can't join your transaction.
Send it with an idempotency key the receiver honours, or emit it from committed state through an
outbox, so the "send" is a row that commits with the dedupe record
([transactional-outbox](transactional-outbox.md)). Request-level idempotency keys are in
[`engineering-practices` reliability](../../engineering-practices/references/reliability.md).

**Ordering and versions.** Dedupe stops repeats; it doesn't stop an older message overtaking a
newer one. Carry a version or sequence per entity and apply only if it is newer
(`WHERE excluded.version > current.version`). Or key the broker by entity so one consumer sees
one entity in order ([publish-subscribe](publish-subscribe.md)).

## In code / In infrastructure

**In code:** the dedupe record, the version guard, and the transaction around both. **In
infrastructure:** how often duplicates arrive (lease length, prefetch, redelivery limits), and
how long they can keep arriving (retention, DLQ redrive).

**Agree:** keep dedupe records for longer than the longest redelivery path: broker retention,
plus DLQ retention, plus the time before someone redrives it. A redrive a week later finds the
record pruned after a day and applies the message again.

## Failure modes and what agents get wrong

- **Relative updates without dedupe.** `balance = balance - amount` per delivery
  (microservices.io's debit example). Three deliveries, three debits.
- **Dedupe and effect in separate transactions** (the example shows both outcomes).
- **Checking without inserting.** `SELECT` then `INSERT` races between two workers that got the
  same message. Let a unique key decide: `INSERT ... ON CONFLICT DO NOTHING` and check the row
  count.
- **Keying on the delivery.** RabbitMQ's delivery tag or the `redeliver` flag identify a
  delivery, not a message. A message published twice by a relay arrives with two tags.
- **Assuming FIFO.** Dedupe passes, then the older update overwrites the newer one.
- **Pruning too early,** shorter than DLQ retention plus redrive.

## Implementation notes

- **Postgres / MySQL / SQLite:** a `processed_messages (consumer, message_id)` primary key,
  `INSERT ... ON CONFLICT DO NOTHING` (MySQL: `INSERT IGNORE`, unverified) inside the handler's transaction.
- **Kafka:** commit the offset only after the effect; for a database sink, store offsets in the
  sink's transaction, or dedupe on the event ID header (Debezium's outbox router puts it in `id`).
- **RabbitMQ:** manual acks after commit; the `redeliver` flag is a hint, not a dedupe key.
- **NATS JetStream:** `Nats-Msg-Id` on publish for short-window producer dedupe; consumer dedupe
  still needed.
- **Redis Streams:** `XACK` after the effect; dedupe on the entry's own field, since a claimed
  message keeps its stream ID.
- **Managed:** queue services with deduplication windows (FIFO queues, duplicate detection) cover
  producer retries within the window only (unverified).

## Example

Three handlers for a debit message, each delivered once with a crash mid-way and then twice
more by the broker (SQLite, in memory, `isolation_level=None`):

```python
def split_tx(db, m, crash=False):                    # dedupe committed first, effect second
    if db.execute("INSERT OR IGNORE INTO processed VALUES ('debit', ?)", (m["id"],)).rowcount == 0:
        return
    if crash:
        raise Crash()                                # killed between the two writes
    db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (m["amount"], m["acct"]))

def same_tx(db, m, crash=False):                     # dedupe and effect commit together
    db.execute("BEGIN IMMEDIATE")
    try:
        if db.execute("INSERT OR IGNORE INTO processed VALUES ('debit', ?)", (m["id"],)).rowcount:
            if crash:
                raise Crash()
            db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?",
                       (m["amount"], m["acct"]))
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK"); raise
```

With `accounts(a1, 100)`, `processed(consumer, msg_id)` as the primary key and a 30 debit:
the naive handler (a bare `UPDATE`) ended at 10, three debits. `split_tx` ended at 100: the
dedupe row survived the crash and every redelivery was dropped, so the debit was lost.
`same_tx` ended at 70: the crash rolled back both, and the redelivery applied it once.

## Review checklist

1. Does every consumer of an at-least-once channel have a dedupe record or a naturally idempotent write?
2. Are the dedupe record and the effect committed in one transaction?
3. Is the key a producer-assigned event ID that survives retries, relays and redrives?
4. Does a unique constraint, not a prior `SELECT`, decide duplicates?
5. Are out-of-order messages rejected by a version or sequence guard?
6. Do external side effects carry the receiver's idempotency key or go through an outbox?
7. Are dedupe records kept longer than retention plus DLQ retention plus redrive delay?
8. Is there a test that delivers the same message twice and crashes mid-handler?

## Related

[`data-pipelines` idempotent-stages](../../data-pipelines/references/idempotent-stages.md)
(the pipeline view and a worked example), [transactional-outbox](transactional-outbox.md),
[dead-letter-queues](dead-letter-queues.md), [publish-subscribe](publish-subscribe.md),
[`cloudevents`](../../cloudevents/SKILL.md) (`id` and `source`),
[`engineering-practices` reliability](../../engineering-practices/references/reliability.md).

## Sources

microservices.io, [Idempotent Consumer](https://microservices.io/patterns/communication-style/idempotent-consumer.html)
and [Transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html)
(relay duplicates). Kafka 4.4, [Design: message delivery semantics](https://kafka.apache.org/44/design/design/).
RabbitMQ, [consumer acknowledgements](https://www.rabbitmq.com/docs/confirms). NATS,
[streams](https://docs.nats.io/nats-concepts/jetstream/streams). Debezium,
[Outbox event router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html).
Azure Architecture Center, [Publisher-Subscriber](https://learn.microsoft.com/en-us/azure/architecture/patterns/publisher-subscriber)
(delivery guarantees).
