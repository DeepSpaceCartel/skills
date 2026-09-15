# Operations and parameters

How an individual endpoint is described. Spec:
<https://spec.openapis.org/oas/v3.2.0.html#operation-object>.

## The Path Item

A path key (`/widgets/{widgetId}`) maps to a Path Item containing:

- the HTTP methods (`get`, `put`, `post`, `delete`, `options`, `head`,
  `patch`, `trace`, and in 3.2 `query` + `additionalOperations`),
- shared `parameters` applied to every operation under that path,
- `servers` (optional override), `summary`, `description`.

Path template variables (`{widgetId}`) must be declared as `path`
parameters, either on the Path Item or on each operation.

## The Operation Object

| Field | Purpose |
| --- | --- |
| `operationId` | Unique, stable name for generated client methods. |
| `summary` / `description` | One-liner / CommonMark detail. |
| `parameters` | Query/header/path/cookie inputs. |
| `requestBody` | The request payload. |
| `responses` | Status code → Response Object. Required. |
| `tags` | Navigation grouping (names must exist in top-level `tags`). |
| `security` | Per-operation override of global security. |
| `deprecated` | `true` marks the operation as deprecated (still callable). |
| `callbacks` | Out-of-band requests triggered by this operation. |

**`operationId` rules:** globally unique, ASCII, stable across
releases. It is the API of your generated SDK.

## Parameters

```yaml
components:
  parameters:
    WidgetId:
      name: widgetId
      in: path
      required: true
      schema: { type: string, format: uuid }
```

- `in`: `query` | `header` | `path` | `cookie`.
- Path parameters **must** be `required: true`; query params default to
  optional.
- Describe serialization for arrays/objects with `style` and `explode`
  (e.g. `style: form, explode: false` for `?id=1,2,3`).
- 3.2's `querystring` keyword lets you model the entire query string as
  one Schema Object; use it when query fields are interdependent, but
  keep discrete `parameters` when each needs its own description.

## Request bodies

```yaml
requestBody:
  required: true
  content:
    application/json:
      schema: { $ref: '#/components/schemas/WidgetCreate' }
```

- `content` is keyed by media type; provide a `schema` per type.
- Set `required: true` unless the body may legitimately be absent.
- For uploads, declare `multipart/form-data` with `encoding` details.
- For 3.2 streams, use the streaming media types with `itemSchema`.

## Responses

```yaml
responses:
  '201':
    description: Widget created
    headers:
      Location: { schema: { type: string } }
    content:
      application/json:
        schema: { $ref: '#/components/schemas/Widget' }
  '400': { $ref: '#/components/responses/BadRequest' }
  '404': { $ref: '#/components/responses/NotFound' }
```

- `responses` is required and must cover every status the operation can
  return. Use `default` for a catch-all only when you truly mean it.
- `description` is required on every Response Object.
- Declare response `headers` (e.g. `Location`, rate-limit headers) as
  part of the contract.
- Error bodies should follow a documented shape — see
  [`../../rfc9457/SKILL.md`](../../rfc9457/SKILL.md) — and be reused via
  `components.responses`.

## Tags

Every name in an operation's `tags` should appear in the top-level
`tags` array (with `description`), or UIs invent an undocumented group.
Keep tag names stable; they're navigation.

## 3.2 method additions

- `query` — a safe/idempotent method that carries a request body, for
  complex searches (`QUERY /search`).
- `additionalOperations` — a map of non-standard methods to Operation
  Objects (e.g. `connect`). Reserved for genuinely non-standard verbs;
  don't reinvent `GET`/`POST`.
