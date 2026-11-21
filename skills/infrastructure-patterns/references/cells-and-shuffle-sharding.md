# Cells and shuffle sharding

## Problem

Redundancy protects against machines and zones failing. It doesn't protect against failures
every replica shares: a bad deploy, a poison request that crashes whichever worker handles it,
one tenant's traffic flood, a configuration push. In a single shared fleet, those reach every
customer. Cells and shuffle sharding limit the **blast radius**: the share of customers any one
such failure can reach.

## When to use / when NOT to use

- **Cells** when a full outage is unacceptable and the workload divides naturally by a key
  (tenant, account, resource) with little cross-key traffic; when one fleet is approaching a
  scaling limit; when tenants need isolation or different update cadences (Azure's Deployment
  Stamps lists these).
- **Shuffle sharding** when one client's bad traffic or poison requests can take down the
  workers that serve it, and clients can retry against other workers in their shard.
- **Not** for a small system that scales fine as one deployment, or when every instance must
  hold all the data (Azure points to geodes or plain sharding instead).
- **Not** when the work is inherently cross-key (global search, a social graph) unless that
  part stays out of the cells.
- **Cost:** stamps duplicate infrastructure, and Azure calls the cost increase substantial;
  AWS notes cells can also just regroup the same hosts behind a router.

## How it works

**Cells (stamps, scale units).** Independent copies of the whole stack, each with its own
compute and data, sharing nothing but a thin router. AWS's Well-Architected guidance:

- **Partition key** aligned with the service's natural grain (customer ID, resource ID),
  present in every request, so cells rarely talk to each other.
- **Router** is the one shared component, so it stays as simple as possible: no business logic,
  a cheap deterministic mapping (hash plus modulo, or a lookup table), horizontally scalable.
- **Fixed maximum cell size,** found by load testing a cell to its breaking point and keeping
  a margin below it. Grow by adding cells, not by growing them.
- **Stable mapping,** with a planned migration path when one tenant outgrows a cell.
- **Deploy in waves,** one cell first, so a bad change hits one cell.
- **Each cell spans zones** for ordinary failures.

With 8 cells of equal size, one cell's failure leaves 7/8 (87.5%) of requests untouched. Azure adds: run at least two
stamps from the start (one stamp lets single-instance assumptions creep in), plan cross-stamp
reporting, and keep stamp configuration from drifting.

**Shuffle sharding.** Instead of fixed shards, give each client its own small, random
combination of k workers out of n. Two clients rarely get the same combination, so a client
that breaks its k workers leaves almost every other client with at least one healthy worker.
The number of distinct shards is C(n, k), which grows fast:

| n workers | k per shard | Distinct shards | Another client fully overlapped | Shares no worker |
|---|---|---|---|---|
| 12 | 3 | 220 | 0.5% | 38.2% |
| 40 | 4 | 91,390 | 0.001% | 64.5% |

(Overlap odds for one other client picked at random: C(k,j) x C(n-k,k-j) / C(n,k).) A
fixed-shard design with 12 workers in 4 shards of 3 would put 25% of clients in the blast
radius. Clients must retry across their shard's workers for this to work (AWS).

Shuffle sharding applies at any layer that assigns clients to capacity: worker pools, queues
(hash each tenant to a few of many queues; see [`data-pipelines` failure-isolation](../../data-pipelines/references/failure-isolation.md)),
endpoints in DNS, ingest partitions.

## Failure modes and what agents get wrong

- **A fat router.** Auth, throttling, feature logic and tenant lookups in the router make it
  the new single point of failure. AWS lists complex router logic as an anti-pattern.
- **Cells that share a database, a queue, a cache or a config service.** Then they are one cell.
- **Deploying to all cells at once,** which removes the main benefit.
- **Unbounded cell growth.** A cell that keeps growing becomes the old monolith.
- **A partition key with heavy cross-cell traffic,** which recouples the cells.
- **Shuffle sharding without client retries,** so the healthy worker in a shard is never tried.
- **Assuming cells give regional redundancy.** Azure: stamps are independent but not
  redundant; tenants on a stamp in a failed region are down until it recovers or they move.
