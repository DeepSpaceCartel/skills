# Creating, updating, and deleting

This is the part of JSON:API implementers get wrong most — the response
code you pick after a write encodes real information (did the server
change anything beyond what was asked?). See
[`errors-and-negotiation.md`](errors-and-negotiation.md) for what an
error body looks like when any of these paths fail instead.

## Creating resources

`POST` to the collection URL. Body is a single resource object as
`data`:
- **MUST** contain at least `type`.
- A supplied relationship's value **MUST** be a relationship object
  with a `data` member (linkage), not a bare related resource.

**Client-generated IDs**: a server may accept a client-supplied `id`.
- The client **SHOULD** use a properly-formatted UUID.
- If the server doesn't support client-generated IDs at all, it
  **MUST** respond `403 Forbidden` to a request that includes one.

### Responses

| Status | Meaning |
|---|---|
| `201 Created` | Resource created, and the server assigned/changed something (e.g. generated `id`) beyond the request. Body **MUST** contain the created resource. **SHOULD** include a `Location` header — if the body also has a `self` link, it **MUST** match `Location`. |
| `201` (no server changes) | Only reachable when the client supplied the ID and the server made no changes — may return an empty-primary-data response or skip the document body. |
| `202 Accepted` | Request accepted, processing not yet complete (async creation). |
| `204 No Content` | Created exactly as sent, no server-side changes — alternative to the no-change `201` above. |
| `403 Forbidden` | Creation unsupported at all, or a client-generated ID was supplied but isn't supported. |
| `404 Not Found` | A related resource referenced in the request doesn't exist. |
| `409 Conflict` | Client-generated `id` already exists, or `type` isn't one this collection accepts. **SHOULD** include error details. |

## Updating resources

`PATCH` to the resource's own URL (its `self` link, or the URL it was
fetched from). Body is a single resource object as `data`:
- **MUST** contain `type` and `id`.
- Any subset of attributes/relationships may be included.
- **A field omitted from the request body means "leave it as its
  current value."** It does **NOT** mean "set it to `null`." This is
  the single most common JSON:API PATCH bug — don't treat a missing key
  as clear-this-field.
- A supplied relationship still needs a `data` member (same linkage
  rule as creation).
- A server may refuse full to-many replacement with `403 Forbidden`
  (e.g. if it only supports incremental add/remove — see below).

### Responses

| Status | Meaning |
|---|---|
| `200 OK` | Accepted, and the server changed something beyond the request (e.g. an updated-at timestamp) — body reflects the full current resource. |
| `200` (no extra changes) | May return with empty primary data if nothing beyond the request changed but the server still wants to respond with a document. |
| `202 Accepted` | Accepted, processing incomplete. |
| `204 No Content` | Accepted exactly as sent, nothing else changed. |
| `403 Forbidden` | Update unsupported, or (for a full to-many relationship replacement) that operation specifically isn't allowed. |
| `404 Not Found` | The resource being updated doesn't exist, or a referenced related resource doesn't. |
| `409 Conflict` | Update violates a server constraint, or `type`/`id` in the body don't match the endpoint. **SHOULD** include error details. |

## Updating relationships directly

Separate from updating the owning resource — these act on the
relationship's own `self` link.

**To-one** — `PATCH` the relationship URL, body's `data` is either a
resource identifier object (set it) or `null` (clear it). Success
**MUST** return a successful response (no special-cased status beyond
the general ones below).

**To-many**, three different verbs with three different semantics:

| Verb | Effect |
|---|---|
| `PATCH` | Full replacement — `data` (array, possibly empty) becomes the entire relationship. Server **MUST** either fully replace it, reject with a normal error, or `403 Forbidden` if replacement isn't supported at all. |
| `POST` | Append — adds each identifier in `data` unless already present (already-present members are silently no-ops, not duplicated). |
| `DELETE` | Remove — removes each identifier in `data`; members already absent are no-ops, not errors. |

### Responses (all three verbs)

| Status | Meaning |
|---|---|
| `200 OK` | Accepted, server changed something beyond the request. |
| `202 Accepted` | Processing incomplete. |
| `204 No Content` | Accepted, nothing else changed — the expected response to a `POST` where every member was already present, or a `DELETE` where every member was already absent. |
| `403 Forbidden` | This relationship-update operation isn't supported. |

## Deleting resources

`DELETE` to the resource's URL.

| Status | Meaning |
|---|---|
| `200 OK` | Deleted; body may carry additional `meta`. |
| `202 Accepted` | Deletion accepted, processing incomplete. |
| `204 No Content` | Deleted, nothing further to report — the common case. |
| `404 Not Found` | **SHOULD** be returned when the resource doesn't exist. |

Any of these operations may also respond with other HTTP codes and an
`errors` body when something the table above doesn't cover goes wrong —
see [`errors-and-negotiation.md`](errors-and-negotiation.md).
