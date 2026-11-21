---
name: infrastructure-patterns
description: Infrastructure pattern catalog - project-agnostic, Kubernetes, self-hosted or any cloud. Caching (cache-aside, read-through, CDN); scaling (load balancing, read replicas, sharding, materialized views); messaging (pub/sub, work queues, competing consumers, transactional outbox, idempotent consumer, CQRS, event sourcing, saga, dead-letter queue); resilience (redundancy and failover across zones, health checks and liveness, readiness and startup probes, disruption budgets, requests, limits and autoscaling, mesh and gateway timeouts, retries, outlier ejection, rate limits, load shedding, static stability, cells and shuffle sharding). Use when asked which pattern fits, whether to add a queue, cache or replica, or how to survive a node or zone failure, or on a dual write, a read/write imbalance or a slow consumer. Not for retries or timeouts in code (see engineering-practices), sizing (see system-design), reviewing a whole architecture (see architecture-review), or pipeline data correctness (see data-pipelines).
---

# Infrastructure Patterns

A catalog of patterns for the infrastructure around a service: how it survives node and zone
failures, overload and bad neighbours; how messages move between components; how reads and
writes scale. Each reference states the problem, when the pattern fits and when it doesn't, how
it works, what agents get wrong, neutral implementation notes (Kubernetes, Envoy/Istio, NGINX,
HAProxy) with a one-line managed-cloud equivalent, a concrete config example, and a numbered
review checklist.

This skill is about *choosing and configuring a pattern*. Sizing the result is
[`system-design`](../system-design/SKILL.md); reviewing a whole architecture is
[`architecture-review`](../architecture-review/SKILL.md); the code side of retries, timeouts,
breakers and idempotency is [`engineering-practices`](../engineering-practices/SKILL.md).

## How to use this skill

1. Start from what you observe in **Symptom to pattern**, or from the family in **The catalog**.
   Read the one or two matching references. Don't load the whole catalog.
2. If the mechanism exists both in code and in the platform (retries, timeouts, breakers,
   bulkheads, rate limits, shedding), read **Reliability at two layers** first and decide which
   layer owns it.
3. Patterns compose. A zone-failure plan needs redundancy, probes, disruption budgets and static
   stability together. Each reference lists its neighbours under **Related**.
4. Verify defaults against the version you run. The references quote defaults from the docs
   they cite; proxies and meshes change them between releases.

## The catalog

### Reliability and infrastructure topology

| Pattern | The question it answers | Read when | Reference |
|---|---|---|---|
| Timeouts and retries (infra) | Which hop times out, which hop retries? | Adding a mesh, gateway or ingress; 504s; duplicate writes after retries; long requests cut at 15 s | [timeouts-and-retries-infra](references/timeouts-and-retries-infra.md) |
| Circuit breaking and outlier ejection | How do we stop sending to a bad host or an overloaded upstream? | One bad pod among many; connection pools exhausted; random 503s with `x-envoy-overloaded` | [circuit-breaking-and-outlier-ejection](references/circuit-breaking-and-outlier-ejection.md) |
| Bulkheads and isolation | Can one workload exhaust what another needs? | Batch and API share nodes, quota, queues or a database; noisy neighbours; tenant isolation | [bulkheads-and-isolation](references/bulkheads-and-isolation.md) |
| Rate limiting and throttling | How much may each caller use, and how do we tell them to slow down? | Public or multi-tenant API; per-tenant limits; 429 and `Retry-After`; local vs global limits | [rate-limiting-and-throttling](references/rate-limiting-and-throttling.md) |
| Load shedding | What do we refuse when the whole service is full? | Latency collapses under load; unbounded queues; priority between traffic classes | [load-shedding](references/load-shedding.md) |
| Health checks and probes | What should restart a container, and what should only stop its traffic? | Writing liveness, readiness or startup probes; LB health checks; crash loops; deep vs shallow checks | [health-checks-and-probes](references/health-checks-and-probes.md) |
| Graceful degradation and static stability | Does the system keep serving without a dependency or its control plane? | Optional dependencies; fallbacks; recovery that needs new capacity or config at failure time | [graceful-degradation-and-static-stability](references/graceful-degradation-and-static-stability.md) |
| Redundancy and failover | Do the replicas fail independently, and how does traffic move? | Surviving a node or zone; active-active vs active-passive; spread and anti-affinity; DNS or LB failover; split brain | [redundancy-and-failover](references/redundancy-and-failover.md) |
| Disruption budgets and safe rollouts | How much may a drain or rollout take away, and do pods finish their work? | PDBs; `maxSurge`/`maxUnavailable`; preStop and grace periods; connection draining; drains that hang | [disruption-budgets-and-safe-rollouts](references/disruption-budgets-and-safe-rollouts.md) |
| Requests, limits and autoscaling | Which QoS class and which autoscaler, and do they agree? | Setting requests and limits; OOM kills; HPA, VPA, KEDA, cluster autoscaler; scale to zero | [requests-limits-and-autoscaling](references/requests-limits-and-autoscaling.md) |
| Cells and shuffle sharding | How many customers can one bad deploy, poison request or tenant reach? | Shrinking blast radius; stamps or scale units; a fleet near its scaling limit; tenant isolation | [cells-and-shuffle-sharding](references/cells-and-shuffle-sharding.md) |

