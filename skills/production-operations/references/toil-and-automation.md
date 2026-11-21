# Toil and automation

Recognising operational work that grows with the service and leaves nothing behind, measuring it,
capping it, and engineering it away. Anchor sources: the SRE book's
[Eliminating Toil](https://sre.google/sre-book/eliminating-toil/) and
[Dealing with Interrupts](https://sre.google/sre-book/dealing-with-interrupts/), and the SRE
Workbook's [Eliminating Toil](https://sre.google/workbook/eliminating-toil/) and
[Identifying and Recovering from Overload](https://sre.google/workbook/overload/).

## What agents typically get wrong

- **Calling all ops work toil.** Meetings and planning are overhead, not toil. Tidying alert
  config is unglamorous but leaves the system better, so it is engineering.
- **Calling work "not toil" because a script runs it.** If a person still has to notice, start,
  watch and check the script every time, the human time is toil.
- **No numbers.** "We spend a lot of time restarting workers" cannot be prioritised against
  feature work. Minutes per occurrence times occurrences per week can.
- **Automating the rarest, most interesting task** instead of the largest pile of time.
- **Copying the manual steps literally into code,** including the workarounds, rather than asking
  what the steps are for.
- **Automation without safeguards:** no input checks, no timeouts, no stop when results look odd.
- **Never saying no.** Accepting every manual request sets the precedent that the ops person does
  it forever.

## Procedure

1. **Log interrupts for two to four weeks:** each task, minutes spent (count the context switch),
   and how it arrived (page, ticket, chat, scheduled chore).
2. **Classify each line** with the test below. Keep only toil.
3. **Rank by hours per week,** then by fix cost. Compute payback (example below).
4. **Set a budget:** an upper bound on toil as a share of each person's time. The SRE books use
   50% for all operational work. A small team can pick a lower number, but must pick one.
5. **For the top items choose a move:** remove the need, self-service, automate, batch, or refuse.
6. **Ship the smallest useful fix,** measure the hours again, and repeat with the next item.
7. **Review quarterly.** Toil comes in spikes; a persistent breach of the budget means the team
   is overloaded.

## Techniques

**Is it toil?** A one-line test per property, in this skill's own framing of the SRE book's
characteristics. The more answers on the left, the more likely it is toil:

| Toil if... | Not toil if... |
|---|---|
| a person has to do or supervise it | it runs and finishes with nobody involved |
| it has been done before and will be again | it is the first time, or a genuinely new problem |
| a machine could do it, or a design change could remove it | it needs real judgment each time |
| it is triggered by an interrupt | it is planned work towards a goal |
| the system is no better afterwards | it leaves a permanent improvement |
| it grows with traffic, users, sources or nodes | its cost stays flat as the service grows |

**Where toil hides** (Workbook taxonomy, regrouped): request tickets for routine changes
(access, quota, config); production interrupts (freeing disk, restarting a leaky process,
re-driving a queue); hand-held releases and rollbacks; manual migrations; capacity and cost chores;
repeated diagnosis of a system with poor observability.

**Measuring.** Pick one unit and keep it: hours is usual, including the context switch. Track it
before, during and after a fix with as little extra work as possible (a ticket label, a chat
command). The SRE book's surveys found SREs averaging about a third of their time on toil, with
individuals from 0 to 80%: report the distribution, not only the mean. On-call alone sets a floor:
roughly a third of time for a 6-person rotation, a quarter for 8.

**Moves, most to least durable:**

| Move | Use when |
|---|---|
| Remove the need | The system can do it itself: defaults from the environment, auto-scaling, self-healing |
| Self-service | Requesters can do it safely with a form, script, API or pull request |
| Human-backed interface first | You know the request shape but not yet every edge case: accept structured requests, do them by hand, automate later |
| Automate the response | The steps are deterministic (see the runbook ladder in [runbooks-and-safe-operations](runbooks-and-safe-operations.md)) |
| Batch | Many small identical requests: do them on a schedule, which also shows patterns |
| Refuse or use the SLO | The task's cost exceeds its value, or the error budget says it can wait |
| Make components uniform | Special cases dominate: give every instance the same interface and config |

**Automation needs the operator's caution built in.** Validate inputs, apply timeouts, cap how much
one run may change, and hand back to a human when conditions are unsafe (Workbook). Build reusable
pieces rather than one script per incident, and measure the automation itself: error rate, rework,
and human time saved.

**Getting time for it.** Show the toil numbers to whoever sets priorities; present the fix with the
reliability, security or cost gain it brings, not only as "less boring work" (Workbook).

## Example

One on-call week's interrupt log for a crawler and ingestion service, with the payback of a
16-hour fix for each line:

```python
def payback_weeks(fix_hours, minutes_each, per_week):
    weekly = minutes_each * per_week / 60
    return fix_hours / weekly if weekly else float("inf")

log = [  # task, minutes each (including the context switch), times per week
    ("restart stuck crawler worker", 20, 9),
    ("rotate expiring source API key", 45, 1),
    ("re-drive dead-letter queue", 15, 6),
    ("answer 'did my export run?'", 10, 12),
]
week_hours = 40
toil = sum(m * n for _, m, n in log) / 60
print(f"toil {toil:.1f} h = {toil / week_hours:.0%} of a {week_hours} h week")
for name, m, n in sorted(log, key=lambda r: -r[1] * r[2]):
    print(f"{name:32} {m * n / 60:4.1f} h/wk  payback: {payback_weeks(16, m, n):4.1f} wk")
```

Run: 7.2 hours, 18% of the week. Ranked: worker restarts 3.0 h/week (payback 5.3 weeks), export
questions 2.0 (8.0), dead-letter re-drives 1.5 (10.7), key rotation 0.8 (21.3). The restarts go
first (fix the hang, or automate the restart with a cap and a page when it repeats); the export
questions become self-service (a status page). Key rotation pays back slowly in hours, but its
failure mode is an outage, so it is automated for risk, not for time: track its expiry in the
deadline inventory in [monitoring-and-alerting](monitoring-and-alerting.md).

## Gotchas and contested points

- **Some toil is fine.** Small amounts are low-stress and teach the system; it hurts in bulk (SRE
  book).
- **Automation is not free.** Weigh build and upkeep against hours saved; imperfect automation that
  covers the common case is often worth shipping (Workbook case study).
- **The budget is a team signal, not a personal score.** Use it to spread work and to argue for
  fixes.
- **Hidden toil.** If people quietly absorb tickets, the measured number is low and the team is
  still drowning: route all of it through one queue (SRE book ch. 29).
- **Restarts that "fix" things** are toil that hides a bug. Count them.

## Review checklist

1. Is there a recent interrupt log with minutes and counts per task type?
2. Was each task tested against the toil properties, separating toil from overhead and
   engineering?
3. Is toil reported as a share of time, as a distribution across people, against a written budget?
4. Are the top items ranked by hours per week and payback, with risk-driven exceptions noted?
5. For each top item, was removal or self-service considered before scripting?
6. Does new automation validate inputs, time out, cap its changes and fall back to a human?
7. Is automation measured for errors and time saved after it ships?
8. Is there a quarterly review, and a plan when the budget is exceeded?

## Related

[on-call](on-call.md) (interrupts, team overload), [runbooks-and-safe-operations](runbooks-and-safe-operations.md)
(runbook-to-automation ladder), [config-and-canary-changes](config-and-canary-changes.md)
(configuration toil), [`core-principles`](../../core-principles/SKILL.md) (KISS, fail fast).

## Sources

SRE book: [Eliminating Toil](https://sre.google/sre-book/eliminating-toil/),
[Dealing with Interrupts](https://sre.google/sre-book/dealing-with-interrupts/); SRE Workbook:
[Eliminating Toil](https://sre.google/workbook/eliminating-toil/),
[Identifying and Recovering from Overload](https://sre.google/workbook/overload/). The toil test
table, the ordering of moves and the payback calculation are this skill's synthesis.
