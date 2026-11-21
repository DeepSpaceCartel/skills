# Graceful degradation and static stability

## Problem

Most outages are partial: one dependency is down, one zone is impaired, a control plane is slow.
A system that needs everything to answer becomes fully unavailable on any partial failure. Two
patterns prevent that: **graceful degradation** keeps the core function working without the
missing parts, and **static stability** keeps the system running on what it already has,
without needing to create, fetch or reconfigure anything during the failure.

## When to use / when NOT to use

- **Degradation:** pages or responses that combine several sources, where some are optional
  (recommendations, counts, previews), and batch steps where partial progress is useful.
- **Static stability:** anything whose recovery today depends on launching capacity, pulling
  configuration or calling a control plane at the moment of failure.
- **Not** for correctness-critical paths. AWS's graceful-degradation guidance: a payment flow may
  prefer consistency to availability. Decide per function which one wins.
- **Not** as a rarely-run fallback. AWS's Builders' Library argues against fallback paths that
  only run in emergencies; prefer paths that run all the time.

## How it works

**Hard vs soft dependencies.** List each dependency and ask what the component does without it.
Turn hard dependencies into soft ones where the business allows: render the page without the
widget, serve the last known value, accept writes into a queue while the primary is away.

**Fallback vs failover.** AWS distinguishes them. A fallback is a different code path taken only
in failure (for example "if the cache fails, read the database directly"); it is rarely
exercised, often broken, and can overload what it falls back to. Its example: a cache fallback
that sent every server straight to the database locked the database. Failover to an
alternative that is *always* in use (both replicas serve all the time) is proven every day.

**Static stability.** A statically stable system behaves the same whether or not a failure is
happening. AWS's ingredients:

- **Capacity held in advance.** Enough already running in each zone that the survivors carry
  the full load after one zone is lost; recovery is only routing away from the bad zone.
- **Data plane independent of the control plane.** The control plane creates and changes
  resources; the data plane serves. Existing EC2 instances keep routing traffic during a
  control-plane impairment because each server holds the state it needs. Design so serving
  needs only the data plane.
- **Push, don't pull, at failure time.** Configuration and credentials are delivered ahead of
  need and cached; a failed refresh keeps the last good copy and raises an alarm.
- **Constant work.** Refresh on a fixed cadence regardless of failures, so failure doesn't change
  the load profile. Letting clients bypass a cache during failures changes it at the worst time.
- **Every tier, not just compute.** A statically stable compute tier in front of a single-zone
  database still fails with that zone; read replicas must carry read load after losing one.

**Spare capacity arithmetic.** With N zones and one lost, each zone runs at (N-1)/N of its
tested capacity in normal operation. 2 zones: 50%. 4 zones: 75%. More zones make static
stability cheaper.

## In code / In infrastructure

**In code.** Timeouts on optional calls, partial responses, last-known-good caches that are
never emptied on a failed refresh (an AWS anti-pattern), feature switches to turn off expensive
features under load. See [`engineering-practices` reliability](../../engineering-practices/references/reliability.md).

**In infrastructure.** Pre-provisioned zonal capacity (replica counts and minimum node counts
sized for N-1), image-baked default configuration, local caches of secrets and service
discovery, zonal routing so a request doesn't cross into the impaired zone.

**Agree:** a code fallback that reads the database when the cache is down needs the database
sized for full uncached load, or it is an outage amplifier. Either size it, or don't fall back.

## Failure modes and what agents get wrong

- **Scale-on-failure as the HA plan.** "The autoscaler will replace the zone" depends on the
  control plane, spare provider capacity and image pulls, all least reliable during a large event.
- **Emptying local state on a failed refresh,** so a config-service outage wipes every
  instance's routing table.
- **A fallback nobody runs.** It is discovered broken during the incident.
- **Startup depends on the control plane.** New pods can't start without fetching config or
  credentials from a service that is down; existing pods are fine, so the outage hits at the
  next deploy or eviction.
