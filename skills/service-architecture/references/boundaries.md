# Boundaries

## Problem

A boundary decides what changes together, who owns it and what crosses the network. Get it
right and most changes stay inside one service and one team. Get it wrong and every feature
crosses three services and two teams, and the boundary is expensive to move once data has
been split. The same rules apply to module boundaries inside one deployable; there they are
just cheaper to fix.

## Where boundaries come from

| Source | Idea | Use it to |
|---|---|---|
| **Subdomain** (DDD) | A part of the business problem: core (where you compete), supporting (needed, specific to you), generic (buy or reuse: auth, billing, email) | Find candidate areas; decide where to invest and what to buy |
| **Bounded context** (DDD) | The area where one model and its vocabulary hold. "Customer" in sales and "customer" in support are different models | Draw the line where the language or the rules change |
| **Business capability** | What the business does (manage inventory, take payments, schedule deliveries), stable over years even as processes change | Cross-check subdomains; name services after capabilities, not nouns |
| **Team ownership** | Each service owned by exactly one team that can build, test and deploy it alone | Size services to teams; split when a team can't hold it, merge when one team owns many trivially |

Start from the business (subdomains, bounded contexts, capabilities). Use team structure to
adjust granularity, not to invent boundaries.

## Heuristics

- **Common closure:** things that change for the same reason belong together. If a typical
  change touches two services, they are one.
- **Language shifts:** where the meaning of a word changes, there is a context boundary.
  Translate at it; don't share the model.
- **Aggregates stay whole.** An aggregate, an entity cluster with one invariant such as "order
  total ≤ credit", lives in one service. Invariants across services need a saga or a different
  boundary.
- **Data and behaviour together.** The service that enforces a rule owns the data the rule
  needs. A service that only stores rows others interpret is an entity service (below).
- **Team-sized.** A service, or a set owned by one team, fits in that team's heads. A team of
  five to nine owning one service is the default; a team owns several only with a reason
  (different scaling, failure isolation, lead time).
- **Conway's law runs both ways.** The system mirrors the communication structure. Arrange
  teams for the architecture you want (the inverse Conway manoeuvre) instead of letting the
  org chart draw the boundaries.
- **Prefer coarse first.** Splitting a service later is easier than merging two with separate
  databases.

## Self-contained services

A service that must answer a synchronous request should be able to do it without waiting on
other services. Each synchronous collaborator multiplies the failure probability and adds
latency (see [collaboration](collaboration.md)). Ways to get there: merge the needed capability
into the service, keep a replica of the other service's data fed by its events, or move the
cross-service work behind an asynchronous saga. The price is a larger service or more
eventual consistency. That price is usually right for the operations on a critical user
journey.

## Smells

| Smell | What it means | Fix |
|---|---|---|
| **Entity services:** one per noun, each CRUD over its table | Behaviour lives in callers; every operation orchestrates many services | Regroup around capabilities and the rules they enforce |
| **Two teams share a service** and queue behind each other | Ownership boundary in the wrong place | Split along the teams' subdomains, or give it one owner |
| **One team owns ten tiny services** that always deploy together | Over-decomposed | Merge into one or two deployables with internal modules |
| **A feature needs coordinated changes in several services** | Design-time coupling across the boundary | Move the boundary so the change sits in one service |
| **A shared domain model library** across services | One model forced on several contexts | Each context owns its model; translate at the edge |
| **"Utility" or "common" service** that everyone calls | A generic capability made into a runtime dependency | A library, a sidecar, or a properly owned platform service with an SLO |

## Example

An e-commerce team proposes `ProductService`, `PriceService`, `InventoryService` and
`ReviewService`, each a CRUD API over one table, plus a `CatalogPageService` that calls all
four. Checking the heuristics: a price change and a stock change are made by different people
for different reasons (merchandising vs warehouse), so those are real contexts. Reviews are
generic and could be bought. But "product" itself has no rules of its own; it is the shared key.
Better: a **Catalog** context (product data and prices, owned by merchandising), an
**Inventory** context (stock, reservations, owned by fulfilment, with the reservation
invariants), and reviews via a vendor. The page reads from a catalog view fed by inventory
events instead of calling four services per request.

## Review checklist

1. What subdomain or bounded context does each service implement, and is its type (core,
   supporting, generic) clear?
2. Does each service have exactly one owning team?
3. Does each invariant live inside one service?
4. For the last few features, how many services did each touch?
5. Are names capabilities ("Fulfilment") rather than nouns ("ShipmentService")?
6. Can the critical user journeys be served without synchronous calls to other services?
7. Where two contexts share a term, is there a translation rather than a shared model?

## Related

[style-choice](style-choice.md), [design-process](design-process.md),
[collaboration](collaboration.md), [anti-patterns](anti-patterns.md),
[`core-principles` high-cohesion](../../core-principles/references/high-cohesion.md) and
[low-coupling](../../core-principles/references/low-coupling.md).

## Sources

microservices.io: [Decompose by subdomain](https://microservices.io/patterns/decomposition/decompose-by-subdomain.html),
[Decompose by business capability](https://microservices.io/patterns/decomposition/decompose-by-business-capability.html),
[Service per team](https://microservices.io/patterns/decomposition/service-per-team.html),
[Self-contained service](https://microservices.io/patterns/decomposition/self-contained-service.html).
Martin Fowler, [Bounded Context](https://martinfowler.com/bliki/BoundedContext.html),
[Conway's Law](https://martinfowler.com/bliki/ConwaysLaw.html). Eric Evans, *Domain-Driven
Design*. Skelton and Pais, *Team Topologies* (team cognitive load). Michael Nygard, "The Entity
Service Antipattern". The heuristics and smell table are this skill's synthesis.
