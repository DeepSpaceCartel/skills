# Security and tags

## Security Scheme Objects

Declared once under `components.securitySchemes`, applied via a
`security` requirement list. Spec:
<https://spec.openapis.org/oas/v3.2.0.html#security-scheme-object>.

| `type` | Use | Key fields |
| --- | --- | --- |
| `apiKey` | Key in a header/query/cookie | `name`, `in` |
| `http` | HTTP auth framework | `scheme` (`basic`, `bearer`, ...), `bearerFormat` |
| `oauth2` | OAuth 2 flows | `flows` (see below) |
| `openIdConnect` | OIDC discovery | `openIdConnectUrl` |
| `mutualTLS` | Client certificates | — |

```yaml
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
    oauth:
      type: oauth2
      flows:
        authorizationCode:
          authorizationUrl: https://id.example.com/authorize
          tokenUrl: https://id.example.com/token
          scopes:
            widgets:read: Read widgets
            widgets:write: Create and modify widgets
```

OAuth 2 flows: `authorizationCode`, `implicit` (deprecated),
`password` (deprecated), `clientCredentials`, and in 3.2 the
**deviceAuthorization** flow. Prefer authorization code + PKCE for
user-facing flows and client credentials for service-to-service.

## Applying security

```yaml
security:
  - bearerAuth: []
  - oauth: [widgets:read]      # OR: either scheme satisfies, with these scopes
```

- The list is an **OR**: any one requirement object satisfies it.
- Within a requirement object, multiple schemes are an **AND**.
- Per-operation `security` overrides the global list. An **empty array**
  (`security: []`) makes a specific operation public.

## Common mistakes

- Describing an authorization *model* (roles, ownership) in the security
  scheme — schemes only say how credentials travel. Document scopes and
  roles in the operation `description`.
- Declaring `type: http, scheme: basic` while the server actually wants
  a bearer token.
- Forgetting that omitting `security` inherits the global default; if an
  endpoint should be public, set `security: []` explicitly.

## Tags

`tags` is an ordered array of Tag Objects; each operation references a
tag by `name`.

```yaml
tags:
  - name: widgets
    summary: Widget operations
    description: Create, read, update, and delete widgets.
```

- Keep the set small and stable. Tags drive UI navigation and generated
  client grouping.
- 3.2 extends the Tag Object with `summary`, `description`, `parent`,
  and `kind`. `kind: nav` marks a tag used for navigation only, so
  tooling can skip it when filtering real operations.
- Every `name` referenced in an operation should be declared, or a UI
  will synthesize an undocumented group.

## Webhooks and callbacks

- **Webhooks** (top-level, 3.1+): requests your API *sends out* — e.g.
  a widget event to a subscriber's URL. Describe the payload the same
  way you'd describe a request body.
- **Callbacks** (per-operation): out-of-band requests triggered by a
  specific call. Less common than webhooks; reach for webhooks when the
  consumer registers an endpoint once.

Both are part of the API contract: version and validate them like any
other operation.
