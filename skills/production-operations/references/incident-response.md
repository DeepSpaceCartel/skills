# Incident response

Running an incident while it is happening: deciding to declare one, who does what, the state
document, mitigating before root-causing, keeping people informed, and closing. Writing the
postmortem afterwards is in [`engineering-practices` reliability](../../engineering-practices/references/reliability.md).
Anchor sources: the SRE book's [Managing Incidents](https://sre.google/sre-book/managing-incidents/),
[Emergency Response](https://sre.google/sre-book/emergency-response/),
[Effective Troubleshooting](https://sre.google/sre-book/effective-troubleshooting/),
[Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/) and its
[example incident document](https://sre.google/sre-book/incident-document/), and the SRE Workbook's
[Incident Response](https://sre.google/workbook/incident-response/).

## What agents typically get wrong

- **Debugging instead of mitigating.** Users judge you by when the failures end, not by whether
  you know why. A rollback, a drain or
  turning a flag off usually works before anyone understands the bug.
- **Nobody in charge.** Several people (or agents) each investigate, each change something, and
  nobody knows the current state. The SRE book calls the uncoordinated changes "freelancing".
- **No written state.** Findings live in chat scroll and heads. The next responder starts over,
  and the postmortem has no timeline.
- **Declaring late.** The incident process starts two hours in, after the outage got worse. The
  Workbook's GKE case set up structure about two hours into a nearly seven-hour outage.
- **Changes nobody recorded,** so nobody can undo them afterwards.
- **Silence towards users and stakeholders** until the fix, or updates with no next-update time.
- **Closing when the graph turns green,** with no exit criteria, so it reopens an hour later.
- **Adding replicas or restarting everything during overload.** New tasks die under full load;
  restarts with cold caches make it worse.

## Procedure

1. **Declare** when any trigger in the table below is true. Declaring and then standing down is
   cheap; declaring late is not.
2. **The person who declares is incident commander (IC)** until they hand over explicitly. Open
   the command post (one channel or call) and the state doc.
3. **Assess impact:** which users, which journeys, since when, getting worse or stable.
4. **Assign roles** as the incident grows: an operations lead, who alone changes production; a
   communications lead; a planner for long incidents. In a small incident the IC holds them all.
5. **Mitigate first:** roll back the last change, turn the flag off, drain the bad zone, shed load,
   freeze automation that may be doing damage. Preserve evidence (logs, a heap dump) as you go.
6. **Communicate on a cadence** written into the state doc (for example every 30 minutes for a
   user-facing outage), each update with the time of the next one.
7. **Investigate once the bleeding stops:** what changed, where in the stack, why.
8. **Close against exit criteria** written early: SLIs back inside the SLO for an agreed period,
   backlog drained, temporary changes listed for reverting. Announce the close.
9. **Hand over to the postmortem:** the state doc and timeline go to its author.

## Techniques

**When to declare.** The SRE book gives three triggers; here they are as a decision rule, with two
added by this skill:

| If ... | Declare? |
|---|---|
| Users can see it | yes |
| A second team (or a second agent with write access) has to be involved | yes |
| An hour of focused work has not found the cause | yes |
| Data may be lost or corrupted | yes (synthesis) |
| A credential may be exposed | yes, and bring in security (synthesis) |
| None of the above | handle it as a ticket, write notes anyway |

**Roles, by the decision each one owns.** Split the decisions so each person can act on their part
without waiting for anyone else to sign off:

| Decision | Owner | Everyone else |
|---|---|---|
| Who may touch production, and what gets tried next | the operations lead (the only hands on prod) | proposes changes in the doc |
| Who talks to users, the business and other teams, and when | the communications lead | sends questions to them |
| What the priorities are, who does what, and who owns any decision not yet handed out | the incident commander (IC), who types nothing into prod | escalates disagreements to the IC |
| What happens after the next hour: shift changes, meals, a running list of temporary changes, follow-up work | the planner, in long incidents | adds temporary changes to the list |

In a small incident the IC holds every row; in a large one a row can become its own
sub-incident. A handoff isn't done until the incoming IC says "I have it" out loud and the
channel has been told. Do it by voice, not by chat.

**Agents in an incident** (synthesis). Treat each agent as a person in the role table. One IC,
human or agent, owns the doc and the assignment of work; investigating agents report findings
into the doc and do not change production unless they are the operations lead. Never let two
agents mitigate in parallel.

**State document.** Everyone in the response can write to it, and a reader who stops after the
first screen should already know the impact and the plan. A template in this skill's own layout:

```
# INCIDENT <id>: <one-line impact>              STATUS: active | mitigated | closed
Command post: <channel/call>   Next update due: <time>   Cadence: <every N min>
IC: <name>   Ops: <name>   Comms: <name>   Next IC: <name or none>

## Impact now
<who is affected, which journeys, numbers, trend>

## Current hypothesis and what we are doing
<one paragraph; replaced, not appended, at each update>

## Exit criteria
- <SLI> inside SLO for <duration>; <backlog> drained; <temporary change> reverted

## Actions
- [ ] <action>  owner: <name>  (production change? y/n)

## Changes made during the incident (to revert or keep)
- <time> <who> <what> <how to undo>

## Timeline (newest first)
- <time UTC> <who> <event or finding, including negative results>
```

**Mitigation moves, in rough order of bluntness:** revert the latest deploy or config push; flag
off; drain a zone or a bad replica set; shed low-priority traffic or pause batch work; enter a
degraded mode; block the bad client or query. Generic moves are blunt but quick (Workbook). Freeze
automation that may be acting on bad data: the SRE book's process-induced emergency was an
automation that read an empty result as "every machine".

**Recognising overload in production** (SRE book, Handling Overload and Addressing Cascading
Failures). Signs: latency rising with queue
length; more timeouts, so work is wasted on requests the caller has dropped; health checks failing
under load and the scheduler killing busy tasks; GC churn; cache hit rate falling; crash loops;
bimodal latency hidden by the mean. First moves: stop the retry amplification, shed load hard
(let a small share through, then ramp up), drop batch traffic, serve degraded results, revert
recent changes. Be careful with "add replicas" and "restart all": in a death spiral new tasks fail
at once. If the scheduler is killing tasks that are slow but working, consider pausing the checks
that kill them. Patterns for designing this in are in
[`infrastructure-patterns` load-shedding](../../infrastructure-patterns/references/load-shedding.md).

**Troubleshooting under pressure** (SRE book ch. 12): ask what changed last (deploys, config,
traffic mix); divide the stack and test at component boundaries; write each hypothesis, test and
result in the timeline, including the negative ones; distrust the first familiar explanation.

## Example

A crawler fleet's write path starts failing at 14:02 after a config push: the health checks stay
green because they only test the process, but the ingestion API returns errors on every write.

- 14:09 The black-box write probe pages. The on-call declares (users see stale data), becomes IC,
  opens the channel and the doc, sets updates every 30 minutes.
- 14:12 Impact: 100% of writes failing since 14:02; reads fine. Exit criteria written: probe green
  and write error ratio inside the SLO for 30 minutes, backlog drained.
- 14:14 The IC assigns one operations lead. A second engineer and an agent are told to
  investigate and report into the doc, not to change anything.
- 14:16 Ops reverts the 14:00 config push (logged in "Changes made"). 14:19 writes recover.
- 14:20 Status: mitigated. Investigation starts. 14:50 exit criteria met, incident closed, doc
  handed to the postmortem owner, with a follow-up to make the health check test a real write.

Checked: every timeline step maps to one role in the table, and the mitigation came before any
root-cause work.

## Gotchas and contested points

- **Freezing versus serving.** If running on risks corrupting data, stopping the service can be the
  right mitigation (SRE book ch. 12).
- **The person who caused it** usually knows the most; involve them, blamelessly.
- **Rest.** In long incidents, rotate responders every few hours; the Workbook's PagerDuty case
  rotated every four hours.
- **Risky rollouts belong in business hours,** when the people who can fix them are awake
  (Workbook).
- **Drills.** Use the process for minor issues and in role-plays so it is familiar when it counts.

## Review checklist

1. Were the declare triggers checked early, and the incident declared when one was true?
2. Was there exactly one incident commander at every moment, with live, announced handoffs?
3. Did only the operations lead (one person or agent) change production?
4. Was there one state doc with impact, hypothesis, exit criteria, actions, changes and timeline?
5. Was mitigation tried before root-cause analysis, and evidence preserved?
6. Did updates go out on the stated cadence, each naming the next update time?
7. Was every production change during the incident logged with how to undo it?
8. Was the incident closed against written exit criteria and announced?
9. During overload, were retries cut and load shed before adding replicas or restarting?

## Related

[`engineering-practices` reliability](../../engineering-practices/references/reliability.md)
(postmortems) and [debugging](../../engineering-practices/references/debugging.md),
[`engineering-practices` release-engineering](../../engineering-practices/references/release-engineering.md)
(rollback), [`data-integrity`](../../data-integrity/SKILL.md) (when data was lost),
[on-call](on-call.md), [runbooks](runbooks-and-safe-operations.md).

## Sources

SRE book: [Managing Incidents](https://sre.google/sre-book/managing-incidents/),
[Emergency Response](https://sre.google/sre-book/emergency-response/),
[Effective Troubleshooting](https://sre.google/sre-book/effective-troubleshooting/),
[Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/),
[Handling Overload](https://sre.google/sre-book/handling-overload/),
[Example Incident State Document](https://sre.google/sre-book/incident-document/); SRE Workbook:
[Incident Response](https://sre.google/workbook/incident-response/); the vendored
`google-cloud-waf-operational-excellence` skill (incident roles and escalation, paraphrased). The
state-doc layout, the agent rules and the two added declare triggers are this skill's synthesis.