- **Counting the router out.** It needs its own redundancy, capacity and static stability.

## Implementation notes

- **Kubernetes:** one cluster or namespace set per cell (separate clusters isolate the control
  plane too); the router as a small stateless gateway or DNS per cell
  (`cell-07.api.example.com`); GitOps with one deployment wave per cell.
- **Envoy/Istio/NGINX/HAProxy:** route on a tenant header or hostname to a per-cell upstream;
  keep the tenant-to-cell table in a replicated store the router caches.
- **Queues and workers:** shuffle-shard tenants onto a few of many queues; consumers per queue.
- **Managed:** separate accounts, projects or subscriptions per cell also separate quotas and
  IAM; Azure notes subscription-wide quotas can force spreading stamps across subscriptions.

## Example

A SaaS API moving from one fleet to cells. Router config (NGINX) maps tenants to cells by a
precomputed table; unknown tenants are refused, not guessed.

```nginx
map $http_x_tenant_id $cell_upstream {
    include /etc/nginx/tenant-cells.map;   # generated: "t_8f3a  cell_02;" one line per tenant
    default "";                            # unmapped: refuse below, never a moving default
}
upstream cell_01 { server cell-01.internal:443; }
upstream cell_02 { server cell-02.internal:443; }
upstream cell_03 { server cell-03.internal:443; }
upstream cell_04 { server cell-04.internal:443; }

server {
    listen 443 ssl;
    location / {
        if ($cell_upstream = "") { return 421; }   # tenant not placed yet
        proxy_pass https://$cell_upstream;   # no auth, no business logic here
    }
}
```

Each cell is sized by load test to 2,000 tenants with 30% margin and is spread across three
zones. The control plane places each new tenant in a cell with room and writes the map line
at signup, so a tenant's cell never changes by accident. Deploys go to the least-loaded cell
first, then one cell per day. The `map` include, `if`/`return 421` and variable `proxy_pass`
are (unverified) against NGINX docs; the design rules are AWS's and Azure's.

## Review checklist

1. What is the partition key, and is it in every request with little cross-key traffic?
2. Is the router thin, redundant and free of business logic, with a cached mapping that survives its store being down?
3. Do cells share anything besides the router (database, queue, cache, config, credentials)?
4. Is there a tested maximum cell size, and a rule for when to add a cell?
5. Do deploys and config pushes go out one cell (or one wave) at a time?
6. Is there a tenant migration path between cells?
7. For shuffle sharding: are shards drawn from enough workers, and do clients retry across their shard?
8. What is the blast radius of one bad deploy, one poison request and one noisy tenant, as a share of customers?

## Related

[bulkheads-and-isolation](bulkheads-and-isolation.md), [redundancy-and-failover](redundancy-and-failover.md),
[graceful-degradation-and-static-stability](graceful-degradation-and-static-stability.md),
[rate-limiting-and-throttling](rate-limiting-and-throttling.md),
[`data-pipelines` failure-isolation](../../data-pipelines/references/failure-isolation.md),
[`architecture-review` failure-mode-analysis](../../architecture-review/references/failure-mode-analysis.md).

## Sources

AWS Well-Architected, [REL10-BP03 Use bulkhead architectures](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel10-bp03.html);
AWS whitepaper, [What is a cell-based architecture?](https://docs.aws.amazon.com/wellarchitected/latest/reducing-scope-of-impact-with-cell-based-architecture/what-is-a-cell-based-architecture.html)
and [introduction](https://docs.aws.amazon.com/wellarchitected/latest/reducing-scope-of-impact-with-cell-based-architecture/reducing-scope-of-impact-with-cell-based-architecture.html).
AWS Builders' Library, [Workload isolation using shuffle-sharding](https://builder.aws.com/content/3F06NpJ8YeoIGP8VHTw4n81pFn8/workload-isolation-using-shuffle-sharding).
Azure [Deployment Stamps pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/deployment-stamp)
and [Bulkhead pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead).
AWS [resilience analysis framework mitigations](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/mitigation-strategies.html).
