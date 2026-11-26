# Design process: from requirements to a service architecture

## Problem

Service boundaries are often drawn on a whiteboard from nouns in the requirements, and then
never checked against the operations the system has to perform. The result looks clean and
behaves badly: most operations turn out to be distributed. A deliberate process works from the
operations, groups them, and evaluates every grouping against explicit forces before anything
is built.

Use it for a new system, for the target architecture of a monolith migration, and again
whenever requirements change enough to move an operation's centre of gravity.

## Steps

The process is adapted from Richardson's Assemblage, with attribution in Sources. It is
condensed here and changed in places.

1. **Write down what the system does,** as operations rather than entities. Use commands
   (`placeOrder`, `cancelOrder`) and queries (`findOrderHistory`), each with its trigger
   (request, message, schedule) and its availability and latency needs. Leave technology out.
2. **Group the rules and data those operations touch** into subdomains or bounded contexts
   ([boundaries](boundaries.md)).
3. **Order the operations by what a wrong design would cost.** Put first the ones where an
   outage loses money, where latency or volume is extreme, or where the design would be hardest
   to change later. These set the shape. The rest fit around them.
4. **Place each operation in turn.** Put its subdomains into an existing service or a new one.
   An operation whose subdomains all land in one service is local and needs nothing more. A
   distributed one gets a collaboration design ([collaboration](collaboration.md)): the APIs,
   events and handlers it needs.
5. **Argue each placement** with the questions below, for *this* operation.
6. **Step back and look at the whole,** using the smells below. Choices that were sensible one
   operation at a time can add up badly.
7. **Adjust and repeat** for the operations that are affected. The levers, cheapest first:
   - relax a requirement (accept staleness, make the operation asynchronous)
   - change the collaboration design
   - move a subdomain to another service
   - split a subdomain
   - merge two services
8. **Record** each service on a service sheet and each significant decision as an ADR.

## Questions that decide a split

Every split trades something for something else. Ask the four questions below for the operation
in front of you. Richardson frames the two sides as *dark energy* (forces that push toward more,
smaller services) and *dark matter* (forces that pull toward fewer). Fowler and Newman add the
operating cost and the security case. The grouping here is this skill's own.

| Question | Argues for splitting | Argues for keeping together |
|---|---|---|
| **Who changes it, and how often?** | Different teams, or very different change rates; one team blocked behind another's release; a build too slow for fast feedback | Most changes touch both sides; a shared model; one team owns both anyway |
| **What does it need at run time?** | Different load, availability, latency or failure isolation; one part must stay up when the other is down | Each request would wait on the other side; many round trips or large transfers per operation |
| **What does the operation need from the data?** | The parts' invariants are independent; eventual consistency is acceptable to the business | One invariant spans both; the business needs the answer to be right *now* (ACID) |
| **What does it cost to build, secure and run?** | A part needs its own stack, upgrade schedule, compliance scope or blast radius (card data, PII, admin) | Another pipeline, dashboard, on-call surface and contract test suite per service; harder end-to-end testing and debugging |

No design answers all four well. A checkout path weighs run-time needs. A back-office report
weighs build and run cost. A team bottleneck weighs who changes it.

## Smells to look for in step 6

- **Several teams in one service:** they queue behind each other. Split along their subdomains.
- **Services that most planned features would change together:** move the boundary.
- **A user-facing operation that waits on several services:** merge, replicate, or go
  asynchronous.
- **A service with no operations of its own,** only data that others interpret: an entity
  service.
- **A saga protecting one invariant** that was split across two services: put it back in one.
- **A service nobody can name a reason for:** no question in the table above argues for it.

## The service sheet

One page per service, kept with the code or the architecture docs:

```markdown
# Fulfilment service
Owner: team-fulfilment          Subdomains: inventory, shipping
Purpose: reserve and ship stock for accepted orders

## Operations it implements
- reserveStock(orderId, lines)      command, async (saga participant), p99 < 200 ms
- getAvailability(sku)              query, sync, 99.95%

## Collaborations
- Publishes: StockReserved, StockReservationFailed, ShipmentDispatched
- Subscribes: OrderAccepted (Ordering)
- Calls synchronously: none
- Keeps replicas of: none

## Data owned
stock_levels, reservations, shipments (schema `fulfilment`; no other service has grants)

## Characteristics
Scales with order volume; must stay up when Ordering is down.
```

The "Calls synchronously" line is the one to watch: it is the runtime coupling budget.

## What agents get wrong

- **Starting from nouns** (Customer, Order, Product) instead of operations. Nouns produce
  entity services.
- **Designing every operation the same way.** One collaboration style for the whole system
  ignores that operations have different needs.
- **Skipping the evaluation pass.** Locally sensible choices can add up to a chatty, fragile
  whole.
- **Treating the process as one-off.** Re-run it for the affected operations when requirements
  change.

## Review checklist

1. Is there a list of system operations, with triggers and non-functional needs?
2. Which operations are distributed, and is each one's collaboration pattern written down?
3. For each split, which of the four questions argues for it, and what was traded away?
4. Was the whole evaluated for the smells above after the per-operation pass?
5. Does each service have a sheet listing its synchronous calls, events, replicas and owned data?
6. Are the decisions recorded as ADRs?

## Related

[boundaries](boundaries.md), [collaboration](collaboration.md),
[anti-patterns](anti-patterns.md), [`adr`](../../adr/SKILL.md),
[`system-design`](../../system-design/SKILL.md) (sizing each service once it's defined).

## Sources

The steps are adapted from Richardson's Assemblage; the questions table regroups his forces
together with Fowler's and Newman's. microservices.io: [Assemblage, an architecture definition process](https://microservices.io/post/architecture/2023/02/09/assemblage-architecture-definition-process.html),
[Assemblage step 3: defining a service architecture](https://microservices.io/post/architecture/2023/10/17/assemblage-step-3-defining-a-service-architecture.html),
[Dark energy and dark matter forces](https://microservices.io/post/architecture/2023/03/26/dark-energy-dark-matter-force-descriptions.html),
[Microservices ate my application](https://microservices.io/post/architecture/2025/02/03/microservices-ate-my-application.html)
(deliberative design). Richardson also publishes a "microservice canvas"; the service sheet here
is this skill's simpler version. Eric Evans, *Domain-Driven Design*.
