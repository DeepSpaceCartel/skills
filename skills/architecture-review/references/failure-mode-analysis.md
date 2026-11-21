# Failure-mode analysis

Finding how each part of an existing or proposed system can fail, per component and per user
journey, and deciding which failures to mitigate, at what cost. It uses the five failure
categories of the AWS resilience analysis framework: single points of failure, excessive load,
excessive latency, misconfiguration and bugs, and correlated failure (AWS calls it "shared
fate"). The category table and neutral mitigations are in the
[crosswalk's failure-mode walk](provider-crosswalk.md#resilience-failure-mode-walk); this page
is the method and a worked table. Designing redundancy and failure domains from scratch is
[`system-design`](../../system-design/references/scaling-and-failure-domains.md); the mechanics
of timeouts, retries and load shedding are in
[`engineering-practices`](../../engineering-practices/references/reliability.md). Anchor
source: the AWS framework's pages on
[the properties and categories](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/overview.html),
[understanding the workload](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/workload-review.html),
[applying it](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/applying-framework.html),
[trade-offs](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/tradeoffs.html),
[observability](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/observability.html)
and [continuous improvement](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/continuous-improvement.html).

## What agents typically get wrong

- **Walking the whole architecture at once.** Start from the most valuable journey and only
  the components on its critical path. Other journeys come in later passes.
- **Stopping at compute.** The five categories apply to the four kinds of component on every
  journey: code and config, infrastructure, data stores, and external dependencies. The
  database, DNS, the registry, the identity provider and the credentials are components.
- **Assuming a mitigation exists.** Write the failure down even if someone says it's handled,
  then check the handling. An untested failover is a hypothesis.
- **One failure, one effect.** Ask both how a failure hurts the component's own job and how it
  hurts what the component talks to: a client's retries can be what overloads the database.
- **Missing the source.** The same overload can come from a customer surge or an operator who
  drained two nodes at once. Different sources need different mitigations.
- **"Healthy" meaning "the process answers".** A probe that never exercises the write path
  stays green while every write fails.
- **Correlated failure hidden in configuration.** A memory limit and a database on the
  container's writable layer, three replicas on one node, two services behind one lock, every
  deploy behind one token: each is one fault with several victims.
- **Forgetting what expires.** Certificates, tokens, API keys, domain registrations and
  provider trials fail on a date, often all at once and with no alert.
- **Mitigating without a signal.** A mitigation needs a metric that says when to act.
- **Agonizing over the category.** The categories are prompts, not a taxonomy. Writing the
  failure down matters; filing it correctly does not.

## Procedure

1. **Pick the journey.** Rank user journeys by business value; take the top one. Include
   operational journeys (deploy, restore, rotate, page) in a later pass, not never.
2. **Draw its path.** Every component it touches, grouped as code and config, infrastructure,
   data stores, external dependencies. On each arrow: sync or async, what data, which failure
   boundary it crosses. Mark components shared with other journeys.
3. **Write each component's baseline:** normal and peak rate, payload size, client timeouts,
   quotas and limits (memory, disk, connections, rate limits).
4. **Walk the five categories per component** with the prompts below. Record each failure
   mode: component, category, source, effect on the journey, effect on neighbours.
5. **Rate likelihood and impact** for each (the grid in [review-process](review-process.md)).
6. **Choose a response:** avoid, mitigate, transfer or accept. For mitigations, prefer a
   preventive one (stops the failure) and add a corrective one (detects and recovers). Price
   each in money, complexity, engineering time, operational load, and latency or consistency.
7. **Name the signal**: a leading indicator (approaching trouble) where possible, a lagging one
   (impact started) always. Pick the mitigation that fits the signal's warning time: a sudden
   spike shows only a lagging signal, so throttling beats autoscaling.
8. **Test it.** Each mitigation, old or new, gets a fault-injection test, game day or drill.
9. **Repeat** on a weekly or fortnightly cadence, one journey or component per session, and
   after every incident (record the failure mode and component it revealed).

## Techniques

### Prompts per category

This page's own wording; ask each of every component on the path.

| Category | Ask |
|---|---|
| Single point of failure | How many of it are there, in how many failure domains? What stops when it stops? Is the thing that would replace it (control plane, registry, credential) also single? |
| Excessive load | What can flood it, and what can it flood? Which limit does it hit first: memory, disk, connections, a quota, a lock? Can a backlog grow past what it can ever drain? Does it waste work on requests that will fail? |
| Excessive latency | What does it do when a dependency slows rather than fails? Are timeouts set and smaller than the caller's? Does failing fast route all traffic to the broken instance? What is its most expensive request? |
| Misconfiguration and bugs | What stops a bad change before production? Can it roll back without a human? What does the health check really test? Which of its inputs expire? Which operator action could break it? |
| Correlated failure | What else shares its node, volume, lock, credential, quota, DNS or deploy? Is it shared between journeys or tenants? What happens on a partial (gray) failure? Is a change rolled out to less than one failure domain first? |

### Ranking against cost

Score, then sort. A finding's priority rises with likelihood and impact and falls with the
mitigation's cost. Write the cheapest effective mitigation first; a redesign (cells, a second
region, a replicated store) is a separate, later item with its own decision.

| Response | When |
|---|---|
| Mitigate (preventive) | Likely, and a cheap fix exists: a PVC, a limit from measured peak, a probe that writes |
| Mitigate (corrective) | Can't be prevented cheaply; detection plus a tested recovery meets RTO |
| Transfer | A provider or another team can carry it: a managed database, a CDN, a paid support contract |
| Avoid | The feature that creates the risk isn't worth it |
| Accept | Unlikely or cheap to recover, within the error budget; recorded with who accepted it |

### Recovery as part of the design

Every failure mode that loses or corrupts work needs a way back: a checkpoint, a re-drive tool,
a stop switch on intake. Assume operators will err; a "human error" root cause means a missing
guardrail. For data-loss modes, check the restore path with
[`data-integrity`](../../data-integrity/SKILL.md).

## Example

The small SaaS from [review-process](review-process.md): 3-node self-hosted Kubernetes, an API
(3 replicas), a job coordinator (1 replica, queue in SQLite), 4 workers that fetch customer
URLs and post to webhooks, one Postgres primary on a node-local volume. Journey J2, "scheduled
export reaches the customer's webhook". L = likelihood, I = impact (H/M/L).

| Component | Category | Failure mode (source) | L | I | Mitigation: preventive / corrective | Cost | Signal |
|---|---|---|---|---|---|---|---|
| Coordinator | Correlated failure | SQLite on the writable layer; an OOM kill at the 512 Mi limit restarts the container and wipes the queue (memory spike on a big export) | H | H | PVC + limit from measured peak / nightly backup, re-drive from Postgres | Low | Restarts with `OOMKilled`; queue length drops to 0 |
| Coordinator | Misconfiguration | Disk full; every write fails; `/healthz` answers from memory and stays green (log growth) | M | H | Probe writes and reads a row; log rotation / alert on time-to-full | Low | Write error rate; disk time-to-full |
| Coordinator | Correlated failure | Admin `/stats` runs a full count inside the write lock; one dashboard refresh stalls every worker's lease (operator) | H | M | Stats from a counter or snapshot, statement timeout / alert on lease latency | Low | Lease p99; lock wait time |
| Coordinator | Single point of failure | One replica; node drain stops all exports (maintenance) | M | M | Accept for launch with RTO 4 h / PDB + runbook for reschedule | Accept | Export freshness SLI |
| Workers | Excessive load | All 4 retry a slow customer webhook with no backoff; one tenant's endpoint consumes every worker (customer outage) | M | M | Per-tenant concurrency cap, capped backoff with jitter / dead-letter after N | Low | Per-tenant in-flight count |
| Workers | Excessive latency | Webhook hangs; no client timeout; leases expire and jobs run twice (customer slowness) | M | M | Timeout below the lease, idempotency key on delivery / duplicate alarm | Low | Delivery duration p99 |
| Postgres | Single point of failure | Node-local volume; node loss means restore from the nightly dump, losing up to 24 h against an RPO of 1 h (hardware) | L | H | Accept the single primary: a measured 23 min restore meets RTO 4 h / add base backup plus WAL archiving for RPO 1 h (a dump can't replay WAL) | Medium | Backup and archive heartbeats |
| Registry token | Misconfiguration (expiry) | One copy, no recorded expiry; on expiry no image can be pushed, so no fix ships and no new image can be built for anything (time) | M | H | Inventory with dates, second holder, alert 30 days ahead / documented re-issue path | Low | Days to expiry |

Checked: every row names a source, both mitigation kinds or an explicit accept, a cost and a
signal; the accepted rows quote the RTO they rely on.

## Gotchas and contested points

- **RPN scoring** (severity x occurrence x detection, 1 to 10 each, from FMEA) is used by the
  AWS samples skill. It adds a detection axis, which is useful, but its precision is false;
  three levels per axis are enough for most reviews.
- **Redundancy can add failure modes**: a failover that flaps, a split brain, a replica that
  serves stale reads. Count the new modes before adding a replica.
- **Static stability.** A mitigation that needs the control plane (scale up, reschedule,
  re-issue a credential) may be unavailable in the very incident it's for.
- **Gray failures** (slow, partial, intermittent) defeat binary health checks. Prefer probes
  and SLIs that measure success rate and latency.

## Review checklist

1. Was the analysis done per journey, starting with the most valuable, over all four component kinds?
2. Does every component have a written baseline with its limits?
3. Were all five categories asked of every component on the path, including expiry and operator error?
4. Does every failure mode name its source and its effect on neighbours?
5. Does each one have a response (avoid, mitigate, transfer, accept) priced against likelihood and impact?
6. Does each mitigation have a leading or lagging signal, and was it tested?
7. Does each health check exercise the path it vouches for (a write for a writer)?
8. Are shared nodes, volumes, locks, credentials and quotas listed as correlated-failure risks?
9. Is there a date for the next pass, and are incidents tagged with the failure mode they revealed?

## Related

[provider-crosswalk](provider-crosswalk.md) (the category table and mitigations),
[review-process](review-process.md) (rating and the report),
[`system-design`](../../system-design/references/scaling-and-failure-domains.md) (failure
domains, overload), [`data-pipelines`](../../data-pipelines/references/failure-isolation.md)
(per-source isolation, keeping reads off the write path),
[`data-integrity`](../../data-integrity/references/state-and-storage.md) (state placement,
disk fill), [`data-integrity`](../../data-integrity/references/disaster-recovery.md)
(credential recovery).

## Sources

AWS Prescriptive Guidance, resilience analysis framework (fetched 2026-11-20): the
[introduction](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/introduction.html),
[overview](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/overview.html),
[understanding the workload](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/workload-review.html),
[applying the framework](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/applying-framework.html),
[mitigating failures](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/mitigating-failures.html),
[trade-offs](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/tradeoffs.html),
[observability](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/observability.html),
[continuous improvement](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/continuous-improvement.html)
and the [table of contents](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/toc-contents.json).
AWS samples `wafr-facilitator` skill (SEEMS walk, RPN scoring), MIT-0, read locally.
Paraphrased; the prompts, tables and example are this skill's own.
