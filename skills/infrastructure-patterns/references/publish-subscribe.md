# Publish-subscribe

## Problem

A component that tells every interested party about a change by calling each one directly has
to know them all, wait on them all and handle each one failing. Adding a consumer means
changing the producer. Pub/sub puts a broker in between: the producer publishes once to a
topic, and every subscription gets its own copy. Its hard parts are not the fan-out. They are
ordering, duplicates, retention, and what a consumer that was down for a day can still read.

## When to use / when NOT to use

- **Use** when several independent consumers need the same events (search index, analytics,
  notifications), they deploy on their own schedules, and they can be eventually consistent.
- **Use** a log-based broker (Kafka, JetStream with limits retention, Redis Streams) when a new
  or recovering consumer must replay history, not only see what arrives from now on.
- **Don't** use it for a request that needs an answer now. A broker adds latency and has no
  reply channel; use a direct call, or request-reply over a separate reply queue.
- **Don't** use it when a few consumers want very different data. Azure's pattern names this
  case: the broker adds complexity without a scaling benefit.
- **Don't** use it to make the producer's write and the publish atomic. That is the
  [transactional-outbox](transactional-outbox.md). Nor to run a multi-step business
  transaction: that is a [saga](sagas.md).
- **Not** a work queue: here every subscription sees every message; in a work queue one worker
  takes each ([work-queues-and-competing-consumers](work-queues-and-competing-consumers.md)).

## How it works

| Concept | What it means | Where agents slip |
|---|---|---|
| Topic / subject / stream | Named channel; the producer publishes there | Too broad means every subscriber filters; too narrow means hundreds of topics |
| Subscription / consumer group | One logical reader; gets every message | Two services sharing one group split the messages between them instead of both getting all |
| Partition | An ordered log inside a topic; the unit of parallelism | Order holds *within* a partition only |
| Partition key | Chooses the partition (a hash of the key) | No key, or a key unrelated to the entity, loses per-entity order |
| Offset / cursor | The reader's position; the broker or the reader stores it | Committed before the work is done, a crash loses messages |
| Retention | How long the broker keeps messages | Shorter than the longest consumer outage means silent data loss |

**Ordering.** Kafka guarantees order within a partition, and each partition is read by exactly
one consumer in a group at a time. So all events for one entity must carry the same key. Raising
the partition count re-hashes keys onto new partitions, and for a while the old and new
partitions both hold events for the same key. Plan the partition count up front (example below).

**Delivery.** Kafka's default is at-least-once: messages are not lost but may be redelivered.
Its exactly-once covers Kafka-to-Kafka only (idempotent producer, transactions, consumers on
`isolation.level=read_committed`). Writing to any outside system needs the offset stored with
the output, or an [idempotent-consumer](idempotent-consumer.md). Assume duplicates everywhere.

**Retention and replay.** A log keeps messages by time or size. Kafka's topic `retention.ms`
defaults to 7 days, and `cleanup.policy=compact` keeps the latest value per key instead, with
tombstones (null values) removing keys. A queue-style broker deletes on acknowledgement, so
there is nothing to replay. A new subscriber on Kafka starts at `auto.offset.reset`, which
defaults to `latest`. Without `earliest` it never sees the history.

## In code / In infrastructure

**In code.** Pick the partition key per event type (the aggregate or entity ID). Commit offsets
only after the effect is durable. Make handlers idempotent and tolerant of reordering across
keys. Ignore unknown fields. Carry an event ID, type, source and correlation ID, in the
[`cloudevents`](../../cloudevents/SKILL.md) envelope or an equivalent.

**In infrastructure.** Partition count, replication, retention per topic, and per-topic
authorization for producers and subscribers. Azure stresses that both sides need it: a rogue
publisher does as much damage as a rogue reader. Plus flow control: limits on unacknowledged
messages per subscriber, and consumer lag alerts per group.

**Agree:** the retention period must exceed the longest outage a consumer might have, plus the
time to notice and fix it. Partition count caps how many consumers in a group can work at once.

## Failure modes and what agents get wrong

- **Auto-commit plus slow processing.** Kafka's `enable.auto.commit` defaults to `true`. The
  offset is committed on a timer, and a crash after the commit but before the work loses those
  messages. Commit manually after the effect.
- **No key, or the wrong key.** Events for one order land on different partitions and are
  applied out of order: "cancelled" before "created".
- **Retention shorter than an outage.** A consumer down for 8 days on a 7-day topic resumes
  past the deleted data and reports nothing. Alert on consumer lag against retention.
- **One hot key.** Fifty keys over six partitions is already uneven (example). One tenant with
  most of the traffic pins one partition and one consumer while the rest sit idle.
- **Redis Streams treated as Kafka.** Persistence and replication are asynchronous by default.
  After a failover, `XADD`s can be missing, and Redis says AOF needs a strong fsync policy if
  messages matter. Redis consumer groups also balance one stream across consumers. They don't
  partition it, so order per item is lost with several consumers.
- **Core NATS for durable events.** Core NATS delivers at most once to subscribers connected at
  that moment. Only JetStream persists and redelivers.

