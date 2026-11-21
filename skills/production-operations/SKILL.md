---
name: production-operations
description: Running a production service from day to day - project-agnostic, any cloud or self-hosted. Covers monitoring design (four golden signals, white-box and black-box probes, symptoms versus causes, dashboards, dead-man's switches, expiry and freshness checks for certificates, credentials, quotas and backups); page versus ticket and alert fatigue; on-call load, handoff and escalation, including solo teams with agents as first responders; incident roles, the state document and mitigating first; runbooks and safe operator commands; toil measurement; config design, staged config rollout and canary analysis. Use when setting up monitoring, alerts or on-call, during or after an incident, when writing a runbook or admin command, or when manual work keeps recurring. Not for SLOs, burn-rate alerts or postmortems, or flags and rollback (see engineering-practices), pattern choice (see infrastructure-patterns), launch reviews (see architecture-review), or GCP-specific ops (see google-cloud-waf-operational-excellence).
---

# Production Operations

Keeping a running service healthy: knowing when it breaks, getting the right person (or agent)
to it, handling the incident, and shrinking the manual work around it. The references are
grounded in Google's SRE book and SRE Workbook (monitoring, alerting, on-call, incidents, toil,
configuration, canarying) and the Prometheus and Alertmanager docs. Each leads with what agents
get wrong, then gives a procedure, a tested example and a numbered review checklist.

Two neighbours own parts of the topic, and this skill links to them rather than restating them:
[`engineering-practices`](../engineering-practices/SKILL.md) reliability (SLIs, SLOs, error
budgets, burn-rate alerts, postmortems) and release-engineering (feature flags, canary rollout
mechanics, rollback).

## How to use this skill

1. Find the task or symptom in the tables below and read that one reference. Don't load all six.
2. **During an incident**, read [incident-response](references/incident-response.md) first and
   mitigate before investigating. Everything else can wait.
3. Before calling monitoring "done", run the review checklist of
   [monitoring-and-alerting](references/monitoring-and-alerting.md); before giving anyone (or any
   agent) the pager, the checklists of [on-call](references/on-call.md) and
   [runbooks-and-safe-operations](references/runbooks-and-safe-operations.md).

## The catalog

| Topic | Read when | Reference |
|---|---|---|
| Monitoring and alerting | Choosing what to measure; golden signals; black-box probes; dashboards; page vs ticket; grouping and inhibition; heartbeats; expiry, quota and freshness checks | [monitoring-and-alerting](references/monitoring-and-alerting.md) |
| On-call | Setting up a rotation or deciding there can't be one; pager load and budgets; handoffs; escalation; interrupts; team overload; agents as first responders | [on-call](references/on-call.md) |
| Incident response | Declaring; incident commander, ops and comms roles; the state doc; mitigation moves; update cadence; closing; overload in production | [incident-response](references/incident-response.md) |
| Runbooks and safe operations | Writing a runbook; making operator commands safe (read-only, timeouts, no heavy queries on the write path); runbook to automation | [runbooks-and-safe-operations](references/runbooks-and-safe-operations.md) |
| Toil and automation | Manual work keeps recurring; measuring toil; a toil budget; what to automate first | [toil-and-automation](references/toil-and-automation.md) |
| Config and canary changes | Designing config; validating it; rolling a config change out in stages; reading a canary's numbers | [config-and-canary-changes](references/config-and-canary-changes.md) |

## Symptom to reference

