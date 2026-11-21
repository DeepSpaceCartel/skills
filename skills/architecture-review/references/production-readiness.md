# Production readiness

A production readiness review (PRR) checks that a service, and the people who run it, can carry
real users before they arrive: it can be watched, paged on, rolled back, restored and scaled,
and its obligations to others are met. A launch checklist is the PRR's working form for one
launch. Anchor sources: the SRE book chapters on
[reliable product launches](https://sre.google/sre-book/reliable-product-launches/), the
[launch coordination checklist](https://sre.google/sre-book/launch-checklist/),
[best practices for production services](https://sre.google/sre-book/service-best-practices/)
and the [evolving engagement model](https://sre.google/sre-book/evolving-sre-engagement-model/)
(the PRR itself), and the SRE Workbook's
[engagement model](https://sre.google/workbook/engagement-model/) (where the PRR sits in a
service's life). The checklist below is this skill's own, grouped into ten areas; for depth in
each area it links to the pack skill that owns it.

## What agents typically get wrong

- **A checklist with no reason per item.** Every item should trace back to a failure someone
  has seen. Items nobody can justify get skipped, and then the important ones get skipped too.
- **The same weight for every launch.** A new country for an existing feature, or a change with
  no new servers and little extra traffic, needs a short list. A new service with new state
  needs the full one. Classify first.
- **Readiness of the code, not of the people.** Who is on call, can they reach the runbook,
  have they practised the restore? A service nobody can operate at 3 a.m. isn't ready.
- **Capacity from the steady state.** Launch-day traffic is not steady-state traffic, and it
  can be far above the estimate. Load-test past the estimate and know what breaks first.
- **No kill switch.** Each new feature needs a way to turn it off, or turn it down, without a
  deploy.
- **Outbound traffic treated as nobody's business.** A service that fetches, crawls, sends
  mail or calls webhooks makes promises to strangers: rates, identification, an abuse contact.
  Unreviewed, those turn into abuse reports to your host and a suspended account.
- **Ignoring the deploy path as a dependency.** CI, the image registry, its token, DNS and the
  cluster API are on the path of every fix. If one breaks during an incident, nothing ships.
- **Ticking boxes on someone's word.** "We have backups" passes only with a timed restore log.

## Procedure

1. **Classify the launch.** Low risk (no new servers, no new stored data, small traffic change,
   a repeat of a known launch type): run the launch blockers only, marked **B** below. Anything
   else: the full checklist and a failure-mode walk
   ([failure-mode-analysis](failure-mode-analysis.md)).
2. **Set the terms.** Settle with the owning team the go-live date, who runs the review, the
   targets it measures against (SLOs, RTO, RPO) and any redesign already on the roadmap.
3. **Collect evidence.** Walk the checklist asking for an artefact per item (as in
   [review-process](review-process.md)). Past outages count too: a postmortem whose follow-ups
   are still open marks a weak spot.
4. **Turn gaps into a plan.** Order the gaps by how much each threatens the SLO, settle that
   order with the team that owns the code, and give each fix an owner and a date. Blockers close
   before launch; the rest get a date after it.
5. **Prepare the operators.** The new owners learn by doing: trace one real request end to end
   with a builder, then perform a rollback and a restore themselves. Hand over in slices
   (dashboards and access first, primary on-call last), builders on the escalation path until
   nobody calls them.
6. **Launch in steps** (rollout section below), watching the SLO at each step.
7. **Keep it ready.** Readiness decays: a big change or a serious incident triggers another
   pass, and each lesson from running the service becomes a checklist item.

## Techniques: the checklist

**B** marks a launch blocker for every launch, including low-risk ones.

### 1. Architecture
- **B** A current diagram of each critical journey's path, every dependency named, sync or async.
- Single points of failure listed, each with a decision: redundancy, graceful degradation, or accepted with its RTO.
- Failure domains known: what survives losing a pod, a node, a zone, the provider. See [`system-design`](../../system-design/references/scaling-and-failure-domains.md).
- Admin, stats and batch paths kept off the production write path and lock.

### 2. Capacity
- **B** Peak load estimated, including launch surge and catch-up after an outage, and load-tested past it; the first thing to saturate is known.
- Headroom for losing the largest failure domain at peak. See [`system-design`](../../system-design/references/capacity-planning.md).
- Every limit inventoried: memory limits from measured peak, disk, connections, quotas, upstream rate limits, autoscaler maximums.
- Overload behaviour defined: what is shed first, and what clients are told.

### 3. Monitoring and alerting
- **B** SLIs measured as users see them, with an SLO per critical journey.
- **B** Pages go to a person, fire on user-visible symptoms, and each names a runbook.
- Health checks exercise the path they vouch for: a writer's probe writes.
- Disk time-to-full, certificate and token days-to-expiry, backup heartbeat and queue age are alerted on.
- The monitoring itself is watched: a missing heartbeat pages.

### 4. On-call and runbooks
- **B** An on-call rota exists for launch week, with an escalation path.
- Runbooks for each page and each single point of failure, runnable by someone who didn't build it.
- Manual steps are written down; repeated ones are on the list to automate.
- Incident roles and a postmortem habit are in place. See [`production-operations`](../../production-operations/SKILL.md) and [`engineering-practices`](../../engineering-practices/references/reliability.md).

### 5. Data safety
- **B** Every store is on durable storage: no database on a container's writable layer or `emptyDir`. See [`data-integrity`](../../data-integrity/references/state-and-storage.md).
- **B** Backups exist for every store, and a timed restore met the RTO. See [`data-integrity`](../../data-integrity/references/backup-and-restore.md).
- RPO and RTO agreed with the business, per store.
- Bulk deletes are capped and reversible; pipelines prove a read was complete before closing records. See [`data-pipelines`](../../data-pipelines/references/completeness-and-absence.md).

### 6. Security
- **B** A credentials inventory: what each unlocks, where every copy lives, its expiry, who can re-issue it. No credential with one copy. See [`data-integrity`](../../data-integrity/references/disaster-recovery.md).
- Least privilege for workloads and people; production access is logged.
- Dependencies and images scanned in CI. See [`engineering-practices`](../../engineering-practices/references/security-practices.md).
- Application controls checked against a level of [`owasp-asvs`](../../owasp-asvs/SKILL.md).

### 7. Rollout and rollback
- **B** A rollback tested in the last month, and its time known.
- Changes go out in stages: a canary, then a fraction of traffic, then all, each watched. Config changes too.
- New features sit behind flags that can turn them off without a deploy. See [`engineering-practices`](../../engineering-practices/references/release-engineering.md).
- Clients retry with capped backoff and jitter, only on retryable errors; server-side settings can slow them down.
- Bad config is rejected, and the service keeps its last good config.

### 8. Dependencies
- **B** The deploy path (source host, CI, registry and its token, cluster API, DNS) is listed as a dependency, with what happens when each is down or its credential expires.
- Each runtime dependency has a timeout, a behaviour when it fails, and a contact.
- Third-party limits and deadlines (quotas, contract dates, API deprecations) are known.
- We don't overload anyone else: our peak against their published or agreed limits.

### 9. Documentation
- The service's purpose, owners, journeys, SLOs and runbooks are findable from one page.
- Decisions, including accepted risks, are recorded. See [`adr`](../../adr/SKILL.md).
- The launch plan names dates, steps, go/no-go criteria and a contingency for each step.

### 10. External commitments
- **B** Outbound traffic to third parties (crawling, fetching user-supplied URLs, mail, webhooks) is reviewed: per-host rate limits, honouring robots.txt and `Retry-After`, an identifying User-Agent with a contact URL, and a stop switch per target.
- **B** An abuse contact is published and watched; someone owns replying to abuse reports within the host's deadline.
- The hosting provider's acceptable-use policy was read for the traffic you send (scanning, crawling, bulk mail).
- SLAs promised to customers are below the SLOs you can measure; status page and support channel exist.
- Legal and privacy duties (data residency, retention, terms of the sources you use) have an owner.

## Example

The crawler case, as a generic system: a fleet of 40 fetch workers on a rented Kubernetes
cluster, launched without area 10. Within a week a target's CERT files an abuse report with
the host, who gives 24 hours to respond before suspending the account; nobody reads the abuse
mailbox. The PRR items that would have caught it, each with its evidence:

| Item | Evidence that passes |
|---|---|
| Per-host rate limit | Code shows a per-host token bucket; a load test against a fake host shows it holds at the configured rate |
| Identifying User-Agent and contact | A fetched request's headers, seen in a test server's log |
| robots.txt and `Retry-After` honoured | Integration test with a fake host that disallows a path and returns 429 |
| Stop switch per target | Runbook step plus a config change that stopped one host in staging within a minute |
| Abuse contact watched | Mailbox routes to the on-call rota; a test mail was answered |
| Host's acceptable-use policy | Link and the clause on crawling, noted in the launch doc |

Checked: every row is proven by an artefact (code, test, log, runbook drill), not by a
statement.

## Gotchas and contested points

- **Checklists grow.** Each added item taxes every later launch. Cut stale items on a fixed
  schedule, and where a shared component covers an area, point at it instead of listing detail.
- **A PRR is cheaper early.** Reviewing a design before it's built avoids redesign; reviewing
  only at launch finds problems when they are most expensive.
- **Not every service needs a handover.** A small service can stay with its builders; the
  review still applies.
- **Shared platforms shorten the PRR.** Services built on a common framework (standard
  probes, metrics, rollout) inherit many items; check the framework once.

## Review checklist

1. Was the launch classified, and the full or blockers-only list chosen on that basis?
2. Are all **B** items closed with evidence, not statements?
3. Has a rollback and a restore each been run and timed recently?
4. Are pages tied to SLOs on user-visible symptoms, each with a runbook and a person?
5. Is every credential inventoried with copies, expiry and a re-issue path, including the deploy path's?
6. Is outbound traffic rate-limited per host, identified, stoppable, with a watched abuse contact?
7. Is there a staged rollout plan with a kill switch and go/no-go criteria per step?
8. Do the remaining gaps have owners and dates, and is a re-review trigger set?

## Related

[review-process](review-process.md), [failure-mode-analysis](failure-mode-analysis.md),
[`system-design`](../../system-design/SKILL.md), [`data-integrity`](../../data-integrity/SKILL.md),
[`data-pipelines`](../../data-pipelines/SKILL.md),
[`engineering-practices`](../../engineering-practices/SKILL.md), [`production-operations`](../../production-operations/SKILL.md).

## Sources

Google SRE book (fetched 2026-11-20):
[ch. 27, Reliable Product Launches at Scale](https://sre.google/sre-book/reliable-product-launches/),
[ch. 32, The Evolving SRE Engagement Model](https://sre.google/sre-book/evolving-sre-engagement-model/),
[Appendix B, Best Practices for Production Services](https://sre.google/sre-book/service-best-practices/),
[Appendix E, Launch Coordination Checklist](https://sre.google/sre-book/launch-checklist/).
SRE Workbook, [ch. 18, SRE Engagement Model](https://sre.google/workbook/engagement-model/)
(lifecycle; it defers PRR detail to the SRE book). CC BY-NC-ND 4.0: paraphrased; the ten
areas, items and example are this skill's own. Area 10's crawler items (robots.txt,
User-Agent, abuse contact, acceptable-use policy) are this skill's synthesis, not from those
pages.
