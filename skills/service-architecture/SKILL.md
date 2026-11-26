---
name: service-architecture
description: Choosing and evolving a service architecture - project-agnostic. Covers monolith vs modular monolith vs microservices and the wrong reasons to split; drawing boundaries by subdomain, bounded context, business capability and team ownership; the forces that push toward more services or fewer; a repeatable design process from system operations to services; per-operation collaboration (sync call or messaging, API composition or CQRS for queries, saga, replica or merge for commands); database per service vs a shared database; API gateway, backends for frontends and identity propagation; strangler migration and anti-corruption layers; and distributed-monolith smells (lockstep changes, chatty calls, shared schemas). Use when deciding whether to split or merge services, where a boundary goes, how a cross-service operation should work, or why services keep changing together. Not for saga or outbox mechanics (see infrastructure-patterns), sizing (see system-design), or launch reviews (see architecture-review).
---

# Service Architecture

How to decide how many deployable components a system has, what each one owns, and how they
work together on operations that cross them. The output is a *service architecture*: the
services, the subdomains and data each owns, their APIs, and the collaboration chosen for every
operation that spans more than one. One service (a monolith) is a valid answer.

The mechanics that make a chosen design work (saga coordination, outbox publishing, idempotent
consumers, read models, circuit breaking) live in
[`infrastructure-patterns`](../infrastructure-patterns/SKILL.md). This skill decides *whether*
and *where* to use them, and links there instead of repeating them.

## How to use this skill

1. Start from the **decision** you face or the **symptom** you see, in the tables below, and
   read the one or two matching references.
2. Decide per operation, not per system. "Do we use sagas?" has no answer; "how does
   `placeOrder` stay consistent when credit lives elsewhere?" does.
3. Write down the force that justifies each split or merge (see
   [design-process](references/design-process.md)). A boundary with no stated reason is a
   guess.
4. Record the outcome as an ADR ([`adr`](../adr/SKILL.md)): what was split, what was kept
   together, and which collaboration each cross-service operation uses.

## Decision to reference

| Decision | Read |
|---|---|
| Monolith, modular monolith or microservices? Should this new system start as services? | [style-choice](references/style-choice.md) |
| Where does the boundary between two areas go? Is this service too big or too small? | [boundaries](references/boundaries.md) |
| Designing a service architecture from requirements, or re-checking one after requirements change | [design-process](references/design-process.md) |
| How should an operation that touches several services work: sync or async, compose or replicate, saga or merge? | [collaboration](references/collaboration.md) |
| Who owns which tables? May two services share a database? | [data-ownership](references/data-ownership.md) |
| Do clients need a gateway, a BFF per client, or neither? How does the caller's identity reach inner services? | [edge-and-identity](references/edge-and-identity.md) |
| How do we move off a monolith or legacy system without a rewrite? | [migration](references/migration.md) |
| Why is the split slower, flakier or harder to change than the monolith was? | [anti-patterns](references/anti-patterns.md) |
| What does every new service need on day one: chassis, template, configuration? | [service-foundations](references/service-foundations.md) |

## Symptom to reference

| Symptom | Look at |
|---|---|
| "Let's use microservices" with no named problem they solve | [style-choice](references/style-choice.md) (wrong reasons) |
| One feature needs changes in three services, released in order | [anti-patterns](references/anti-patterns.md) (lockstep changes), [boundaries](references/boundaries.md) |
| Two teams share one service and queue behind each other's releases | [boundaries](references/boundaries.md) (team ownership) |
| A service per table or per noun: `CustomerService`, `OrderService`, `ProductService`, all CRUD | [boundaries](references/boundaries.md) (entity services) |
| One request fans out into a chain of five synchronous calls; one slow service slows everything | [collaboration](references/collaboration.md) (availability arithmetic), [anti-patterns](references/anti-patterns.md) |
| A page or report joins data from several services and is slow or times out | [collaboration](references/collaboration.md) (API composition vs CQRS) |
| A command needs another service's data and fails when that service is down | [collaboration](references/collaboration.md) (replica, merge) |
| Services read or write each other's tables | [data-ownership](references/data-ownership.md) |
| A schema change in one service breaks another | [data-ownership](references/data-ownership.md), [anti-patterns](references/anti-patterns.md) |
| The mobile app makes thirty calls per screen; the web and mobile teams fight over one API | [edge-and-identity](references/edge-and-identity.md) |
| Inner services trust a `user_id` header anyone could set | [edge-and-identity](references/edge-and-identity.md) |
| A rewrite has run for a year and nothing is in production | [migration](references/migration.md) |
| The new service's model is full of the legacy system's names and quirks | [migration](references/migration.md) (anti-corruption layer) |
| A shared "common" library forces every service to redeploy | [anti-patterns](references/anti-patterns.md), [service-foundations](references/service-foundations.md) |
| Each service logs, configures and checks health differently | [service-foundations](references/service-foundations.md) |

## Working rules

