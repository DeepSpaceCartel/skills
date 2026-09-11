# CloudEvents Documented Extensions

Spec index:
[github.com/cloudevents/spec/tree/main/cloudevents/extensions](https://github.com/cloudevents/spec/tree/main/cloudevents/extensions).
These are attributes the CloudEvents project has already designed,
named, and documented for common cross-cutting needs — check here
before defining a new extension attribute of your own, and reuse one of
these rather than reinventing it under a different name.

| Attribute(s) | Extension | Purpose |
|---|---|---|
| `traceparent`, `tracestate` | Distributed tracing | Carries W3C Trace Context (`traceparent` required, `tracestate` optional) so an event can be correlated into a distributed trace. |
| `partitionkey` | Partitioning | A string used to group/route causally related events (e.g. to the same processing shard). May be altered or dropped across hops — don't rely on it surviving multi-hop delivery unchanged. |
| `sequence`, `sequencetype` | Sequence | `sequence` is a non-empty, lexicographically-orderable string giving relative order of events from the same `source`; recommend monotonically increasing, contiguous, and zero-padded so plain string comparison sorts correctly. |
| `sampledrate` | Sampled rate | Integer > 0: how many equivalent occurrences this one event represents (30 occurrences sampled down to 1 emitted event → `sampledrate: 30`). Absence/1 means no sampling. |
| `dataref` | Dataref (claim check) | URI-reference to the event's payload stored externally — for payloads too large to inline, for producers wanting a source-of-truth/integrity check, or for access-controlled data. May coexist with `data`; middleware may strip `data` once it's confident all downstream consumers can resolve `dataref`. |
| `datacontenttype`/`dataschema` versioning hooks | — | (Core attributes, not extensions — see the Versioning section of the main [SKILL.md](../SKILL.md).) |
| — | Also documented: `authcontext`, `bam` (business activity monitoring), `correlation`, `data-classification`, `deprecation`, `expirytime`, `opcua` (OPC UA metadata), `recordedtime`, `severity`, `verifiability` | Narrower/domain-specific; read the individual spec file under `cloudevents/extensions/` in the spec repo before adopting one. |

## Designing a new extension (only after checking the table above)

- Scope it to **routing/processing metadata** the transport or an
  intermediary needs — not application data, which belongs in `data`.
- Keep it minimal: in HTTP binary mode every extension becomes its own
  header, and header budgets are small (as low as ~8 KiB total on some
  servers).
- Follow the same naming rules as core attributes (lowercase
  `[a-z0-9]`, starts with a letter, ideally ≤20 chars) and the same
  abstract type system — an extension is not a place to smuggle in a
  richer type model.
- Extensions sit flat at the top level of the event, exactly like core
  attributes — never nest them under an `"extensions"` object.
- A widely-useful extension is a candidate for eventual promotion into
  the core spec; that's the normal lifecycle, not a sign you did
  something wrong by starting as an extension.
