# Vocabularies, annotations, and extensibility

2020-12 splits the keyword set into named **vocabularies**. A dialect
(identified by a `$schema` meta-schema URI) declares which
vocabularies it uses via `$vocabulary`. Most schema authors just
declare `"$schema": "https://json-schema.org/draft/2020-12/schema"`
and get the standard bundle — but knowing the split explains why
`format` and `contentEncoding`/`contentMediaType`/`contentSchema`
don't validate anything by default even though they look like
validation keywords.

## `$schema` and `$vocabulary`

| Keyword | Meaning |
|---|---|
| `$schema` | On a root schema, declares which meta-schema (dialect) it's written against — e.g. `https://json-schema.org/draft/2020-12/schema`. Determines which keywords are recognized and what they mean. |
| `$vocabulary` | Only meaningful **on a meta-schema itself** (a schema that other schemas' `$schema` points at). Maps vocabulary URI → boolean: `true` means an implementation **must** understand that vocabulary to process schemas of this dialect correctly (unrecognized-but-required ⇒ error); `false` means it's optional (unrecognized ⇒ ignore those keywords). Custom dialects assemble their own keyword set this way. |

The 2020-12 core meta-schema pulls in these vocabularies:

| Vocabulary | Keywords |
|---|---|
| Core | `$schema`, `$id`, `$ref`, `$anchor`, `$dynamicRef`, `$dynamicAnchor`, `$defs`, `$vocabulary`, `$comment` |
| Applicator | `allOf`, `anyOf`, `oneOf`, `not`, `if`/`then`/`else`, `properties`, `patternProperties`, `additionalProperties`, `propertyNames`, `prefixItems`, `items`, `contains`, `dependentSchemas` |
| Unevaluated | `unevaluatedItems`, `unevaluatedProperties` |
| Validation | `type`, `enum`, `const`, and the numeric/string/array/object assertion keywords (see [`references/validation-keywords.md`](validation-keywords.md)) |
| Meta-Data | `title`, `description`, `default`, `deprecated`, `readOnly`, `writeOnly`, `examples` |
| Format-Annotation | `format` (collected as an annotation, not asserted) |
| Content | `contentEncoding`, `contentMediaType`, `contentSchema` |

(Format-Assertion is a separate, mutually-exclusive-with-Format-Annotation
vocabulary — see below.)

## `unevaluatedProperties` / `unevaluatedItems`

These apply **after** every other applicator that touched the instance
has been evaluated — not just the adjacent `properties`/`items` in the
same schema object, but also everything reached through `allOf`,
`$ref`, `$dynamicRef`, `if`/`then`/`else`, `anyOf`/`oneOf`. A property
(or item) counts as "evaluated" if *any* applicator in the whole
evaluation, however it was reached, matched it — `unevaluatedProperties`
only constrains what's left over after all of that.

This is what makes "closed" schemas composable, where plain
`additionalProperties: false` isn't:

```json
{
  "allOf": [
    { "properties": { "id": { "type": "integer" } } },
    { "properties": { "name": { "type": "string" } } }
  ],
  "unevaluatedProperties": false
}
```

Here `additionalProperties: false` on either branch of the `allOf`
would reject the *other* branch's properties (each branch only sees
its own `properties`). `unevaluatedProperties: false` on the outer
schema instead sees everything evaluated across both branches, and
only rejects properties neither branch claimed. This is the standard
pattern for "extend a base schema, then close the result."

## `format`: annotation vs. assertion

`format` names a semantic string format — `date-time`, `date`, `time`,
`duration`, `email`, `idn-email`, `hostname`, `idn-hostname`, `ipv4`,
`ipv6`, `uuid`, `uri`, `uri-reference`, `iri`, `iri-reference`,
`uri-template`, `json-pointer`, `relative-json-pointer`, `regex`.

By default (Format-Annotation vocabulary), `format` is **collected as
an annotation only** — a conforming implementation is not required to
reject `"not-an-email"` against `{"format": "email"}`. To make `format`
actually fail validation, the dialect must declare the
**Format-Assertion** vocabulary instead (a different meta-schema, or
`$vocabulary` on a custom one), or the implementation must be
explicitly configured to assert formats regardless of dialect (many
validators offer this as a strictness flag). Don't assume `format`
alone rejects bad input — check what your validator actually does with
it before relying on it for anything security- or correctness-critical.

## `contentEncoding` / `contentMediaType` / `contentSchema`

For a string instance that actually holds encoded content of another
type:

| Keyword | Meaning |
|---|---|
| `contentEncoding` | How the string is encoded, e.g. `base64` (values per RFC 2045 §6.1's content-transfer-encodings). |
| `contentMediaType` | The media type of the decoded content, e.g. `application/json`, `image/png`. |
| `contentSchema` | A schema applied to the decoded content — only meaningful when `contentMediaType` indicates a JSON-compatible format. |

Like `format`, these are **annotations by default** — the Content
vocabulary doesn't require implementations to actually decode and
validate. Treat them as documentation of intent unless you've
confirmed your tooling enforces them.

## Meta-data annotations

`title`, `description`, `default`, `examples` (array of example
values), `deprecated` (boolean), `readOnly`, `writeOnly` — pure
documentation/tooling hints, no effect on whether an instance is
valid. `readOnly`/`writeOnly` are meant for API tooling to know a
field is server-generated or write-only (e.g. a password field),
respectively; they don't make a schema reject a request that includes
a read-only field or a response that includes a write-only one — that
enforcement, if wanted, is the API's job, not the validator's.

## `$comment`

A string for schema authors/maintainers — not shown to end users of
whatever the schema validates, and has zero effect on validation.
Tools *may* log it (e.g. during debugging) but shouldn't surface it as
part of a validation error. Use it for "why this keyword is here" notes
aimed at the next person editing the schema, not for anything meant to
reach an API consumer (that's what `description` is for).

## Custom dialects

Because the keyword set is vocabulary-driven, a project can define its
own meta-schema that mixes standard vocabularies with custom ones (its
own `$vocabulary` entries mapping to custom keyword semantics an
implementation is taught separately) — most schema authoring never
needs this, but it's why "is this a valid keyword?" is technically a
question relative to the dialect in play, not a fixed global list.