1. **Default to one well-modularised deployable** until a specific force justifies a split:
   teams blocked by each other, parts that need different scaling, availability or security,
   a different technology, or a build that is too slow. "It's modern" is not a force.
2. **Boundaries follow the business, then the team.** Cut where the language and the rules
   change (subdomain, bounded context), and give each service exactly one owning team. Never
   cut by technical layer.
3. **Each service owns its data.** No other service writes its tables; reads go through its
   API, its events, or a replica it publishes. A shared database is a stage of a migration, not
   a destination.
4. **Choose collaboration per operation.** Local operations need no pattern. For each
   distributed one, pick sync or async, and for queries composition or a view, for commands a
   saga, a replica, or moving the boundary.
5. **Count the synchronous hops.** A request that waits on *n* services is up only when all of
   them are; availability multiplies and latencies add. Fewer hops beat faster hops.
6. **Measure coupling, don't assume it.** Services that change together in the same commits or
   releases are one service with a network in the middle. Check git history before and after a
   split.
7. **Change the architecture in small, reversible steps.** Extract one capability at a time
   behind a routing seam; no big-bang rewrite.

## Worked example: one operation, three designs

`placeOrder` must check the customer's credit limit, owned by a Customer area, before accepting
an order, owned by an Order area.

| Design | How | Pays | Costs |
|---|---|---|---|
| **One service** (Order and Customer in one deployable, separate modules) | A local ACID transaction checks credit and inserts the order | Simple, consistent, fast | One team or a shared release; one stack |
| **Sync call** | Order calls `Customer.reserveCredit` over HTTP, then commits | Familiar request/response | `placeOrder` fails whenever Customer is down; two hops of latency; a timeout leaves the reservation unknown |
| **Saga** | Order commits `PENDING`, Customer reserves credit on the event, Order approves or rejects on the reply ([sagas](../infrastructure-patterns/references/sagas.md)) | Order accepts work while Customer is down; teams deploy independently | Eventual consistency; compensations; the client polls for the outcome |

Before choosing, ask which force is real here. If one team owns both areas and neither needs a
different scaling or stack, the first row wins and the boundary is a module boundary. If the
teams are separate and checkout must stay up while the customer area is down, the saga wins. A
sync call is the default people reach for, and it is usually the worst of the three for a
command: it adds the network without removing the coupling.

## Where to look

| Reference | Covers |
|---|---|
| [style-choice](references/style-choice.md) | Monolith, modular monolith, microservices; prerequisites; the microservice premium; wrong reasons |
| [boundaries](references/boundaries.md) | Subdomains and bounded contexts, business capabilities, team ownership and cognitive load, Conway's law, sizing, self-contained services |
| [design-process](references/design-process.md) | From system operations to services; the questions that decide a split; the service sheet; re-evaluating |
| [collaboration](references/collaboration.md) | Sync vs async; queries (API composition, CQRS view); commands (saga, command-side replica, merge); availability and latency arithmetic |
| [data-ownership](references/data-ownership.md) | Database per service, isolation levels, grants, shared database, reporting |
| [edge-and-identity](references/edge-and-identity.md) | API gateway, backends for frontends, partial responses, access tokens, discovery, UI composition |
| [migration](references/migration.md) | Strangler fig at service scale, anti-corruption layer, extracting code and data, branch by abstraction |
| [anti-patterns](references/anti-patterns.md) | Distributed monolith, lockstep releases, entity services, chatty chains, shared libraries, measuring coupling |
| [service-foundations](references/service-foundations.md) | Chassis vs template, externalized configuration, the cross-cutting baseline every service needs |

## Related

- [`infrastructure-patterns`](../infrastructure-patterns/SKILL.md) — sagas, transactional outbox, idempotent consumer, CQRS and materialized views, event sourcing, pub/sub, circuit breaking.
- [`core-principles`](../core-principles/SKILL.md) — cohesion, coupling and information hiding, the same ideas one level down.
- [`system-design`](../system-design/SKILL.md) — sizing the services once the boundaries are drawn.
- [`architecture-review`](../architecture-review/SKILL.md) — reviewing a whole design or a launch.
- [`engineering-practices`](../engineering-practices/SKILL.md) — contract tests, refactoring, API evolution, database migrations.
- [`adr`](../adr/SKILL.md) — recording each boundary and collaboration decision.

## Sources

Chris Richardson, [microservices.io](https://microservices.io/patterns/) (pattern catalog; the
decomposition forces he calls dark energy and dark matter; the Assemblage process; service
collaboration patterns; self-contained service). Martin Fowler,
[Monolith First](https://martinfowler.com/bliki/MonolithFirst.html),
[Microservice Trade-Offs](https://martinfowler.com/articles/microservice-trade-offs.html),
[Bounded Context](https://martinfowler.com/bliki/BoundedContext.html). Sam Newman,
[Backends For Frontends](https://samnewman.io/patterns/architectural/bff/) and *Building
Microservices* (2nd ed.). Eric Evans, *Domain-Driven Design*. Matthew Skelton and Manuel Pais,
*Team Topologies*. The rules and tables above are this skill's own synthesis.
