---
name: architecture-review
description: Reviewing an existing or proposed architecture, or a service before launch - project-agnostic, vendor-neutral (any cloud or self-hosted). Covers well-architected pillar reviews (operations, security, reliability, performance, cost, sustainability) with a Google/AWS/Azure crosswalk; failure-mode analysis per component and user journey (single points of failure, excessive load, excessive latency, misconfiguration and bugs, correlated failure) with mitigations priced against risk; production readiness reviews (PRR) and launch checklists; and running a review as a conversation that leaves owned, prioritized findings. Use when asked "is this production-ready?", "review this design", before a launch or migration, after an incident, or when writing a design doc's risks section. Not for designing or sizing a new system (see system-design), choosing a pattern (see infrastructure-patterns), GCP-only reviews (see google-cloud-waf-*), app security requirements (see owasp-asvs), or reviewing a code diff.
---

# Architecture Review

Evaluating a system that exists or is proposed: what can fail, what it costs to prevent, who
owns each risk, and whether the service and its people are ready for real users. The method is
vendor-neutral: the same questions apply to a managed-cloud workload and to a self-hosted
cluster. It draws on the Google, AWS and Azure well-architected frameworks (mapped onto neutral
pillars), the AWS resilience analysis framework, and Google's SRE book chapters on launches and
production readiness. Each reference leads with what agents get wrong, then gives a procedure,
a worked example and a numbered review checklist.

A review is a **conversation, not an audit**. It ends with a short ranked list of risks, each
with evidence, an owner, a decision and a follow-up date, not with a score.

This skill **evaluates** a design. Producing and sizing one is
[`system-design`](../system-design/SKILL.md). Choosing a specific pattern (cache, queue, replica,
managed service) is `infrastructure-patterns`. Fixing what a review finds usually lands in
[`engineering-practices`](../engineering-practices/SKILL.md),
[`data-integrity`](../data-integrity/SKILL.md) or [`data-pipelines`](../data-pipelines/SKILL.md).

## How to use this skill

1. Scope the review first with [review-process](references/review-process.md): trigger, depth
   (quick, full, pillar-scoped), critical journeys, evidence. Its output template is the report.
2. For any depth, walk the critical journeys with
   [failure-mode-analysis](references/failure-mode-analysis.md).
3. For a launch or a handover to operations, run
   [production-readiness](references/production-readiness.md); at minimum its blockers.
4. For a full or pillar-scoped review, check the pillar practices in
   [provider-crosswalk](references/provider-crosswalk.md). Use it also when someone quotes one
   provider's framework at a system that runs elsewhere.
5. Ground every finding in evidence you looked at. Say what you could not determine.

## The catalog

| Topic | Read when | Reference |
|---|---|---|
| Review process | Scoping a review; depth levels; gathering evidence; running the session; severity and priority; the report template and a filled example; follow-up | [review-process](references/review-process.md) |
| Failure-mode analysis | Walking components and journeys over the five failure categories; preventive vs corrective mitigations; ranking by likelihood x impact against cost; the worked table | [failure-mode-analysis](references/failure-mode-analysis.md) |
| Production readiness | "Is this production-ready?"; a PRR or launch checklist; launch classification; staged rollout and kill switches; outbound-traffic obligations | [production-readiness](references/production-readiness.md) |
| Provider crosswalk | The six neutral pillars and their practices; mapping Google, AWS and Azure terms and products; what to ignore off-cloud | [provider-crosswalk](references/provider-crosswalk.md) |

## Symptom to reference

| Symptom or situation | Look at |
|---|---|
| "Is this ready for production?" / launch in a few weeks | [production-readiness](references/production-readiness.md), then [failure-mode-analysis](references/failure-mode-analysis.md) |
| "Review this design doc" / write its risks section | [review-process](references/review-process.md), [failure-mode-analysis](references/failure-mode-analysis.md) |
| "Do a well-architected review" of a non-GCP or self-hosted system | [provider-crosswalk](references/provider-crosswalk.md), [review-process](references/review-process.md) |
| Data vanished after an OOM kill or a restart | [failure-mode-analysis](references/failure-mode-analysis.md): correlated failure (memory cap and data share one fate); fix with [`data-integrity`](../data-integrity/SKILL.md) |
| Health checks green while every write fails (full disk) | [failure-mode-analysis](references/failure-mode-analysis.md): what the probe really tests |
| An admin or stats page slows the production write path | [failure-mode-analysis](references/failure-mode-analysis.md): shared lock is correlated failure |
| An abuse report from a target or the host about our crawler or fetcher | [production-readiness](references/production-readiness.md): external commitments |
| An expired token blocked deploys, then blocked rebuilding anything | [failure-mode-analysis](references/failure-mode-analysis.md) "what expires"; [production-readiness](references/production-readiness.md) dependencies and security |
| Just had a serious incident; what else is like it? | [failure-mode-analysis](references/failure-mode-analysis.md), pillar-scoped [review-process](references/review-process.md) |
| A migration to a new cluster, provider or store | Full [review-process](references/review-process.md) of the target design, then [production-readiness](references/production-readiness.md) |
| Fifty findings and no idea which matter | [review-process](references/review-process.md): rate by likelihood and impact, rank by severity, then cost |

