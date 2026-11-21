# On-call

Who answers the pager, how much they carry, how a shift hands over, and when to escalate. Includes
the case most guidance skips: a team too small for a rotation, often one person plus AI agents.
Anchor sources: the SRE book's [Being On-Call](https://sre.google/sre-book/being-on-call/) and
[Dealing with Interrupts](https://sre.google/sre-book/dealing-with-interrupts/), and the SRE
Workbook's [On-Call](https://sre.google/workbook/on-call/) and
[Identifying and Recovering from Overload](https://sre.google/workbook/overload/) (which is about
*team* overload, not service overload).

## What agents typically get wrong

- **Counting alerts, not incidents.** Load is the number of distinct problems per shift. Ten
  alerts for one outage is one incident and a grouping bug.
- **Lowering thresholds to quiet the pager.** With SLO-based alerting, relaxing a threshold is
  rarely the fix; the page is telling you about the system (Workbook).
- **"Transient, closed."** A page dismissed without follow-up comes back on the next shift. Each
  page gets a cause, or added monitoring if the cause stays unknown.
- **On-call plus a full project load.** The person holding the pager is not expected to deliver
  project work that week (SRE book ch. 29).
- **Tickets spread over the whole team.** Everyone grabs a few, nobody sees the real volume, and
  everyone loses focus. One person (or two) owns the queue.
- **Handoffs by memory.** Open issues, silences and half-done changes are lost at shift change.
- **Copying a big-company rotation onto two people,** or the opposite: a solo founder who gets
  paged at 3 a.m. for things that could wait until 9.
- **Agents with the pager and production admin rights,** or several agents answering the same page
  independently.

## Procedure

1. **Set the response targets per alert class:** minutes for user-facing outages, around half an
   hour for less time-critical systems, business hours for tickets (SRE book and Workbook give 5
   and 30 minutes as examples).
2. **Size the rotation or choose the small-team model** (below). Don't pretend to 24/7 cover you
   don't have; publish the actual hours.
3. **Set a pager budget,** for example at most two incidents per 12-hour shift, and track
   pages as structured data linked to bugs.
4. **Name primary and secondary.** Primary answers; secondary catches missed pages and helps under
   load. Write the escalation path: who next, after how long, and how to reach them out of band.
5. **Make handoff a written step** (template below), read at the start of every shift.
6. **Review weekly or monthly:** pages per shift, time to resolve, repeat offenders. Fix the top
   source or silence it with a dated fix ticket.
7. **Practise:** role-play an old incident ("wheel of misfortune") with each new person before
   they go primary.

## Techniques

**Rotation sizes and limits** (attributed, because the two books differ slightly):

| Figure | Source |
|---|---|
| On-call at most 25% of an engineer's time; operational work at most 50% | SRE book ch. 11 |
| Single-site 24/7 needs about 8 people; dual-site about 6 per site | SRE book ch. 11 |
| Multisite minimum 5 per site, single-site 8; one extra per site for slack | Workbook ch. 8 |
| About 6 hours of total work per incident, so at most 2 per 12-hour shift | SRE book ch. 11 |
| Shifts no longer than 12 hours | Workbook ch. 8 |

The point for small teams: below about 6–8 people, a 24/7 rotation is not sustainable. Choose a
model that reduces what has to page instead.

**Pager load sources.** New bugs that tests missed, noisy or mistuned alerts, and slow
identification and mitigation. Each has its fix: canaries and rollback-first, deleting alerts
that need no action, and pages that link straight to the runbook and dashboard. Fixing a page
source pays off when the fix costs less than the time it keeps taking: 120 hours of work against
4 hours per page breaks even at 30 pages (Workbook).

**Interrupts.** Pages, tickets and ongoing chores (rollouts, flag flips, questions). Give
interrupts to one person in blocks of a day or a week; protect everyone else's focus. Silence a
recurring interrupt once a fix is scheduled, with the fix date as the deadline.

**Handoff note** (written, read at shift start):

```
Shift: <start> to <end>, primary <name>, secondary <name>
Open incidents: <id, state, next action, owner>
Silences in place: <matcher, reason, expires>
Changes in flight: <deploys or config pushes not yet complete>
Pages this shift: <count>; repeat sources: <alert names>
Watch for: <anything expected in the next shift>
```

**Team overload.** Signs (Workbook ch. 17): tickets ageing, long hours, falling morale, interrupts
arriving faster than they close. Recovery: list and triage every open task together, close the
obsolete ones, automate or document the quick ones, park the rest with notes, cut alerts that do
not reflect user pain, and hand back or drop work you cannot carry. Pick the load metrics as a
team and review them on a schedule.

**Small team, solo founder, and agents.** This section is the skill's own synthesis; the sources
assume real rotations.

- **No rotation, so fewer pages.** Only three classes wake someone: the service is down or losing
  data for users, a deadline (disk, certificate, credential) will expire before business hours,
  or the alerting heartbeat stopped. Everything else becomes a business-hours ticket.
- **Publish the hours.** State the support window to users and in the status page; a promise of
  24/7 you cannot keep is worse than an honest one.
- **Agents as first responders.** Let an agent receive alerts first, gather the dashboard, recent
  deploys and logs, and draft the incident state doc. Its permissions are bounded: read-only by
  default, plus a short allow-list of reversible, runbook-named actions (restart one pod, scale
  within limits, pause one consumer). No deletes, no credential changes, no deploys without a
  human, every action logged.
- **One responder per incident.** When several agents or sessions can react, one claims the
  incident (a lock, a label, a channel message) and the rest only report to it. This is the
  incident-commander rule applied to automation.
- **Escalation still needs a human.** The agent escalates by paging the person when the issue is in
  a paging class, a runbook step fails, or the fix needs an action outside its allow-list.
- **A second human for the worst case.** Even solo, name someone who can reach the hosting
  account and the runbooks if the founder is unreachable.

## Example

Business-hours routing for a small team (Alertmanager). Pages go out at any time; tickets are only
delivered inside working hours:

```yaml
time_intervals:
  - name: business-hours
    time_intervals:
      - weekdays: ['monday:friday']
        times: [{start_time: '09:00', end_time: '18:00'}]
        location: 'UTC'            # your team's time zone
route:
  receiver: ticket-queue
  group_by: [alertname, service]
  routes:
    - matchers: ['severity="page"']
      receiver: pager
    - matchers: ['severity="heartbeat"']
      receiver: dead-mans-switch
      repeat_interval: 1m
    - matchers: ['severity="ticket"']
      receiver: ticket-queue
      active_time_intervals: [business-hours]
```

The YAML parses. Top-level `time_intervals` (with `weekdays`, `times` and `location`) and the
route option `active_time_intervals` are in the Alertmanager configuration reference. It was not
loaded into an Alertmanager here, and receivers are omitted for brevity. A hosted paging service
needs the same three things: escalation when nobody acknowledges, a business-hours schedule for
tickets, and a check that pages when the alert source goes quiet.

## Gotchas and contested points

- **Underload is a risk too.** Someone who is on call once a year has forgotten the system. Keep
  each person on at least once or twice a quarter, or run drills (SRE book).
- **Compensation and limits.** Paying for out-of-hours work with a cap stops a few people from
  carrying all of it (SRE book).
- **Playbook depth is contested.** Teams disagree on general guidance versus step-by-step
  commands; agree on a minimal common structure (Workbook).
- **Silencing is not fixing.** Every silence has an expiry and a ticket.
- **An agent that restarts things blindly** hides the bug; restarts count as pages in the load
  review.

## Review checklist

1. Are response targets written per alert class, and are the published support hours true?
2. Is the rotation large enough for its hours, or has the small-team model cut paging to the
   three classes?
3. Is pager load counted in incidents per shift, against a budget, and reviewed?
4. Does every page get a cause or new monitoring, never "transient"?
5. Is there a primary, a secondary or named backup, and an out-of-band escalation path?
6. Is the handoff written, including silences and changes in flight?
7. Do tickets go to one owner, not the whole team?
8. If agents respond first, are their permissions read-only plus an allow-list, logged, with one
   agent claiming each incident?
9. Are signs of team overload watched, with a plan to triage, automate or hand back work?

## Related

[monitoring-and-alerting](monitoring-and-alerting.md) (what pages),
[incident-response](incident-response.md), [runbooks-and-safe-operations](runbooks-and-safe-operations.md),
[toil-and-automation](toil-and-automation.md),
[`core-principles` least privilege](../../core-principles/references/least-privilege.md) (agent
permissions).

## Sources

SRE book: [Being On-Call](https://sre.google/sre-book/being-on-call/),
[Dealing with Interrupts](https://sre.google/sre-book/dealing-with-interrupts/); SRE Workbook:
[On-Call](https://sre.google/workbook/on-call/),
[Identifying and Recovering from Overload](https://sre.google/workbook/overload/); Prometheus
[Alertmanager configuration](https://prometheus.io/docs/alerting/latest/configuration/). The
small-team and agent guidance and the handoff template are this skill's synthesis.
