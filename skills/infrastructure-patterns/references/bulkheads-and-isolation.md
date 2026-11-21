# Bulkheads and isolation

## Problem

Workloads that share a node, a namespace, a queue or a database share each other's failures.
A batch job's memory spike evicts the API, one tenant's backlog delays everyone's messages, a
runaway migration holds every database connection. A bulkhead gives each workload its own
bounded share, so exhausting one share leaves the rest working.

## When to use / when NOT to use

- **Use** when workloads differ in criticality (user-facing API vs batch), in load shape (steady
  vs bursty), or in trust (tenants, untrusted jobs), and they share capacity today.
- **Use** platform isolation before hand-rolled isolation. Azure's Bulkhead pattern says to use
  the platform's quotas and limits rather than rebuilding them in code.
- **Don't** split when the cost of idle reserved capacity outweighs the risk, or when the
  system is small enough that one pool is simpler. Azure names lower resource efficiency and
  added complexity as the reasons not to.
- **Don't** confuse a bulkhead with a cell: a bulkhead isolates one resource; a cell is a whole
  independent copy of the stack (see [cells-and-shuffle-sharding](cells-and-shuffle-sharding.md)).

## How it works

Isolate at the level where the shared resource lives:

| Shared resource | Bulkhead | Mechanism |
|---|---|---|
| Node CPU and memory | Separate node pools for critical and batch work | taints + tolerations + node affinity |
| Cluster capacity per team or tenant | Namespace with a ResourceQuota | `requests.cpu`, `requests.memory`, `count/pods`; 403 on overrun |
| Scheduling order under scarcity | PriorityClasses | higher priority preempts lower |
| Container defaults | LimitRange | default requests and limits for pods that set none |
| Connections to a dependency | Per-dependency pools | mesh connection-pool limits, or pools in code |
| Message flow | Separate queues per workload or priority | own consumers per queue |
| Database | Separate databases, users with connection limits, or replicas per workload | per-role connection caps |

**Dedicated nodes.** A taint keeps other pods off; the Kubernetes docs note a toleration only
*allows* scheduling there, so to keep the workload *on* those nodes add a matching node label
and required node affinity as well.

**Quotas.** Once a namespace has a compute quota, pods that set no requests or limits for that
resource may be rejected, so pair the quota with a LimitRange that supplies defaults. A quota
with a `scopeSelector` on PriorityClass caps pods of that class in its namespace only. To keep a
high class out of other namespaces, list it under `limitedResources` in the API server's
ResourceQuota admission config: pods of that class are then admitted only where a matching
quota exists (the priority docs warn untrusted users could otherwise create top-priority pods
and evict others).

**Priority.** Pods without a `priorityClassName` get priority 0 unless a class has
`globalDefault: true`. User classes go up to 1,000,000,000; larger values are reserved for
`system-cluster-critical` and `system-node-critical`. `preemptionPolicy: Never` queues ahead
without evicting anyone. Preemption tries to respect PodDisruptionBudgets but will violate them
if no other victims exist.

## In code / In infrastructure

**In code.** A semaphore or pool per dependency, sized by Little's law, so one slow dependency
can't take all threads. See [`engineering-practices` reliability](../../engineering-practices/references/reliability.md)
and, for per-source pools in pipelines, [`data-pipelines` failure-isolation](../../data-pipelines/references/failure-isolation.md).

**In infrastructure.** Node pools, quotas, priority, separate queues and databases, and mesh
connection limits. These hold even when the code is wrong.

