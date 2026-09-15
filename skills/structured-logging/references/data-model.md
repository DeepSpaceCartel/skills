# Log data model

Source: [OpenTelemetry Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/)
(Stable).

A log record is a structured event, not a line of text. The fields:

| Field | Required | Notes |
| --- | --- | --- |
| `Timestamp` | no | When the event occurred, origin clock, nanoseconds since epoch. |
| `ObservedTimestamp` | yes | When it was observed by the collecting system; for SDK-emitted logs this is usually generation time. |
| `SeverityText` | no | The level string (`info`, `error`). |
| `SeverityNumber` | no | Numeric 1–24, mapped in bands to `Trace`…`Fatal4`. |
| `Body` | no | The message — any type. A string body is fine, but see events below. |
| `Resource` | yes | Attributes describing the source (service, host, k8s object). Fixed for a source. |
| `Attributes` | no | Extra fields specific to this occurrence. |
| `TraceId` | no | W3C trace-id of the containing span. |
| `SpanId` | no | Span-id; if present, `TraceId` must also be present. |
| `EventName` | no | Stable name identifying the event class; non-empty means it's an Event. |
| `Flags` | no | Trace flags (sampling), W3C. |

## Logs vs Events

An **Event** is a log record whose `EventName` uniquely identifies a
class of event and whose `Body`/`Attributes` carry the specifics. Use
events for domain milestones (`image.build.completed`), and reserve
free-form logs for diagnostic messages.

The distinction matters because an event name is a **contract**: you
build dashboards and alerts on it. Renaming one is a breaking change.

```json
{
  "Timestamp": "2026-09-15T12:00:00.123Z",
  "SeverityText": "info",
  "EventName": "image.build.completed",
  "Body": "image.build.completed",
  "Resource": {
    "service.name": "devcontainer-builder",
    "service.version": "0.1.0",
    "deployment.environment.name": "production"
  },
  "Attributes": {
    "image.registry": "ghcr.io",
    "image.name": "example/app",
    "image.tag": "1.2.3",
    "duration_ms": 4200
  },
  "TraceId": "4bf92f3577b34da6a3ce929d0e0e4736",
  "SpanId": "00f067aa0ba902b7"
}
```

## Resource attributes

The `Resource` is the identity of the emitter. The three that make logs
usable across a fleet:

- `service.name` — required in practice; the logical service.
- `service.version` — the running version.
- `deployment.environment.name` — `production`, `staging`, etc.

Set them once. If they vary per record, they aren't resource attributes.

## Severity

OTel defines six text severities with numeric subtypes:

| `SeverityText` | `SeverityNumber` range |
| --- | --- |
| `TRACE` | 1–4 |
| `DEBUG` | 5–8 |
| `INFO` | 9–12 |
| `WARN` | 13–16 |
| `ERROR` | 17–20 |
| `FATAL` | 21–24 |

The trailing number (`INFO2`) encodes extra granularity within a level
and is optional. Most app code sets the level and ignores the subtype.

## Mapping from an existing logging library

When shaping structured logs out of Pino/Winston/zap/structlog/etc.:

- Put the level into `SeverityText`/`level` (string), not a numeric
  enum, if the backend reads text.
- Map the message to `Body` (or `EventName` for events).
- Map extra fields to `Attributes`; don't stringify them into the body.
- Add resource attributes at logger construction, not per call.
- Let the tracing instrumentation add `TraceId`/`SpanId`; don't
  hand-thread them.

## Cardinality of attributes

`Attributes` are per-record and may be high-cardinality (a request id, a
duration, a tag). That's fine — they're indexed as data, not as stream
identity. The cardinality rule applies to *backend labels*, not to
attributes; see [`backends-and-cardinality.md`](backends-and-cardinality.md).
