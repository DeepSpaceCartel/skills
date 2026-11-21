# Toil and automation

Recognising operational work that grows with the service and leaves nothing behind, measuring it,
capping it, and engineering it away. Anchor sources: the SRE book's
[Eliminating Toil](https://sre.google/sre-book/eliminating-toil/) and
[Dealing with Interrupts](https://sre.google/sre-book/dealing-with-interrupts/), and the SRE
Workbook's [Eliminating Toil](https://sre.google/workbook/eliminating-toil/) and
[Identifying and Recovering from Overload](https://sre.google/workbook/overload/).

## What agents typically get wrong

- **Calling all ops work toil.** Meetings and planning are overhead, not toil. Deleting dead
  dashboards or renaming confusing metrics is dull, but it leaves things better, so it isn't toil.
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

**Is it toil? A five-point score.** Give the task one point for each statement that is true:

- You could write it as a script today, or a design change would make it unnecessary.
- If the fleet, the user count or the number of sources doubled, the task would happen twice as often.
- It arrives by alert, ticket or chat message rather than from a plan.
- A person has to start it, watch it or check its result.
- When it is done, nothing about the system has changed for the better.

Three or more points: treat it as toil and put it in the log. The exception is work that needs a
fresh decision every time; that is engineering or incident work, however often it comes up. The
idea of toil and its traits come from the SRE book's chapter on eliminating toil; this score is
this skill's own.

**Where toil hides,** grouped by how the work reaches you (informed by the Workbook):

- **Asked for:** access, quota and config change requests.
- **Alerted:** a full disk, a stuck worker, a queue to re-drive, and the same diagnosis repeated
  because the system can't be seen into.
- **On the calendar:** releases that need a human at each step, recurring migrations, cost and
  headroom reviews.

**Measuring.** Count in hours, and include the cost of switching into the task. Take a baseline,
keep logging while the fix is being built, and compare afterwards. Make logging a one-click label
or a chat command; otherwise the measuring becomes toil too. The SRE book's surveys found SREs averaging about a third of their time on toil, with
individuals from 0 to 80%: report the distribution, not only the mean. On-call alone sets a floor:
roughly a third of time for a 6-person rotation, a quarter for 8.

**Moves, most to least durable:**

| Move | Use when |
|---|---|
| Remove the need | The system can do it itself: defaults from the environment, auto-scaling, self-healing |
| Self-service | Requesters can do it safely themselves: a PR to a config repo, a CLI, a small web form |
| Human-backed interface first | You know the request shape but not yet every edge case: accept structured requests, do them by hand, automate later |
| Automate the response | The steps are deterministic (see the runbook ladder in [runbooks-and-safe-operations](runbooks-and-safe-operations.md)) |
| Batch | Many small identical requests: do them on a schedule, which also shows patterns |
| Refuse or use the SLO | The task's cost exceeds its value, or the error budget says it can wait |
| Make components uniform | Special cases dominate: give every instance the same interface and config |

**Automation needs the operator's caution built in.** Treat every input as untrusted, give every
step a deadline, put a ceiling on how much one run may change, and when a precondition fails,
stop and page rather than guess. Build reusable pieces rather than one script per incident. Then
watch the automation itself: how often it fails or has to be redone, and how many person-hours it
actually returns.

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