## The pillar pass

For a full or pillar-scoped review, take each neutral pillar, pull its evidence, and check it
against the numbered practices in the crosswalk.

| Pillar | Evidence to pull | Crosswalk |
|---|---|---|
| Operations | Deploy pipeline, last incidents and postmortems, alert rules, runbooks | [Operations](references/provider-crosswalk.md#operations) |
| Security | Credentials inventory, RBAC and network policies, image and dependency scans, audit logs | [Security](references/provider-crosswalk.md#security) |
| Reliability | Replica counts and placement, volumes, probes, SLOs, backups and restore logs | [Reliability](references/provider-crosswalk.md#reliability) |
| Performance | Load-test results, latency percentiles, saturation dashboards, scaling rules | [Performance](references/provider-crosswalk.md#performance) |
| Cost | Bill by label or namespace, utilization, idle resources, cost per unit of work | [Cost](references/provider-crosswalk.md#cost) |
| Sustainability | Utilization of always-on resources, data without owner or expiry, the host's energy mix | [Sustainability](references/provider-crosswalk.md#sustainability) |

## When to re-review

- **At milestones**: before launch, before general availability, before a migration, and at a
  set cadence (at least yearly) for anything critical.
- **After an incident**: a pillar-scoped review of what the incident touched, and a search for
  the same failure mode elsewhere.
- **After a big change**: new state or store, new failure domain or provider, a tenfold load
  change, a new external dependency or outbound traffic, a change of owning team.
- **When an accepted risk's date arrives**, or the condition it was accepted under changes.

## Working rules

A synthesis across the references:

1. **Owned risks, not a grade.** Every finding has evidence, a severity, one decision, an owner
   and a follow-up date.
2. **Journeys first.** Analyse the critical user journeys' paths, including operational ones
   (deploy, restore, rotate, page).
3. **Evidence over the diagram.** Read code, IaC, the running system, dashboards and incidents;
   label each claim observed, stated or inferred.
4. **Unknown is not absent.** Without evidence, record "cannot determine" and a check, with no
   severity.
5. **Price every mitigation.** Weigh likelihood and impact against money, complexity, effort,
   operational load and latency. Accepting a risk is fine when recorded.
6. **Look for shared fate in config.** A limit and the data, two paths and one lock, every
   deploy and one token.
7. **A mitigation needs a signal and a test.** Name the metric that triggers it and when it
   was last exercised.
8. **Calibrate.** Match the bar to the workload's criticality; don't invent criticals, and say
   what is already good.

## Gotchas

- "Shared fate" means correlated failure in AWS's resilience framework but a provider
  partnership model at Google. This skill says correlated failure.
- Azure has five pillars; its sustainability guidance sits across them.
- The Google, AWS and Azure agent skills assume their own cloud's tools; their principles
  transfer, their product checks don't.
- A full best-practice-by-best-practice review can take days and bury the top risks. Cover the
  critical journeys fully and state what was left out.

## Related

- [`system-design`](../system-design/SKILL.md): designing and sizing; failure domains and capacity in depth.
- [`data-integrity`](../data-integrity/SKILL.md): state placement, backups, restores, DR, credential recovery.
- [`data-pipelines`](../data-pipelines/SKILL.md): pipeline SLOs, completeness, per-source isolation.
- [`engineering-practices`](../engineering-practices/SKILL.md): reliability, release-engineering, security-practices.
- [`owasp-asvs`](../owasp-asvs/SKILL.md): application security requirements by level.
- [`adr`](../adr/SKILL.md): recording decisions and accepted risks.
- `infrastructure-patterns`, `production-operations`, `secure-reliable-systems`: choosing
  patterns, running incidents, designing for recovery and revocation.
- google-cloud-waf-* (from google/skills): GCP-specific pillar reviews.