### Messaging

Filled by a later part of this catalog.

### Performance and scaling

Filled by a later part of this catalog.

## Symptom to pattern

| Symptom | Look at |
|---|---|
| One user action produces many upstream requests; retries show up in both client logs and the mesh | [timeouts-and-retries-infra](references/timeouts-and-retries-infra.md) |
| A gateway returns 504 while the backend finishes the work, then the client retries it | [timeouts-and-retries-infra](references/timeouts-and-retries-infra.md) |
| Exports or uploads fail at exactly 15 s behind Envoy | [timeouts-and-retries-infra](references/timeouts-and-retries-infra.md) |
| One replica returns errors fast and gets more traffic than the others | [circuit-breaking-and-outlier-ejection](references/circuit-breaking-and-outlier-ejection.md) |
| A slow dependency holds every connection and unrelated calls start failing | [circuit-breaking-and-outlier-ejection](references/circuit-breaking-and-outlier-ejection.md), [bulkheads-and-isolation](references/bulkheads-and-isolation.md) |
| A batch job or backfill evicts or slows the API on the same nodes | [bulkheads-and-isolation](references/bulkheads-and-isolation.md) |
| One tenant's traffic or backlog degrades everyone else | [rate-limiting-and-throttling](references/rate-limiting-and-throttling.md), [bulkheads-and-isolation](references/bulkheads-and-isolation.md) |
| Clients see 503 when they were only over their rate | [rate-limiting-and-throttling](references/rate-limiting-and-throttling.md) |
| Under a spike, throughput stays high but almost every response is too late | [load-shedding](references/load-shedding.md) |
| Health checks fail under load and the balancer removes instances, so the rest overload | [load-shedding](references/load-shedding.md), [health-checks-and-probes](references/health-checks-and-probes.md) |
| A database blip restarts every pod at once | [health-checks-and-probes](references/health-checks-and-probes.md) (liveness depends on a shared dependency) |
| Probes are green while the disk is full or the consumer is stuck | [health-checks-and-probes](references/health-checks-and-probes.md) |
| A slow-starting service never becomes ready: CrashLoopBackOff during startup | [health-checks-and-probes](references/health-checks-and-probes.md) |
| An optional widget or service failing takes the whole page down | [graceful-degradation-and-static-stability](references/graceful-degradation-and-static-stability.md) |
| "The autoscaler will replace the lost zone" is the HA plan | [graceful-degradation-and-static-stability](references/graceful-degradation-and-static-stability.md) |
| A config or secrets service outage stops new pods from starting | [graceful-degradation-and-static-stability](references/graceful-degradation-and-static-stability.md) |
| All replicas landed on one node or zone; a node failure took the whole service | [redundancy-and-failover](references/redundancy-and-failover.md) |
| Pods on a dead node take about five minutes to be replaced | [redundancy-and-failover](references/redundancy-and-failover.md) |
| After a failover, two primaries accepted writes | [redundancy-and-failover](references/redundancy-and-failover.md) |
| Connection resets or 502s on every deploy | [disruption-budgets-and-safe-rollouts](references/disruption-budgets-and-safe-rollouts.md) |
| A node drain or cluster upgrade hangs forever | [disruption-budgets-and-safe-rollouts](references/disruption-budgets-and-safe-rollouts.md) |
| A drain took every replica down at once | [disruption-budgets-and-safe-rollouts](references/disruption-budgets-and-safe-rollouts.md) |
| The HPA never scales, or `kubectl apply` keeps resetting the replica count | [requests-limits-and-autoscaling](references/requests-limits-and-autoscaling.md) |
| Queue backlog grows while worker CPU stays low | [requests-limits-and-autoscaling](references/requests-limits-and-autoscaling.md) |
| Containers `OOMKilled`, or the wrong pods evicted under node pressure | [requests-limits-and-autoscaling](references/requests-limits-and-autoscaling.md), [`system-design` capacity-planning](../system-design/references/capacity-planning.md) |
| One bad deploy or one poison request took down every customer at once | [cells-and-shuffle-sharding](references/cells-and-shuffle-sharding.md) |
| A single noisy tenant breaks the workers or queues everyone shares | [cells-and-shuffle-sharding](references/cells-and-shuffle-sharding.md), [bulkheads-and-isolation](references/bulkheads-and-isolation.md) |

