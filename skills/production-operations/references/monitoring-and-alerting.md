# Monitoring and alerting

What to measure on a running service, what turns into a page or a ticket, and how to know the
monitoring itself still works. SLO definition, error budgets and the burn-rate maths live in
[`engineering-practices` reliability](../../engineering-practices/references/reliability.md); this
reference assumes an SLO exists and covers everything around it. Anchor sources: the SRE book's
[Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/) and
[Practical Alerting](https://sre.google/sre-book/practical-alerting/), the SRE Workbook's
[Monitoring](https://sre.google/workbook/monitoring/), and the Prometheus
[alerting practices](https://prometheus.io/docs/practices/alerting/),
[instrumentation](https://prometheus.io/docs/practices/instrumentation/) and
[Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/) pages.

## What agents typically get wrong

- **An "alert" that is a line in a log file.** A watchdog that writes `WARN stalled` and waits for
  someone to read it is not monitoring. If no person or system is notified, the stall is found by
  a user.
- **No watch on the watcher.** The scraper, rule evaluator or notifier dies, and silence looks like
  health. Every alerting path needs a heartbeat that something outside it checks.
- **Health checks green while the service is useless.** A `/healthz` that returns 200 from the
  process says nothing about whether writes commit. Only a black-box probe of the real user path
  (write, then read back) catches that.
- **Only symptom alerts.** Symptoms are the right default for pages, but some causes give no
  symptom until it is too late: a disk filling, a certificate or token expiring, a quota running
  out, a backup that stopped. These need their own deadline checks.
- **Paging on every cause.** CPU, queue depth and per-task restarts page for things that do not
  hurt users, and the on-call learns to ignore the pager.
- **Averages.** A mean latency hides a slow tail; measure distributions (histograms) and alert on
  percentiles or on the SLO.
- **One alert per replica.** A fleet-wide problem sends hundreds of notifications. Group, and
  inhibit dependent alerts.
- **Alerts with no owner, no runbook and no review.** Rules nobody has seen fire in a quarter are
  either broken or useless.
- **Dashboards as wallpaper:** dozens of panels and no question they answer.

## Procedure

1. **Write down the user-visible journeys** and their SLIs (from the SLO work). These become the
   symptom alerts.
2. **Instrument the four golden signals** for each serving component and each dependency it
   calls: traffic, errors, latency (successful and failed requests kept apart) and saturation of
   the scarcest resource.
3. **Add a black-box probe** per journey that exercises the real path from outside: for a write
   API, create a record and read it back; for a pipeline, push a marker item and time its
   arrival at the end.
4. **Build the deadline inventory** (below): every certificate, credential, quota, disk and
   scheduled job whose failure is silent until it is fatal.
5. **Classify every alert** with the page-or-ticket table. Anything that is neither goes to a
   dashboard or is deleted.
6. **Route and deduplicate:** group by service and alert name, inhibit downstream alerts while a
   dependency alert fires, and point Prometheus at every Alertmanager instance rather than a load
   balancer in front of them.
7. **Monitor the monitoring:** an always-firing heartbeat alert that an external service expects
   to receive, plus alerts on scrape failures and rule evaluation errors.
8. **Test before paging.** Run a new alert in ticket-only mode for about a week and count how
   often it would have paged (Workbook on-call chapter). Keep alert config in version control and
   lint it in CI.
9. **Review monthly:** page count per shift, alerts that never fired, alerts that fired with no
   action taken.

## Techniques

**Page, ticket or neither.** A decision table in this skill's own words, built on the SRE book's
paging criteria:

| Question | Yes | No |
|---|---|---|
| Are users hurt now, or will they be within hours if nobody acts? | keep asking | ticket or dashboard |
| Does it need a human decision (not a scripted reaction)? | keep asking | automate the reaction |
| Is it already covered by an alert that is firing or will fire? | suppress it | keep asking |
| Must someone act within the next hour? | **page** | **ticket** (business hours) |

**White-box and black-box together.** White-box (exported metrics, logs) sees causes, and failures
that retries hide from the caller. Black-box sees what users see, including failures that never reach the server:
DNS, TLS, a load balancer with no healthy backends. Probe both the public entry point and the
backends behind it, so the alert says where the break is.

**Symptoms page, causes explain.** Put cause metrics on the dashboard the page links to. Whether a
signal is a symptom depends on whose service it is: a storage team pages on its own slow queries,
while the web tier in front only shows them on its dashboard.
Page on latency at one layer of a stack, as high as possible (Prometheus).

**The deadline inventory.** Cause-side checks that must exist whatever the SLO says. Each is a
timestamp or a level, turned into "time left":

| Item | Signal | Page | Ticket |
|---|---|---|---|
| Disk and volume fill | time-to-full by linear prediction (see [`data-integrity` state-and-storage](../../data-integrity/references/state-and-storage.md)) | hours left | days left |
| TLS certificates | expiry timestamp from a probe or the issuer | under ~3 days | under ~3 weeks |
| Tokens, API keys, registry and cloud credentials | expiry date recorded at issue time | under ~2 days | under ~3 weeks |
| Quotas and rate limits | usage / limit, and its trend | at the limit, users affected | headroom under ~20% |
| Backups, batch jobs, cron | Unix timestamp of last success | when lateness hurts users | at two missed cycles |
| Each pipeline stage, each crawler | timestamp of the last heartbeat item seen | stall past the freshness SLO | -- |

The thresholds are starting points to tune, not sourced values. Credentials without a machine-
readable expiry go into a list with their dates, and a scheduled job turns that list into metrics.

**Batch jobs.** Export the Unix timestamp of the last success as a gauge, never "seconds since",
and compute the age in the query (`time() - last_success`). Alert at no less than two full run
cycles: a job every 4 h that takes 1 h gets a 10 h threshold (Prometheus).

**Dashboards answer questions.** One page per service: the golden signals, the SLO and budget
left, current deploy and config versions, and each dependency's signals. The Workbook asks for
versions and flags on the dashboard, because "what changed?" is the first question in an
incident. Add panels when a postmortem shows a missing one.

**Resolution and retention.** Scrape fast enough for the SLO (a probe every 30-60 s is plenty for a
99.9% target); keep months of data for trends. Keep labels low-cardinality; per-entity IDs
belong in logs, not metric labels.

**Alertmanager hygiene.** Group by `alertname` and service so one outage is one notification;
defaults are `group_wait` 30 s, `group_interval` 5 m, `repeat_interval` 4 h. Inhibit rules mute
targets while a source alert fires, matched on `equal` labels. Silences are for known work, with
an expiry and a comment. Email and Slack receivers do not send resolved notices by default
(`send_resolved: false`).

**Hosted monitoring and paging** (synthesis) have the same parts under other names: uptime or
synthetic checks are the black-box probes, notification or escalation policies are the routing
tree, maintenance windows are silences. Give the hosted pipeline its own heartbeat too, and export
its configuration to version control.

## Example

A heartbeat for the alerting pipeline and a freshness rule for a nightly job (Prometheus):

```yaml
groups:
  - name: meta
    rules:
      - alert: AlertPipelineHeartbeat      # always fires; an external dead-man's switch
        expr: vector(1)                    # pages when it stops arriving
        labels: {severity: heartbeat}
      - alert: BackupStale
        expr: time() - backup_last_success_timestamp_seconds > 2 * 86400
        labels: {severity: ticket}
        annotations:
          runbook_url: https://runbooks.example.internal/backup-stale
```

Route `severity: heartbeat` to an external dead-man's-switch receiver that repeats often and
alerts when it stops (the prometheus-operator Watchdog runbook describes this pattern). The YAML
was checked to parse; the rules were not evaluated by Prometheus here.

The same logic as a scheduled script, for a deadline inventory that is not in Prometheus:

```python
from dataclasses import dataclass
from datetime import datetime, timedelta as td, timezone

@dataclass(frozen=True)
class Deadline:
    name: str
    due: datetime      # expiry time, or last success + allowed age
    page: td           # page when this little is left
    ticket: td         # ticket when this little is left

def classify(d, now):
    left = d.due - now
    return ("page" if left <= d.page else "ticket" if left <= d.ticket else "ok"), left

now = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
for d in [
    Deadline("api TLS certificate", now + td(days=9), td(days=3), td(days=21)),
    Deadline("registry pull token", now + td(hours=20), td(days=2), td(days=21)),
    # freshness: due = last success + allowed age (two cycles for a nightly job)
    Deadline("nightly backup", now - td(hours=50) + td(hours=48), td(days=-5), td(0)),
    Deadline("alert heartbeat", now - td(minutes=12) + td(minutes=10), td(0), td(0)),
]:
    verdict, left = classify(d, now)
    print(f"{d.name:20} {verdict:6} {left.total_seconds() / 3600:+.1f} h")
```

Run: the certificate gave `ticket` (+216 h), the token `page` (+20 h, inside its 2-day page
window), the backup `ticket` (-2 h: 50 h since the last success, past two cycles; it would page
only a week late) and the missed heartbeat `page` (-0.0 h, two minutes overdue).

## Gotchas and contested points

- **Deadline alerts are the exception to symptom-only paging.** Expiry and fill give no
  symptom until the outage, so they page on time left.
- **Black-box probes that write** need their own test tenant or marker records, and must clean up.

## Review checklist

1. Does every user journey have a symptom alert and a black-box probe of its real path, including
   writes?
2. Could the health check stay green while every write fails? What would page then?
3. Does every alert reach a person or a ticket queue, rather than only a log?
4. Is there an always-firing heartbeat checked by something outside the monitoring stack?
5. Is every certificate, credential and token listed with its expiry, with ticket and page
   thresholds?
6. Do disks have time-to-full alerts, and quotas a headroom alert?
7. Do backups, cron and batch jobs export a last-success timestamp, alerted at two missed cycles?
8. Does each page pass the page-or-ticket table and link a runbook and a dashboard?
9. Are alerts grouped and inhibited so one outage sends one notification?
10. Are alert rules in version control, linted, and trialled before they page?

## Related

[`engineering-practices` reliability](../../engineering-practices/references/reliability.md)
(SLOs, burn-rate alerts), [`data-integrity`](../../data-integrity/SKILL.md) (time-to-full, backup
checks), [`infrastructure-patterns` health checks](../../infrastructure-patterns/references/health-checks-and-probes.md),
[`data-pipelines`](../../data-pipelines/SKILL.md) (freshness and completeness SLIs),
[`structured-logging`](../../structured-logging/SKILL.md), [on-call](on-call.md),
[runbooks](runbooks-and-safe-operations.md).

## Sources

SRE book: [Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/),
[Practical Alerting](https://sre.google/sre-book/practical-alerting/); SRE Workbook:
[Monitoring](https://sre.google/workbook/monitoring/), [On-Call](https://sre.google/workbook/on-call/);
Prometheus: [Alerting](https://prometheus.io/docs/practices/alerting/),
[Instrumentation](https://prometheus.io/docs/practices/instrumentation/),
[Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/),
[Alertmanager configuration](https://prometheus.io/docs/alerting/latest/configuration/);
prometheus-operator [Watchdog runbook](https://runbooks.prometheus-operator.dev/runbooks/general/watchdog/);
[blackbox_exporter](https://github.com/prometheus/blackbox_exporter) README and
[`prober/http.go`](https://raw.githubusercontent.com/prometheus/blackbox_exporter/master/prober/http.go).
The deadline inventory, its thresholds and the hosted-service mapping are this skill's synthesis.
The blackbox exporter's certificate-expiry metric name was not confirmed, so it is not named.
