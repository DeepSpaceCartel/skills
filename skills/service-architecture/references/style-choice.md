# Style choice: monolith, modular monolith, microservices

## Problem

The first architecture decision is how many independently deployable components the system
has. Teams often make it by fashion ("modern apps are microservices") or by deployment target
("it's for Kubernetes, so services"). Both are poor reasons. The style is a means to fast,
safe, frequent delivery by several teams. When it doesn't serve that goal, it only adds cost.

## The three options

| Style | What it is | Fits | Costs |
|---|---|---|---|
| **Monolith** | One deployable, one database, one pipeline | One team or a few; a domain still being discovered; early products | Grows into a big ball of mud unless its internals are kept modular; one stack for everything; the pipeline slows as the code grows |
| **Modular monolith** (better: a *modular component*) | One deployable whose top-level structure is domain modules, each hiding its implementation and schema behind a small API | Most systems with up to a handful of teams; the usual starting point and often the end point | Discipline: module APIs must be enforced (build modules, dependency rules, schema ownership); a shared release train; the whole stack upgrades at once |
| **Microservices** | Two or more independently deployable, loosely coupled services, each owned by one team, with its own data, repository and pipeline | Many teams that must deliver independently; parts with genuinely different scaling, availability, security or technology needs | Distributed operations, eventual consistency, runtime coupling, more infrastructure and operations, harder end-to-end testing |

Modularity is not what separates the styles. A monolith can be well modularised, and a
microservice can be a ball of mud inside. Whatever the style, put domains at the top of each
deployable's structure (`ordering/`, `billing/`, each with its own layers), not technical
layers (`controllers/`, `services/`, `repositories/`) that every feature cuts across.

## When to split

Split a part out only when the modular monolith demonstrably can't meet a need. The needs that
justify it, grouped by where they come from:

- **People:** teams block each other on one codebase, review queue or release train, and the
  build and test cycle has grown past fast feedback even with build modules and test selection.
- **Run time:** a part has a different load, availability or latency target, or must keep
  running when the rest fails.
- **Risk and compliance:** a part handles data or privileges that should sit in a smaller blast
  radius and audit scope (card data, PII, admin functions). Fowler counts this among the real
  benefits.
- **Technology:** a part needs a different language, runtime or datastore, or must upgrade on
  its own schedule.

Weigh these against what a split costs every time: operations that become distributed and
eventually consistent, calls that can fail, and one more thing to deploy, monitor, secure and
test. The full set of questions is in [design-process](design-process.md).

## Prerequisites

Microservices pay off only with these in place. Without them you get the costs and none of the
benefits:

- **Continuous delivery:** automated, fast pipelines, and each service deployable alone.
- **Small, long-lived, cross-functional teams** that own services end to end (Team
  Topologies' stream-aligned teams).
- **A platform:** container orchestration or serverless, service discovery, configuration,
  secrets, centralised logs, metrics and traces.
- **Operational maturity:** on-call, SLOs and alerts per service, incident practice.

Fowler calls the extra cost the *microservice premium*: worth paying only when the system is
complex enough. He also observes that most successful service architectures started as a
monolith that was split once its boundaries were understood, and that systems built as
services from the start often struggled. Start with services from day one only when the domain
is well understood and the team has done it before.

## Wrong reasons

| Claim | Why it's wrong | Ask instead |
|---|---|---|
| "Modern applications use microservices" | Popularity isn't a requirement | Which delivery or runtime problem do we have? |
| "It runs in the cloud / on Kubernetes" | A monolith deploys there too | Do parts need different scaling or isolation? |
| "Microservices will fix our slow delivery" | Slowness is usually process, testing or coupling | What do the DORA metrics and the pipeline say? Where does the time go? |
| "Microservices will fix performance" | Network hops make most operations slower | Is it the query, the algorithm, or the network? |
| "So each team can use any stack" | Unbounded stack diversity is an operational cost | Which part *needs* a different stack? |
| "It's how we'll scale" | Most monoliths scale horizontally behind a load balancer | Which part needs to scale differently from the rest? |

## What agents get wrong

- **Recommending services for a new, small or single-team system.** Start modular, extract
  later.
- **Treating "modular monolith" as unstructured monolith plus folders.** Modules need enforced
  APIs, private schemas and dependency rules, or they rot.
- **Splitting by layer** (a "frontend service", a "business logic service", a "data service").
  Every feature then crosses every service.
- **Ignoring the platform cost.** Ten services means ten pipelines, ten dashboards, ten on-call
  surfaces.
- **Assuming the decision is one-way.** Merging services back is a legitimate fix when they
  change together.

## Example

A four-person team builds a job-alert product: crawl sources, normalise jobs, match against
saved searches, send emails. The obvious split is four services. But one team owns all four, the
domain is still moving, and matching needs jobs and searches in one query. Recommendation: one
deployable with four domain modules (`ingest`, `catalog`, `matching`, `notify`), each owning its
tables. The crawler fleet runs as a separate *workload* of the same codebase because it has a
different scaling and failure profile (a run-time reason to split). Revisit when a second team arrives or a module's
pipeline time dominates.

## Review checklist

1. Which named reason to split justifies each separately deployed service?
2. Could a modular monolith meet the same need with less cost?
3. Are CD, team ownership, platform and on-call in place for the number of services proposed?
4. Is each deployable's top-level structure by domain, not by technical layer?
5. Are module APIs and schema ownership enforced, not just conventions?
6. Is there a trigger written down for revisiting the decision (team count, pipeline time, load)?

## Related

[boundaries](boundaries.md), [design-process](design-process.md),
[anti-patterns](anti-patterns.md), [`system-design`](../../system-design/SKILL.md),
[`build-systems`](../../build-systems/SKILL.md) (build modules and test selection for a large
monolith).

## Sources

microservices.io: [Monolithic architecture](https://microservices.io/patterns/monolithic.html),
[Microservice architecture](https://microservices.io/patterns/microservices.html),
[No such thing as a modular monolith](https://microservices.io/post/architecture/2024/05/13/how-modular-can-your-monolith-go-part-7-no-such-thing-as-a-modular-monolith.html),
[Modular monolith patterns for fast flow](https://microservices.io/post/architecture/2024/09/09/modular-monolith-patterns-for-fast-flow.html),
[Architecting monoliths for fast, sustainable flow](https://microservices.io/post/architecture/2024/08/21/architecting-monoliths-for-fast-flow.html),
[Wrong reasons to adopt microservices](https://microservices.io/post/architecture/2025/02/18/wrong-reasons-to-adopt-microservices.html).
Martin Fowler, [Monolith First](https://martinfowler.com/bliki/MonolithFirst.html),
[Microservice Premium](https://martinfowler.com/bliki/MicroservicePremium.html),
[Microservice Trade-Offs](https://martinfowler.com/articles/microservice-trade-offs.html).
Skelton and Pais, *Team Topologies*. The grouping of reasons to split is this skill's own.
