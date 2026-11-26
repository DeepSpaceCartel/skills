# Anti-patterns: when the split makes things worse

## Problem

A service architecture that went wrong rarely fails all at once. Delivery slows, releases need
coordination, incidents cascade, and data drifts between services. Then "microservices" gets
the blame. The usual cause is a set of specific design decisions that can be found and fixed.
The worst case is the **distributed monolith**: services that must change, release and run
together, so the system pays the costs of distribution and gets none of the independence.

## Catalog

| Anti-pattern | Symptoms | Cause | Fix |
|---|---|---|---|
| **Distributed monolith** | Releases bundle several services; an outage anywhere is an outage everywhere | Boundaries that don't match change or failure patterns | Merge what changes together; make critical paths self-contained |
| **Lockstep changes** | Most features touch two or more services; deploy order matters | Design-time coupling: shared model, a leaky API, a split aggregate | Move the boundary; make APIs smaller and stable; version, expand then contract |
| **Entity services** | Services named after nouns, each CRUD; an "orchestrator" service holds the logic | Decomposition by data rather than by capability | Regroup around capabilities and their rules ([boundaries](boundaries.md)) |
| **Chatty synchronous chains** | One request triggers many hops; latency and errors multiply; retry storms | Commands and queries done as sync calls | Replicas, views, sagas, merging ([collaboration](collaboration.md)) |
| **Shared database** | Schema changes need sign-off from several teams; one service's lock stalls another | Splitting code but not data | Ownership, grants, staged separation ([data-ownership](data-ownership.md)) |
| **Shared domain library** | A change to `common-models` forces every service to rebuild and redeploy | One model imposed on several contexts | Each service owns its model; share only stable technical libraries, versioned |
| **Nanoservices** | One team owns dozens of tiny services that always deploy together | Granularity driven by "small is good" | Merge into team-sized services with internal modules |
| **Shared team, shared service** | Several teams commit to one service and wait on each other | Ownership not aligned with boundaries | One owning team per service; split along subdomains |
| **Gateway monolith** | Every feature needs a gateway change by a central team | Business logic or ownership centralised at the edge | Routing and edge policy only; BFFs owned by UI teams |
| **Microservices as a cure-all** | Services adopted to fix slow delivery or poor performance, and neither improved | Root cause not analysed | Find the real constraint (tests, pipeline, process, queries) first |

## Measuring coupling

Don't argue about coupling; measure it.

- **Co-change:** how often do two services change in the same commit, pull request, ticket or
  release? A pair that co-changes in most changes is one service.

  ```bash
  # pairs of top-level directories (one per service) changed in the same commit, last 6 months
  git log --since=6.months --name-only --format='tformat:@@' \
    | awk -F/ '/^@@$/{for(a in s)for(b in s)if(a<b)print a, b; delete s; next}
               NF>1{s[$1]=1}
               END{for(a in s)for(b in s)if(a<b)print a, b}' \
    | sort | uniq -c | sort -rn | head
  ```

  In a monorepo where services sit under `services/<name>/`, use `$2` instead of `$1`. Compare
  each pair's count with each service's total commit count: a pair that co-changes in most of
  either service's commits is the signal.

  ```text
       41 billing ordering      <- 41 shared commits; ordering has 52 in total: one service
        3 catalog fulfilment
  ```

- **Release coupling:** how many deploys required another service to deploy first?
- **Breaking API changes:** how often does a provider break a consumer, and how many
  consumers does each change touch?
- **Synchronous fan-out:** hops per critical request, from traces.
- **Delivery metrics:** DORA's lead time, deployment frequency, change failure rate and
  recovery time, per team. A split that worked improves them for the teams involved.

## Remedies, in order

1. **Own the decision.** Treat the architecture as something to analyse and change, not fate.
2. **Diagnose with data**, using the measures above, before proposing a new structure.
3. **Fix the boundary, not the symptom.** Merging two services is a valid change. So is moving
   one subdomain.
4. **Change in small, reversible steps** ([migration](migration.md)), tracking whether the
   metrics improve.

## What agents get wrong

- **Proposing more services** to fix problems caused by too many.
- **Treating merging as failure.** It is often the cheapest fix for a distributed monolith.
- **Adding a shared library** to remove duplication between services, creating release
  coupling.
- **Fixing a chatty chain with caching** alone instead of changing the collaboration.

## Review checklist

1. Which service pairs co-change most, and is that coupling intended?
2. Does any deploy require another service to deploy first?
3. How many synchronous hops do the critical requests take?
4. Does any shared library contain domain models or force coordinated upgrades?
5. Does each service have one owning team, and does each team own a sensible number?
6. Have lead time and deploy frequency improved for the teams whose services were split?

## Related

[boundaries](boundaries.md), [collaboration](collaboration.md),
[data-ownership](data-ownership.md), [style-choice](style-choice.md),
[`architecture-review`](../../architecture-review/SKILL.md),
[`engineering-practices` api-evolution](../../engineering-practices/references/api-evolution.md).

## Sources

microservices.io: [Microservices ate my application](https://microservices.io/post/architecture/2025/02/03/microservices-ate-my-application.html),
[Loose design-time coupling](https://microservices.io/post/architecture/2024/11/09/loose-coupling-enabling-the-winning-org.html),
[Microservices rules: what good looks like](https://microservices.io/post/architecture/2024/07/10/microservices-rules-what-good-looks-like.html).
Sam Newman, *Building Microservices* (2nd ed.). DORA,
[the four key metrics](https://dora.dev/guides/dora-metrics-four-keys/). Michael Nygard,
[The Entity Service Antipattern](https://www.michaelnygard.com/blog/2017/12/the-entity-service-antipattern/). The catalog and the co-change script are this skill's own.
