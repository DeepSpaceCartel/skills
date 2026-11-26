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

1. **List the system operations.** From user stories, scenarios and non-functional
   requirements, write each operation the system must perform, technology-free: commands
   (`placeOrder`, `cancelOrder`) and queries (`findOrderHistory`). Note what triggers each (a
   request, a message, a schedule) and its availability and latency needs.
2. **Find the subdomains.** Group the data and rules the operations act on into subdomains or
   bounded contexts (see [boundaries](boundaries.md)). Each is something a small team could own.
3. **Rank the operations.** Most important first: business-critical, technically risky (high
   throughput, tight latency, large data, complex rules), or where the business needs to
   experiment fast. The top of the list shapes the architecture; the tail fits around it.
4. **Assign, operation by operation.** Walk the ranked list. For each operation, put its
   unassigned subdomains into an existing or a new service. If all its subdomains end up in one
   service, the operation is **local** and needs no collaboration pattern. If not, it is
   **distributed**: choose how it works ([collaboration](collaboration.md)) and add the APIs,
   events and handlers it needs.
5. **Weigh each choice** against the two groups of forces below. Prefer the candidate that
   satisfies the forces that matter for *this* operation.
6. **Evaluate the whole.** Choices made one operation at a time can add up badly. Look for the
   smells below.
7. **Refactor** at the right level: change an operation's collaboration pattern, move a
   subdomain to another service, split a subdomain, or relax an operation's requirement (accept
   eventual consistency, make it asynchronous). Repeat from step 4 for affected operations.
8. **Record** each service on a service sheet and each significant decision as an ADR.

## Forces

Two groups pull in opposite directions. Richardson calls them *dark energy* (pushes toward
more, smaller services) and *dark matter* (pulls toward fewer). The framing is his; the
wording here is this skill's.

| Reasons to split | Reasons to keep together |
|---|---|
| Each part is simpler to understand on its own | The operation stays a local call instead of a distributed interaction |
| Teams can develop, test and deploy without each other | Fewer round trips and less data moved per operation |
| Each pipeline stays fast | One ACID transaction instead of a saga and eventual consistency |
| A part needs its own technology or upgrade schedule | The operation doesn't depend at run time on other services being up |
| A part needs different scaling, availability or security | Changes don't ripple across services that must release in step |

No grouping satisfies all ten. The design question is which ones matter for each operation:
a checkout path weighs availability and latency, a back-office report weighs simplicity, a
team bottleneck weighs autonomy.

## Smells to look for in step 6

- **A service shared by many teams:** autonomy lost; split along team subdomains.
- **Services that would change together** for most planned features: design-time coupling;
  move the boundary.
- **An operation spanning many services**, especially synchronously: low availability, high
  latency; merge, replicate, or go asynchronous.
- **A service with no operations of its own,** only data others read: an entity service.
- **A saga where a local transaction would do,** because two subdomains with one invariant were
  split.

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
3. For each split, which reason to split justifies it, and which reasons to keep together were
   traded away?
4. Was the whole evaluated for the smells above after the per-operation pass?
5. Does each service have a sheet listing its synchronous calls, events, replicas and owned data?
6. Are the decisions recorded as ADRs?

## Related

[boundaries](boundaries.md), [collaboration](collaboration.md),
[anti-patterns](anti-patterns.md), [`adr`](../../adr/SKILL.md),
[`system-design`](../../system-design/SKILL.md) (sizing each service once it's defined).

## Sources

microservices.io: [Assemblage, an architecture definition process](https://microservices.io/post/architecture/2023/02/09/assemblage-architecture-definition-process.html),
[Assemblage step 3: defining a service architecture](https://microservices.io/post/architecture/2023/10/17/assemblage-step-3-defining-a-service-architecture.html),
[Dark energy and dark matter forces](https://microservices.io/post/architecture/2023/03/26/dark-energy-dark-matter-force-descriptions.html),
[Microservices ate my application](https://microservices.io/post/architecture/2025/02/03/microservices-ate-my-application.html)
(deliberative design). Richardson also publishes a "microservice canvas"; the service sheet here
is this skill's simpler version. Eric Evans, *Domain-Driven Design*.
