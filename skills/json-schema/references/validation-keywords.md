# Validation keywords

The Validation vocabulary's assertion keywords, plus the Applicator
vocabulary's boolean-logic and conditional keywords. Every keyword
here applies only to instances of the relevant JSON type — a keyword
that doesn't match the instance's type is simply skipped (not an
error, not a failure). This is why `type` is usually the first keyword
in a schema even though nothing enforces that ordering.

## Any instance

| Keyword | Applies to | Meaning |
|---|---|---|
| `type` | any | A single type string (`"string"`, `"number"`, `"integer"`, `"boolean"`, `"object"`, `"array"`, `"null"`) or an array of type strings (instance must match at least one). `"integer"` means a JSON number with a zero fractional part — `1.0` matches `"integer"`. |
| `enum` | any | Array of allowed values (any JSON type, compared by deep equality). Instance must equal one of them exactly. |
| `const` | any | Single allowed value — shorthand for `"enum": [value]`. |

```json
{ "type": ["string", "null"] }
{ "enum": ["draft", "published", "archived"] }
{ "const": "2020-12" }
```

## Numbers (`number`, `integer`)

| Keyword | Meaning |
|---|---|
| `multipleOf` | Instance divided by this value must be an integer. Must be > 0. |
| `maximum` | Instance ≤ this value. |
| `exclusiveMaximum` | Instance < this value. (A number, not a boolean — see the SKILL.md Gotchas.) |
| `minimum` | Instance ≥ this value. |
| `exclusiveMinimum` | Instance > this value. |

## Strings

| Keyword | Meaning |
|---|---|
| `maxLength` / `minLength` | Length in Unicode code points (not UTF-16 code units, not bytes). |
| `pattern` | ECMA-262 regular expression; matches if the pattern is found **anywhere** in the string (not implicitly anchored — use `^`/`$` for full-string matches). |

## Arrays

| Keyword | Meaning |
|---|---|
| `prefixItems` | Array of schemas for **tuple validation** — index 0 of the instance is checked against `prefixItems[0]`, index 1 against `prefixItems[1]`, etc. Instance may be longer; extra elements aren't touched by `prefixItems`. |
| `items` | Schema applied to every array element **at or past** the end of `prefixItems` (or every element, if there's no `prefixItems`). `false` here means "no elements beyond the tuple are allowed" — the 2020-12 replacement for draft-07's `additionalItems: false`. |
| `contains` | At least one element must validate against this schema (subject to `minContains`/`maxContains`, below). |
| `minContains` / `maxContains` | Bound how many elements must match `contains` (default `minContains` is 1). Setting `minContains: 0` makes `contains` always pass regardless of `maxContains`. Only meaningful alongside `contains`. |
| `minItems` / `maxItems` | Bounds on array length. |
| `uniqueItems` | `true` ⇒ no two elements may be deeply equal. |

```json
{
  "type": "array",
  "prefixItems": [
    { "enum": ["GET", "POST", "PUT", "DELETE"] },
    { "type": "string", "format": "uri-reference" }
  ],
  "items": { "type": "string" },
  "minItems": 2
}
```
Matches `["GET", "/users"]` or `["POST", "/users", "extra", "extra2"]`
(the trailing elements are checked against `items`), but not
`[1, "/users"]`.

## Objects

| Keyword | Meaning |
|---|---|
| `properties` | Map of property name → schema, applied when that property is present. |
| `patternProperties` | Map of regex → schema; applies to every property whose **name** matches the regex. |
| `additionalProperties` | Schema (or `false`) applied to every property **not** matched by `properties` or `patternProperties`. `false` closes the object to any name not explicitly listed/patterned. |
| `propertyNames` | Schema applied to every property name, treated as a string instance (e.g. `{"pattern": "^[a-z_]+$"}` to constrain naming). |
| `required` | Array of property names that must be present. Declared once on the object schema — there's no per-property "required" flag inside a `properties` subschema. |
| `minProperties` / `maxProperties` | Bounds on the object's property count. |
| `dependentRequired` | Map of property name → array of other property names that become required **when** the key property is present. `{"dependentRequired": {"creditCard": ["billingAddress"]}}`. |
| `dependentSchemas` | Map of property name → schema applied to the **whole object** when the key property is present. Use this (not `dependentRequired`) when the condition needs more than "these other keys must exist." |

`additionalProperties` only sees properties left over after
`properties` and `patternProperties` have claimed theirs — it does not
re-check properties those already matched, even if the property also
happens to fail what `additionalProperties` would have asserted.

## Boolean composition (Applicator vocabulary)

| Keyword | Meaning |
|---|---|
| `allOf` | Array of schemas; instance must validate against **all** of them. |
| `anyOf` | Instance must validate against **at least one**. |
| `oneOf` | Instance must validate against **exactly one** — two matching subschemas is a failure, not a pass. |
| `not` | Instance must **not** validate against the given schema. |

`oneOf` is the one people misuse most: reaching for it to mean "any of
these" (use `anyOf`) or to pick a variant by a discriminator-like field
without actually making the branches mutually exclusive — if two
branches can both match the same instance, `oneOf` fails instances
that satisfy either of them.

## Conditional application

```json
{
  "if": { "properties": { "country": { "const": "US" } } },
  "then": { "required": ["zipCode"] },
  "else": { "required": ["postalCode"] }
}
```

- `if` is evaluated purely to decide a branch — its own pass/fail is
  never itself a validation failure.
- If `if` is absent, `then`/`else` are both ignored.
- If `if` passes and `then` is absent, that's fine (no constraint
  added). Same for `if` failing with no `else`.
- Chain several by nesting `if`/`then`/`else` inside `allOf` entries
  rather than trying to express an if/elif/elif/else ladder in one
  keyword set.
