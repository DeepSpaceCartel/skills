# Semantic conventions

Source: [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/).
Use the standard attribute name when one exists; only invent a
namespaced name for genuinely domain-specific concepts.

## General attribute rules

- Lowercase, dot-separated namespaces: `http.request.method`,
  `db.system`, `k8s.pod.name`.
- Segments after a dot use underscores for multi-word parts:
  `http.request.header.x_custom_header`.
- Values are typed (string, int, double, bool, arrays of these) — not
  "everything is a string".
- Reserved namespaces you must not squat on: `otel.*` (OTel compat) and
  the standard namespaces (`http.*`, `k8s.*`, `cloud.*`, ...).

## Resource attributes

| Attribute | Meaning |
| --- | --- |
| `service.name` | Logical service name. |
| `service.version` | Running version. |
| `service.instance.id` | Unique instance id. |
| `deployment.environment.name` | Environment (`production`). |
| `telemetry.sdk.name`/`.language`/`.version` | SDK metadata (auto). |
| `k8s.namespace.name`, `k8s.pod.name`, `k8s.deployment.name` | K8s identity. |
| `cloud.provider`, `cloud.region`, `cloud.account.id` | Cloud identity. |

`service.instance.id` and `telemetry.*` are often set by the SDK/collector.

## HTTP (server and client)

| Attribute | Meaning |
| --- | --- |
| `http.request.method` | `GET`, `POST`, ... |
| `http.route` | The route **template** (`/widgets/{id}`), not the path. |
| `url.path` | The concrete path (`/widgets/123`). |
| `url.query` | Query string. **Often sensitive/high-cardinality — handle with care.** |
| `http.response.status_code` | Status code. |
| `server.address` / `server.port` | Target host/port. |
| `user_agent.original` | User-Agent header. |
| `http.request.body.size` / `http.response.body.size` | Sizes. |

Key distinction for logs: log `http.route` (bounded) not the raw URL.
`/widgets/123` and `/widgets/456` are the same route; logging the path
for every request creates unbounded distinct values.

## Errors and exceptions

| Attribute | Meaning |
| --- | --- |
| `error.type` | Stable, low-cardinality error classification (`timeout`, `invalid_argument`, ... or an exception type). |
| `exception.type` | Exception class/type name. |
| `exception.message` | Exception message. |
| `exception.stacktrace` | Full stack trace (string). |

- `error.type` is the field to group and alert on; make its values
  bounded and meaningful, not the raw message.
- For a caught-and-handled error, still record `error.type` plus
  context; for an unhandled exception, include the `exception.*` set.
- OTel's reserved `exception` **event** name is for the standard
  exception event.

## Messaging, database, and other domains

Semconv covers many domains (`messaging.*`, `db.*`, `rpc.*`, `faas.*`,
`gen_ai.*`, ...). Before inventing `myapp.db.call`, check whether
`db.system`, `db.operation.name`, `db.collection.name`, etc. already fit.

## Domain-specific namespacing

When nothing standard fits, namespace under your domain:

```
image.registry, image.name, image.tag, image.digest
build.duration_ms, build.cache_hit
```

Rules: pick the namespace once, document it, and don't mix styles
(`image.registry` and `registry` for the same thing). Treat the names as
stable — they're queried by dashboards.

## Stability

Semconv attribute groups are marked Stable / Development / Experimental.
Stable names won't break; Development ones can. If you depend on a
development convention, pin your SDK/semconv package version and revisit
on upgrade. Prefer stable conventions in anything long-lived.
