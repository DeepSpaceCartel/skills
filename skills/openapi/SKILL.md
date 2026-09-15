---
name: openapi
description: How to write and review an OpenAPI 3.1/3.2 description of an HTTP API (https://spec.openapis.org/oas/v3.2.0.html, https://www.openapis.org/) - project-agnostic. Covers the document skeleton (openapi, info, servers, paths, components), paths and operations, parameters/requestBody/responses, Schema Objects and how 3.1+ reuses JSON Schema 2020-12, reusable components and $ref, security schemes (apiKey/http/OAuth2/OIDC), operationId and tag conventions, webhooks, and 3.2 additions (the query method, additionalOperations, querystring, streaming media types). Use when writing or reviewing an OpenAPI document, designing an HTTP endpoint contract, generating an API reference or client, or wiring schema-first generation in a framework like Fastify/TypeBox or Spring.
---

# OpenAPI

An OpenAPI description is a machine-readable contract for an HTTP API
([spec](https://spec.openapis.org/oas/v3.2.0.html)). It is the source
of truth that generates docs, clients, servers, and mock servers — so
treat drift between it and the running service as a bug, not a docs
chore.

Current versions: **3.2.0** (Sep 2025, strictly compatible with 3.1)
and the **3.1.x** patch line. Both reuse **JSON Schema
2020-12** — unlike 3.0, whose schema dialect only *resembled* JSON
Schema. See [`../json-schema/SKILL.md`](../json-schema/SKILL.md).

## The document skeleton

```yaml
openapi: 3.2.0            # spec version, NOT your API's version
info:
  title: Widget API
  version: 1.4.2          # your API's version (see ../semver/SKILL.md)
servers:
  - url: https://api.example.com/v1
paths: {}                 # the operations (below)
components: {}            # reusable schemas, parameters, responses, security schemes
security: []              # global security requirements (empty = no global auth)
tags: []                  # grouping/navigation metadata
```

- **`openapi`** is the version of the *specification*, `info.version`
  is the version of *your API* — do not conflate them.
- Put reusable shapes under `components` and reference them with
  `$ref: '#/components/schemas/Widget'`. Inline duplication drifts.
- Prefer `servers` with a base path over baking a host into every path.

## Paths and operations

```yaml
paths:
  /widgets/{widgetId}:
    parameters:
      - $ref: '#/components/parameters/WidgetId'
    get:
      operationId: getWidget
      summary: Fetch one widget
      responses:
        '200':
          description: The widget
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Widget' }
        '404':
          $ref: '#/components/responses/NotFound'
```

- **`operationId` is required in practice** — it names the generated
  client method. Keep it globally unique and stable; renaming it is a
  breaking change for generated clients.
- Path templates (`{widgetId}`) must match a declared parameter exactly.
- Use the correct HTTP method semantics: `GET`/`HEAD` must be safe and
  idempotent; `POST` creates; `PUT` replaces; `PATCH` partially
  updates; `DELETE` removes. Don't tunnel reads through `POST`.

## Parameters, request bodies, responses

- **`parameters`** carry a required `in` (`query`/`header`/`path`/`cookie`)
  and `name`; path params are always `required: true`. Give every
  parameter a `schema` (and `description` unless self-evident).
- **`requestBody`** is where request payloads live, with a `content`
  map keyed by media type (`application/json`). 3.2 adds a
  `querystring` keyword for describing all query parameters as a single
  Schema Object instead of one `parameters` entry each.
- **`responses`** must include every status the operation can return,
  including errors (4xx/5xx). An undocumented error still happens; the
  contract should say so. Reuse problem-detail shapes from
  [`../rfc9457/SKILL.md`](../rfc9457/SKILL.md).
- Mark optional response fields as optional in the schema. Consumers
  generate nullable/undefined handling from the schema, not from prose.

## Schemas and components

- 3.1+/3.2 schemas **are** JSON Schema 2020-12, with the OpenAPI
  additions `discriminator`, `example`/`examples`, `xml`, `externalDocs`.
  Use `$defs` for local reuse and `$ref` across the document.
- **`discriminator`** makes polymorphic `oneOf`/`anyOf` unions
  efficiently resolvable — use it when a field selects the variant.
- Reuse, don't repeat: define `Widget`, `WidgetList`, error objects, and
  common parameters once under `components`.
- Add `example`/`examples` at the schema or media-type level — generated
  docs and mock servers are far more useful with them.

## Security

```yaml
components:
  securitySchemes:
    bearerAuth: { type: http, scheme: bearer, bearerFormat: JWT }
    oauth: { type: oauth2, flows: { ... } }
security: [{ bearerAuth: [] }]   # global; override per-operation as needed
```

- Declare schemes once under `components.securitySchemes`; apply globally
  in top-level `security`, and override on an operation (including with
  an empty list `security: []` for a deliberately public endpoint).
- 3.2 adds OAuth 2.0 Device Authorization Flow and OAuth 2.0 Server
  Metadata; prefer `type: openIdConnect` over hand-rolled OIDC prose.
- Security schemes describe *how* credentials are sent, not the
  authorization model — document scopes where they matter.

## Tags and navigation

- `tags` is an ordered, documented grouping used by UIs. In 3.2 a tag
  gains `summary`, `description`, and `kind` (e.g. `kind: nav` for
  navigation-only tags tooling can skip). Reference a tag by its
  `name` from each operation's `tags: [...]`.
- Keep the set small and stable; tags are a navigation contract.

## 3.2 additions worth knowing

- `query` HTTP method (safe, idempotent query with a body).
- `additionalOperations` for methods not first-class in OpenAPI
  (e.g. `connect`).
- Streaming media types: `text/event-stream`, `application/jsonl`,
  `application/json-seq`, `multipart/mixed`, with `itemSchema`.
- `webhooks` (introduced in 3.1) describe callbacks the API *sends*.

## Generating from code

When a framework generates the document from route schemas (Fastify +
TypeBox, Spring, FastAPI, …), the generator output is the contract:
- Keep schemas on the route definitions, not in parallel prose.
- Serve the document (`GET /openapi.json`) and diff it in CI so a
  breaking change to the contract fails the build.
- Never hand-edit a generated file; fix the source schema.

## Where to look

| File | Covers |
| --- | --- |
| [`references/document-structure.md`](references/document-structure.md) | `info`, `servers`, `paths`, top-level shape, versioning |
| [`references/operations-and-parameters.md`](references/operations-and-parameters.md) | operations, parameters, bodies, responses, `operationId` |
| [`references/schemas-and-components.md`](references/schemas-and-components.md) | Schema Objects, JSON Schema dialect, `$ref`/`components`/`discriminator` |
| [`references/security-and-tags.md`](references/security-and-tags.md) | security schemes, global vs per-operation, tags, webhooks |

## What NOT to do

- Don't set `openapi:` to your API's version, or `info.version` to the
  spec version — they're different fields with different jobs.
- Don't generate clients/docs from a hand-maintained description that
  isn't validated against the running service; wire the spec into CI.
- Don't document only the happy path — every reachable 4xx/5xx is part
  of the contract.
- Don't change or reuse an `operationId` for a different operation;
  generated callers break silently on the next regeneration.
- Don't use 3.0's schema dialect with a 3.1/3.2 document (or vice
  versa) — it changes which validation keywords are legal.
