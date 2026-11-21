# The NALSD method

Non-abstract large system design: turning requirements into a design with numbers on every box,
then iterating until it fits the SLOs, the budget and the failures it must survive. The method
comes from the SRE Workbook chapter
[Non-Abstract Large System Design](https://sre.google/workbook/non-abstract-design/); the
worked example below is this skill's own. Estimation technique is in
[estimation](estimation.md), limits and headroom in [capacity-planning](capacity-planning.md),
failure domains in [scaling-and-failure-domains](scaling-and-failure-domains.md).

## What agents typically get wrong

- **Boxes without numbers.** A diagram of "fetchers → queue → parsers → DB" says nothing about
  whether it works. Every box needs a rate, a size and a count.
- **Requirements stated as adjectives** ("fast", "fresh", "scalable"). Without an SLO sentence
  there is nothing to check an iteration against.
- **Designing for the average.** The design must carry the peak, plus catch-up after an outage,
  plus the loss of a node or zone.
- **Checking storage capacity but not IOPS, bandwidth, connections or memory.** The Workbook's
  example fails on disk operations long before disk space.
- **Choosing batch when the SLO is a freshness bound** shorter than a batch cycle.
- **Stopping at the first design that is possible.** "Possible" ignores hardware; "feasible"
  is the bar, and "resilient" the one after it.
- **Treating rough numbers as commitments.** Estimates exist to reject designs early. Round
  generously, state the assumption, and move on.
- **Putting both replicas in one failure domain**, or multiplying capacity by the number of
  zones without asking how replicas stay in sync.

## Procedure

1. **Write the requirements** with the template below. Get missing numbers from the user or mark
   each guess as an assumption.
2. **Is it possible?** Ignore hardware limits. Does any design meet the SLOs at all? Write the
   simplest one: often one process on one machine.
3. **Can we do better?** Reduce the work itself: skip unchanged items, batch, index, cache a
   computation. Halving the work beats doubling the machines.
4. **Is it feasible?** Size it against real hardware: CPU, memory, disk ops and space, network,
   connections, file descriptors, quotas, budget. Split components where their growth or
   resource profile differs, so each scales alone.
5. **Is it resilient?** Remove a process, a node, a zone, the database primary, a shared
   dependency. Does the SLO still hold, and for how long? What happens to the backlog?
6. **Can we do better again?** Now cost: cheaper interruptible capacity for stateless parts,
   fewer zones if the error budget allows, smaller headroom where scaling is fast.
7. **Record each iteration** with its numbers and the reason it was rejected. The rejections are
   the design rationale; an [`adr`](../../adr/SKILL.md) can hold the final decision.

The phases are not strictly in order. A later check can send you back to step 2.

## Requirements template

| Item | Write it as | Example |
|---|---|---|
| SLOs | "X% of <events> meet <bound> over <window>" | 99% of site results queryable within 1 h of the visit's due time, over 30 days |
| Load | Events per day or second, and what one event costs | 10M site visits/day, 5 page fetches each |
| Load shape | Peak-to-average ratio, bursts, catch-up need | Flat (scheduler-paced), but 2x to drain a backlog |
| Growth | Per month or year, and its driver | +50% sites per year |
| Data size | Bytes per record, records, retention, replication | 1 KB per item, 200M items, 90 days of history |
| Budget | Money per month, or a fixed node or memory cap | ~12 nodes; one 8 GB dev box for development |
| Constraints | Politeness, legal, provider quotas, latency to users, team skill | ≤1 request/s per host; 10-node public-IP quota |
| Failure tolerance | Which domains must be survivable, and at what capacity | Lose any node with no SLO impact; lose a zone degraded |

## Techniques

- **Scientific notation and units on every number** (`5e7 fetches/day`), so a factor of 1,000
  shows up as a wrong exponent. See [estimation](estimation.md).
- **Split by growth axis.** Fetching grows with sites, parsing with changed pages, storage with
  history. One process doing all three must be sized for the worst of each.
- **Shard by the key of the work**, and route records to shards with a log sharder (Workbook).
  Replicate across failure domains, never within one.
- **Use the error budget** to decide how much residual risk to accept, such as two replicas
  failing together (Workbook).
- **Backlog arithmetic.** After an outage of length T at load λ, the backlog is λT. Spare
  capacity S drains it in λT/S. A system with no spare capacity never catches up.

## Example: a crawler that revisits 10M sites a day

**SLO:** 99% of site visits have their results queryable within 1 h of the visit's due time,
over 30 days; 99.5% of sites visited every 24 h. **Assumptions:** 5 fetches per visit, 50 KB
compressed per page, 1 s typical fetch, 5% of fetches hit a 10 s timeout, 20 ms CPU to parse a
page, 20 items per site at 1 KB each, 5% of items change per day.

**Iteration 1: possible?** One machine.

- Fetches: 1e7 × 5 = 5e7/day ÷ 86,400 ≈ **580/s**.
- Mean fetch time W = 0.95 × 1 + 0.05 × 10 = 1.45 s; by Little's law ≈ **840 sockets in flight**
  (1,700 at 2x catch-up). Check that against the process's file-descriptor limit (`ulimit -n`).
- Bandwidth 580 × 50 KB ≈ 29 MB/s ≈ **230 Mbit/s**; 460 Mbit/s at 2x.
- Parse CPU 580 × 0.02 ≈ **12 cores**; 24 at 2x.
- Raw pages 5e7 × 50 KB = **2.5 TB/day**.

A 16-core, 64 GB, 1 Gbps machine is at 75% CPU on average with no room to catch up, fills a
4 TB disk in under two days, and is a single point of failure. Possible, not feasible.

**Iteration 2: better?** Conditional requests (ETag, If-Modified-Since) and a content hash.
Assume 70% of pages are unchanged and answer with a small "not modified".

- Parse CPU falls to 580 × 0.3 × 0.02 ≈ **3.5 cores** (7 at 2x). Bandwidth ≈ 70 Mbit/s.
- Raw store only changed pages: 0.75 TB/day; 7 days in object storage = **5.25 TB** rolling.
- Database: 2e8 items × 1 KB = 200 GB, ~400 GB with indexes. Changes 1e7 rows/day ≈ 116/s;
  "last seen" for all items ≈ 2,300 rows/s unless batched or kept per site instead of per item.

**Iteration 3: feasible?** Split by resource profile on Kubernetes.

| Component | Sizing | Count |
|---|---|---|
| Fetchers (I/O) | 300 connections each; 1,700 peak ÷ 300 = 5.6 | 6 + 2 spare = 8 pods × 0.5 CPU, 512Mi |
| Parsers (CPU) | 7 cores peak ÷ 0.7 target utilization = 10 | 5 + 1 = 6 pods × 2 CPU, 1Gi |
| Queue | 1 h of fetches = 2.1M entries × 1 KB ≈ 2 GB | 1 × 1 CPU, 4Gi |
| Scheduler | One leader, one standby (lease) | 2 × 0.25 CPU |
| Database | 400 GB + history, many writers on several nodes | Postgres on its own 8 vCPU, 32 GB nodes (primary + standby), or managed |

Worker nodes are 4 vCPU, 16 GB, with ~3.5 CPU and ~14 GB allocatable (read the real figure from
the node's `allocatable`). CPU requests: 8 × 0.5 + 6 × 2 + 1 + 2 × 0.25 = 17.5 cores → 5 nodes,
**6 with N+1**. Memory requests: 4 + 6 + 4 + 0.5 = 14.5 GiB against ~70 GB, so CPU is the
dominant resource. The database cannot fit a 3.5-CPU worker, hence its own node pool.

SQLite is ruled out: writers and readers run on several nodes, and its one writer at a time
means a long batch transaction stalls the freshness path. Postgres connections: 4 (writer) +
3 API × 10 + 2 × 2 (scheduler) + 5 (admin) = 43, under the default 100 minus 3 reserved. An
API autoscaled to 10 replicas needs 4 + 100 + 4 + 5 = 113: cap the pools or add a pooler.

DNS: 1e7 hostnames/day ≈ 116 lookups/s; doubled for IPv6 records and multiplied by search-list
expansion under the default `ndots:5` (amplification factor unverified), this can reach ~1,000/s
at the cluster resolver and its upstream. An upstream resolver may enforce a query-rate limit:
find it before the crawl does. Use fully qualified names, a node-local cache, and long
per-host caching.

**Iteration 4: resilient?**

- Node loss: N+1 covers it.
- Zone loss: with every node in one zone, everything stops. Across 3 zones, surviving a zone at
  full catch-up capacity needs 5 nodes in the remaining 2: 3 per zone = **9 workers**, plus 2
  database nodes = 11. That exceeds a 10-public-IP quota: private nodes behind NAT, or a quota
  raise, before the autoscaler's max is set.
- Database primary: a standby in another zone with automated failover; backups and restore
  drills per [`data-integrity`](../../data-integrity/SKILL.md).
- Outage of 4 h: backlog 4 × 3,600 × 580 ≈ 8.3M fetches; 1x spare drains it in 4 h. Served
  oldest first, new visits wait behind the backlog, so about 8 h of visits (3.3M) land over 1 h
  late: 1.1% of the month's 3e8 visits, more than the whole 1% budget. Serving fresh work first
  and the backlog with spare capacity limits it to the 4 h of visits due during the outage:
  0.56%. The 24 h SLO holds either way.

**Iteration 5: better again (cost).** Average load: 3 fetcher pods (840 ÷ 300), parsers at
3.5 ÷ 0.7 = 5 cores, plus queue and scheduler = 8 CPU → 3 nodes. Six workers (2 per zone) leave
4 after a zone loss: above average load, so only catch-up slows. That spends some error budget
in a rare event to save 3 nodes. Fetchers and parsers are stateless and can run on
interruptible capacity; the queue and database cannot.

The arithmetic was checked with a short Python script: 580 fetches/s, 840 in flight, 230
Mbit/s, 3.5 parse cores, 5.25 TB rolling, 17.5 CPU and 14.5 GiB requested, 43 and 113
connections, 8.3M backlog, 1.1% and 0.56% of visits late.

## Migrations as designs

A move (to Kubernetes, from SQLite to Postgres, from one node to many) is a new design with a
known baseline. Size the target before moving.

- **Fill the template from measurements** of the current system: peak rates, resident memory
  per process, data size and growth, the longest transactions, connection counts.
- **List the limits that change shape.** One SQLite writer becomes a Postgres connection limit
  and network round trips per query; one machine's memory cap becomes per-pod requests and
  limits; local disk becomes a volume class with its own operations and throughput limits; one
  cron becomes distributed scheduling (see [scaling-and-failure-domains](scaling-and-failure-domains.md)).
- **Size the transition itself:** both systems running at once, a full data copy plus space
  for a restore, backfill or dual-write load on top of live traffic, and the rollback path.
- **Cutover mechanics** are elsewhere: schema and data moves in
  [`engineering-practices`](../../engineering-practices/references/database-migrations.md)
  database-migrations, storage placement and restore drills in `data-integrity`'s
  [state-and-storage](../../data-integrity/references/state-and-storage.md).

## Gotchas and contested points

- The Workbook's numbers are deliberately rounded and not all consistent. Copy its method,
  not its figures.
- "Within 1 h" usually hides two SLOs: the processing latency and the age of the oldest queued
  item. The second is what breaks after an outage; alert on it.
- Interruptible capacity is cheap until all of it is reclaimed at once. Keep enough on-demand
  capacity for average load.
- Over-designing is a failure too. If one node with a restore plan meets the SLO and its error
  budget, the cluster is cost without benefit.

## Review checklist

1. Is every requirement written as a number: SLO sentences, load, shape, growth, data, budget?
2. Does every component have a rate, a size and a count, with the arithmetic shown?
3. Was the work itself reduced before machines were added?
4. Was each resource checked: CPU, memory, disk ops and space, bandwidth, connections, file
   descriptors, quotas?
5. Is there capacity for peak plus catch-up, and is the backlog drain time computed?
6. Was the design re-checked with a node, a zone, the database primary and each shared
   dependency removed?
7. Does every replica sit in a different failure domain from its peer?
8. For a migration, was the target sized from measured baseline numbers, including the
   capacity the transition needs (both systems, the data copy, backfill load)?
9. Are rejected iterations and their reasons recorded?

## Related

[estimation](estimation.md), [capacity-planning](capacity-planning.md),
[scaling-and-failure-domains](scaling-and-failure-domains.md);
[`data-pipelines`](../../data-pipelines/SKILL.md) for the crawler's correctness;
`architecture-review` for reviewing a finished design; `infrastructure-patterns` for choosing a
queue, cache or replica.

## Sources

SRE Workbook, [Non-Abstract Large System Design](https://sre.google/workbook/non-abstract-design/);
SRE book, [Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/)
(N+2 planning); [SQLite: Appropriate Uses](https://www.sqlite.org/whentouse.html);
[PostgreSQL connection settings](https://www.postgresql.org/docs/current/runtime-config-connection.html);
Kubernetes, [DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
and [NodeLocal DNSCache](https://kubernetes.io/docs/tasks/administer-cluster/nodelocaldns/).
