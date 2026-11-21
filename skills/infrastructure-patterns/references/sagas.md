# Sagas

## Problem

A business operation spans services that each own their database: place the order, reserve
credit, charge the card, book shipping. There is no transaction across them, and two-phase
commit is ruled out. A saga runs the operation as a sequence of local transactions, each
committing in one service and triggering the next. If a later step fails, earlier steps are
undone by compensating transactions that someone had to write. Agents tend to treat it as a
distributed rollback. It is not one. Each step is visible as soon as it commits, compensations
can fail, and concurrent sagas can see each other's half-finished work.

## When to use / when NOT to use

- **Use** when a multi-service operation must end consistent, every step has a business undo
  (cancel, refund, release), and temporary inconsistency is acceptable.
- **Use** for long-running workflows (minutes to days) where holding locks is impossible.
- **Don't** when the data can live in one database. A local transaction beats any saga; it may
  mean the service boundary is in the wrong place.
- **Don't** when the system can't tolerate visible intermediate states, or compensation can't
  restore a valid state (Azure's Compensating Transaction pattern).
- **Don't** add compensation when retries alone would do: if most failures are transient and
  steps are idempotent, a retried forward path is simpler (also Azure).

## How it works

**Step kinds.** Order the saga around its point of no return:

| Before the pivot | The pivot | After the pivot |
|---|---|---|
| Steps that can be undone; each has a compensation | The step that commits the business outcome (often the payment) | Steps that must eventually succeed, retried until they do; idempotent |
| A failure here triggers compensation of what ran | Success means the saga only goes forward | A failure here means retry, alert, or human follow-up, not undo |

Put irreversible side effects (an email, a shipment, a legal commitment) after the pivot, once
validations have passed.

**Coordination.**

| | Orchestration | Choreography |
|---|---|---|
| Who decides the next step | A saga orchestrator sends commands and reads replies | Each service reacts to the previous service's events |
| Saga state | One place, the orchestrator's log | Spread across participants |
| Fits | Many steps, branching, changes over time | Two or three steps, stable flow |
| Risks | The orchestrator is a critical component to run and scale | Hard to see the whole flow; cyclic event dependencies; hard to test end to end |

Both need each step's database update and outgoing message to be atomic: a
[transactional-outbox](transactional-outbox.md) or [event-sourcing](event-sourcing.md)
(microservices.io). Both need at-least-once messaging with durable subscriptions, so steps and
compensations must be [idempotent](idempotent-consumer.md).

**Compensations.** A compensation is a new business action, not a restore. It doesn't put the
data back as it was, because other work may have changed it since; a refund may be partial. It
doesn't have to run in reverse order, and some can run in parallel. It can fail, so record
progress durably and resume. When it can't succeed automatically, alert a person with the
context (Azure).

**Isolation: the missing I.** Each local commit is visible at once, so concurrent sagas can
lose each other's updates, read data another saga is about to compensate, or read different
values in two steps. microservices.io says countermeasures are needed and defers the details
to its book; the Azure Saga page names them. Grouped by what they do:

| Approach | Countermeasure | In practice |
|---|---|---|
| Flag the conflict | Semantic lock: a state marks the record as in-flight | Order `PENDING` until `APPROVED` or `REJECTED`; others wait or fail |
| Remove the conflict | Commutative updates | Credit holds as rows, not a read-modify-write balance |
| Remove the conflict | Pessimistic view: put risky updates in the retryable steps | Mark stock sold only after payment |
| Detect the conflict | Reread value: check it didn't change; restart if it did | A version check on the record |
| Detect the conflict | Version file: log operations per record, apply in order | Spots a cancel that arrives before its create |
| Choose per risk | Risk-based choice: pick the mechanism by business value | Large transfers take a stronger path |

## In code / In infrastructure

**In code.** The saga's steps, compensations, pivot and states, a durable saga log keyed by saga
ID, idempotent handlers, semantic-lock states on the records, and a status the client can poll or
be notified about (microservices.io lists waiting, polling and a push notification).

**In infrastructure.** The broker with durable subscriptions, a DLQ for steps that exhaust
retries ([dead-letter-queues](dead-letter-queues.md)), timeouts that turn a stuck step into a
failure (Azure: a step may block rather than fail), and tracing by saga ID across services.

**Agree:** a step's timeout must exceed the participant's worst processing time plus queueing,
or the orchestrator compensates a step that is about to succeed. Make the participant reject
work for a saga that was already compensated.

## Failure modes and what agents get wrong

- **"It rolls back."** Other users saw the intermediate state, and the compensation is a
  separate, visible business action.
- **Irreversible steps before the pivot.** The confirmation email went out; the payment then
  failed.
- **Non-idempotent compensations.** Redelivered, `release_credit` gives the credit back twice.
- **No saga log.** The orchestrator restarts and no longer knows which steps ran.
- **No semantic lock.** A second saga spends credit that the first is about to release.
- **Choreography that grew to eight services.** Nobody can say which events a step reacts to.
- **No timeout on a step.** The saga hangs in `PENDING` forever, holding its semantic lock.

## Implementation notes

- **Postgres / SQLite:** the saga log and semantic-lock states as tables in the orchestrator's
  and participants' own databases; an outbox per service for step messages.
- **Kafka / RabbitMQ / NATS JetStream:** commands and replies (orchestration) or domain events
  (choreography); key messages by saga ID or aggregate ID to keep one saga's messages ordered.
- **Managed:** workflow engines and cloud state-machine services play the orchestrator, with
  durable state, timers and retries; managed brokers carry the messages.

## Example

An orchestrated order saga with a durable log in SQLite: `reserve_credit` (compensable,
compensated by `release_credit`), `charge_card` (pivot), `schedule_shipping` (retryable). The
order sits in `PENDING`, the semantic lock, until the saga ends:

```python
def run(o):
    db.execute("INSERT OR IGNORE INTO orders VALUES (?, 'PENDING')", (o["id"],))
    done = {s for (s,) in db.execute(
        "SELECT step FROM saga_log WHERE order_id=? AND status='done'", (o["id"],))}
    for i, (name, action, _) in enumerate(STEPS):
        if name in done:
            continue                                  # resume: skip finished steps
        try:
            db.execute("BEGIN IMMEDIATE"); action(o)
            db.execute("INSERT OR REPLACE INTO saga_log VALUES (?, ?, 'done')", (o["id"], name))
            db.execute("COMMIT")
        except ValueError as e:
            db.execute("ROLLBACK")
            for prev, _, undo in reversed(STEPS[:i]):  # compensate what already committed
                if undo:
                    db.execute("BEGIN IMMEDIATE"); undo(o)
                    db.execute("INSERT OR REPLACE INTO saga_log VALUES (?, ?, 'compensated')",
                               (o["id"], prev))
                    db.execute("COMMIT")
            db.execute("UPDATE orders SET state='REJECTED' WHERE id=?", (o["id"],))
            return f"REJECTED ({e})"
    db.execute("UPDATE orders SET state='APPROVED' WHERE id=?", (o["id"],))
    return "APPROVED"
```

With 100 of credit: order o1 for 60 was `APPROVED`; o2 for 30 with a declined card was
`REJECTED` and its credit hold released; o3 for 50 was `REJECTED` for insufficient credit (40
left, so the release had worked). Re-running o1 skipped every logged step and left credit at 40.
`release_credit` deletes the hold with `RETURNING` and adds back only what it deleted, so it is
safe to run twice.

## Review checklist

1. Could this operation be one local transaction if the data moved?
2. Is every step classified as compensable, pivot or retryable, with irreversible effects after the pivot?
3. Does every compensable step have a written, idempotent compensation?
4. Is saga progress logged durably so a restart resumes rather than repeats?
5. Is each step's database update and message atomic (outbox or event sourcing)?
6. Which isolation anomalies can occur, and which countermeasure covers each (semantic lock first)?
7. Does every step have a timeout, and does a stuck saga alert someone?
8. Can the client see the saga's outcome (status endpoint or notification)?
9. Is orchestration used once the flow has more than a few steps?

## Related

[transactional-outbox](transactional-outbox.md), [idempotent-consumer](idempotent-consumer.md),
[dead-letter-queues](dead-letter-queues.md), [event-sourcing](event-sourcing.md),
[`data-pipelines` idempotent-stages](../../data-pipelines/references/idempotent-stages.md)
(compensation is not rollback),
[`engineering-practices` reliability](../../engineering-practices/references/reliability.md).

## Sources

microservices.io, [Saga](https://microservices.io/patterns/data/saga.html) and
[Managing data consistency using Sagas, part 2](https://microservices.io/post/sagas/2019/08/04/developing-sagas-part-2.html)
(coordination, at-least-once messaging, atomic update and send). Azure Architecture Center,
[Saga](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga) (step kinds,
anomalies, countermeasures) and [Compensating Transaction](https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction).
