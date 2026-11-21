# Dead-letter queues

## Problem

Some messages never succeed: malformed payloads, a field the parser can't read, a reference to
a row that was deleted, a bug that only this input triggers. Retried forever, a poison message
burns workers, blocks an ordered partition or session, and hides the real backlog. Dropped, it
is data loss nobody sees. A dead-letter queue (DLQ) parks it after a bounded number of attempts,
with enough context to fix the cause and replay it.

This reference covers broker-level DLQs, retry topics and redrive tooling. The pipeline view
(attempt counting per record, quarantine, redrive into the normal path) is in
[`data-pipelines` failure-isolation](../../data-pipelines/references/failure-isolation.md).

## When to use / when NOT to use

- **Use** on every queue or subscription whose consumer can fail on a specific message.
- **Use** retry queues or topics with delays when failures are often transient (a dependency
  down) and immediate redelivery would hammer it.
- **Don't** dead-letter on the first failure. A single timeout is not poison. SQS warns that a
  `maxReceiveCount` of 1 sends a message to the DLQ after one failed receive.
- **Don't** put a DLQ behind a strictly ordered stream unless skipping a message is acceptable.
  SQS says not to use one with FIFO queues where the exact order of operations matters, and an
  ordered session blocks behind its poison message until it is moved (Azure, Sequential Convoy).
- **Not** a substitute for an alert: an unwatched DLQ is a slower way to drop data.

## How it works

**What sends a message there.**

| Broker | Trigger | Configured by |
|---|---|---|
| RabbitMQ | Rejected or nacked with `requeue=false`; per-message TTL expired; queue length limit; quorum-queue delivery limit exceeded | A dead-letter exchange (DLX), set by policy (recommended) or `x-dead-letter-exchange` queue argument |
| SQS | Received more than `maxReceiveCount` times without being deleted | Redrive policy on the source queue; redrive allow policy on the DLQ |
| Kafka Connect | A record fails with `errors.tolerance=all` (which failures count: unverified) | `errors.deadletterqueue.topic.name`; default is none (fail on first error) |
| Kafka clients | Nothing built in; the application publishes to a dead-letter topic | Convention, often `<topic>.DLT` or `<topic>-dlq` (unverified) |
| Redis Streams | Nothing built in; the delivery counter from `XPENDING` | The application moves entries past a limit to another stream (Redis docs describe this) |
| NATS JetStream | Max deliveries reached (unverified) | Consumer `MaxDeliver` plus an advisory (unverified) |

**What to keep with it.** The original payload and headers, the source queue or topic and
offset, the attempt count, the last error, the stage, the code version, and the time it was
parked. RabbitMQ adds an `x-death` header: per queue and reason, a count, time, exchange and
routing keys, plus `x-first-death-*` and `x-last-death-*` headers.

**Retry before dead-letter.** A ladder of delays (immediate, 1 min, 10 min) separates
transient failures from poison. With RabbitMQ, a TTL on a retry queue that dead-letters back to
the work exchange was the classic trick; RabbitMQ now recommends quorum queues' native delayed
retry instead, and keeps dead-lettering for messages that can't be processed. With Kafka (unverified), retry
topics per delay level keep the main partition moving, at the cost of per-key order.

**Redrive.** After the fix ships: replay a small sample, watch it pass, then replay the rest at
a throttled rate, into the normal path, with the original message IDs so
[idempotent consumers](idempotent-consumer.md) skip anything already applied. SQS has a built-in
redrive back to the source queue.

## In code / In infrastructure

**In code.** Classify errors: permanent (validation, parse) goes to the DLQ at once; transient
(timeout, 503) retries with backoff. Count attempts before processing, so a crash that kills the
worker still counts. Never swallow an error and ack.

**In infrastructure.** DLQ per source queue or subscription, its retention, an owner, alarms,
and a redrive tool with a rate limit.

**Agree:** the broker's delivery limit and the code's retry loop multiply: 5 in-process retries
times 5 deliveries is 25 attempts against a struggling dependency. Pick one retrying layer, as in
[timeouts-and-retries-infra](timeouts-and-retries-infra.md).

## Failure modes and what agents get wrong

- **Retention shorter than the fix.** SQS keeps a standard-queue message's original enqueue time
  in the DLQ, so a 4-day DLQ deletes a message that already spent 1 day in the source after 3
  more. SQS advises DLQ retention longer than the source's. (FIFO queues reset it.)
- **The DLX doesn't exist.** RabbitMQ silently drops messages dead-lettered to a missing
  exchange.
- **Classic-queue dead-lettering is at-most-once.** RabbitMQ republishes without confirms and
  can lose the message if the target can't take it. Quorum queues support at-least-once dead-lettering (whether it is on by default: unverified).