- **A degraded mode that's slower than normal** (heavier queries, verbose logging) and adds
  load during the failure.
- **Statically stable compute, single-zone data.**

## Implementation notes

- **Kubernetes:** replica counts and HPA `minReplicas` sized for zone loss with topology spread
  across zones (see [redundancy-and-failover](redundancy-and-failover.md)); a low-priority
  overprovisioning deployment holds spare node capacity the cluster autoscaler would otherwise
  remove (see [requests-limits-and-autoscaling](requests-limits-and-autoscaling.md));
  `imagePullPolicy: IfNotPresent` with pinned digests so restarts on a node that already has
  the image don't need the registry (unverified).
- **Mesh and DNS:** services keep their last known endpoints if the control plane is down
  (proxy behaviour varies; verify for your mesh).
- **Managed:** multi-zone managed databases and load balancers with cross-zone balancing; AWS
  notes cross-zone balancing is sometimes disabled on purpose, so check it.

## Example

A storefront page with one hard and three soft dependencies, and a stamp of three zones sized
for one zone's loss.

| Dependency | Kind | Without it |
|---|---|---|
| Catalog database (read replicas in 3 zones) | hard | page fails; replicas sized so any 2 carry peak reads |
| Recommendations | soft | omit the block after a 150 ms timeout |
| Review counts | soft | serve the cached count, up to 1 h stale |
| Feature-flag service | soft | flags baked into the image at build, refreshed every 60 s, last good kept |

```yaml
# Peak 1,800 rps; one pod serves 100 rps at the SLO. Survivors must carry peak.
# 3 zones, lose 1: need 18 pods in 2 zones -> 9 per zone -> 27 pods total.
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: {name: storefront}
spec:
  scaleTargetRef: {apiVersion: apps/v1, kind: Deployment, name: storefront}
  minReplicas: 27          # floor = statically stable for one zone loss at peak
  maxReplicas: 60
  metrics:
  - type: Resource
    resource: {name: cpu, target: {type: Utilization, averageUtilization: 60}}
```

The floor is computed from peak, not from today's load, so a zone loss at peak needs no
scale-up. Pair it with a zone topology spread so the 27 land 9 per zone. HPA fields are from
the Kubernetes HPA docs; the numbers are this example's.

## Review checklist

1. Is each dependency classified hard or soft, with the behaviour without it written down and tested?
2. Do degraded paths run regularly (or always), rather than only in emergencies?
3. Can the system serve with its control plane, config service and registry down?
4. Is capacity for losing one zone already running, for every tier including data?
5. Do failed refreshes keep the last good state and alarm, rather than clear it?
6. Is anything a fallback falls back to sized for the full load it would receive?
7. Is the degraded mode cheaper than the normal one?

## Related

[redundancy-and-failover](redundancy-and-failover.md), [load-shedding](load-shedding.md),
[cells-and-shuffle-sharding](cells-and-shuffle-sharding.md),
[requests-limits-and-autoscaling](requests-limits-and-autoscaling.md),
[`system-design` capacity-planning](../../system-design/references/capacity-planning.md),
[`architecture-review` failure-mode-analysis](../../architecture-review/references/failure-mode-analysis.md).

## Sources

AWS Builders' Library, [Static stability using Availability Zones](https://builder.aws.com/content/3K9SiqiJ369TGkkGzqPM95BuYWI/static-stability-using-availability-zones)
and [Avoiding fallback in distributed systems](https://builder.aws.com/content/3EuS9Sakq7L3VLQIF3qzfMfke1Y/avoiding-fallback-in-distributed-systems).
AWS Well-Architected, [REL11-BP05 static stability](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel11-bp05.html)
and [REL05-BP01 graceful degradation](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_graceful_degradation.html).
AWS [resilience analysis framework mitigations](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/mitigation-strategies.html).
Google SRE book, [Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/).
Kubernetes [HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/).
