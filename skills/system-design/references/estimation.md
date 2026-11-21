# Back-of-the-envelope estimation

Getting a number within a factor of two or so, fast enough to reject a design before building
it: request rates from daily volume, storage growth, bandwidth, disk operations, memory,
connections and concurrency. The method follows the SRE Workbook's
[NALSD chapter](https://sre.google/workbook/non-abstract-design/) and the SRE book's
[Handling Overload](https://sre.google/sre-book/handling-overload/); latency ballparks are
from the widely circulated
[latency numbers list](https://gist.github.com/jboner/2841832) credited to Jeff Dean and Peter
Norvig (circa 2012); Little's law is a standard queueing result
([summary](https://en.wikipedia.org/wiki/Little%27s_law)).

## What agents typically get wrong

- **Bits versus bytes.** Network links are quoted in bits per second, disks and objects in bytes.
  A factor of 8 lost silently.
- **MB versus MiB, and Kubernetes `m`.** `400m` of memory is 0.4 bytes, not 400 MB; use `Mi` or
  `M` (Kubernetes docs). The 5% gap between MB and MiB is noise; the `m` mistake is not.
- **Daily volume ÷ 86,400 as the design load.** That is the average. Real traffic has a daily
  peak, bursts, and catch-up after outages.
- **QPS as the capacity unit.** Requests vary in cost by orders of magnitude, and the mix shifts.
  Measure capacity in the resource that runs out, usually CPU (SRE book, Handling Overload).
- **Forgetting multipliers:** replicas, indexes, retries, page fetches per logical item, DNS
  lookups per fetch, read amplification, write-ahead logs.
- **Capacity without operations.** 100 TB fits on a few dozen disks but may need thousands of
  disks' worth of random operations (Workbook).
- **Per-process memory without the count.** 300 MB per worker is fine; 300 MB × 16 workers × 3
  replicas on one node is not.
- **False precision.** Four significant figures on a guess. Round to one or two, upward for
  costs and downward for capacities.
- **Mean latency in Little's law when the tail dominates.** A few slow requests set the
  concurrency.

## Procedure

1. Write each input with its unit and its source: measured, given, or assumed.
2. Convert everything to per-second rates and bytes, in scientific notation.
3. Multiply out the amplifiers: per-item fan-out, replication, retries, indexes.
4. Apply the peak factor and the catch-up factor separately; record both.
5. For each resource, divide demand by per-unit capacity, then by the target utilization
   (headroom), then round up to whole units.
6. Sanity-check against one real measurement if any exists: a benchmark, current metrics, a
   bill.
7. Write the dominant term. That is the resource the design will run out of first.

## Techniques

**Conversions worth knowing**

| Quantity | Value | Use |
|---|---|---|
| Seconds per day | 86,400 ≈ 1e5 (rounding up underestimates rate by ~14%) | rates from daily volume |
| Seconds per 30 days | ~2.6e6 | monthly volume, error budgets |
| 1 Gbit/s | 125 MB/s before protocol overhead | NIC and link sizing |
| 1 M requests/day | ~12/s average | quick conversion |
| 99.9% over 30 days | 43.2 min of failure | budgets |

**Peak factors.** Use measured peak-to-average from metrics (p99 of per-minute rate ÷ daily
mean). If none exists, state an assumption and size for it explicitly. Scheduled work
(crawls, batch) can be flat if the scheduler paces it, but then needs a catch-up factor: the
spare capacity that drains an outage's backlog within the SLO. Top-of-hour and midnight bursts
appear whenever many clients schedule by the clock (see the cron section of
[scaling-and-failure-domains](scaling-and-failure-domains.md)).

**Little's law: L = λW.** Average items in a system equal arrival rate times average time in
it. It holds for any stable system regardless of arrival distribution or service order, and for
any subsystem. Three uses:

| Want | Formula | Example |
|---|---|---|
| Concurrency (sockets, threads, DB connections) | λ × W | 500 req/s × 0.2 s = 100 in flight |
| Wait from a queue | queue length ÷ drain rate | 2.1M queued ÷ 580/s = 1 h |
| Throughput a pool can carry | pool size ÷ W | 20 connections ÷ 50 ms = 400 queries/s |

Use the mean that includes the tail: if 5% of calls take 10 s and the rest 1 s, W is 1.45 s,
not 1 s. Little's law needs a stable system; if arrivals exceed capacity, the queue grows
without bound and W is not defined.

**Storage growth.** Bytes per record × records × replication × (1 + index overhead) + history
rate × retention. Then add what the volume needs beyond data: see
[capacity-planning](capacity-planning.md) and [`data-integrity`](../../data-integrity/SKILL.md)'s state-and-storage reference.

**Memory.** Per-process resident set × processes per node, plus caches, plus the queue's
in-memory backlog at its cap, plus memory-backed `emptyDir` (Kubernetes counts it as container
memory).

**Connections.** Per client pool × client replicas at the autoscaler's maximum, not today's
count. Compare with the server's limit minus its reserved slots.

## The ballpark sheet (orders of magnitude)

Rough tiers from the 2012 list and the SRE material, regrouped by this skill. Modern hardware
differs (current figures unverified here); use them to compare options, then measure.

| Order of magnitude | Operations at that scale |
|---|---|
| ~1 ns | CPU cache hit, branch |
| ~100 ns | main-memory access, uncontended lock |
| ~1–10 µs | compress 1 KB, send 1 KB on a 1 Gbit link |
| ~100 µs | random 4 KB SSD read; read 1 MB from memory |
| ~0.5–1 ms | round trip inside one datacenter; read 1 MB sequentially from SSD; durable log write (1 to several ms) |
| ~10 ms | hard-disk seek (so ~100–200 random ops/s per disk; the Workbook uses 200 IOPS); read 1 MB from a hard disk |
| ~50–150 ms | round trip across a continent (~45 ms) or an ocean (~70–150 ms) |

Consequences that survive hardware changes: memory beats disk by orders of magnitude,
sequential beats random, and a cross-region round trip caps a sequential protocol at tens of
operations per second per stream (the Workbook: ~25 ms per consensus operation, ~40 sequential
operations/s per process).

## Example

Size an API that serves 30M requests/day, measured peak 3x average, 20 ms CPU per request,
80 ms mean latency including the tail, a pool of 10 database connections per replica.

```python
avg = 30e6 / 86_400          # 347 req/s
peak = avg * 3               # 1,042 req/s
cores = peak * 0.020         # 20.8 cores busy at peak
cores_at_target = cores / 0.6   # 34.7 cores at 60% target utilization
in_flight = peak * 0.080     # Little: 83 requests in flight
replicas = -(-cores_at_target // 4)   # 4-core replicas, rounded up -> 9
conns = replicas * 10        # 90 DB connections, against a limit of 100 - 3 reserved
```

The script printed 347, 1,042, 20.8, 34.7, 83, 9 and 90. The dominant resource is CPU; the
next limit is database connections, which run out at the tenth replica, so the autoscaler's
maximum or the pool size must change before growth does.

## Gotchas and contested points

- The 2012 numbers are often quoted as current. Treat them as ratios, not as specifications.
- Peak factors vary widely by product. A consumer service with one time zone has a sharp daily
  peak; a global or machine-driven one may be nearly flat but bursty. Don't borrow another
  system's factor.
- Estimates are for rejecting designs, not for buying exact capacity. Before purchase, load
  test (see `engineering-practices` performance).
- Utilization targets trade cost against latency and headroom. Queueing delay grows sharply as
  a resource nears full use (a standard queueing result, not from the sources here); this is
  why targets sit well below 100%.

## Review checklist

1. Does every number carry a unit and a source (measured, given, assumed)?
2. Are bits and bytes, MB and MiB, and Kubernetes `m` versus `Mi` used correctly?
3. Is the design load the peak (measured or stated), plus a catch-up factor, not the daily
   average?
4. Are amplifiers multiplied in: fan-out, replicas, retries, indexes, DNS lookups?
5. Is capacity measured in the resource that runs out, not in requests per second?
6. Was Little's law used for concurrency, connections and queue wait, with a tail-inclusive W?
7. Were memory and connections multiplied by process count at the autoscaler's maximum?
8. Is the dominant term named, and the next limit after it?

## Related

[nalsd-method](nalsd-method.md), [capacity-planning](capacity-planning.md);
[`engineering-practices`](../../engineering-practices/SKILL.md) performance (measuring and
benchmarking real code).

## Sources

SRE Workbook, [Non-Abstract Large System Design](https://sre.google/workbook/non-abstract-design/);
SRE book, [Handling Overload](https://sre.google/sre-book/handling-overload/) and
[Managing Critical State](https://sre.google/sre-book/managing-critical-state/) (round-trip and
log-write times); [Latency numbers every programmer should know](https://gist.github.com/jboner/2841832)
(~2012); [Little's law](https://en.wikipedia.org/wiki/Little%27s_law); Kubernetes,
[Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
(units, memory-backed `emptyDir`);
[PostgreSQL connection settings](https://www.postgresql.org/docs/current/runtime-config-connection.html).
