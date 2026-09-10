# Fetching data & query parameters

## Fetching resources

- A server **MUST** support `GET` on every URL it hands out as a `self`
  or `related` link.
- `200 OK` — a single resource returns a resource object, a resource
  identifier object, or `null`; a collection returns an array (possibly
  empty).
  - `null` is only correct for a URL that *could* identify a single
    resource but currently doesn't (e.g. a to-one relation with nothing
    linked) — it is not a substitute for `404`.
- `404 Not Found` — the resource genuinely doesn't exist. (Contrast with
  the `null`-via-`200` case above: that's for URLs that name a slot, not
  a specific resource.)

## Fetching relationships

- A server **MUST** support `GET` on every relationship URL it exposes
  as a `self` link.
- `200 OK` — primary data is exactly the resource linkage form (see
  [`document-structure.md`](document-structure.md)): `null` for an empty
  to-one, `[]` for an empty to-many. Top-level `links` may carry `self`/
  `related`.
- `404 Not Found` — the relationship's owning resource doesn't exist.

## `include` — related-resource inclusion

- Value: comma-separated relationship paths; a path is dot-separated
  relationship names walking through the resource graph.
  - `?include=comments` — direct relationship.
  - `?include=comments.author` — nested.
  - `?include=comments.author,ratings` — multiple paths.
- A response honoring `include` **MUST** be a compound document with an
  `included` array, and **MUST NOT** include resources that weren't
  requested (no "helpfully" including more than asked).
- If the endpoint doesn't support `include` at all, or can't resolve a
  requested path, it **MUST** respond `400 Bad Request`.

## Sparse fieldsets

- `fields[TYPE]=name1,name2` restricts which fields come back for
  resources of `TYPE` — in primary data *and* in `included`.
  `?include=author&fields[articles]=title,body&fields[people]=name`
- An empty value for `fields[TYPE]` means: no fields for that type.
- Once a client specifies `fields[TYPE]`, the server **MUST NOT** add
  fields beyond that set. Without it, the server may send all, some, or
  no fields, at its own discretion.

## `sort`

- Value is a comma-separated list of fields, applied in the order
  given: `?sort=age,name` sorts by age first, ties broken by name.
- A leading `-` means descending: `?sort=-created,title` is newest
  first, then alphabetical.
- Default order is ascending.
- Sorting support is optional per-endpoint; if a server can't honor a
  requested sort, it responds `400 Bad Request`. A server may apply a
  default sort when `sort` is absent.

## `page` — pagination

- Reserved query-parameter family for pagination; the strategy
  (offset/limit, cursor, page number, ...) is entirely up to the
  server — the spec only reserves the parameter namespace and the link
  shape.
- Pagination links (`first`, `last`, `prev`, `next`) live in the
  `links` object alongside the paginated collection — top-level for
  primary data, inside the relevant relationship for an included
  collection. Omit or set `null` for a link that doesn't apply (e.g.
  `prev` on the first page).
- Whatever ordering pagination implies **MUST** stay consistent with
  the `sort` rules above — page 2 has to mean "the next slice of the
  same order," not an independently-ordered batch.

## `filter`

- Reserved query-parameter family for filtering; the spec is
  deliberately silent on filter strategy/syntax — it just reserves the
  namespace so implementations don't collide with future spec use.

## Query-parameter-family rules (apply to all of the above)

- A "family" is a base name plus optional bracket suffixes —
  `page[offset]` and `page[limit]` are two distinct parameters in the
  `page` family; `filter[status]`, `filter[]`, and
  `filter[author.name]` are all valid shapes in the `filter` family.
- **Extension** parameters: base name **MUST** be prefixed
  `namespace:`.
- **Implementation-specific** parameters: base name **MUST** still be a
  legal member name, and **MUST** contain at least one character
  outside `a-z` — the convention is camelCase, so a made-up param
  doesn't collide with a future spec-reserved lowercase name.
- An unrecognized query parameter **MUST** get `400 Bad Request` — don't
  silently ignore it.
- Square brackets in parameter names should conceptually be
  percent-encoded per standard `application/x-www-form-urlencoded`
  rules, but servers **SHOULD** also accept them unencoded and treat
  the request identically either way.
