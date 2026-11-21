# Redundancy and failover across nodes and zones

## Problem

Replicas only help if they don't fail together. Three pods on one node, three nodes in one zone,
or a standby on the primary's volume are one failure domain with extra cost. Redundancy means
spare capacity placed in independent failure domains, plus a way to move traffic or leadership
to it that works while the failure is happening.

## When to use / when NOT to use

- **Use** N+1 at least for anything on the request path: one domain (node or zone) can be lost
  and the rest carry peak load.
- **Active-active** for stateless services and anything that can serve from any replica.
- **Active-passive** for single-writer state (a primary database, a leader-elected scheduler),
  with a warm standby in another zone.
- **Not** a substitute for backups: replicas copy corruption and deletes faithfully (see
  [`data-integrity`](../../data-integrity/SKILL.md)).
- **Not** without capacity math: redundancy at 80% utilization per zone becomes overload after
  one zone fails (see [`system-design` scaling-and-failure-domains](../../system-design/references/scaling-and-failure-domains.md)).

## How it works

**Choose the domain.** Node (hardware, kernel, kubelet), zone (power, network, a provider's
zonal control plane), region. Kubernetes exposes them as node labels such as
`kubernetes.io/hostname` and `topology.kubernetes.io/zone`.

**Spread the replicas.** Topology spread constraints:

| Field | Meaning |
|---|---|
| `maxSkew` | Max difference in matching pods between any domain and the least-populated one |
| `topologyKey` | Node label defining the domain |
| `whenUnsatisfiable` | `DoNotSchedule` (default, hard) or `ScheduleAnyway` (soft, prefers lower skew) |
| `labelSelector` | Which pods count; a pod should match its own selector |
| `matchLabelKeys` | Label keys (e.g. `pod-template-hash`) merged into the selector so each rollout revision spreads on its own |
| `minDomains` | Minimum eligible domains; useful with autoscaled pools (see docs for exact semantics) |

Limits from the docs: constraints are checked only at scheduling, so a scale-down can leave
the spread uneven (the descheduler can rebalance); the scheduler knows only domains that have
nodes, so a node pool scaled to zero in one zone is invisible to it. Required pod anti-affinity
is cruder: one pod per domain, and preferred anti-affinity can't enforce anything.

**Detect and move.**

- *Inside Kubernetes:* readiness removes failed pods from Services quickly, but pods on a node
  that goes NotReady or unreachable stay bound for 300 s by default (an automatically added
  toleration with `tolerationSeconds: 300`) before eviction; a partitioned node's pods may keep
  running because the kubelet can't hear the deletion.
- *Load balancer:* health checks drop the zone's targets; active-active absorbs it if
  capacity was there.
- *DNS failover:* health-checked records switch, but clients and resolvers cache answers, so
  failover takes at least the TTL and often longer (Azure notes the delay).
- *Active-passive:* promote the standby, repoint clients (DNS name or virtual IP), and fence
  the old primary.

**Split brain.** When the old primary isn't dead but merely partitioned, two writers accept
writes. Prevent it with a quorum (an odd number of voters across at least three domains) and a
lease from a proven consensus system; a holder that loses its lease must stop acting at once.
Storage-level fencing of the old primary is a further safeguard (unverified here). Leader election
and quorum design are in [`system-design` scaling-and-failure-domains](../../system-design/references/scaling-and-failure-domains.md).

## Failure modes and what agents get wrong

- **`replicas: 3` and done.** Without spread constraints, the scheduler may put all three on one
  node or zone.
- **Hard spread with autoscaled zonal pools.** `DoNotSchedule` with a pool at zero nodes in one
  zone: pods stay Pending, or the zone is ignored. Use an autoscaler aware of topology, or keep
  a minimum of one node per zone.
- **Redundant compute, single-everything-else.** One NAT, one database, one queue, one DNS
  resolver, one ingress controller replica.
- **Active-passive never failed over.** The standby is missing a config change, a credential
  or a schema migration; the first real failover is the test.
- **5-minute eviction surprises.** A dead node's pods aren't replaced for 300 s by default;
  for fast-failover stateless services lower `tolerationSeconds`, and for stateful ones keep or
  raise it to avoid churn on brief partitions.
