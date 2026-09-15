# Backends and cardinality

Structured logs are only as good as how the backend indexes them. The
one rule that matters most: **labels are for low-cardinality
dimensions; everything else is data.**

## Labels vs data (Loki as the canonical example)

Loki (and similar systems) group log streams by a fixed label set. A
label with unbounded distinct values creates an explosion of streams —
the classic outage cause.

| Good label (low cardinality) | Bad label (high cardinality) |
| --- | --- |
| `service` / `app` | `request_id` |
| `environment` (`prod`, `staging`) | `user_id` |
| `cluster` / `namespace` | `url` / `path` |
| `level` (5-ish values) | `timestamp` |
| `event_name` (bounded set, if stable) | `duration_ms` |

Everything else belongs in the log **body/attributes**, which are
indexed differently (or scanned), not in the label set.

## Rule of thumb

- If the number of distinct values is bounded and small (≲ tens), it can
  be a label.
- If it grows with traffic or users (ids, URLs, IPs, timings), it's
  data, not a label.
- Promote a field to a label only after confirming its cardinality, and
  preferably with the platform team.

## Level as a field, not a label (usually)

Putting `level` on every log line lets the backend classify severity —
Loki's `detected_level` heuristic reads a text level and lets you filter
`{service="x"} | level="error"` or build an error-rate panel. If your
logger emits a numeric level (Pino's default is a number), override it
to the string label so the backend classifies correctly. Keep the field
**name** stable (`level`, not `severity`) once dashboards depend on it.

## Retention and cost

- Log volume is dominated by high-frequency info logs (per-request
  access logs). Either sample/drop them at the collector or keep them
  terse and structured.
- `debug` should be off in production by default, togglable per service.
- Stack traces are expensive; log them once at the error's origin, not
  at every layer that re-wraps it.

## Querying well

Structured fields make these one-liners instead of regex:

```
# error rate by event
sum by (event_name) (rate({service="devcontainer-builder"} | level="error" [5m]))

# p95 build duration from a field, not a parsed string
quantile_over_time(0.95, {event_name="image.build.completed"} | unwrap duration_ms [1h])

# trace everything for one trace id
{service=~".+"} | trace_id="4bf92f3577b34da6a3ce929d0e0e4736"
```

## Access logs specifically

The default per-request access log that logs the raw `url` including its
query string is the canonical anti-pattern:

- high cardinality (every path/id is a distinct value), and
- a latent secret-leak surface (tokens/keys in query params).

Replace it with a structured request-completed event carrying
`http.route` (the template), `url.path`, `http.request.method`,
`http.response.status_code`, duration, and the trace ids.

## A workable default label set

```
service, environment, level, cluster (or region)
```

Start there. Add a label only when a query you need can't be answered
from the structured fields.
