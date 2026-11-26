---
name: system-design
description: Turning requirements into a concrete, sized design (NALSD) - project-agnostic. Covers requirements (SLOs, load shape, growth, data, budget); back-of-envelope estimates of QPS, peak factors, storage growth, bandwidth, IOPS, memory, connections and Little's law; capacity planning (N+1/N+2 headroom, a limits inventory (quotas, file descriptors, DB connections, shm caps), Kubernetes requests, limits and OOM kills, autoscaler ceilings, runway dates); single points of failure, failure domains, overload, load balancing, leader election and distributed cron. Use when designing a new service or a move (to Kubernetes, SQLite to Postgres, one node to many), when asked how many nodes, how much storage or memory, or will it scale, or before buying capacity. Not for service boundaries (see service-architecture), design or launch reviews (see architecture-review), cache, queue or replica patterns (see infrastructure-patterns), tuning slow code (see engineering-practices), or backups and volume safety (see data-integrity).
---

# System Design

Designing with numbers: every component gets a rate, a size and a count, and the design is
iterated until it meets its SLOs within its budget and survives the failures it must. The method
is Google's non-abstract large system design (NALSD) from the SRE Workbook, with the SRE book's
chapters on load balancing, overload, cascading failure, critical state and distributed cron,
the Kubernetes resource and autoscaler docs, and the AWS resilience analysis framework. Each
reference leads with what agents get wrong, then gives a procedure, a worked example and a
numbered review checklist.

This skill **produces** a design. Reviewing one that exists, or a launch, is [`architecture-review`](../architecture-review/SKILL.md).
Choosing a specific pattern (a cache, a queue, a read replica) is [`infrastructure-patterns`](../infrastructure-patterns/SKILL.md).
Making existing code faster is [`engineering-practices`](../engineering-practices/SKILL.md)
(performance).

## How to use this skill

1. For a new design or a migration, start with [nalsd-method](references/nalsd-method.md):
   fill the requirements template, then iterate (possible → better → feasible → resilient →
   better). Open the other references when an iteration needs them.
2. For a sizing question ("how many nodes?", "how much disk?", "will Postgres keep up?"), go to
   [estimation](references/estimation.md), then [capacity-planning](references/capacity-planning.md).
3. Before calling any design done, run the review checklists of
   [capacity-planning](references/capacity-planning.md) and
   [scaling-and-failure-domains](references/scaling-and-failure-domains.md).
4. Show the arithmetic. Run it in a short script when there are more than a few numbers, and
   say which inputs were measured, given or assumed.

## The catalog

| Topic | Read when | Reference |
|---|---|---|
| NALSD method | Designing a service or a move; writing requirements; iterating a design; the worked crawler example | [nalsd-method](references/nalsd-method.md) |
| Estimation | QPS from daily volume, peak and catch-up factors, storage, bandwidth, IOPS, memory, connections, Little's law, the ballpark sheet | [estimation](references/estimation.md) |
| Capacity planning | Headroom; the limits inventory; memory budgets under a fixed cap; Kubernetes requests, limits and OOM kills; autoscaler ceilings and quotas; runway dates | [capacity-planning](references/capacity-planning.md) |
| Scaling and failure domains | Single points of failure; zones; overload and cascading failure; load-balancing choices; consensus and leader election; distributed cron | [scaling-and-failure-domains](references/scaling-and-failure-domains.md) |

## Symptom to reference

