# Review process

How to run an architecture review that ends with owned, prioritized risks rather than a grade:
scoping, depth, gathering evidence, running the session as a conversation, rating severity,
writing findings, and following them up. The method is vendor-neutral and works the same for a
managed-cloud workload and a self-hosted one (bare VMs plus Kubernetes). Anchor sources: the
AWS Well-Architected Framework's
[welcome page](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)
(reviews are a constructive conversation at milestones, not an audit), the AWS
[resilience analysis framework](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/introduction.html)
(user stories, likelihood and impact against cost), the SRE book's
[engagement model chapter](https://sre.google/sre-book/evolving-sre-engagement-model/)
(findings negotiated into an agreed plan), and the MIT-0 AWS samples skills
`wafr-facilitator` and `aws-well-architected-framework-review` (depth levels, the evidence
gate, the risk grid). The pillar practices themselves are in
[provider-crosswalk](provider-crosswalk.md).

## What agents typically get wrong

- **Treating the review as an audit.** A pass/fail verdict or a pillar score gives nobody
  anything to do. The output is a short list of risks, each with an owner, a decision and a date.
- **Reviewing the boxes, not the journeys.** Walk the request and data paths of the critical
  user journeys; components off every critical path get a lighter look.
- **Reporting absence of evidence as absence of the control.** If no file or person was
  checked where the control would live, the status is "cannot determine" plus a verification
  action, with no severity.
- **Believing the diagram.** The diagram shows intent. The manifests, the running cluster, the
  dashboards and the incident log show what exists. Prefer them when they disagree, and record
  the disagreement as a finding.
- **Fifty findings of equal weight.** Rank them, and put the few that matter most on top.
- **Generic advice.** "Add redundancy" is not a finding. "The coordinator runs one replica with
  its database on the container's writable layer; an OOM kill loses the queue" is.
- **Manufacturing criticals.** A small internal tool on one zone can be fine. Calibrate severity
  to the workload's stated criticality and recovery targets.
- **Ignoring the operational paths.** Deploying, restoring, rotating a credential and paging
  someone are journeys too, and they fail in incidents when they are needed most.
- **No follow-up.** Findings without a follow-up date are never re-checked.

## Procedure

1. **Scope.** Agree in writing: the workload and its boundary, the trigger (launch, migration,
   incident, milestone), the depth (table below), the decision the review feeds, and who
   attends. Name the critical user journeys (two to five) and the recovery targets (RTO, RPO)
   and SLOs, or record that they are missing; that is the first finding.
2. **Gather evidence before the session.** Use the evidence table below. Build a component
   inventory and a data-flow sketch for each critical journey: every hop, sync or async, which
   failure domain each part sits in, what limit it has.
3. **Pre-assess.** Run the failure-mode walk ([failure-mode-analysis](failure-mode-analysis.md))
   over the inventory and draft candidate findings. Mark each as observed, stated or inferred.
4. **Hold the session as a conversation.** Ask open questions about the journeys, then the
   specific ones your pre-assessment raised ("the database volume is node-local; what happens
   when that node is drained?"). Ask to be shown the runbook, the alert, the restore log. "It's
   on the backlog" counts as not done. Capture, don't solve, in the room.
5. **Rate and rank** each finding with the grid below. Note cross-pillar trade-offs (a cheaper
   design that costs reliability) instead of hiding them.
6. **Decide** per finding: fix, accept, transfer (to a provider or another team) or avoid (drop
   the feature). Accepted risks get an ADR or a dated note with who accepted them.
7. **Write the report** in the template below, top findings first, with what is already good.
8. **Follow up** on each finding's date. Re-review on the triggers in
   [SKILL.md](../SKILL.md#when-to-re-review).

## Techniques

### Depth levels

| Depth | When | Scope | Typical effort |
|---|---|---|---|
| Quick | A small change, an internal tool, a first look | Critical journeys only; the five failure categories on their components; the launch blockers in [production-readiness](production-readiness.md) | Hours |
| Full | A launch, a migration, a new critical service | Every pillar in the crosswalk; every component of every critical journey; the full readiness checklist | Days |
| Pillar-scoped | A known concern ("is DR real?", "cut cost by 30%"), or after an incident | One or two pillars in full depth; others only for an obvious critical issue | Hours to a day |

### Evidence to gather

| Source | What it proves | Look for |
|---|---|---|
| Code | Behaviour: timeouts, retries, locking, what a health check tests | Health handlers, transaction scope, admin routes, client retry loops |
| IaC and manifests (Terraform, Helm, Kustomize) | What should be deployed | Replica counts, PVCs vs `emptyDir`, requests and limits, anti-affinity, PodDisruptionBudgets, probes |
| The running system (`kubectl`, cloud console) | What is deployed; drift from IaC | Pods' restart counts and last termination reason (`OOMKilled`), node placement, volume types |
| Config and secrets inventory | What can expire or be lost | Token and certificate expiry dates, where each credential's copies are |
| Dashboards and alerts | What the team would notice | SLO panels, disk time-to-full, alert routing to a person |
| Incidents and postmortems | What already broke and what was promised | Open action items, repeats |
| People | Intent, constraints, history | Ask to be shown, not told |

Label each piece of evidence: **observed** (seen in code, config or the running system),
**stated** (someone said so), **inferred** (deduced). A finding resting only on "stated" needs a
verification action.

### Rating: likelihood x impact

This grid is this skill's own, after the samples skill's impact-by-likelihood table. The AWS
framework asks only that likelihood and impact be weighed against the cost of mitigation.

| Impact \ Likelihood | Low (needs rare conditions) | Medium (plausible this year) | High (expected; has happened) |
|---|---|---|---|
| Severe (critical journey down, data lost, legal or security breach) | High | High | Critical |
| Moderate (degraded, some users, recoverable) | Medium | Medium | High |
| Minor (cosmetic, one user, cheap to recover) | Low | Low | Medium |

Then prioritize: **severity first; within one severity, the cheapest effective fix first.**
Every Critical gets an owner and a date at once, even when its fix is a redesign; cheap fixes
for Highs can run alongside it. "Cannot determine" gets no severity, only a verification
action and a date.

### Report template

```markdown
# Architecture review: <workload>, <date>
Scope and trigger: <boundary, why now, depth, attendees, decision it feeds>
Journeys and targets: <J1..Jn with SLOs; RTO and RPO per store, or "missing" (a finding)>
What is good: <strengths, with evidence>

| ID | Finding | Journey / component | Pillar / category | Evidence (type) | Severity | Decision (ADR) | Owner | Follow-up |

Accepted risks: <ID, who accepted, ADR or note link, revisit date or condition>
Cannot determine: <question, the check that decides it, owner, date>
Not covered: <pillars, journeys or components left out, and why>
Next re-review: <milestone, date or trigger>
```

### Pillar prompts

One or two questions per neutral pillar, to open the conversation; the practices to check
against are numbered in the [crosswalk](provider-crosswalk.md).

| Pillar | Opening question |
|---|---|
| Operations | Walk me through the last deploy and the last page. What was manual? |
| Security | Which credentials can reach production data, where do their copies live, and when do they expire? |
| Reliability | For each critical journey: what is the single thing whose loss stops it, and how long until it's back? |
| Performance | What is the peak load, how was it measured, and what saturates first? |
| Cost | What does one unit of work cost, and what runs that nobody uses? |
| Sustainability | What runs always-on at low utilization, and what data has no owner or expiry? |

## Example

A generic small SaaS: an HTTP API (3 replicas) and a job coordinator (1 replica) that hands work
to 4 workers, on a self-hosted 3-node Kubernetes cluster. One Postgres primary holds tenant data
on a node-local volume, nightly dump to object storage. The coordinator keeps its queue in
SQLite. Trigger: launch to paying customers in four weeks. Depth: full. Critical journeys: J1
"submit a report and download it"; J2 "scheduled export reaches the customer's webhook"; J3
"operator ships a fix". Targets: SLO 99.5% for J1, RPO 1 h, RTO 4 h.

Report excerpt (top four of eleven findings):

| ID | Finding | Journey / component | Pillar / category | Evidence | Sev. | Decision | Owner | Follow-up |
|---|---|---|---|---|---|---|---|---|
| F1 | SQLite file has no volume mount, so it lives on the container's writable layer. The 512 Mi memory limit was hit twice last month (`OOMKilled`); each kill restarted the container with an empty queue. Memory cap and data share one fate. | J1, J2 / coordinator | Reliability / correlated failure | observed: `values.yaml` L41 (no `volumeMounts`), `kubectl get pod` last state; stated: "jobs vanished once" | Critical | Fix: PVC, limit from measured peak, backup and restore drill | Platform lead | 2026-12-04 |
| F2 | `/healthz` returns 200 from memory; with a full disk every write fails while the probe stays green, so nothing restarts or pages. | J1, J2 / coordinator | Operations / misconfiguration | observed: `health.go` L12; inferred: no disk alert in the alert rules | High | Fix: probe does a tiny write; alert on time-to-full | Backend lead | 2026-11-27 |
| F3 | The registry push token has one copy (a CI secret) and no recorded expiry. When it expires no image can be pushed, so no fix ships. | J3 / CI and registry | Security, Operations / misconfiguration (what expires) | observed: CI config; cannot determine expiry: provider console not checked | High (expiry: verify) | Fix: inventory with dates, second holder, alert 30 days ahead | Platform lead | 2026-11-27 |
| F4 | RPO is 1 h but the only backup is a nightly `pg_dump`, which can lose up to 24 h and can't be combined with WAL for point-in-time recovery. | J1 / Postgres | Reliability / single point of failure | observed: backup CronJob; restore log | High | Fix: base backup plus WAL archiving, or the business agrees RPO 24 h (ADR) | Platform lead | 2026-12-11 |

Also noted as good: API replicas spread across nodes with a PDB; the nightly dump was restored
in a drill last month (23 min). Accepted: a single Postgres primary for launch (ADR-0012, revisit
at 200 tenants), because a 23 min restore meets RTO 4 h; F4 covers the RPO gap.

Checked: each finding names a journey, a component, evidence with its type, one decision, one
owner and a date; the "cannot determine" part of F3 carries a verification action, not a guess;
the acceptance quotes the measured restore time it rests on.

## Gotchas and contested points

- **Scores and maturity ratings** help compare many workloads over time. For one team before a
  launch they distract from the top risks. Use them only when the organization tracks them.
- **Who reviews.** A reviewer outside the team sees assumptions the team can't; the team knows
  where the bodies are. Have both in the room.
- **Breadth vs depth.** A full review of every best practice can take days and produce noise.
  When time is short, cover the critical journeys fully and say what was not covered.
- **Accepting a risk is a valid outcome,** if someone with the authority accepts it, in
  writing, with a date to revisit.

## Review checklist

1. Are the scope, trigger, depth, attendees and the decision the review feeds written down?
2. Are the critical user journeys named, with SLOs and RTO/RPO (or a finding that they're missing)?
3. Was evidence taken from code, IaC, the running system, dashboards and incidents, not only the diagram?
4. Is each finding's evidence labelled observed, stated or inferred?
5. Does every "cannot determine" carry a verification action and no severity?
6. Is each finding rated by likelihood and impact, ranked by severity, and within a severity by cost of the fix?
7. Does each finding have one decision (fix, accept, transfer, avoid), an owner and a follow-up date?
8. Is every accepted risk recorded in an ADR or dated note with who accepted it?
9. Does the report list what is good, what was not covered, and the next re-review trigger?

## Related

[failure-mode-analysis](failure-mode-analysis.md), [production-readiness](production-readiness.md),
[provider-crosswalk](provider-crosswalk.md); [`adr`](../../adr/SKILL.md) for recording accepted
risks; [`system-design`](../../system-design/SKILL.md) when a finding needs a redesign.

## Sources

- AWS Well-Architected Framework, [welcome](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html) (fetched 2026-11-20).
- AWS resilience analysis framework: [introduction](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/introduction.html), [understanding the workload](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/workload-review.html), [trade-offs and risks](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/tradeoffs.html).
- Google SRE book, [The Evolving SRE Engagement Model](https://sre.google/sre-book/evolving-sre-engagement-model/); SRE Workbook, [SRE Engagement Model](https://sre.google/workbook/engagement-model/) (joint prioritization of review findings).
- AWS samples, `wafr-facilitator` and `aws-well-architected-framework-review` skills,
  https://github.com/aws-samples/sample-well-architected-skills-and-steering, MIT-0 (read locally).

Paraphrased; no tables or text reproduced from the SRE books or AWS documentation.