**Agree:** a code pool of 50 connections per pod behind a database that allows 100 connections
in total is not a bulkhead once you run three pods. Size the code pools from the infrastructure
limit divided by replicas at their maximum (the HPA max, not today's count).

## Failure modes and what agents get wrong

- **Isolation by label only.** A node pool with a taint but no affinity on the critical pods:
  batch is kept out, but the API still schedules onto shared nodes and shares their fate.
- **A quota with no LimitRange,** so deploys start failing with 403s for pods that never set
  requests.
- **Everything high priority.** If every workload claims the top class, priority means nothing
  and preemption picks victims arbitrarily.
- **One queue for all work.** A bulk backfill enqueued ahead of user-triggered jobs delays every
  user. Separate queues, or a priority queue with its own consumers.
- **Shared database, separate services.** Microservices with separate pods but one database and
  one connection limit are one bulkhead.
- **Monitoring the whole, not each partition.** Azure recommends watching each partition's
  performance; an aggregate dashboard hides the one bulkhead that is full.
- **Noisy neighbour on the node:** a BestEffort or low-request pod that bursts gets evicted
  first under node pressure, but until then it steals CPU from everyone; give batch real
  requests and its own pool.

## Implementation notes

- **Kubernetes:** taints/tolerations, node affinity, `ResourceQuota` (with `scopeSelector` on
  `PriorityClass`), `LimitRange`, `PriorityClass`, plus NetworkPolicy for traffic isolation.
- **Mesh:** per-destination `connectionPool` limits (Istio DestinationRule) are bulkheads on
  the caller side.
- **Queues and databases:** separate queues or topics per workload; per-role connection limits
  in the database; read replicas for analytics so reports can't starve writes.
- **Managed:** managed Kubernetes offers node pools or node groups; managed databases offer read
  replicas and per-user connection limits.

## Example

A batch node pool that only batch uses, a quota on batch-priority pods, and default requests.

```yaml
# Nodes: kubectl taint nodes <node> workload=batch:NoSchedule ; label workload=batch
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata: {name: batch-low}
value: 1000
preemptionPolicy: Never          # waits for room, never evicts the API
description: "Batch and backfill jobs"
---
apiVersion: v1
kind: ResourceQuota
metadata: {name: batch-compute, namespace: batch}
spec:
  hard:
    requests.cpu: "24"
    requests.memory: 96Gi
    count/pods: "60"
  scopeSelector:
    matchExpressions:
    - {scopeName: PriorityClass, operator: In, values: ["batch-low"]}
---
apiVersion: v1
kind: LimitRange
metadata: {name: batch-defaults, namespace: batch}
spec:
  limits:
  - type: Container
    defaultRequest: {cpu: 500m, memory: 1Gi}
    default: {memory: 1Gi}
```

Batch pods also need a toleration for `workload=batch` and a required node affinity on
`workload=batch`, so they land only on their pool. The quota caps what `batch-low` pods in the
namespace can request; it doesn't stop the namespace using another class (that needs the
`limitedResources` admission config). The LimitRange gives defaults so the quota doesn't reject
pods without requests. Quota and priority fields are from the Kubernetes docs; the
`LimitRange` field names are (unverified).

## Review checklist

1. Which resources do the critical and the batch workloads share today: nodes, quota, queues, database connections?
2. Do critical pods have both toleration *and* affinity, so they stay on their pool?
3. Does every namespace with a compute quota also have a LimitRange?
4. Are high priority classes admitted only in namespaces that need them (`limitedResources` plus a matching quota), and is batch `preemptionPolicy: Never` where appropriate?
5. Are code-level pools sized from the infrastructure limit divided by the maximum replica count?
6. Is each partition monitored separately?
7. Is the cost of the reserved capacity written down next to the risk it removes?

## Related

[cells-and-shuffle-sharding](cells-and-shuffle-sharding.md),
[requests-limits-and-autoscaling](requests-limits-and-autoscaling.md),
[rate-limiting-and-throttling](rate-limiting-and-throttling.md) (per-tenant limits),
[`data-pipelines` failure-isolation](../../data-pipelines/references/failure-isolation.md),
[`system-design` capacity-planning](../../system-design/references/capacity-planning.md).

## Sources

Azure [Bulkhead pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead).
Kubernetes: [resource quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/),
[pod priority and preemption](https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/),
[taints and tolerations](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/),
[pod QoS](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/) (read from the
[website source](https://github.com/kubernetes/website/tree/main/content/en/docs)).
Istio [DestinationRule](https://istio.io/latest/docs/reference/config/networking/destination-rule/).
