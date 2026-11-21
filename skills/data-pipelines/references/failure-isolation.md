# Failure isolation

Keeping one bad record, one unhappy source or one slow stage from stopping everything else:
poison records and dead-letter queues, redrive, rate limits and cooldowns per source or tenant,
hotspots and work partitioning, queue backlogs and load leveling, and keeping reads off the
coordinator's write path. Per-call timeouts, retry budgets and circuit breakers are in
[reliability](../../engineering-practices/references/reliability.md); choosing a broker or
workflow engine belongs to `infrastructure-patterns`. Anchor sources: the AWS Builders' Library,
[Avoiding insurmountable queue backlogs](https://builder.aws.com/content/3EuRcgkTP1MI0c7zM8W6HL3WIqA/avoiding-insurmountable-queue-backlogs);
the Azure [Queue-Based Load Leveling](https://learn.microsoft.com/en-us/azure/architecture/patterns/queue-based-load-leveling),
[Competing Consumers](https://learn.microsoft.com/en-us/azure/architecture/patterns/competing-consumers)
and [Pipes and Filters](https://learn.microsoft.com/en-us/azure/architecture/patterns/pipes-and-filters)
patterns; the [SRE Workbook](https://sre.google/workbook/data-processing/) (hotspotting,
quarantine of bad work units); and the AWS
[resilience analysis framework](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/mitigation-strategies.html)
(redrive, checkpointing, stopping intake).

## What agents typically get wrong

- **Retrying a poison record forever.** A record that crashes the parser goes back on the queue,
  crashes the next worker, and so on. Throughput falls to the rate of crashes. Azure's Competing
  Consumers says not to let such messages return indefinitely; AWS moves them to a dead-letter
  queue.
- **A dead-letter queue nobody reads.** Records go there and stay. AWS treats any message there
  as a bug worth an alarm, and redrives after the fix.
- **One cooldown per hostname.** Many tenants share one provider host. A 429 for one tenant
  pauses every tenant on that host, and the provider's freshness goes to zero with no error
  anywhere. Key the cooldown on the unit the source actually limits.
- **One shared queue for every source.** A surge from one source fills it and everyone waits
  behind it. AWS notes that once messages are in one shared queue, it is hard to isolate
  workloads, and backpressure on a shared queue penalises the innocent.
- **Autoscaling consumers with no cap on their total rate.** Azure warns that this moves the
  overload to the downstream service.
- **FIFO after an outage.** Draining a backlog oldest-first means every item, fresh or not, is
  late. For freshness-sensitive work, serve fresh items first and the backlog behind.
- **One work unit per huge source.** The largest source sets the run time, and a hanging chunk
  blocks the stage (SRE book). Split large units and rebalance.
- **Admin and stats queries on the coordinator's write path.** A long report query holds the
  lock the workers need to claim and commit, and every worker stalls. Read from a replica or a
  snapshot, or keep counters the writers maintain.

## Procedure

1. **Bound attempts per record.** Count attempts per record ID across workers. After N, move
   the record to a dead-letter store with the error, the attempt count, the stage and the code
   version.
2. **Alert on dead-letter arrivals and age**, not only total depth, and give the dead-letter
   store an owner and a runbook.
3. **Redrive deliberately**: after the fix ships, re-queue a sample, confirm it passes, then
   re-queue the rest at a throttled rate, into the normal path (so idempotency still applies).
4. **Find each source's limit unit** (per account, per tenant, per API key, per IP, per host)
   and key rate limiters, cooldowns and retry state on exactly that unit.
5. **Give each source or tenant its own budget**: a token bucket or concurrency cap, so one
   source's slowness uses only its own share of workers and connections. Workers skip sources in
   cooldown and take other work.
6. **Partition queues** by source group or priority. Use a separate queue or tier for backfills
   and retries so live work goes first.
7. **Cap the consumers' total rate** against the tightest downstream (source rate limits, the
   store's write rate), and add workers only when that downstream has headroom.
8. **Size for recovery, not just steady state.** Draining a backlog needs capacity above the
   arrival rate (arithmetic below). Plan the burst and how fresh work jumps the backlog.
9. **Keep reads off the write path.** Dashboards and admin queries read from a replica,
   snapshot or precomputed counters, with a statement timeout. The coordinator's lock is for
   claims and commits only.
10. **Keep an andon cord**: a switch that stops intake or pauses a stage without losing queued
    work, for when output is going wrong.

## Techniques

- **Poison detection.** Use the broker's maximum delivery count where it has one (Azure names
  Service Bus's `MaxDeliveryCount`); otherwise count attempts in your own store keyed by record
  ID. A crash that kills the worker before it can count still needs counting, so increment
  before processing.
- **Quarantine fine-grained.** The workbook suggests blocking the specific bad record or key
  so the rest of the pipeline progresses, and a config flag that skips problem input in an
  emergency. Its maturity matrix lists automatic quarantine of bad work units.
- **Sideline, don't drop.** AWS's techniques: move a tenant's excess traffic to a spillover queue
  processed when capacity frees; move old messages to a backlog queue processed after the live
  queue is current; re-enqueue with a delay so fresher work goes first. Drop old messages only
  when a later full sweep makes them redundant.
- **Shuffle sharding.** A fixed set of queues, each tenant hashed to a small subset, enqueue to
  the least-loaded one. One tenant's surge backs up only its few queues (AWS).
- **Per-workload pools.** Separate thread or connection pools, or semaphores, per workload, so
  one cannot take them all. Little's law sizes them: concurrency is arrival rate times latency,
  so 50 requests per second at 200 ms needs about 10 in flight, and at 4 s about 200.
- **Backlog arithmetic.** A backlog built over an outage of length T at arrival rate A holds
  A x T items. Draining it at capacity C takes A x T / (C - A). With C = 2A it takes T; with
  C = 1.1A it takes 10 T. That is why AWS says recovery needs roughly double capacity for as long
  as the outage lasted.
- **Leases and heartbeats** for long work, so a slow worker's item isn't handed out again while
  it is still running (see [idempotent-stages](idempotent-stages.md)).
- **Spare polling capacity.** AWS tracks empty polls: if nearly every poll returns work, there is
  no headroom for a burst.

## Example

Cooldowns keyed on the unit the source limits, and a worker that dead-letters a poison record
after three attempts instead of blocking the queue:

```python
import time
from collections import defaultdict

class Cooldowns:
    """Back off per limit key. The key is the unit the source rate-limits, not the hostname."""
    def __init__(self, key_fn, clock=time.monotonic):
        self.key_fn, self.clock, self.until = key_fn, clock, {}
    def ready(self, target):
        return self.clock() >= self.until.get(self.key_fn(target), 0)
    def on_429(self, target, retry_after):
        k = self.key_fn(target)
        self.until[k] = max(self.until.get(k, 0), self.clock() + retry_after)

class Worker:
    """Retry a record a few times, then dead-letter it with its error; never block the queue."""
    def __init__(self, process, max_attempts=3):
        self.process, self.max_attempts = process, max_attempts
        self.attempts, self.dead, self.done = defaultdict(int), [], []
    def run(self, queue):
        while queue:
            rec = queue.pop(0)
            self.attempts[rec["id"]] += 1          # count first: a crash mid-process still counts
            try:                                   # (in production, a shared store, not a dict)
                self.done.append(self.process(rec))
            except Exception as e:
                if self.attempts[rec["id"]] >= self.max_attempts:
                    self.dead.append({"record": rec, "error": repr(e),
                                      "attempts": self.attempts[rec["id"]]})
                else:
                    queue.append(rec)              # back of the queue, behind fresh work
```

With 50 tenants on one provider host and a 429 with `Retry-After: 600` for one tenant, the
hostname-keyed cooldown left 0 of 50 tenants ready; keyed on `(host, tenant)` it left 49. Given
five records where one has no body, the worker completed `[0, 1, 3, 4]` and dead-lettered
record 2 after 3 attempts, with its error kept for the redrive.

## Gotchas and contested points

- **Some providers really do limit per host or per IP.** Then a host-wide cooldown is right.
  Find out from the source's documentation or its responses (headers naming the limit), and key
  on what you learn.
- **Dead-letter vs retry later.** A transient dependency outage sends good records to the
  dead-letter store too. Separate "this record is bad" (parse or validation errors) from "the
  world is down" (timeouts, 503s), and don't dead-letter the second kind on the same count.
- **Ordering vs isolation.** Per-key ordering forces one consumer per key, which brings back the
  hotspot. Make stages order-free where you can.
- **Load leveling has limits.** If average arrival exceeds average capacity, a queue only delays
  the failure; Azure says to scale within safe limits or shed at the producer.
- **Read replicas lag.** A dashboard on a replica can show minutes-old numbers. Label it.

## Review checklist

1. Is there a cap on attempts per record, counted across workers and before processing?
2. Do capped records land in a dead-letter store with error, stage and version, with an owner,
   an alert on arrivals and a tested redrive path?
3. Are "bad record" and "dependency down" failures handled differently?
4. Are rate limiters, cooldowns and retry state keyed on the unit the source actually limits?
5. Does each source or tenant have its own budget, so one source's 429s or slowness cannot
   stall the others?
6. Are queues partitioned (by source group, priority, live versus backfill), so a surge in one
   doesn't delay all?
7. Is the consumers' total rate capped against the tightest downstream?
8. Is there capacity and a plan to drain a backlog, with fresh work served first?
9. Are large work units split, and can a hanging unit be detected and rebalanced?
10. Do dashboards and admin queries stay off the coordinator's write path, with timeouts?
11. Is there a switch to stop intake or pause a stage without losing queued work?

## Related

[completeness-and-absence](completeness-and-absence.md) (error classes: whose failure it was),
[idempotent-stages](idempotent-stages.md) (leases, redrive safety),
[pipeline-slos](pipeline-slos.md) (freshness by reason, queue age),
[reliability](../../engineering-practices/references/reliability.md) (timeouts, retry budgets,
bulkheads, load shedding), `infrastructure-patterns` (broker and queue choice, read replicas).

## Sources

AWS Builders' Library,
[Avoiding insurmountable queue backlogs](https://builder.aws.com/content/3EuRcgkTP1MI0c7zM8W6HL3WIqA/avoiding-insurmountable-queue-backlogs)
(recovery capacity, sidelining, shuffle sharding, per-workload pools, Little's law, backpressure
on shared queues, dead-letter alarms and reprocessing, heartbeats, empty polls). Azure
Architecture Center, [Queue-Based Load Leveling](https://learn.microsoft.com/en-us/azure/architecture/patterns/queue-based-load-leveling),
[Competing Consumers](https://learn.microsoft.com/en-us/azure/architecture/patterns/competing-consumers),
[Pipes and Filters](https://learn.microsoft.com/en-us/azure/architecture/patterns/pipes-and-filters)
(set aside failing messages, backpressure, capping aggregate rate). Google SRE Workbook,
[Data Processing Pipelines](https://sre.google/workbook/data-processing/) (hotspotting, skipping
problem input, automatic quarantine of bad work units). Google SRE book,
[Data Processing Pipelines](https://sre.google/sre-book/data-processing-pipelines/) (uneven
chunks, hanging chunks). AWS,
[Resilience analysis framework: mitigation strategies](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/mitigation-strategies.html)
(redrive tooling, checkpointing, an andon cord to stop intake). The limit-key rule and the
read-path rule are this skill's synthesis. Azure's Quarantine pattern was read but not used: it
covers vetting third-party software artifacts, not bad records.