| Symptom or situation | Look at |
|---|---|
| A watchdog or alert only writes to a log; a stall was found by a user, not a page | [monitoring-and-alerting](references/monitoring-and-alerting.md): alerts must reach a person; add a heartbeat |
| The monitoring or alert pipeline could be down and nobody would know | [monitoring-and-alerting](references/monitoring-and-alerting.md): dead-man's switch |
| A certificate, API key or registry token expired and broke things in a chain | [monitoring-and-alerting](references/monitoring-and-alerting.md): the deadline inventory |
| A volume filled to 100%; no disk alert existed | [monitoring-and-alerting](references/monitoring-and-alerting.md), then [`data-integrity`](../data-integrity/SKILL.md) for time-to-full |
| Health checks green while every write fails | [monitoring-and-alerting](references/monitoring-and-alerting.md): a black-box write probe; probe depth in [`infrastructure-patterns`](../infrastructure-patterns/SKILL.md) health checks |
| A backup, cron or batch job silently stopped | [monitoring-and-alerting](references/monitoring-and-alerting.md): last-success timestamps |
| Hundreds of notifications for one outage; the pager is ignored | [monitoring-and-alerting](references/monitoring-and-alerting.md), [on-call](references/on-call.md) |
| A page with no runbook, or a runbook that is out of date | [runbooks-and-safe-operations](references/runbooks-and-safe-operations.md) |
| An operator's status or stats command stalled a production coordinator or primary | [runbooks-and-safe-operations](references/runbooks-and-safe-operations.md): safe-command rules |
| Something is broken right now | [incident-response](references/incident-response.md) |
| Several people or agents worked one incident with no commander and no shared doc | [incident-response](references/incident-response.md): one IC, one state doc |
| Latency and queues climbing, timeouts, crash loops under load | [incident-response](references/incident-response.md): recognising overload |
| One or two people, no rotation, and the question "what should wake me?" | [on-call](references/on-call.md): small-team model |
| Letting an AI agent triage alerts or act on production | [on-call](references/on-call.md), [runbooks-and-safe-operations](references/runbooks-and-safe-operations.md) |
| The same manual fix every week; tickets piling up | [toil-and-automation](references/toil-and-automation.md), [on-call](references/on-call.md) (team overload) |
| A config push broke production, or a config change is about to go out | [config-and-canary-changes](references/config-and-canary-changes.md) |
| Deciding whether a canary passed | [config-and-canary-changes](references/config-and-canary-changes.md) |

## Working rules

A synthesis across the references:

1. **An alert nobody receives is not an alert.** Every alert reaches a pager or a ticket queue,
   and an always-firing heartbeat proves the path works.
2. **Page on user pain and on deadlines.** Symptoms of user impact page; so do causes that give no
   symptom until they are fatal (disk fill, expiry, stopped backups). Everything else is a ticket
   or a dashboard.
3. **Test from outside.** A black-box probe of the real path, including writes, is the check that
   a process-level health check cannot replace.
4. **Every page has a runbook,** and every runbook step says whether it changes anything.
5. **Diagnose without making it worse.** Read-only by default, timeouts on every admin call, and
   no heavy queries on a primary or coordinator's write path.
6. **One incident, one commander, one doc.** Only the operations lead changes production, whether
   the responders are people or agents.
7. **Mitigate first.** Roll back, flag off, drain or shed, then find the cause.
8. **Measure toil, cap it, and spend the rest removing it.**
9. **Config is code.** Version it, validate it at commit, and roll it out with a canary.

## Gotchas

- Process-level health checks pass while the write path, the disk or a dependency is broken.
- Prometheus should send to every Alertmanager instance directly, not through a load balancer.
- Email and Slack receivers in Alertmanager do not send "resolved" notices unless configured.
- Export the timestamp of the last success, not "seconds since"; compute the age in the query.
- An empty target list must never mean "all": the SRE book's machine-wipe emergency began that way.
- Adding replicas or restarting everything during overload can deepen it.
- The SRE Workbook's chapter called "overload" is about teams drowning in operational work, not
  servers; service overload is in the SRE book's Handling Overload and Cascading Failures chapters.

## Related

- [`engineering-practices`](../engineering-practices/SKILL.md): reliability (SLOs, burn-rate
  alerts, postmortems), release-engineering (flags, canaries, rollback), debugging.
- [`data-integrity`](../data-integrity/SKILL.md): disk time-to-full, backup checks, restores.
- [`infrastructure-patterns`](../infrastructure-patterns/SKILL.md): health checks, load shedding,
  safe rollouts.
- [`data-pipelines`](../data-pipelines/SKILL.md): freshness and completeness SLIs for pipelines.
- [`architecture-review`](../architecture-review/SKILL.md): production readiness and launch
  reviews.
- [`system-design`](../system-design/SKILL.md): capacity planning and limits.
- [`structured-logging`](../structured-logging/SKILL.md), [`core-principles`](../core-principles/SKILL.md)
  (least privilege for agents and operators).
- `secure-reliable-systems`: designing for recovery, revocation and break-glass access.
- google-cloud-waf-operational-excellence (from google/skills): GCP-specific operations guidance.