- **Two-node clusters.** Two voters can't form a majority after one fails.
- **Cross-zone traffic for every request.** Zonal services that call each other across zones
  multiply the chance of hitting the impaired zone; AWS shows a chain of N regional hops
  avoiding a bad zone with probability (2/3)^N versus 2/3 for a zonal chain.

## Implementation notes

- **Kubernetes:** `topologySpreadConstraints` on zone (hard) and hostname (soft); PDBs so
  drains don't undo the spread (see [disruption-budgets-and-safe-rollouts](disruption-budgets-and-safe-rollouts.md));
  `tolerationSeconds` on `node.kubernetes.io/not-ready` and `unreachable`; StatefulSets with
  zonal volumes need one volume per zone.
- **Envoy/Istio:** locality-aware load balancing and failover between localities (unverified); outlier detection ejects a bad zone's hosts.
- **HAProxy/NGINX:** health checks with `fall`/`rise`; backup-server options for
  active-passive (unverified).
- **Managed:** multi-zone node groups, zone-redundant load balancers, managed databases with a
  standby in another zone and DNS-based failover (AWS's RDS example).

## Example

A 9-replica stateless API: exactly balanced across three zones, best-effort across nodes, and
replaced within a minute when a node dies.

```yaml
spec:
  replicas: 9
  template:
    metadata:
      labels: {app: orders-api}
    spec:
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: DoNotSchedule
        labelSelector: {matchLabels: {app: orders-api}}
        matchLabelKeys: [pod-template-hash]   # spread each rollout revision
      - maxSkew: 1
        topologyKey: kubernetes.io/hostname
        whenUnsatisfiable: ScheduleAnyway
        labelSelector: {matchLabels: {app: orders-api}}
        matchLabelKeys: [pod-template-hash]
      tolerations:
      - {key: node.kubernetes.io/not-ready, operator: Exists, effect: NoExecute, tolerationSeconds: 45}
      - {key: node.kubernetes.io/unreachable, operator: Exists, effect: NoExecute, tolerationSeconds: 45}
```

Three per zone; losing a zone leaves 6, so each pod must handle peak / 6 (sized in
[`system-design`](../../system-design/SKILL.md)). Pods on a dead node are evicted after 45 s
instead of 300 s. Spread and taint fields are from the Kubernetes docs; the 45 s value is this
example's trade-off between fast replacement and churn.

## Review checklist

1. What is the failure domain for each tier (node, zone, region), and is every tier, including data, DNS, NAT and ingress, redundant across it?
2. Do survivors carry peak load after losing one domain, with the replicas already running?
3. Are spread constraints set on zone and node, and do they cope with autoscaled pools at zero?
4. How long does each failover path take end to end (probe thresholds, eviction toleration, DNS TTL, client caching)?
5. For single-writer state, is there a quorum or lease, and is the old primary fenced on failover?
6. When was the passive side last failed over for real?
7. Do services prefer same-zone dependencies, so one impaired zone isn't on every request path?

## Related

[graceful-degradation-and-static-stability](graceful-degradation-and-static-stability.md),
[health-checks-and-probes](health-checks-and-probes.md),
[disruption-budgets-and-safe-rollouts](disruption-budgets-and-safe-rollouts.md),
[cells-and-shuffle-sharding](cells-and-shuffle-sharding.md),
[`system-design` scaling-and-failure-domains](../../system-design/references/scaling-and-failure-domains.md),
[`data-integrity` disaster-recovery](../../data-integrity/references/disaster-recovery.md).

## Sources

Kubernetes: [topology spread constraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/),
[taints and tolerations](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)
(taint-based evictions, 300 s default), read from the
[website source](https://github.com/kubernetes/website/tree/main/content/en/docs).
AWS Builders' Library, [Static stability using Availability Zones](https://builder.aws.com/content/3K9SiqiJ369TGkkGzqPM95BuYWI/static-stability-using-availability-zones).
AWS [resilience analysis framework mitigations](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/mitigation-strategies.html).
Azure [Health Endpoint Monitoring pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/health-endpoint-monitoring) (DNS caching delays failover).
Kubernetes [disruptions task](https://kubernetes.io/docs/tasks/run-application/configure-pdb/) (quorum guidance).
