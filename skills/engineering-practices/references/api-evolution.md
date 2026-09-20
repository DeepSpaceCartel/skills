# API evolution and compatibility

Changing something other people depend on (an HTTP or RPC API, a library, an event or
message schema, CLI or config output) without breaking consumers you can't see or
control. `semver` numbers a change and `openapi` describes the contract; this is the
practice between them: classify the change, take a compatible path, deprecate
properly, and detect breaks automatically. Anchor sources: Google's
[API Improvement Proposals](https://google.aip.dev/180) (180 backward compatibility,
181 stability levels, 185 versioning), Stripe's
[API versioning](https://stripe.com/blog/api-versioning), [Hyrum's Law](https://www.hyrumslaw.com/),
Fowler's [Consumer-Driven Contracts](https://martinfowler.com/articles/consumerDrivenContracts.html),
the [Pact docs](https://docs.pact.io/), the
[Protocol Buffers guidance](https://protobuf.dev/best-practices/dos-donts/) and the
[Kubernetes deprecation policy](https://kubernetes.io/docs/reference/using-api/deprecation-policy/).

## What agents typically get wrong

- **Renaming a field "because it is cleaner."** AIP-180: a rename is semantically a
  remove plus an add, so the old name must stay. Protobuf's JSON and text formats
  break on rename because they use names.
- **Adding a required request field or a non-nullable property.** Google, Azure,
  Microsoft Graph and the protobuf best practices all say no.
- **Changing a default,** a field's type, or a resource name or id format that
  clients parse.
- **Removing enum values,** or adding values without checking that consumers
  tolerate unknown ones.
- **Tightening validation,** or changing which condition produces which error code.
- **Adding server-side pagination to an existing collection** (Microsoft Graph lists
  this as breaking).
- **Reusing a protobuf field number, or a deleted field's name,** or forgetting
  `reserved`.
- **Treating an "internal-looking" or undocumented API as private.** Hyrum's Law: with
  enough users, every observable behavior is depended on. An agent can't know who
  the consumers are, so assume someone depends on it.
- **Believing passing tests prove compatibility.** The consumers are outside your
  repository.
- **Bumping a version number and skipping the migration path,** or creating a new
  version when an additive change would have done.

## Procedure

1. **List every surface of the interface:** schema, semantics, defaults, errors,
   ordering, limits, authentication, and events or webhooks.
2. **Classify the change:**
   - (a) additive and compatible;
   - (b) schema-breaking: remove, rename, retype, make required, remove an enum value;
   - (c) behavioral: defaults, validation, error codes, ordering, pagination, timing.
   Treat (c) as breaking unless the documentation disclaims it.
3. **Prefer the additive path.** Add the new field or endpoint beside the old one and
   keep the old one working with the same behavior.
4. **Dual-write and dual-read.** Emit both names, or accept both and map them, with
   the same semantics for each.
5. **Deprecate loudly.** Mark it in the schema, docs and changelog. Send the
   `Deprecation` header ([RFC 9745](https://www.rfc-editor.org/rfc/rfc9745.html)) and a
   `Sunset` header (the sunset date must not precede the deprecation date), with a
   `Link` to the migration guide. Meter use of deprecated elements per consumer.
6. **Set a timeline sized to the stability level.** Policies vary: Google beta
   versions get a 180-day deprecation period (AIP-185); Microsoft Graph GA APIs are
   supported for at least 24 to 36 months; Kubernetes doesn't remove GA elements
   within a major version.
7. **Remove only when usage is at or near zero,** or after the announced date. If
   removal is unavoidable, ship it as a new major version that coexists with the old.
8. **Automate detection in CI:** `buf breaking` for protobuf, a schema diff such as
   `oasdiff` for OpenAPI, a compatibility mode in a schema registry for Avro or
   Kafka, and consumer-driven contract tests with Pact plus `can-i-deploy`. Schema
   diff tools don't catch behavioral changes, so class (c) needs contract tests or
   review.

## Techniques

- **Additive-only evolution** (AIP-180, Stripe). The default. When a semantic change
  is unavoidable, use a new field name or a new version.
- **Tolerant reader / must-ignore.** Consumers use only what they need and ignore
  unknown fields, enum values and events. Be tolerant of unknown *extensions*, not
  of malformed data: RFC 9413 warns that silently accepting bad input entrenches
  errors.
- **Versioning strategies.** Major version in the path (`v1`, `v1beta`) is simple and
  visible but forces coexisting stacks, so use it only for truly incompatible
  changes. Date-based header versioning (Stripe) pins each account to a version and
  transforms responses backward; it allows many small upgrades but needs heavy
  platform machinery, so don't build it for a small API.
- **Stability channels** (AIP-181): alpha carries no promises, beta is time-boxed,
  stable has no breaking changes within the major version.
- **Expand and contract for APIs:** add the new form beside the old, migrate
  consumers, then remove the old form. Don't skip the middle step.
- **Consumer-driven contract tests (Pact).** Consumers publish what they actually
  use; the provider verifies it. Good for internal services with known consumers;
  weak for public APIs with unknown consumers, where telemetry and versioning carry
  the load.
- **Schema diffing.** `buf breaking` has strictness categories (FILE, PACKAGE,
  WIRE_JSON, WIRE); `oasdiff` has `breaking` and `changelog` modes.

## Example

Rename `phone` to `mobile_number` in a JSON response without breaking existing
clients. Expand at release N: emit both, accept either on writes, mark the old one
deprecated:

```json
{"id": "c_1", "phone": "+15551234", "mobile_number": "+15551234"}
```

```yaml
phone:
  type: string
  deprecated: true
  description: Use mobile_number. Removal no earlier than 2027-03-01.
```

Timeline: dual-write now with a changelog entry, migration guide and `Sunset` header;
measure requests that still use `phone`, per client, and contact the heaviest users;
remove at the sunset date only if usage is near zero, otherwise extend; ship the
removal in a new API version, not silently.

For protobuf, checked with `buf breaking` on a message with `string phone = 2`:

| Change | `WIRE` | `WIRE_JSON` | `FILE` |
|---|---|---|---|
| Rename to `mobile_number`, same number | ok | breaking | breaking |
| Add `mobile_number = 3`, mark `phone` deprecated | ok | ok | ok |
| Delete `phone` with no `reserved` | breaking | breaking | breaking |
| Delete `phone`, with `reserved 2; reserved "phone";` | ok | ok | **still breaking** |

So a rename that is safe on the wire breaks JSON consumers and generated code, and
`reserved` makes a deletion safe at the wire and JSON level but not for code that
compiles against the old field. The compatible path is to add the new field, keep
both populated, deprecate the old one, and delete (with `reserved`) only at the end.

## Gotchas and contested points

- **Breaking is defined by consumers, not by the spec** (Hyrum). Published lists of
  breaking changes (Microsoft Graph, Stripe) are policy decisions that only bind
  consumers who were told.
- **Direction matters.** Adding a field can be safe in a response and breaking in a
  request. In schema-registry terms, BACKWARD means new readers can read old data
  (upgrade consumers first) and FORWARD means old readers can read new data (upgrade
  producers first). Work out who sends and who receives.
- **Adding a value to a response enum breaks consumers that switch on it,** while an
  optional request field is safe. Google says to document that response enums may
  gain values, which is weaker than "safe".
- **Wire compatibility is not source compatibility** (the table above).
- **Most REST APIs use JSON regardless,** so field names *are* the contract.
- **When to bump the major version:** only for an incompatible change that cannot be
  made additively (AIP-185). Security or regulatory emergencies override the normal
  rules.
- **New event or webhook types are treated as compatible** by Stripe's model, so
  consumers must ignore events they don't know.

## Review checklist

1. Have I classified this change as compatible, schema-breaking or behavioral?
2. Can it be made additively, with old and new both working?
3. Did I avoid renaming, retyping, removing, or reusing field numbers?
4. Are new request fields optional, with a default that keeps the old behavior?
5. Have I checked for changed defaults, validation, error codes, ordering or pagination?
6. Is deprecation announced with a date and headers, and is use of the old form measured?
7. Did I run a schema diff and the consumer contract tests?
8. Do consumers ignore unknown fields, enum values and events?

## Related

`semver` (version numbers), `openapi` (describing the contract), `database-migrations`
(the same expand/contract idea for schemas), `refactoring` (Parallel Change), and
`release-engineering` (deploying the removal separately).

## Sources

Google AIPs [180](https://google.aip.dev/180), [181](https://google.aip.dev/181) and
[185](https://google.aip.dev/185); Stripe,
[API versioning](https://stripe.com/blog/api-versioning) and
[upgrades](https://docs.stripe.com/upgrades); [Hyrum's Law](https://www.hyrumslaw.com/);
Fowler,
[Consumer-Driven Contracts](https://martinfowler.com/articles/consumerDrivenContracts.html);
[Pact](https://docs.pact.io/); protobuf
[updating guidance](https://protobuf.dev/programming-guides/proto3/#updating) and
[dos and don'ts](https://protobuf.dev/best-practices/dos-donts/); Buf
[breaking-change detection](https://buf.build/docs/breaking/);
[oasdiff](https://github.com/oasdiff/oasdiff); Microsoft
[API guidelines](https://github.com/microsoft/api-guidelines);
[Kubernetes deprecation policy](https://kubernetes.io/docs/reference/using-api/deprecation-policy/);
[RFC 9745](https://www.rfc-editor.org/rfc/rfc9745.html) (Deprecation header);
[RFC 9413](https://www.rfc-editor.org/rfc/rfc9413.html); Confluent
[schema evolution](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html).
Every cell of the protobuf table was produced by running `buf breaking` on the
described change. AIP-214 is about resource expiration and is not a deprecation
policy.
