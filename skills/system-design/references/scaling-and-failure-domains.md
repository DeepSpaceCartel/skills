# Scaling and failure domains

Designing for failure before it happens: finding single points of failure, placing replicas in
separate failure domains, treating overload and cascading failure as inputs to sizing,
choosing how load is balanced, deciding when consensus or leader election is needed, and
scheduling periodic work across many machines. Anchor sources: the SRE book chapters on
[frontend](https://sre.google/sre-book/load-balancing-frontend/) and
[datacenter](https://sre.google/sre-book/load-balancing-datacenter/) load balancing,
[handling overload](https://sre.google/sre-book/handling-overload/),
[cascading failures](https://sre.google/sre-book/addressing-cascading-failures/),
[managing critical state](https://sre.google/sre-book/managing-critical-state/) and
[distributed cron](https://sre.google/sre-book/distributed-periodic-scheduling/); the SRE
Workbook's [Managing Load](https://sre.google/workbook/managing-load/); and the AWS
resilience analysis framework's
[mitigation strategies](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/mitigation-strategies.html).
The mechanics of timeouts, retry budgets and load shedding are in
[`engineering-practices`](../../engineering-practices/references/reliability.md) reliability;
this page decides where they are needed and what they cost in capacity.

## What agents typically get wrong

- **Redundant compute in front of one of everything else:** one database, one queue, one DNS
  resolver, one NAT gateway, one scheduler, one credential.
- **Replicas in the same failure domain**: two pods on one node, three nodes in one zone, a
  standby on the same volume.
- **A single-writer store on the hot path.** SQLite allows one writer at a time; one long batch
  transaction (a rebuild, a backfill) stalls every other writer for its whole length.
- **Ignoring external limits on shared dependencies.** Cluster DNS forwards to an upstream
  resolver, which may enforce a query-rate limit; if it does, under crawl load every pod's
  lookups time out together. Find the limit before the load does.
- **Sizing for steady state only.** A lost zone shifts its load onto the rest; if they were at
  80%, they are now over 100% and fail in turn.
- **Health checks that kill slow-starting tasks** during recovery, turning overload into a
  crash loop.
- **Heartbeats and timeouts for leader election.** Under a slow or lossy network both sides
  decide they lead (split brain).
- **Consensus where none is needed**, or a two-node "cluster" that cannot form a majority after
  one failure.
- **Every node running the same cron job**, or all jobs scheduled at midnight.

## Procedure

1. **Draw the request and data paths** end to end, including DNS, NAT, identity, secrets, the
   scheduler and the deploy pipeline.
2. **Mark every component with one instance or one location.** Each is a single point of
   failure. For each, either add redundancy in another failure domain, or degrade gracefully
   without it, or accept it with the error budget and a recovery time.
3. **List the failure domains** (process, node, rack, zone, region, provider, account,
   shared dependency) and say which of each the design survives and at what capacity.
4. **Size for the loss of the largest domain you must survive**: the remaining capacity must
   carry peak load. Treat that capacity as the design's real ceiling.
5. **Write the overload behaviour** for each tier: what it rejects first, how clients learn to
   back off, and how it recovers from zero (cold caches, slow start).
6. **Choose load balancing** per hop (table below).
7. **Decide whether any state needs a single owner.** If yes, use a proven consensus service or
   a lease from one, not hand-built heartbeats.
8. **Place periodic jobs**: one launcher, a recorded launch, idempotent or queryable jobs, and
   spread start times.

## Techniques

**Overload and cascading failure as design inputs** (SRE book)

- Capacity per task is measured in resources (CPU), not requests per second.
- Plan headroom so a lost cluster or zone does not overload the rest: for example, 4,000/s
  peak at 1,000/s per cell needs 4 cells, 5 for N+1, 6 for N+2.
- Keep server queues short relative to threads; long queues turn overload into latency for
  everyone instead of fast rejections.
- Know which caches are for latency (the service survives them empty) and which are for
  capacity (it does not). A capacity cache needs warm-up time in the recovery plan.
- Retries multiply load at each layer that retries; allow them at one layer (see
  `engineering-practices` reliability).
- Scaling frontends can overload the database behind them; size the autoscaler's max by the
  downstream (Managing Load).
- Use shedding thresholds above autoscaling triggers so the system scales before it rejects.

**Load-balancing choices**

| Hop | Option | Use when | Watch for |
|---|---|---|---|
| Users to sites | DNS | coarse geography, site failover | cached answers ignore changes for the TTL or longer; the resolver, not the user, is located |
| Into a site | Virtual IP / network load balancer | one address, many backends | needs connection-stable hashing as the pool changes |
| Request routing | Layer-7 proxy | per-request policy, retries, lame-duck drain | proxy is itself a tier to size and replicate |
| Service to service | Client-side, with subsetting | many clients and backends | random subsets load backends unevenly; use deterministic subsets |
| Sticky or sharded work | Consistent hashing | caches, per-key state | hot keys; rebalancing on pool change moves only a fraction of keys |

Policies: plain round robin can leave a 2x spread in backend load; least-loaded can send a flood
to a backend that fails fast (count recent errors as load); weighted by backend-reported
utilization narrows the spread (SRE book). Drain backends with a lame-duck state before
shutdown.

**Consensus and leader election**

- Needed when exactly one actor must own something: a leader, a lock, a lease, group
  membership, an ordered log of critical state. Not needed for stateless replicas or for work
  made idempotent and keyed.
- Use an existing consensus system (etcd, ZooKeeper, Consul) or a lease built on one, rather
  than writing one.
- 2f+1 replicas survive f failures: 3 survive one (not maintenance plus a failure), 5 survive
  two. An even count adds cost without adding tolerance.
- Each commit costs a quorum round trip plus a durable log write; across regions that caps a
  sequential stream at tens of operations per second. Batch, or keep the quorum close.
- Locks are leases with expiry. A holder that loses its lease must stop acting immediately.
- Consensus replicas are not backups: a bad write reaches all of them.

**Distributed periodic scheduling** (SRE book, distributed cron)

- Decide per job whether a skipped run or a double run is worse. Usually a skip is easier to
  recover from; prefer it.
- One leader launches; it records the launch before and after acting, so a successor can tell
  what already ran.
- Give each run a name derived from its scheduled time, so a launch can be checked and is safe
  to repeat.
- Spread start times: hash the job's identity into its allowed window instead of everyone using
  minute 0 or midnight.

## Example

A design review of a crawler on 8 nodes finds: one Postgres primary (SPOF), one scheduler pod
(SPOF), all nodes in one zone (shared fate), cluster DNS forwarding to one upstream resolver.
Fixes, in order of risk: spread workers across 3 zones and size for losing one (3 per zone at
full catch-up, or 2 per zone accepting slower catch-up); a Postgres standby in another zone with
automated failover; two scheduler replicas with a lease, each run named `site-id@due-time` so a
double launch is a no-op; a node-local DNS cache, fully qualified hostnames, and the
upstream's query limit, if it has one, added to the limits inventory. Arithmetic for the cheaper
option: 6 workers lose 2 with a zone, leaving 4 × 3.5 = 14 CPU against 8 CPU of average demand
and 17.5 at full catch-up, so the SLO holds for new work and only the backlog drains more
slowly (figures from [nalsd-method](nalsd-method.md)). Exercise it with a zone drain before
relying on it.

## Gotchas and contested points

- Graceful degradation is a design, not an accident: decide what can be turned off (a widget, a
  report) to protect the core path (AWS framework).
- More zones raise resilience and cost, and add cross-zone traffic and latency. Use the error
  budget to choose.
- A failover mechanism that never runs is a SPOF in disguise. Exercise it.
- Overriding health checks during a crash loop can help recovery; build the switch in advance.
- Global control planes (DNS providers, identity, a cloud's management API) are shared
  dependencies; prefer depending on data planes at run time (AWS framework).

## Review checklist

1. Has every single-instance or single-location component been listed, including DNS, NAT,
   scheduler, secrets and the deploy path, with a decision for each?
2. Are replicas spread across failure domains, and does losing the largest required domain
   leave enough capacity for peak?
3. Is there a single-writer store on a path with an SLO, and can a long transaction on it
   stall other writers?
4. Are external limits of shared dependencies (upstream DNS, provider APIs, rate limits)
   known and below projected load?
5. Is the overload behaviour written per tier: what is rejected, how clients back off, and how
   the tier recovers from cold?
6. Is each load-balancing hop's choice justified, with drain and uneven-load behaviour covered?
7. Where a single owner is needed, is it a lease from a proven consensus system with an odd
   replica count?
8. Is each periodic job launched once, named by its scheduled time, idempotent or checkable,
   and spread in time?

## Related

[nalsd-method](nalsd-method.md), [capacity-planning](capacity-planning.md);
[`engineering-practices`](../../engineering-practices/references/reliability.md) reliability
(timeouts, retries, shedding mechanics);
[`data-pipelines`](../../data-pipelines/references/failure-isolation.md) failure-isolation
(per-source limits, backlogs); [`infrastructure-patterns`](../../infrastructure-patterns/SKILL.md) (choosing a queue, replica or cache);
[`architecture-review`](../../architecture-review/SKILL.md) (reviewing an existing design).

## Sources

SRE book: [Load Balancing at the Frontend](https://sre.google/sre-book/load-balancing-frontend/),
[Load Balancing in the Datacenter](https://sre.google/sre-book/load-balancing-datacenter/),
[Handling Overload](https://sre.google/sre-book/handling-overload/),
[Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/),
[Managing Critical State](https://sre.google/sre-book/managing-critical-state/),
[Distributed Periodic Scheduling with Cron](https://sre.google/sre-book/distributed-periodic-scheduling/);
SRE Workbook, [Managing Load](https://sre.google/workbook/managing-load/); AWS Prescriptive
Guidance, [resilience analysis framework: mitigation strategies](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/mitigation-strategies.html);
[SQLite: Appropriate Uses](https://www.sqlite.org/whentouse.html) and
[Write-Ahead Logging](https://www.sqlite.org/wal.html); Kubernetes,
[NodeLocal DNSCache](https://kubernetes.io/docs/tasks/administer-cluster/nodelocaldns/).
