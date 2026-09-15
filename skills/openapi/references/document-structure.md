# Document structure

The top-level OpenAPI Object, and the fields that shape a whole
document. Spec: <https://spec.openapis.org/oas/v3.2.0.html>.

## Required vs optional at the top level

| Field | Required | Notes |
| --- | --- | --- |
| `openapi` | yes | The **spec** version string, e.g. `3.2.0`. Tooling switches behavior on `major.minor`. |
| `info` | yes | `info.title` and `info.version` are required; `description`, `termsOfService`, `contact`, `license` optional. |
| `paths` | conditional | Required unless the document describes only `webhooks` (3.1+). |
| `servers` | no | Defaults to a single server at `/` when omitted. |
| `components` | no | Reusable objects, referenced by `$ref`. |
| `security` | no | Global security requirement list; can be overridden per operation. |
| `tags` | no | Ordered metadata for grouping operations in UIs. |
| `externalDocs`, `webhooks`, `jsonSchemaDialect` | no | See below. |

## `info`

`info.version` is the version of the **API being described** — your
service's version, not the spec's. It's a free-form string but a SemVer
value ([`../../semver/SKILL.md`](../../semver/SKILL.md)) is the useful
convention. `info.title` shows up as the docs heading, so make it a
real product name, not the repo name.

## `servers`

```yaml
servers:
  - url: https://api.example.com/v1
    description: Production
  - url: https://staging.example.com/v1
    description: Staging
```

- Each entry has a `url` (may contain `{variables}`) plus optional
  `variables` (with `default` and `enum`).
- A per-path or per-operation `servers` overrides the global list —
  use it sparingly; a differing base path usually signals two APIs.
- Don't put credentials or environments in the URL beyond host/path.

## Versioning the API

Two independent numbers coexist:

1. `info.version` — this API release.
2. The URL base path (`/v1`) or header used to select a major version.

Keep the *major* version in the URL (or equivalent) and let
`info.version` track the full release. When you cut a breaking change,
publish a new path (`/v2`) and a new description; don't silently mutate
the `1.x` contract.

## `jsonSchemaDialect`

In 3.1+, the default schema dialect is JSON Schema 2020-12. A
top-level `jsonSchemaDialect` can set a different default for schemas
that don't declare their own `$schema`. Only change this deliberately —
most tooling assumes 2020-12.

## `externalDocs`

A pointer (`url`, optional `description`) to human documentation that
lives elsewhere. Use it to link guides; keep the contract itself in the
description, not in prose only the linked page has.

## A minimal valid document

```yaml
openapi: 3.2.0
info:
  title: Widget API
  version: 0.1.0
servers:
  - url: https://api.example.com/v1
paths:
  /health:
    get:
      operationId: getHealth
      responses:
        '200':
          description: Service is up
```