- **Queue arguments, not a policy** (RabbitMQ): changing them means deleting the queue.
- **Alerting on depth only.** One arrival is the signal; alert on arrivals and oldest age.
- **Redrive at full speed, before the fix, or with new IDs** (so dedupe can't catch repeats).
- **Dead-lettering on the consumer side but acking first,** so the original is gone if the DLQ
  publish fails.

## Implementation notes

- **RabbitMQ:** a policy setting `dead-letter-exchange` (and optionally
  `dead-letter-routing-key`) on the work queues; quorum queues, which support at-least-once
  dead-lettering (check how it is enabled), and a `delivery-limit`.
- **Kafka:** an application-owned dead-letter topic per source topic, keyed like the source,
  with headers for error, attempts and origin offset; Connect's `errors.*` settings for
  connectors.
- **Redis Streams:** `XPENDING` delivery counts, `XCLAIM` or `XAUTOCLAIM` to take the entry,
  `XADD` to a dead-letter stream, `XACK` the original. Redis 8.8's `XNACK FATAL` marks a message
  permanently failed.
- **Postgres / SQLite:** a `dead_letters` table, as in the example.
- **Managed:** cloud queues with redrive policies and DLQ redrive; managed brokers with
  dead-letter subqueues per subscription.

## Example

A table queue that counts attempts before processing, backs off, parks poison messages with
their context, and redrives with the same IDs (SQLite; driver loop omitted):

```python
def deliver(handler, now):
    row = db.execute("SELECT msg_id, body, attempts FROM queue WHERE not_before <= ? "
                     "ORDER BY not_before LIMIT 1", (now,)).fetchone()
    if not row:
        return None
    msg_id, body, attempts = row
    db.execute("UPDATE queue SET attempts = attempts + 1 WHERE msg_id = ?", (msg_id,))  # count first
    try:
        handler(json.loads(body))
        db.execute("DELETE FROM queue WHERE msg_id = ?", (msg_id,)); return "ok"
    except Exception as e:
        if attempts + 1 >= MAX_ATTEMPTS:                     # park it with its context
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO dead_letters VALUES (?, ?, ?, ?, 'parse', ?, ?, NULL)",
                       (msg_id, body, attempts + 1, repr(e), VERSION, now))
            db.execute("DELETE FROM queue WHERE msg_id = ?", (msg_id,))
            db.execute("COMMIT"); return "dead"
        db.execute("UPDATE queue SET not_before = ? WHERE msg_id = ?", (now + 2 ** attempts, msg_id))
        return "retry"

def redrive(limit):                                          # same IDs, attempts reset, throttled
    rows = db.execute("SELECT msg_id, body FROM dead_letters WHERE redriven_at IS NULL "
                      "ORDER BY dead_at LIMIT ?", (limit,)).fetchall()
    db.execute("BEGIN IMMEDIATE")
    for msg_id, body in rows:
        db.execute("INSERT INTO queue (msg_id, body) VALUES (?, ?)", (msg_id, body))
        db.execute("UPDATE dead_letters SET redriven_at = julianday('now') WHERE msg_id = ?",
                   (msg_id,))
    db.execute("COMMIT"); return len(rows)
```

Three messages through a parser that does `int(price)`, with `MAX_ATTEMPTS = 4`: `"12"` and `"7"`
succeeded; `"12.50"` retried at 1, 2 and 4 ticks and was parked with 4 attempts, stage `parse`
and version `parser-1.7.0`. After the fix (`float(price)`), `redrive(limit=10)` moved 1 message
back and it succeeded.

## Review checklist

1. Does every queue or subscription have a DLQ, with an owner and a runbook?
2. Is the delivery limit high enough for transient failures, with backoff between attempts?
3. Are permanent errors dead-lettered at once and transient ones retried?
4. Does each parked message keep payload, origin, attempts, last error, stage and code version?
5. Is DLQ retention longer than the source's, and long enough to ship a fix?
6. Do alerts fire on any arrival and on oldest-message age, not only depth?
7. Is redrive sampled, throttled, into the normal path, with the original IDs?
8. Is exactly one layer retrying (code or broker), with the product of the two bounded?
9. On RabbitMQ: a policy rather than arguments, an existing DLX, quorum queues with at-least-once dead-lettering confirmed on where loss matters?

## Related

[`data-pipelines` failure-isolation](../../data-pipelines/references/failure-isolation.md)
(poison records, quarantine, redrive), [idempotent-consumer](idempotent-consumer.md),
[work-queues-and-competing-consumers](work-queues-and-competing-consumers.md),
[timeouts-and-retries-infra](timeouts-and-retries-infra.md).

## Sources

RabbitMQ, [Dead letter exchanges](https://www.rabbitmq.com/docs/dlx) and
[consumer acknowledgements](https://www.rabbitmq.com/docs/confirms). AWS,
[SQS dead-letter queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html).
Apache Kafka 4.4, [Kafka Connect user guide](https://kafka.apache.org/44/kafka-connect/user-guide/)
(error reporting and the dead letter queue topic). Redis,
[Streams](https://redis.io/docs/latest/develop/data-types/streams/) (delivery counter, dead
letters, `XNACK`). Azure Architecture Center,
[Competing Consumers](https://learn.microsoft.com/en-us/azure/architecture/patterns/competing-consumers)
and [Sequential Convoy](https://learn.microsoft.com/en-us/azure/architecture/patterns/sequential-convoy).
