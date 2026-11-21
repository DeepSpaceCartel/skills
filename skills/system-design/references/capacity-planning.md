# Capacity planning

Making sure the design has enough of every resource at peak, with a failure, until a known
date: headroom, an inventory of hard limits, memory budgets under a fixed cap, Kubernetes
requests and limits, autoscaler ceilings and provider quotas, and the runway date. Anchor
sources: the Kubernetes docs on
[resource management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
and [node-pressure eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/),
the [cluster autoscaler FAQ](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/FAQ.md),
and the SRE material on [managing load](https://sre.google/workbook/managing-load/) and
[cascading failures](https://sre.google/sre-book/addressing-cascading-failures/). Volume
sizing for data safety (WAL peaks, restore space, time-to-full) is in
[`data-integrity`](../../data-integrity/SKILL.md) state-and-storage; this page sizes it as one
limit among many.

## What agents typically get wrong

- **No memory budget on a shared box.** A workspace or single node with a fixed cap runs an
  editor, several agent sessions, an API and batch jobs. Each fits alone; two heavy jobs at
  once exceed the cap and the OOM killer takes whatever scores highest, often the editor or
  the API.
- **Ceilings found by hitting them.** The autoscaler's max size is set to 50 while the provider
  allows 10 public IPs, 20 vCPUs or 8 volumes per node. Nobody listed the limits.
- **Limits only on the obvious resource.** CPU and RAM are checked; file descriptors, database
  connections, conntrack entries, IP addresses, inodes, API rate limits and DNS query rates
  are not.
- **Requests set to typical use, limits far above.** The scheduler packs by requests, so the
  node is overcommitted and every pod bursts at once at peak.
- **Memory limit without a request,** or the reverse. A limit alone copies into the request; a
  request alone leaves no upper bound.
- **Sizing a volume for today's data,** not data plus WAL peak plus a restore copy plus growth
  to the next review.
- **Headroom only for load,** none for losing a node, a rollout's surge pods, or catch-up.
- **No date.** "We have room" without "until when, at the current growth".

## Procedure

1. **Inventory every limit** (table below) for each component, with its current use and its
   source: a quota page, a config value, a kernel setting.
2. **Compute peak demand** per limit from [estimation](estimation.md), including amplifiers,
   catch-up and rollout surge.
3. **Add failure headroom:** N+1 means losing one unit still carries peak; N+2 tolerates two
   (the SRE book's cascading-failures chapter plans clusters for N+2). A common reading is one
   unit in maintenance plus one failure (unverified as the book's own rationale).
4. **Write the memory budget** for any fixed-size host: each process's peak resident memory ×
   count, plus the OS, plus a margin. Mark which jobs are heavy and allow one at a time.
5. **Set Kubernetes requests from measured peak use** and limits from the budget. Memory: set
   the request equal to the limit for anything whose death hurts.
6. **Check the autoscaler's maximum against every quota** it depends on: nodes, vCPUs, IPs,
   volumes, load balancers. The max must be the smallest of them, minus a margin.
7. **Compute the runway date** for each limit and put the earliest in the plan.
8. **Set a review cadence** and alerts at a fraction of each limit. Re-plan on a fixed
   interval (monthly or quarterly), and also when growth deviates from the forecast, a launch
   or migration changes the load profile, a limit's runway drops below the lead time to raise
   it (a quota request, a purchase), or an incident shows an unlisted limit.

## Techniques

**The limits inventory**

| Limit | Where it lives | Typical way it bites |
|---|---|---|
| Node memory / container cap | node size, cgroup limit | OOM kill of the highest-scoring process |
| CPU | node size, cgroup limit | throttling, latency, health-check timeouts |
| Disk space and inodes | volume size, filesystem | write failures, eviction at the kubelet threshold |
| Disk operations / throughput | volume class, disk type | latency long before space runs out |
| File descriptors | per-process and system limits | accept or connect failures under fan-out |
| Database connections | server setting (Postgres default 100, 3 reserved for superusers; restart to change) | errors once replicas × pool exceeds it |
| Network bandwidth, NAT ports, conntrack | NIC, gateway, kernel table | dropped packets, DNS timeouts |
| Provider quotas | account or project quota page | autoscaler cannot add nodes |
| Shared dependency rates | an upstream resolver, an API's rate limit | throttling that looks like our bug |
| Autoscaler capability | its documented tested scale | slow or failed decisions past it |

**Memory budget under a fixed cap.** Example: an 8 GB development box.

| Consumer | Peak | Count | Total |
|---|---|---|---|
| Editor and language servers | 2.0 GB | 1 | 2.0 GB |
| Agent sessions | 0.6 GB | 3 | 1.8 GB |
| API and UI dev servers | 0.45 GB | 2 | 0.9 GB |
| OS, sidecars | 0.3 GB | 1 | 0.3 GB |
| **Baseline** | | | **5.0 GB** |
| Heavy job slot (test suite, rebuild, browser) | 2.5 GB | 1 | 2.5 GB |
| **Margin** | | | **0.5 GB** |

One heavy slot fits. A second heavy job is 2 GB over the cap. Rules that follow: one heavy job
at a time, a lock or queue that enforces it, bulk work moved to a cluster, and fewer parallel
agents when the slot is in use.

**Kubernetes requests and limits** (from the Kubernetes docs)

- The scheduler places pods by **requests** against the node's **allocatable** (capacity minus
  system reservations), not by actual use. A pod stays `Pending` with `FailedScheduling` if no
  node fits its requests.
- **CPU over its limit is throttled**, never killed. **Memory over its limit may be OOM-killed**:
  enforcement is reactive, so use can briefly exceed the limit. The container shows
  `OOMKilled`, exit code 137, and restarts per its restart policy; repeated kills become a
  crash loop.
- A limit without a request copies the limit into the request.
- Memory-backed `emptyDir` counts as container memory, up to the pod's limit unless it has a
  `sizeLimit`.
- **Node pressure** is separate. The kubelet evicts pods when node memory falls below its
  threshold (default `memory.available<100Mi` on Linux), first those using more than their
  requests, then by priority. If memory rises faster than the kubelet polls, the kernel's OOM
  killer acts first, and it favours killing pods of lower QoS with high use relative to their
  request. Reserve system memory (`systemReserved` sized to include the eviction threshold) so
  the scheduler doesn't pack pods that trigger eviction at once.

**Autoscaler ceilings** (cluster autoscaler FAQ)

- It adds nodes for pods that cannot be scheduled, judged by their requests, not by
  utilization.
- It never grows a node group past its configured max. When the provider refuses (quota), it
  falls back, backs off per node group (5 min initial, up to 30 min) and keeps retrying; the
  pods stay `Pending`.
- Nodes that don't register within 15 min are given up on.
- Scale-down needs node requests under 50% of allocatable for 10 min and movable pods; local
  storage, restrictive PodDisruptionBudgets and `safe-to-evict: "false"` block it.
- Documented scale: tested to 1,000 nodes of ~30 pods.

Horizontal pod autoscalers have the same shape: a max replica count that must respect the
downstream's limits (connections, rate limits), not just the node pool (Managing Load).

**The runway date.** For each limit: `days = (limit × alert_fraction − current) ÷ growth per
day`. Use growth measured over at least a few weeks, and the peak, not the average.

## Example

A Postgres volume of 2 TB holds 1.1 TB and grows 12 GB/day; the plan alerts at 80%.
Runway = (2,000 × 0.8 − 1,100) ÷ 12 ≈ **42 days**. A restore copy for a drill needs another
1.1 TB, so that volume can't host it: the drill needs separate space now. The API autoscaler's
max of 12 replicas × 10 connections = 120 exceeds the 97 usable connections: the ceiling is
the database, at the tenth replica, so cap the max at 9 or add a pooler. The node pool's max of
15 needs 15 public IPs against a quota of 10: the real ceiling is 10 nodes. The checks were
done with a short calculation; the earliest runway (connections: already exceeded at max) goes
first in the plan.

## Gotchas and contested points

- Memory limits equal to requests waste memory when use varies; limits far above requests
  overcommit the node. For stateful or user-facing pods, prefer equal; for batch, a modest gap
  with low priority.
- CPU limits are debated: they make latency predictable but throttle bursts even on idle nodes.
  Many teams set CPU requests and omit CPU limits (practitioner view, unverified); set memory
  limits regardless.
- An autoscaler that scales on CPU grows the fleet when a bug burns CPU, until the quota
  stops it (Managing Load). The quota is the last safety; set the max below it on purpose.
- Scale-up is riskier than scale-down: too little capacity drops traffic. Keep a minimum per
  zone so failover has room (Managing Load).
- Shared caps include tools: an editor, a language server and a browser count against the same
  budget as the services.

## Review checklist

1. Is there a limits inventory per component, with current use and the source of each limit?
2. On any host with a fixed memory cap, is there a written budget, and is the number of
   concurrent heavy jobs enforced?
3. Do memory requests and limits come from measured peak use, and are critical pods' requests
   equal to their limits?
4. Is the autoscaler's maximum below every provider quota it depends on (nodes, vCPUs, IPs,
   volumes)?
5. Do replica maxima respect downstream limits such as database connections and rate limits?
6. Is headroom sized for peak plus one failed unit (N+1, or N+2 with maintenance), plus rollout
   surge?
7. Is each volume sized for data plus WAL peak plus a restore copy plus growth to the next
   review?
8. Does every limit have a runway date and an alert before it?

## Related

[estimation](estimation.md), [scaling-and-failure-domains](scaling-and-failure-domains.md);
[`data-integrity`](../../data-integrity/SKILL.md) (volume sizing, ephemeral-storage evictions);
[`helm-charts`](../../helm-charts/SKILL.md) (where requests and limits are templated);
`infrastructure-patterns` (choosing node pools, poolers, managed services).

## Sources

Kubernetes, [Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
and [Node-pressure Eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/);
[Cluster Autoscaler FAQ](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/FAQ.md);
SRE Workbook, [Managing Load](https://sre.google/workbook/managing-load/); SRE book,
[Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/);
[PostgreSQL connection settings](https://www.postgresql.org/docs/current/runtime-config-connection.html).