## Reliability at two layers

Several mechanisms can live in application code or in the platform (mesh, gateway, load
balancer, scheduler). **The two layers must agree.** Pick one owner per mechanism per call path
and configure the other layer to stay out of the way, because the effects compound: retries in
both the client and the mesh multiply, and a gateway timeout shorter than the backend's lets
work continue after the caller gave up.

| Mechanism | In code | In infrastructure | Rule for agreeing |
|---|---|---|---|
| Retries | [reliability](../engineering-practices/references/reliability.md): one layer, ≤ 3 attempts, full jitter, budget, idempotency keys | [timeouts-and-retries-infra](references/timeouts-and-retries-infra.md): mesh retry policy, retry budget | One retrying layer per path. Istio retries by default (2 retries, up to 3 requests), so a client retry loop must turn the mesh's off, or the reverse |
| Timeouts and deadlines | [reliability](../engineering-practices/references/reliability.md): per-attempt timeout, propagated deadline | [timeouts-and-retries-infra](references/timeouts-and-retries-infra.md): route, per-try, idle, drain | Outer hops wait longer than inner hops x attempts. Envoy's route default is 15 s; Istio's request timeout is off unless set |
| Circuit breaking | [reliability](../engineering-practices/references/reliability.md): breaker with a fallback | [circuit-breaking-and-outlier-ejection](references/circuit-breaking-and-outlier-ejection.md): host ejection, pool limits | Proxy ejects single hosts; code breaks for a whole dependency and owns the fallback |
| Bulkheads | [reliability](../engineering-practices/references/reliability.md): pool or semaphore per dependency | [bulkheads-and-isolation](references/bulkheads-and-isolation.md): node pools, quotas, priority, per-destination pools | Code pools sized from the infrastructure limit divided by the maximum replica count |
| Rate limits | [reliability](../engineering-practices/references/reliability.md): honour 429 and `Retry-After` | [rate-limiting-and-throttling](references/rate-limiting-and-throttling.md): edge and mesh limits per key | Each principal's limit enforced in one place; 429s propagated, never silently retried |
| Load shedding | [reliability](../engineering-practices/references/reliability.md): criticality, deadline checks, client throttling | [load-shedding](references/load-shedding.md): proxy caps, bounded queues | Proxy caps sit above the server's own shedding point, so the server sheds by priority first |

## Working rules

1. **Read the defaults you inherit.** Meshes and proxies retry, time out and cap connections out
   of the box (or don't cap them at all). Write down the effective value at every hop.
2. **One owner per mechanism per call path,** as in the table above.
3. **Size from measurement.** Limits, caps and pool sizes come from a load test and Little's
   law, not from a default or a round number. Sizing itself is
   [`system-design`](../system-design/SKILL.md).
4. **Plan for the failure, not the steady state.** Capacity for a lost node or zone, a rollout's
   surge and a retry wave is provisioned before it's needed.
5. **Make the overload and failure paths observable and tested.** Overflow counters, ejections,
   rejections and degraded modes each get a metric, and a test that exercises them.
6. **Prefer the platform's mechanism to a hand-rolled one** when it exists and is configured,
   but know exactly what it does.

## Related

- [`engineering-practices`](../engineering-practices/SKILL.md) — the code layer: retries, timeouts, breakers, idempotency, SLOs; release engineering.
- [`system-design`](../system-design/SKILL.md) — sizing, capacity planning, failure domains.
- [`architecture-review`](../architecture-review/SKILL.md) — reviewing a whole design or a launch.
- [`data-pipelines`](../data-pipelines/SKILL.md) — pipeline correctness, per-source limits, dead letters.
- [`data-integrity`](../data-integrity/SKILL.md) — backups, storage, ephemeral disk and volume growth.
- [`helm-charts`](../helm-charts/SKILL.md), [`container-images`](../container-images/SKILL.md) — packaging what these patterns configure.
