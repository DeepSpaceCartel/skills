# Document structure

## Top level

A JSON:API document's root object **MUST** contain at least one of:
`data`, `errors`, or `meta` (or an extension-defined member).
- `data` and `errors` **MUST NOT** coexist in the same document — a
  response is either primary data or a problem report, never both.
- If `data` is absent, `included` **MUST NOT** be present either —
  there's nothing for included resources to link back to.
- Optional top-level members: `jsonapi`, `links`, `included`.

### Primary data
- A single resource is a resource object, a resource identifier
  object, or `null`.
- A logical collection **MUST** be an array — of resource objects, of
  identifier objects, or empty (`[]`), never a bare object standing in
  for "the collection."

### Top-level links
- `self` — the link that generated this document.
- `related` — when primary data represents a relationship, the link to
  the related resource(s).
- `describedby` — a link to a description document (e.g. OpenAPI,
  JSON Schema) for this API.
- Pagination: `first`, `last`, `prev`, `next` (see
  [`query-parameters.md`](query-parameters.md)).

## Resource objects

Required:
- `type` — always.
- `id` — always, **except** a client may omit it for a not-yet-created
  resource and use `lid` (a client-generated local id) instead.

Optional: `attributes`, `relationships`, `links`, `meta`.

- `id`, `type`, and `lid` values **MUST** be strings.
- Within an API, a resource object's `type`+`id` pair **MUST** identify
  exactly one resource.
- `type` values follow the same character rules as member names (see
  below).

### Fields share one namespace

Attributes and relationships are collectively called **fields**. A
resource's fields, together with its `type` and `id`, **MUST** share a
single namespace:
- No attribute and relationship can have the same name.
- No field can be named `type` or `id`.

### Attributes
- The `attributes` value is itself an object; members represent data
  about the resource (can be any valid JSON value, including nested
  objects/arrays).
- **SHOULD NOT** contain a key that references another resource in a
  foreign-key-shaped way (e.g. `author_id`) — if it's a reference to
  another resource, it belongs in `relationships`, not `attributes`.

### Relationships
- The `relationships` value is an object; each member is a
  "relationship object" describing a to-one or to-many relationship.
- A relationship object **MUST** contain at least one of: `links`,
  `data`, `meta`.
- `links` may include `self` (the relationship link itself — fetching
  it returns *linkage*, not the related resources) and `related`
  (fetching it returns the related resource(s) as primary data).
- `data` holds **resource linkage** — see below.
- To-many relationships may carry their own pagination links.
- A `related` link **MUST** reference a valid URL even when nothing is
  currently linked, and **MUST NOT** change just because the
  relationship's content changes (it's a stable endpoint, not a
  pointer to current state).

### Resource linkage

The `data` member of a relationship object:

| Relationship | Empty | Populated |
|---|---|---|
| to-one | `null` | single resource identifier object |
| to-many | `[]` | array of resource identifier objects |

The spec assigns no meaning to array order — an implementation may, but
readers can't assume order is significant by default.

## Resource identifier objects

Identifies one resource by type + id, used anywhere a full resource
object isn't needed (relationship linkage, `included`-adjacent
references):
- **MUST** contain `type`.
- **MUST** contain `id`, except when representing a not-yet-created
  resource (then it may carry `lid` instead).
- `type`/`id`/`lid` values **MUST** be strings.
- May carry `meta`.

## Links and link objects

A `links` value **MUST** be an object (a "links object"). Each member
is either:
- a plain string (a URI reference), or
- a link object, or
- `null`.

A link object's members:
- `href` — **required**, a URI-reference string.
- `rel` — a link relation type.
- `describedby` — link to a description document.
- `title` — human-readable label.
- `type` — media-type hint (not a guarantee about the target).
- `hreflang` — a language tag, or array of them.
- `meta` — non-standard metadata.

The relation type **SHOULD** be inferred from the member's name (e.g. a
`self` member is a self link) unless the link object's own `rel`
overrides it.

## The `jsonapi` object

Optional top-level member describing the server's implementation:
- `version` — highest JSON:API version the server supports. If absent,
  clients should assume at least `1.0`.
- `ext` — array of extension URIs in use.
- `profile` — array of profile URIs in use.
- `meta`

Clients and servers **MUST NOT** use `ext`/`profile` *here* for content
negotiation — that happens via media-type parameters (see
[`errors-and-negotiation.md`](errors-and-negotiation.md)); this object
just documents what's in play.

## `meta`

Anywhere `meta` is allowed, its value **MUST** be an object, and any
members are allowed inside it — it's the escape hatch for non-standard
information (copyright, authorship, timing) that doesn't fit the
spec'd structure.

## Member names

- **MUST** contain at least one character.
- **MUST** start and end with a "globally allowed character":
  `a-z`, `A-Z`, `0-9`, or U+0080 and above (non-ASCII Unicode is
  allowed but not recommended).
- Interior characters may additionally include `-` (hyphen) and `_`
  (underscore); a space is technically allowed but not recommended.
- Case-sensitive, always.
- Forbidden everywhere: URL-special characters (`+ , . [ ]`) and other
  symbols (`! " # $ % & ' ( ) * / : ; < = > ? @ \ ^ \` { | } ~`), plus
  control characters.
- **RECOMMENDED**: stick to RFC 3986 unreserved characters even within
  what's technically allowed.

Two special forms:
- **`@`-members** (starting with U+0040) may appear anywhere and
  **MUST** be ignored under this spec's own rules — reserved for
  embedding foreign conventions like JSON-LD.
- **Extension members** **MUST** be prefixed `namespace:`, and the part
  after the colon follows the same member-name rules.

## Compound documents

A response that includes related resources alongside primary data uses
the top-level `included` member:
- `included` **MUST** be an array.
- **Full linkage**: every resource object in `included` **MUST** be
  reachable via a chain of relationships starting from the primary
  data (directly, or via other included resources) — the one exception
  is when a sparse fieldset (see
  [`query-parameters.md`](query-parameters.md)) deliberately excludes
  the relationship that would have linked it.
- **MUST NOT** include more than one resource object for a given
  `type`+`id` pair — a compound document has exactly one canonical copy
  of each resource, referenced by identifier everywhere else.
