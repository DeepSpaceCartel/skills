---
name: structured-logging
description: How to emit structured logs and correlate them with traces following OpenTelemetry (log data model https://opentelemetry.io/docs/specs/otel/logs/data-model/, semantic conventions https://opentelemetry.io/docs/specs/semconv/) - project-agnostic. Covers the log record model (Timestamp, SeverityText/Number, Body, Attributes, EventName), resource attributes (service.name, service.version, deployment.environment.name), naming events instead of free-text messages, attribute namespacing and naming rules, trace_id/span_id correlation, HTTP and error semantic conventions (http.request.method, http.route, url.path, error.type, exception.*), redacting secrets, and keeping backend labels low-cardinality (e.g. Loki). Use when adding or reviewing logging, designing a log or event schema, correlating logs with traces, or debugging noisy, high-cardinality, or secret-leaking logs.
---

# Structured logging

A structured log is a record with named, typed fields, not a formatted
sentence. Follow OpenTelemetry's log data model
([spec](https://opentelemetry.io/docs/specs/otel/logs/data-model/)) and
[semantic conventions](https://opentelemetry.io/docs/specs/semconv/)
even if you don't run the OTel SDK — the naming is the reusable part,
and it's what makes logs queryable and correlatable across services.

## The model in one table

| Field | Meaning |
| --- | --- |
| `Timestamp` | when it happened, at the source |
| `ObservedTimestamp` | when the collector saw it |
| `SeverityText` / `SeverityNumber` | the level (`info`, `error`, ...) |
| `Body` | the message — ideally a stable event name, not free text |
| `Attributes` | typed fields specific to this record |
| `Resource` | where it came from (service, version, environment) — fixed per source |
| `EventName` | a stable identifier for the class of event |
| `TraceId` / `SpanId` | W3C trace context, when in a request |

## Structured fields, not interpolation

```text
# BAD: everything is a string; you can't filter or aggregate
info: "Built image registry=e cr name=app tag=1.2.3 took 4.2s"

# GOOD: a stable event with typed fields
event=image.build.completed registry=e.cr name=app tag=1.2.3 duration_ms=4200
```

The bad version forces regular-expression parsing to answer "how long do
builds take". The good version is a group-by on `name` and an average on
`duration_ms`.

## Resource attributes (constant per source)

Set these once on the logger/resource, never per call site:

| Attribute | Example |
| --- | --- |
| `service.name` | `devcontainer-builder` |
| `service.version` | the running build's version |
| `deployment.environment.name` | `production` / `staging` |

Notes:
- It's `deployment.environment.name` in current semconv — not the older
  `deployment.environment`.
- Derive `service.name` from one source (e.g. the chart's app label) so
  it can't drift from what your dashboards label.
- `service.version` should be the version actually running, not a
  config-overridable value.

## Name events, don't write prose

Give each interesting thing that happens a stable, dotted name:

```
http.request.completed
image.build.started
image.build.completed
image.build.failed
image.lookup.miss
```

- Keep names **low-cardinality** and stable; treat them as API.
- The human message/body can be the event name; the detail goes in
  attributes.
- `EventName` is a first-class field in the log model — set it rather
  than prefixing a free-text body.

## Attribute naming rules

Semconv attribute names are dot-namespaced, lowercase, with underscores
inside a segment:

- `http.request.method`, `http.route`, `url.path`, `url.scheme`
- `error.type`, `exception.type`, `exception.message`, `exception.stacktrace`
- `server.address`, `server.port`
- Domain fields use a service-specific namespace, e.g. `image.registry`,
  `image.name`, `image.tag`.

Use the standard name when one exists. Invent a namespaced one only for
genuinely domain-specific concepts.

## Severity

- Levels: `trace`, `debug`, `info`, `warn`, `error`, `fatal` (OTel names
  `SeverityText`) plus a numeric `SeverityNumber`.
- `error` means "a human should look at this"; `warn` means "degraded but
  handled". Don't cry wolf.
- Emit the **string** level (`"info"`), not a numeric enum, if a log
  backend classifies severity by text (Loki's `detected_level` is the
  common case). Pick one field name for level and keep it stable across
  the fleet — renaming a shipped, dashboard-relied-on field is pure risk.

## Correlate logs with traces

When a logger and tracer are both active, inject the W3C trace context
into every log record so you can jump from a log line to its trace:

```
trace_id=4bf92f3577b34da6a3ce929d0e0e4736 span_id=00f067aa0ba902b7
```

- Many SDKs do this automatically once tracing is enabled; verify the key
  names match what your backend queries (`trace_id`/`span_id` at the
  top level, or `trace.id`/`span.id` if you use dotted semconv style —
  pick one and be consistent).
- Log outside a request has no trace context; that's fine, don't fake it.
- Don't conflate a request ID (your own correlation id) with `trace_id` —
  keep both if you generate request IDs; they answer different questions.

## Never log secrets

- Redact `authorization`, API keys, tokens, cookies, `x-*-password`
  headers, and anything that could carry credentials — at the logger
  level (a redaction config), not by remembering not to.
- Don't log full request URLs with query strings if the querystring can
  carry secrets or high-cardinality IDs.
- Prefer structured fields over dumping whole objects (`request.headers`,
  `process.env`) — a denylist always misses something.

## Where to look

| File | Covers |
| --- | --- |
| [`references/data-model.md`](references/data-model.md) | log record fields, events vs logs, body/attributes/resource |
| [`references/semantic-conventions.md`](references/semantic-conventions.md) | general, HTTP, error/exception, resource attribute names |
| [`references/correlation.md`](references/correlation.md) | trace context propagation, trace_id/span_id, context fields |
| [`references/backends-and-cardinality.md`](references/backends-and-cardinality.md) | Loki labels, cardinality, retention, querying |

## What NOT to do

- Don't interpolate values into a message string — the value is lost as
  a field the moment you do.
- Don't log the raw `req.url` with its querystring; log the route
  (`http.route`) and path (`url.path`) separately.
- Don't put unbounded values (user IDs, URLs, timestamps) in **backend
  labels** (Loki streams) — labels are for low-cardinality dimensions.
- Don't rename an already-shipped level/field for cosmetic consistency;
  migrate dashboards first, or don't do it.
- Don't log PII or credentials "temporarily" — log pipelines are
  long-lived, copied, and hard to purge.
