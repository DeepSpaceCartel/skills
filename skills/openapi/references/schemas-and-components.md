# Schemas and components

OpenAPI 3.1+ schemas are JSON Schema 2020-12 with a few OpenAPI
keywords added. The full keyword set lives in
[`../../json-schema/SKILL.md`](../../json-schema/SKILL.md); this file
covers how OpenAPI reuses it.

## The Schema Object

A Schema Object is a JSON Schema 2020-12 schema, plus:

| Keyword | Meaning |
| --- | --- |
| `discriminator` | Field (and optional `mapping`) selecting a `oneOf`/`anyOf` variant. |
| `example` / `examples` | Media-type or schema-level samples. |
| `xml` | XML representation hints (`name`, `namespace`, `attribute`, `wrapped`). |
| `externalDocs` | Link to further documentation. |

Everything else (`type`, `properties`, `required`, `enum`, `allOf`,
`oneOf`, `$ref`, `$defs`, `unevaluatedProperties`, `format`, ...) is
plain JSON Schema 2020-12 semantics. Because it's a real dialect:

- `$ref` **can** carry sibling keywords (e.g. `description` next to a
  `$ref`) — unlike 3.0, where siblings were ignored.
- `nullable: true` is gone; express nullability as `type: ["string", "null"]`.
- Use `unevaluatedProperties: false` to close objects that compose via
  `allOf` (this is the 2020-12 replacement for 3.0 `additionalProperties: false`
  inside composed schemas).

## `components`

`components` is a holding area for reusable objects, all referenced by
`$ref` from elsewhere. Its maps:

| Key | Holds |
| --- | --- |
| `schemas` | Schema Objects (`Widget`, `Error`, ...) |
| `responses` | Response Objects |
| `parameters` | Parameter Objects |
| `requestBodies` | Request Body Objects |
| `headers` | Header Objects |
| `examples` | Example Objects |
| `securitySchemes` | Security Scheme Objects |
| `links` | Link Objects |
| `callbacks` | Callback Objects |
| `pathItems` | Path Item Objects (3.1+) |

Reference with a JSON Pointer: `$ref: '#/components/schemas/Widget'`.

## Rules for reusable schemas

- **Name by concept, not by endpoint**: `Widget`, `WidgetCreate`,
  `WidgetUpdate`, `WidgetList` — not `PostWidgetsRequestBody`.
- **Separate request and response schemas** when they differ (server
  fields, required-ness, read-only attributes). Don't force one shape to
  serve both.
- **Compose, don't copy**: `allOf` a shared base; use `$defs` inside a
  schema for local helpers.
- Use `readOnly: true` / `writeOnly: true` to mark fields that appear
  only in responses / requests; generators honor these.

## Polymorphism

```yaml
components:
  schemas:
    Pet:
      oneOf:
        - $ref: '#/components/schemas/Cat'
        - $ref: '#/components/schemas/Dog'
      discriminator:
        propertyName: petType
        mapping:
          cat: '#/components/schemas/Cat'
          dog: '#/components/schemas/Dog'
```

The discriminator turns an ambiguous union into an O(1) lookup for
tooling and makes generated models cleaner. Ensure every variant
requires the discriminator property.

## Paging and collections

Model a list envelope explicitly rather than returning a bare array:

```yaml
WidgetList:
  type: object
  required: [items]
  properties:
    items: { type: array, items: { $ref: '#/components/schemas/Widget' } }
    next: { type: ["string", "null"] }
```

If you follow JSON:API instead, use that document structure — see
[`../../jsonapi/SKILL.md`](../../jsonapi/SKILL.md). Don't mix the two in
one API.

## Validation

Keep the description honest by validating it in CI:

- `openapi-generator validate`, `redocly lint`, or `swagger-cli validate`.
- For a code-first service, regenerate and diff the served
  `/openapi.json` so an unintended contract change fails the build.
