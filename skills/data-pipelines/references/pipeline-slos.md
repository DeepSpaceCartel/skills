# Pipeline SLOs

What "the pipeline is healthy" means, as numbers users would recognise: how fresh the data is,
how much of what should be there is there, whether each field is filled, and whether it is
right. Measured end to end, over every source that should be read, and shown on a dashboard
that says which stage and which source is behind. Burn-rate alert maths and error budgets are
in [reliability](../../engineering-practices/references/reliability.md); this reference is
about choosing and computing pipeline SLIs. Anchor sources: Google's
[SRE Workbook, Data Processing Pipelines](https://sre.google/workbook/data-processing/) and
[SRE book, Data Processing Pipelines](https://sre.google/sre-book/data-processing-pipelines/),
and the AWS Builders' Library on
[queue backlogs](https://builder.aws.com/content/3EuRcgkTP1MI0c7zM8W6HL3WIqA/avoiding-insurmountable-queue-backlogs).

## What agents typically get wrong

- **"The job succeeded" as the SLI.** A run that exits 0 after reading half the source is a
  success by that measure. Count what reached the output, not how runs ended.
- **Per-stage SLOs only.** The workbook warns that per-stage targets don't match what users see
  and can make alerts noisy. Its example: one stage adds a field, a later stage drops it, both
  report success, and users get nothing.
- **A denominator that shrinks with the outage.** Freshness computed over "sources read this
  hour" or "sources not paused" stays at 100% while a whole provider is dark. The denominator
  is every source that should be current.
- **Record counts without field counts.** A list endpoint that omits a field for some records
  produces the right number of rows with a hole in each. Only per-field completeness shows it.
- **Freshness from the wrong clock.** Client or source timestamps can be late or wrong. The
  workbook's case study timestamps events on receipt for that reason. Measure from a clock you
  control.
- **Queue depth as the latency signal.** Depth says how much is waiting, not how long. The AWS
  article uses the age of messages at dequeue, measured on the first attempt.
- **Metrics only at the end of a run.** The SRE book notes that batch jobs often report stats on
  completion, so a run that dies mid-way reports nothing. Emit progress while running.
- **Correctness left unmeasured because it is hard.** It is hard without a known answer, so make
  one: golden inputs with known outputs (the workbook suggests test accounts).

## Procedure

1. **Name the users and what they need from the data.** For a search index: new items findable
   within N hours. For a report: complete by a date. For an alert feed: few false "removed"
   events. Each need becomes one SLI.
2. **Pick SLIs from the four families** (below), each as good / valid over a window.
3. **Define the population.** List every source, tenant or partition that should be current.
   Paused, cooling-down, erroring and never-read sources stay in the denominator. Report them
   separately as reasons, not as exclusions.
4. **Measure end to end.** Freshness from source-change (or our first sight) to visible in the
   final store. Completeness against an independent count where one exists.
5. **Add per-field completeness** for each field users filter or alert on. Compare against a
   rolling baseline per source, because some sources never send some fields.
6. **Set targets loosely first**, agreed with the users, then tighten. Compute the error budget
   and write what happens when it is spent (see
   [reliability](../../engineering-practices/references/reliability.md)).
7. **Alert on the SLI symptoms** with a runbook link on every page. Keep cause metrics (CPU,
   queue depth, error counts) on the dashboard for diagnosis.
8. **Build the dashboard** (below) and link it from the pipeline's system diagram.

## Techniques

**The four SLI families**

| Family | Good event | Valid events | Catches |
|---|---|---|---|
| Freshness | Source's last proven-complete read is younger than max age | Every source that should be current | Stalled workers, cooldowns, a dark provider |
| Coverage | Source is tracked and read at least once | Every source known to exist | Discovery gaps, sources stuck in review |
| Completeness | Item from the source is present in the output; field is non-empty | Items the source states, or a sample from an audit | Partial walks, dropped fields, filtered rows |
| Correctness | Output matches a known answer | Golden inputs, or audited samples | Parser and transform bugs, wrong joins |

- **Freshness forms.** A batch job can promise a finish time; a stream can bound how old its
  oldest waiting item gets, or what share of items clears within T. A fleet of sources needs the
  share of sources whose last *proven-complete* read is within T; a failed or partial run does
  not reset the clock.
- **Completeness against a stated total.** Where a source states how many items it has, rows
  walked over the stated total is a per-run completeness check. See
  [completeness-and-absence](completeness-and-absence.md).
- **Completeness by audit.** Where no total exists, sample sources daily, read them by an
  independent path, and compare. The workbook's case study audits delivered against published
  events daily.
- **Per-field completeness.** For each field, the share of records with a usable value. Alert
  on a drop from the source's own baseline, not an absolute floor.
- **Golden data.** A few inputs per source type whose correct output is known and checked in.
  Run them through the real pipeline on a schedule; any diff is a correctness failure.
- **Message age.** On dequeue, now minus enqueue time. AWS records it on the first attempt
  only, so retries and slow readers don't hide a system-wide delay.
- **Priority tiers.** The workbook suggests processing higher-priority data first when short of
  capacity. Give each tier its own freshness SLO.

**The pipeline dashboard**

| Panel | Shows |
|---|---|
| SLIs vs targets | Freshness, coverage, completeness, correctness, with budget remaining |
| Not-fresh sources by reason | Erroring, cooling down, paused, never read, our-side failure |
| Per-field completeness | One line per key field against baseline |
| Stage progress | Items in, out, failed and dead-lettered per stage, live during the run |
| Queue age | Oldest message age and first-attempt age per queue or tier |
| Canaries | Known-good sources: if these fail, the fault is ours |
| Run history | Duration and item counts per run, to spot slow growth before it breaks |

## Example

A freshness SLI over every expected source, a per-field completeness SLI, and an alert. It
also shows how dropping "not due" sources hides the outage.

```python
from datetime import datetime, timedelta, timezone

def freshness_sli(sources, now, max_age):
    """Share of ALL expected sources whose last proven-complete read is within max_age.
    Paused, cooling-down and our-side-failed sources stay in the denominator."""
    good = sum(1 for s in sources
               if s["last_complete_read"] and now - s["last_complete_read"] <= max_age)
    return good / len(sources)

def field_completeness(records, fields):
    """Per-field share of records with a non-empty value."""
    n = len(records)
    return {f: sum(1 for r in records if r.get(f) not in (None, "", [])) / n for f in fields}

def alerts(fresh, completeness, baseline, *, fresh_slo=0.95, max_drop=0.05):
    out = []
    if fresh < fresh_slo:
        out.append(f"freshness {fresh:.1%} < SLO {fresh_slo:.0%}")
    for f, v in completeness.items():
        if baseline[f] - v > max_drop:
            out.append(f"field '{f}' completeness {v:.1%}, baseline {baseline[f]:.1%}")
    return out

now = datetime(2026, 1, 10, 12, tzinfo=timezone.utc)
h = timedelta(hours=1)
sources = ([{"last_complete_read": now - 2 * h}] * 900       # healthy
           + [{"last_complete_read": now - 30 * h}] * 60     # cooling down, still counted
           + [{"last_complete_read": None}] * 40)            # never read completely
records = ([{"title": "t", "location": "Berlin"}] * 7000
           + [{"title": "t", "location": None}] * 3000)     # list endpoint omitted it
fresh = freshness_sli(sources, now, max_age=6 * h)
comp = field_completeness(records, ["title", "location"])
for a in alerts(fresh, comp, baseline={"title": 1.0, "location": 0.97}):
    print("ALERT:", a)
print(f"excluding cooling/never-read: {freshness_sli(sources[:900], now, 6 * h):.1%}")
```

Run with Python 3.13, it printed `ALERT: freshness 90.0% < SLO 95%`,
`ALERT: field 'location' completeness 70.0%, baseline 97.0%`, and
`excluding cooling/never-read: 100.0%`. The same data reads healthy once the cooling and
never-read sources leave the denominator, and the row count alone (10,000) shows nothing wrong
with `location`. In production, feed these ratios into multiwindow burn-rate rules rather than a
single threshold.

## Gotchas and contested points

- **Baselines move.** A source that legitimately stops sending a field looks like a regression.
  Keep per-source baselines and let a person accept a new one.
- **Prefer late to wrong.** That is the workbook's stance: downstream jobs should wait for complete
  input rather than run on partial data. Streaming systems with event-time windows can start
  partial work earlier; say which data is provisional.
- **Coverage is open-ended.** The number of sources that exist is unknown. Measure coverage
  against a sample found by an independent method, not against your own list.
- **Too many SLOs** dilute attention. Two to four per user group is usually enough; keep the rest
  as dashboard panels.
- **Latency SLOs on asynchronous work still matter.** The AWS article's point: work done too late
  loses its value, which is an availability loss in practice.

## Review checklist

1. Is each SLI defined as good over valid events, with the population written down?
2. Do paused, cooling-down, erroring and never-read sources stay in the freshness denominator?
3. Does freshness reset only on a proven-complete read, measured from a clock we control?
4. Is there a per-field completeness SLI for every field users filter or alert on, against a
   per-source baseline?
5. Is at least one SLI measured end to end, from source to the store users read?
6. Is correctness checked against golden data or an independent audit, on a schedule?
7. Is queue latency measured as message age on first attempt, not depth?
8. Do runs emit progress while running, so a run that dies mid-way is visible?
9. Do alerts fire on SLI symptoms, each with a runbook, with causes left to the dashboard?
10. Does the dashboard break not-fresh sources down by reason, and include canary sources?

## Related

[completeness-and-absence](completeness-and-absence.md) (stated totals, our-side failures),
[failure-isolation](failure-isolation.md) (cooldowns that empty a provider),
[reliability](../../engineering-practices/references/reliability.md) (burn-rate alerts, error
budgets), [`structured-logging`](../../structured-logging/SKILL.md) (per-item IDs).

## Sources

Google SRE Workbook, [Data Processing Pipelines](https://sre.google/workbook/data-processing/)
(SLOs for freshness, correctness, isolation; end-to-end measurement; golden data; the case
study's timeliness, skewness and completeness SLOs; stale versus incorrect data). Google SRE
book, [Data Processing Pipelines](https://sre.google/sre-book/data-processing-pipelines/)
(metrics reported only at the end of a run). AWS Builders' Library,
[Avoiding insurmountable queue backlogs](https://builder.aws.com/content/3EuRcgkTP1MI0c7zM8W6HL3WIqA/avoiding-insurmountable-queue-backlogs)
(message age, first-attempt age, late work as lost availability). The four-family table, the
dashboard layout and the denominator rule are this skill's synthesis.
