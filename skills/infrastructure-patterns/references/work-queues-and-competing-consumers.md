# Work queues and competing consumers

## Problem

Work arrives faster than one worker can handle, or in bursts the downstream can't absorb. A
queue lets producers hand off and return while a pool of workers drains it at a safe rate, each
message to one worker. The hard parts: a worker dying holding a message, how long a message stays
hidden, urgent work getting ahead of bulk work, and not moving the overload one hop on.

## When to use / when NOT to use

- **Use** for independent tasks that can run asynchronously and in parallel: exports, image
  processing, page fetches, emails, webhook delivery.
- **Use** for load leveling when bursts would overwhelm a service and the caller can wait.
- **Don't** when the caller needs the result synchronously and quickly. Azure lists a
  low-latency synchronous response as the case where the pattern doesn't fit.
- **Don't** use plain competing consumers when tasks must run in sequence: use per-key order
  (sessions, message groups, partitions: Azure's Sequential Convoy).

## How it works

**Competing consumers.** Workers pull from one queue; each message goes to one of them,
at least once, so handlers must be [idempotent](idempotent-consumer.md).

**Leases (visibility timeout, ack deadline, lock).** A delivered message stays in the queue,
hidden or locked, until the worker acknowledges it. If the worker dies or the lease runs out,
the message comes back.

| Broker | Lease mechanism | Verified detail |
|---|---|---|
| SQS | Visibility timeout | Default 30 s, extend with `ChangeMessageVisibility`, at most 12 h from first receive |
| RabbitMQ | Unacked delivery on a channel | Requeued when the channel or connection closes; prefetch caps unacked per channel |
| Kafka share groups | Per-record lock | `share.record.lock.duration.ms`, default 30 s; ack, release, reject or renew |
| Redis Streams | Pending entries list | Stays with its consumer until claimed (`XCLAIM`, `XAUTOCLAIM` with a min idle time) |
| NATS JetStream | Ack within the ack wait | Redelivered if not acked in time; `MaxAckPending` default 1000 |
| Postgres table | `FOR UPDATE SKIP LOCKED` or a lease column | Postgres documents `SKIP LOCKED` for queue-like tables with many consumers |

**Lease length.** Too short, and a slow but healthy worker loses its message to a second worker:
both do the work. Too long, and a crashed worker's message waits that long to be retried. Set it
near the normal processing time and renew with a heartbeat for long tasks (SQS's own advice). A
completion from a worker that no longer holds the lease must be rejected (example).

**Load leveling.** The queue absorbs the burst; workers drain at a bounded rate. Azure warns
that autoscaling consumers without a cap on their combined rate only moves the overload to the
dependency, and that a producer rate above the consumer rate grows the queue without bound.
Watch depth and the age of the oldest message; shed or slow producers when it keeps growing.

**Priority.** One queue ordered by priority, or a queue per priority with a shared pool (high
first; low can starve) or a pool each (isolation, idle capacity). Azure suggests ageing old
messages up so low-priority work still finishes.

**Backpressure.** Prefetch or max-in-flight stops one worker hoarding messages; RabbitMQ
suggests 100–300 for throughput, 1 being the slowest. When the queue is full: reject new
messages (JetStream `discard: new`), drop the oldest (`old`, the default), or block producers.

**Claim check.** For payloads near the broker's size limit, write them to object storage and
send a reference. Publish only after the write succeeds, name who deletes the payload, keep it
longer than the message, add a content hash, and keep credentials out of the reference (Azure).

## In code / In infrastructure

**In code.** Ack after the effect is durable. Renew leases on long work from a separate thread
or task with its own budget. Reject stale completions with a holder check. Count attempts and
dead-letter past a limit ([dead-letter-queues](dead-letter-queues.md)).

**In infrastructure.** Durable queues (quorum queues, replicas), lease defaults, max receive
count and DLQ, prefetch, queues per priority or tenant, and a backlog autoscaler with a hard
maximum ([requests-limits-and-autoscaling](requests-limits-and-autoscaling.md)).

**Agree:** the autoscaler's maximum times each worker's concurrency must stay under what the
downstream can take. The lease must exceed the code's per-message timeout plus the time to ack.

## Failure modes and what agents get wrong

- **Lease shorter than the work.** Under load, processing slows, leases expire and messages are
  redelivered to more workers, which slows things further. Heartbeat, and size from p99.
- **Ack on receive.** RabbitMQ calls automatic acknowledgement unsafe for some workloads: the
  message is gone when the worker crashes mid-task.
- **Requeue loops.** A message that always fails goes back to the head and spins. RabbitMQ
  suggests tracking redeliveries and rejecting or delaying them.
- **Shared queue for bulk and live work.** A backfill of a million jobs delays every user. Use
  separate queues, or priority with dedicated workers
  ([bulkheads-and-isolation](bulkheads-and-isolation.md)).
- **Scaling on CPU.** I/O-bound workers idle at low CPU as the backlog grows; scale on depth.
- **A table queue without `SKIP LOCKED` or a lease.** Workers block on each other, or two take one row.

## Implementation notes

- **Postgres:** `SELECT ... FOR UPDATE SKIP LOCKED LIMIT n` inside the transaction that does the
  work, or a lease column for work that outlives a transaction. Fine up to moderate rates when
  the database is already there.
- **RabbitMQ:** quorum queues, manual acks, prefetch, a DLX, and a delivery limit.
- **NATS JetStream:** a work-queue retention stream: the first ack removes the message, and the
  server rejects overlapping consumers.
- **Redis Streams:** one group; `XREADGROUP`, `XACK`, `XAUTOCLAIM`; delivery count for poison.
- **Kafka:** group parallelism stops at the partition count; share groups lift that limit.
- **Managed:** cloud queues (visibility timeout, max receive count, DLQ) and managed brokers with
  sessions or message groups for per-key order.

## Example

A lease-based claim on a SQLite jobs table, with priority, attempt counting and a holder check
on completion (`sqlite3` 3.35+ for `RETURNING`):

```python
import sqlite3, uuid
db = sqlite3.connect(":memory:", isolation_level=None)
db.execute("""CREATE TABLE jobs (id INTEGER PRIMARY KEY, priority INTEGER NOT NULL, payload TEXT,
              attempts INTEGER NOT NULL DEFAULT 0, holder TEXT,
              lease_until REAL NOT NULL DEFAULT 0, done INTEGER NOT NULL DEFAULT 0)""")

def claim(now, lease=30.0, max_attempts=5):        # one atomic UPDATE: two workers can't both win
    token = uuid.uuid4().hex
    row = db.execute("""UPDATE jobs SET holder=?, lease_until=?, attempts=attempts+1
        WHERE id = (SELECT id FROM jobs WHERE done=0 AND lease_until<=? AND attempts<?
                    ORDER BY priority, id LIMIT 1) RETURNING id, attempts""",
        (token, now + lease, now, max_attempts)).fetchone()
    return (row[0], token, row[1]) if row else None

def complete(job_id, token):                       # rejected if the lease has moved on
    return db.execute("UPDATE jobs SET done=1 WHERE id=? AND holder=? AND done=0",
                      (job_id, token)).rowcount == 1

db.executemany("INSERT INTO jobs (priority, payload) VALUES (?, ?)",
               [(5, "backfill page 1"), (1, "user export"), (5, "backfill page 2")])
a = claim(now=0)     # worker A takes the priority-1 job, then stalls
b = claim(now=10)    # B, inside A's lease, gets the next job instead
c = claim(now=31)    # A's lease expired: C re-claims A's job (attempt 2)
print(complete(*a[:2]), complete(*c[:2]))          # False True
```

Run on SQLite 3.46: A got the priority-1 job, B the oldest backfill page, C re-claimed A's job
after the lease ran out (attempts = 2); A's late completion was rejected, C's accepted. Jobs at
`max_attempts` stop being claimed and belong in a dead-letter table.

## Review checklist

1. Can every handler run twice for one message without a wrong result?
2. Is the lease set from p99 processing time, renewed by a heartbeat on long tasks, and are stale completions rejected?
3. Are messages acked only after the effect is durable?
4. Is prefetch or max-in-flight bounded per worker?
5. Is the consumers' total rate capped below the downstream's limit, autoscaler maximum included?
6. Do urgent and bulk work have separate queues or pools, with a guard against starvation?
7. Are attempts counted and poison messages moved to a DLQ?
8. Are large payloads sent by claim check, and are queue depth and oldest-message age alerted on?

## Related

[publish-subscribe](publish-subscribe.md), [idempotent-consumer](idempotent-consumer.md),
[dead-letter-queues](dead-letter-queues.md), [load-shedding](load-shedding.md),
[bulkheads-and-isolation](bulkheads-and-isolation.md),
[requests-limits-and-autoscaling](requests-limits-and-autoscaling.md),
[`data-pipelines` failure-isolation](../../data-pipelines/references/failure-isolation.md) (backlog recovery),
[`data-pipelines` idempotent-stages](../../data-pipelines/references/idempotent-stages.md) (leases).

## Sources

Azure Architecture Center: [Queue-Based Load Leveling](https://learn.microsoft.com/en-us/azure/architecture/patterns/queue-based-load-leveling),
[Competing Consumers](https://learn.microsoft.com/en-us/azure/architecture/patterns/competing-consumers),
[Priority Queue](https://learn.microsoft.com/en-us/azure/architecture/patterns/priority-queue),
[Claim Check](https://learn.microsoft.com/en-us/azure/architecture/patterns/claim-check),
[Sequential Convoy](https://learn.microsoft.com/en-us/azure/architecture/patterns/sequential-convoy).
AWS, [SQS visibility timeout](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html).
RabbitMQ, [consumer acknowledgements](https://www.rabbitmq.com/docs/confirms). Kafka 4.4,
[Design: share groups](https://kafka.apache.org/44/design/design/). Redis,
[Streams](https://redis.io/docs/latest/develop/data-types/streams/). NATS,
[consumers](https://docs.nats.io/nats-concepts/jetstream/consumers),
[streams](https://docs.nats.io/nats-concepts/jetstream/streams),
[retention policies](https://docs.nats.io/learn/jetstream/retention-policies). PostgreSQL,
[SELECT: the locking clause](https://www.postgresql.org/docs/current/sql-select.html).