| Symptom or situation | Look at |
|---|---|
| "How many nodes / replicas / disks do we need?" | [estimation](references/estimation.md), then [capacity-planning](references/capacity-planning.md) |
| A design is boxes and arrows with no numbers | [nalsd-method](references/nalsd-method.md) |
| Moving to Kubernetes, from SQLite to Postgres, or from one node to many | [nalsd-method](references/nalsd-method.md): size the target before moving |
| A shared box (dev workspace, single node) with a fixed memory cap; things get OOM-killed when two heavy jobs overlap | [capacity-planning](references/capacity-planning.md): memory budget, one heavy-job slot |
| Pods `OOMKilled` (exit 137), evicted under memory pressure, or `Pending` with `FailedScheduling` | [capacity-planning](references/capacity-planning.md) |
| The autoscaler stopped adding nodes; pods pending; a provider quota (IPs, vCPUs, nodes) was hit | [capacity-planning](references/capacity-planning.md): ceilings and the limits inventory |
| "Too many connections" after scaling out the API | [capacity-planning](references/capacity-planning.md), [estimation](references/estimation.md) (connections) |
| A volume sized for today's data | [capacity-planning](references/capacity-planning.md) runway; [`data-integrity`](../data-integrity/SKILL.md) for WAL and restore space |
| One long batch transaction blocks every other writer (SQLite or any single-writer store) | [scaling-and-failure-domains](references/scaling-and-failure-domains.md); [nalsd-method](references/nalsd-method.md) iteration 3 |
| DNS timeouts across the cluster under crawl or fan-out load | [scaling-and-failure-domains](references/scaling-and-failure-domains.md): external limits on shared dependencies |
| Losing one node or zone takes the service down | [scaling-and-failure-domains](references/scaling-and-failure-domains.md) |
| Overload spreads from one replica or zone to all | [scaling-and-failure-domains](references/scaling-and-failure-domains.md) |
| Need exactly one leader, lock or scheduler | [scaling-and-failure-domains](references/scaling-and-failure-domains.md): consensus, leases |
| A cron job ran twice, or every job starts at midnight | [scaling-and-failure-domains](references/scaling-and-failure-domains.md): distributed cron |
| Backlog after an outage never drains | [nalsd-method](references/nalsd-method.md) backlog arithmetic; [`data-pipelines`](../data-pipelines/SKILL.md) failure-isolation |

## Working rules

A synthesis across the references:

1. **Numbers on every box.** Rate, size and count, with units and with each input marked
   measured, given or assumed.
2. **Requirements as SLO sentences** before any design: what fraction of which events meet which
   bound, over what window.
3. **Size for the peak, plus catch-up, plus the largest failure you must survive.** The daily
   average is not a design load.
4. **Reduce the work before adding machines**: skip unchanged items, batch, index.
5. **Every resource, not just CPU and RAM.** Disk operations, bandwidth, file descriptors,
   connections, IPs, quotas, shared dependencies' rate limits.
6. **Know every ceiling before the autoscaler finds it.** The max is the smallest quota or
   downstream limit, minus a margin.
7. **Budget a fixed cap.** On any shared host, write what each process uses at peak and how
   many heavy jobs may run at once; enforce it.
8. **Replicas in different failure domains.** A single-instance component is a decision with an
   owner and a recovery time, not an oversight.
9. **A date on every limit.** Runway = remaining headroom ÷ growth rate.

## Gotchas

- Estimates reject designs; they do not buy capacity. Load test before purchase.
- 86,400 s/day rounded to 1e5 underestimates rates by about 14%.
- The scheduler packs by requests; a node full of small requests and large limits is
  overcommitted and fails together at peak.
- A memory limit is enforced by the kernel's OOM killer, reactively; a CPU limit only throttles.
- Cluster autoscaler adds nodes only for unschedulable pods, by their requests, and stops at the
  group max or the provider's quota, retrying with backoff while pods wait.
- An even number of consensus replicas costs more without tolerating more failures.
- SQLite allows one writer at a time and is a poor fit when the data is reached over a network
  or from several machines.

## Related

- [`engineering-practices`](../engineering-practices/SKILL.md): reliability (timeouts, retry
  budgets, load shedding, SLOs and burn-rate alerts), performance (profiling and benchmarking),
  database-migrations (moving schemas and data).
- [`data-integrity`](../data-integrity/SKILL.md): volume sizing for safety, WAL growth, backups,
  restore drills, DR.
- [`data-pipelines`](../data-pipelines/SKILL.md): pipeline SLOs, completeness, per-source limits,
  backlogs.
- [`core-principles`](../core-principles/SKILL.md): KISS and YAGNI against over-design.
- [`service-architecture`](../service-architecture/SKILL.md): how many services, where the
  boundaries go, and how they collaborate, before sizing them.
- [`adr`](../adr/SKILL.md): recording the chosen design and the rejected iterations.
- [`helm-charts`](../helm-charts/SKILL.md): where requests, limits and replica counts are set.
- [`architecture-review`](../architecture-review/SKILL.md): reviewing an existing design or a launch.
- [`infrastructure-patterns`](../infrastructure-patterns/SKILL.md): choosing a cache, queue, replica, pooler or managed service.
- [`production-operations`](../production-operations/SKILL.md): incident response when a limit is hit in production.
