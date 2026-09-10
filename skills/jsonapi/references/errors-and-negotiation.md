# Content negotiation, extensions/profiles, and errors

## Content negotiation

- Both clients and servers **MUST** send every JSON:API payload with
  `Content-Type: application/vnd.api+json`.
- The **only** media-type parameters allowed on that header are `ext`
  (extensions in use) and `profile` (profiles in use) — when either is
  applied to a document, it **MUST** be named in the parameter.
- Clients **MUST** ignore any media-type parameter that isn't `ext` or
  `profile` when reading a server response.
- A client **MAY** use `ext` in its `Accept` header to *require*
  specific extensions, and `profile` to *request* profiles.
- Server responsibilities:
  - `415 Unsupported Media Type` — the request named an extension the
    server doesn't support.
  - `406 Not Acceptable` — nothing the server can produce satisfies the
    client's `Accept` header.
  - **SHOULD** attempt to honor requested profile(s) — profiles are a
    request, not a hard requirement, unlike extensions.
  - **SHOULD** send `Vary: Accept` (among other values) since the
    response shape can depend on it.

## Extensions vs. profiles

**Extensions** add new *specification* semantics:
- **MUST** declare a unique namespace (alphanumeric).
- **MAY** define new document members and new query parameters.
- **MUST NOT** alter or remove anything the base spec already defines.
- Extension members in a document are namespaced (`namespace:member`,
  per [`document-structure.md`](document-structure.md)); extension
  query parameters are namespaced the same way (per
  [`query-parameters.md`](query-parameters.md)).

**Profiles** describe a usage pattern within the existing spec —
implementation semantics, not new wire format:
- May standardize things like a timestamp format for attribute values.
- **MUST NOT** alter or remove any processing rule the base spec or an
  active extension already defines.
- **MUST NOT** define new query parameters (only implementation
  -specific ones, same as anyone else).

Rule of thumb: if it changes what a byte in the document *means*, it's
an extension; if it just narrows *how* you use the existing meanings,
it's a profile.

## Error objects

Returned as an array under the top-level `errors` key (mutually
exclusive with `data` — see
[`document-structure.md`](document-structure.md)).

Each error object **MUST** contain at least one of:

| Member | Purpose |
|---|---|
| `id` | Unique identifier for *this occurrence* of the problem. |
| `links` | `about` (human-readable further detail) and/or `type` (dereferenceable link identifying the error's general type). |
| `status` | HTTP status code for this problem, as a string. |
| `code` | Application-specific error code. |
| `title` | Short, human-readable summary — **should not** vary between occurrences of the same problem (so it's stable enough to key off of). |
| `detail` | Human-readable explanation specific to *this* occurrence — localizable, unlike `title`. |
| `source` | Where the problem came from — see below. |
| `meta` | Non-standard metadata. |

`source` distinguishes *what part of the request* caused the problem:
- `pointer` — a JSON Pointer into the request document (e.g.
  `/data/attributes/title`).
- `parameter` — the name of an offending URI query parameter.
- `header` — the name of an offending request header.

## Multiple problems, one response

A server may stop at the first error it finds, or keep going and
collect several into one `errors` array. When a response reports
multiple problems with different natural status codes, it **SHOULD**
use the most generally applicable HTTP status for the top-level
response (e.g. don't pick `404` for the whole response just because one
of three problems was a missing resource, if the others were `400`
-shaped validation failures — pick the code that best characterizes the
response as a whole).