## Implementation notes

| Need | Kafka | RabbitMQ | NATS JetStream | Redis Streams |
|---|---|---|---|---|
| Model | Partitioned log | Exchanges route to queues | Stream (log) on subjects, consumers as views | Append-only stream per key |
| Fan-out | One consumer group per subscriber | One queue per subscriber, bound to a fanout or topic exchange (unverified) | One durable consumer per subscriber | One consumer group per subscriber |
| Order | Per partition | Per queue, single consumer (unverified) | Per stream, single consumer (unverified) | Per stream, single consumer |
| Replay | Yes, by offset (by time unverified), within retention | No for classic queues (ack deletes) | Yes, from start, sequence or time | Yes, by ID range, within `MAXLEN` |
| Dedupe help | Idempotent producer | None built in (unverified) | `Nats-Msg-Id` within the duplicate window (default 2 min) | Idempotent production in 8.6+ |
| Durability | Replicated log | Quorum queues | Replicas (default 1) | Async replication; AOF fsync policy |

- **Choose Kafka** for high-volume event logs, replay and many subscribers. **RabbitMQ** for
  routing by key or header (unverified), per-message acks and DLX. **JetStream** when you already run NATS
  or want one system for streams, work queues and KV. **Redis Streams** when Redis is already
  there and losing a few messages on failover is acceptable.
- **Managed:** hosted Kafka-compatible services, cloud pub/sub topics with subscriptions, and
  managed event buses provide the same model. Check each one's ordering-key and retention limits.

## Example

Per-key order with one consumer per partition, and what adding partitions does to key placement
(standard-library Python, the CRC32 hash standing in for the client's key hash):

```python
import zlib
from collections import defaultdict

def partition(key: str, n: int) -> int:
    return zlib.crc32(key.encode()) % n

events = [(f"order-{i % 50}", seq) for seq, i in enumerate(range(1000))]  # 50 keys x 20 events

def per_key_ordered(n):
    logs = defaultdict(list)                     # one append-only log per partition
    for key, seq in events:
        logs[partition(key, n)].append((key, seq))
    seen = {}
    for log in logs.values():                    # one consumer per partition, in log order
        for key, seq in log:
            assert seq > seen.get(key, -1), "per-key order broken"
            seen[key] = seq
    return max(map(len, logs.values())), min(map(len, logs.values()))

print(per_key_ordered(6))                        # (260, 100): busiest vs quietest partition
keys = [f"customer-{i}" for i in range(10_000)]
print(sum(partition(k, 6) != partition(k, 8) for k in keys) / len(keys))   # 0.75
```

Run as shown: the order assertion held for every key. With 50 keys over 6 partitions the
busiest got 2.6x the quietest's events. Going from 6 to 8 partitions moved 75% of 10,000 keys,
so during a resize one key's events sit in two partitions. Kafka's own default hash differs from
CRC32 (unverified); the proportions are what matter.

## Review checklist

1. Does every event type have a partition key that matches the entity whose order matters?
2. Is each subscriber its own consumer group or queue, so none splits another's messages?
3. Are offsets or acks committed only after the effect is durable (auto-commit off where that matters)?
4. Is retention longer than the longest plausible consumer outage, with lag alerts per group?
5. Does a new subscriber know where it starts (`earliest` vs `latest`, or a backfill)?
6. Are handlers idempotent and safe under reordering across keys?
7. Is the partition count sized for peak consumer parallelism and a hot key?
8. Are publishers and subscribers authorized per topic?
9. Do events carry an ID, type, source and correlation ID, and evolve additively?

## Related

[work-queues-and-competing-consumers](work-queues-and-competing-consumers.md),
[transactional-outbox](transactional-outbox.md), [idempotent-consumer](idempotent-consumer.md),
[dead-letter-queues](dead-letter-queues.md), [cqrs-and-materialized-views](cqrs-and-materialized-views.md),
[`cloudevents`](../../cloudevents/SKILL.md) (the envelope), [`engineering-practices` api-evolution](../../engineering-practices/references/api-evolution.md) (additive schema changes).

## Sources

Azure Architecture Center, [Publisher-Subscriber pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/publisher-subscriber).
Apache Kafka 4.4, [Design](https://kafka.apache.org/44/design/design/) (consumer position,
delivery semantics, transactions, share groups, log compaction),
[consumer configs](https://kafka.apache.org/44/configuration/consumer-configs/) (`enable.auto.commit`,
`auto.offset.reset`) and [topic configs](https://kafka.apache.org/44/configuration/topic-configs/)
(`retention.ms`, `cleanup.policy`). NATS, [JetStream](https://docs.nats.io/nats-concepts/jetstream)
and [streams](https://docs.nats.io/nats-concepts/jetstream/streams). Redis,
[Streams](https://redis.io/docs/latest/develop/data-types/streams/) (consumer groups, differences
with Kafka partitions, persistence and replication). RabbitMQ,
[consumer acknowledgements and publisher confirms](https://www.rabbitmq.com/docs/confirms).
