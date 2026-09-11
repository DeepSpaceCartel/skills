# Identifiers, `$ref`, and `$dynamicRef`

How schemas name themselves, reference each other, and — the part
that trips people up — how recursive and extensible schemas resolve
which subschema actually applies.

## `$id`: declaring a schema resource

`$id` sets the **base URI** for a schema and everything nested inside
it (until a nested subschema declares its own `$id`), and marks that
schema object as a distinct, independently-identifiable resource.

```json
{
  "$id": "https://example.com/schemas/address.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object"
}
```

- The root schema's `$id` is typically an absolute URI — this is the
  URI other schemas use in `$ref` to point at it, and doesn't need to
  be dereferenceable (it's an identifier, not necessarily a fetchable
  URL), though making it resolve to the actual schema is good practice.
- A **non-root** `$id` can be relative; it resolves against the
  nearest enclosing base URI, the same way relative URIs resolve
  against a document's base URI in HTML.
- Don't put a non-empty fragment on `$id` (`"$id": "#foo"` is
  draft-07-era usage). In 2020-12, fragment-only identification within
  a resource is `$anchor`'s job, not `$id`'s.

## `$anchor`: naming a location without a JSON Pointer

```json
{
  "$id": "https://example.com/schemas/product.json",
  "$defs": {
    "money": {
      "$anchor": "money",
      "type": "object",
      "properties": { "amount": { "type": "number" }, "currency": { "type": "string" } }
    }
  }
}
```

Referenced as `"$ref": "https://example.com/schemas/product.json#money"`
(or just `"$ref": "#money"` from within the same resource). `$anchor`
values must be a valid plain name (letter, then letters/digits/`-`/`_`/
`.`) — no JSON Pointer syntax, no leading `#` in the value itself.

## `$defs`: where reusable subschemas live

`$defs` is a reserved, purely conventional location for subschemas
meant to be referenced (by `$ref`, `$dynamicRef`, or another schema
entirely) rather than applied in place. It has no special validation
behavior itself — a schema author could put reusable subschemas
anywhere and reference them by JSON Pointer, but `$defs` is the
convention every tool expects.

## `$ref`: pointing at another schema

`$ref`'s value is a URI reference, resolved against the current base
URI, and can point at:
- Another schema resource entirely (`$ref: "address.json"`, resolved
  relative to the current `$id`).
- A JSON Pointer fragment within a resource (`$ref: "#/$defs/money"`).
- A plain-name fragment matching an `$anchor` (`$ref: "#money"`).

Since 2019-09, **`$ref` can appear alongside other keywords** in the
same schema object, and all of them apply together:

```json
{
  "$ref": "#/$defs/money",
  "description": "The order total"
}
```

This is a change from draft-07/draft-04, where `$ref` was exclusive
and sibling keywords were silently ignored — don't carry that
assumption into 2020-12 schemas.

## `$dynamicRef` / `$dynamicAnchor`: extensible recursive schemas

Plain `$ref` always resolves to one fixed schema, chosen at
schema-authoring time. `$dynamicRef` exists for the case where a
**base** schema wants to reference "whatever the most-derived version
of this concept is," so a schema that extends the base can override
part of it without editing the base.

```json
// base.json — a generic list, recursively referencing "itemType"
{
  "$id": "https://example.com/list.json",
  "$dynamicAnchor": "itemType",
  "type": "array",
  "items": { "$dynamicRef": "#itemType" }
}
```

```json
// strings.json — extends base.json, pinning itemType to strings
{
  "$id": "https://example.com/string-list.json",
  "$ref": "list.json",
  "$dynamicAnchor": "itemType",
  "type": "string"
}
```

Resolution: a `$dynamicRef` first resolves exactly like a normal
`$ref` (giving a fallback target). Then the implementation walks the
**dynamic scope** — the chain of schema resources actually traversed
to reach this point during evaluation, not the static reference graph
— for the *outermost* resource in that chain that also defines a
matching `$dynamicAnchor`. If one exists, that schema is used instead
of the plain-`$ref` fallback. This is what lets `string-list.json`'s
`items` end up validated as `{"type": "string"}` even though
`list.json` itself only ever says `$dynamicRef: "#itemType"`.

Use `$dynamicRef`/`$dynamicAnchor` only when you actually need this
override-by-extension pattern (it's how 2020-12's own meta-schemas
compose vocabularies). For ordinary recursion — a tree schema
referencing itself with no intent to be overridden — plain `$ref` to
the schema's own `$id`/`$anchor` is simpler and sufficient:

```json
{
  "$id": "https://example.com/tree.json",
  "type": "object",
  "properties": {
    "value": { "type": "string" },
    "children": { "type": "array", "items": { "$ref": "#" } }
  }
}
```

(`$dynamicRef`/`$dynamicAnchor` replace draft 2019-09's
`$recursiveRef`/`$recursiveAnchor`, which had no name-matching — any
`$recursiveAnchor: true` in the dynamic scope was eligible. 2019-09
schemas using the old keywords need updating, not just renaming, when
moving to 2020-12.)

## Bundling multiple resources in one document

A single JSON file can contain more than one schema resource: embed
additional `$id`-bearing schemas under `$defs` in the root document,
and reference them by their `$id` from anywhere, including from
outside the file. This lets a set of related schemas ship as one file
(e.g. for distribution) while each keeps its own identity for `$ref`
purposes — implementations that support bundling register each nested
`$id` as its own resource, not just as a nested object.

## Gotchas

- The base URI used to resolve a *root* schema with no `$id` is
  whatever URI it was retrieved from (or an implementation-defined
  default if there is none, e.g. a schema handed over in-memory) — a
  schema isn't required to declare `$id` to have `$ref` work inside it.
- A `$ref` cycle isn't automatically an error — recursive schemas
  (trees, linked lists) are supposed to reference themselves.
  Implementations must support this, not reject it.
- `$anchor` and `$dynamicAnchor` share a namespace concern only in
  that both must be valid plain names — but they're resolved by
  different keywords (`$ref`/`$dynamicRef` respectively) and mean
  different things; don't use them interchangeably.
