# Collaboration: how a cross-service operation works

## Problem

Once data is split across services, every operation that needs data from more than one
service crosses two boundaries. A **transaction boundary**: each service commits locally, so
there is no ACID across them. A **process boundary**: each call is slow, can fail, and can time
out with an unknown result. The design question for each distributed operation is how to live
with both. Agents tend to default to "call the other service over HTTP" for everything. That is
the most fragile choice for commands and often the slowest for queries.

## First: sync or async

| | Synchronous call (HTTP, gRPC) | Asynchronous messaging (events, commands on a broker) |
|---|---|---|
| Caller waits for | The answer | Nothing; the broker accepts the message |
| When the other side is down | The operation fails or waits | The message waits in the broker |
| Good for | Queries that need fresh data; simple request/reply; low volume | Commands across services; fan-out notifications; anything that may take long |
| Costs | Runtime coupling; latency adds up; retries can duplicate | A highly available broker; eventual consistency; request/reply over messaging is awkward |
| Needs | Timeouts, retries with idempotency, circuit breakers ([`engineering-practices` reliability](../../engineering-practices/references/reliability.md)) | Atomic publish ([transactional-outbox](../../infrastructure-patterns/references/transactional-outbox.md)), [idempotent consumers](../../infrastructure-patterns/references/idempotent-consumer.md), [dead-letter queues](../../infrastructure-patterns/references/dead-letter-queues.md) |

### The arithmetic of synchronous chains

A request that waits on *n* services succeeds only if all of them do:

```
availability ≈ a1 × a2 × … × an
five services at 99.9% each  →  0.999^5 ≈ 99.5%   (about 3.6 hours a month down instead of 43 minutes)
latency      ≈ sum of the hops on the critical path (plus retries)
```

Retries raise availability at the cost of latency and duplicate work. The structural fix is
fewer synchronous hops on the critical path.

## Queries that need data from several services

| Pattern | How | Fits | Costs |
|---|---|---|---|
| **API composition** | A composer (the gateway, a BFF, or the service the client called) calls each owning service and joins the results in memory | Few services, small result sets, data that must be fresh | Runtime coupling to every provider; large joins in memory; no consistent snapshot across services |
| **CQRS view** | A query service keeps a denormalised view built from the providers' events and answers from it ([cqrs-and-materialized-views](../../infrastructure-patterns/references/cqrs-and-materialized-views.md)) | Joins, filters or sorting across services; large data; high query load; queries that must stay up when providers are down | Eventual consistency (the view lags); another store to run and rebuild; providers must publish events |

Start with composition. Move a query to a view when it filters or sorts across services, when
the join is large, or when composition makes the query's availability unacceptable.

## Commands that need data or effects in several services

| Pattern | How | Fits | Costs |
|---|---|---|---|
| **Merge** | Move the subdomains into one service so the command is a local transaction | One team owns both; the invariant is tight; no force justifies the split | A larger service |
| **Command-side replica** | The command's service keeps a read-only copy of the other service's data, fed by its events, and validates against it | The command only needs to *read* the other data (a price, a customer's status), and slight staleness is acceptable | Staleness; design-time coupling to the replicated data's shape; PII spread into another store |
| **Saga** | A sequence of local transactions with compensations, coordinated by events or an orchestrator ([sagas](../../infrastructure-patterns/references/sagas.md)) | The command must *change* data in several services and may complete asynchronously | Compensations to write; no isolation between concurrent sagas; the client learns the outcome later |
| **Synchronous call** | Call the other service inside the request, then commit locally | Rarely right for commands; tolerable for low-stakes reads where staleness isn't acceptable and the provider is very available | Runtime coupling; a timeout leaves the remote effect unknown; no atomicity with the local commit |

A replica can replace the read-only steps of a saga: if a saga's only job for one participant
is to check a value, replicate the value instead.

### Choosing for a command

1. Can the invariant live in one service? Merge or move the boundary.
2. Does the command only need to read another service's data? Replica.
3. Must it change several services? Saga: orchestrated for more than a few steps, choreographed
   for two or three.
4. A synchronous call only if staleness is unacceptable *and* the provider is on the same
   availability tier *and* the remote effect is idempotent.

## Telling the client

An asynchronous command returns before it is done. Pick one: hold the response until the saga
completes or a short deadline passes; return `202 Accepted` with a status URL to poll; or notify
(webhook, WebSocket, push). Design the states (`PENDING`, `APPROVED`, `REJECTED`) as part of the
API.

## What agents get wrong

- **A synchronous call for every cross-service need.** It recreates the monolith's coupling
  with a network in the middle.
- **Composition for a query that filters or sorts across services.** Paging and sorting a join
  in memory across services doesn't scale. Use a view.
- **A saga where one service would do.** Often the boundary is wrong.
- **A replica treated as the source of truth.** It's a cache with a lag. The owner still
  decides.
- **Dual writes** (update the database, then publish) without an outbox.
- **Ignoring the unknown outcome of a timed-out call.** The remote side may have done it.

## Example

`getOrderDetails` shows the order, its payment status, its shipment tracking and the customer's
name: four services.

- *Composition:* the Order BFF calls Ordering, then in parallel Payments, Fulfilment and
  Customers, and merges. Simple. The page is up only when all four are, and p99 is the slowest
  of the three parallel calls plus Ordering.
- *View:* an `order_details` view updated from `OrderPlaced`, `PaymentCaptured`,
  `ShipmentDispatched` and `CustomerRenamed` events. One read, stays up when providers are down,
  lags by seconds.

Recommendation: composition with graceful degradation (show the order even if tracking times
out) for the detail page. Use the view for `searchOrders`, which filters by payment status and
date across all customers.

## Review checklist

1. Is each distributed operation marked command or query, sync or async?
2. How many synchronous hops sit on each critical user journey, and what availability does that
   multiply out to?
3. Does each composed query degrade gracefully when one provider fails?
4. Would any composed query be better as a view (cross-service filtering, sorting, large joins)?
5. For each cross-service command: could it be merged, served by a replica, or must it be a
   saga?
6. Is every message published atomically with its state change, and consumed idempotently?
7. How does the client learn the outcome of each asynchronous command?

## Related

[`infrastructure-patterns`](../../infrastructure-patterns/SKILL.md) (sagas, outbox, idempotent
consumer, CQRS, pub/sub, circuit breaking), [boundaries](boundaries.md),
[data-ownership](data-ownership.md), [edge-and-identity](edge-and-identity.md) (composition at
the gateway), [`cloudevents`](../../cloudevents/SKILL.md) (event envelopes).

## Sources

microservices.io: [Service collaboration patterns](https://microservices.io/post/patterns/2023/07/29/service-collaboration-patterns.html),
[API composition](https://microservices.io/patterns/data/api-composition.html),
[CQRS](https://microservices.io/patterns/data/cqrs.html),
[Command-side replica](https://microservices.io/patterns/data/command-side-replica.html),
[Saga](https://microservices.io/patterns/data/saga.html),
[Remote procedure invocation](https://microservices.io/patterns/communication-style/rpi.html),
[Messaging](https://microservices.io/patterns/communication-style/messaging.html),
[Domain event](https://microservices.io/patterns/data/domain-event.html). Martin Fowler,
[Microservice Trade-Offs](https://martinfowler.com/articles/microservice-trade-offs.html)
(distribution, eventual consistency). The choosing procedure and availability example are this
skill's own.
