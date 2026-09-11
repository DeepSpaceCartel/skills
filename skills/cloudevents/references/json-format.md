# CloudEvents JSON Event Format

Spec:
[github.com/cloudevents/spec .../formats/json-format.md](https://github.com/cloudevents/spec/blob/main/cloudevents/formats/json-format.md).

## Media types

| Mode | Media type |
|---|---|
| Structured, single event | `application/cloudevents+json` |
| Structured, batch of events | `application/cloudevents-batch+json` |

## Abstract type → JSON mapping

| Abstract type | JSON representation |
|---|---|
| Boolean | JSON boolean |
| Integer | JSON number (integer component) |
| String | JSON string |
| Binary | JSON string, Base64-encoded |
| URI / URI-reference | JSON string |
| Timestamp | JSON string, RFC 3339 |

An attribute may be encoded as JSON `null` to mean "explicitly unset";
on decode, `null` and "member absent" are equivalent — don't treat a
`null` differently from an omitted key.

## Structured mode

Every context attribute becomes a top-level JSON member with the same
name and the mapping above; `data`/`data_base64` (see below) carries
the payload. This is the shape used in the [Quick example](../SKILL.md)
in the main skill file.

## Batched mode

A JSON array of structured-mode objects, each independently valid.
Media type `application/cloudevents-batch+json`. Only use batching
when the receiving side has actually solicited it (see the HTTP
binding's batching rule in
[`protocol-bindings.md`](protocol-bindings.md)) — don't default to
batching just because it's convenient for the producer.

## `data` vs. `data_base64`

The two members are **mutually exclusive** — never emit both on the
same event.

- **`data_base64`**: used when the payload is arbitrary binary data.
  Contains the Base64-encoded bytes. `datacontenttype` still describes
  the *decoded* payload's real media type (e.g. `image/png`), not
  `application/base64` — `data_base64` is purely a JSON-format encoding
  detail, not part of the event's semantic content type.
- **`data`**: used for everything else, and its shape depends on
  `datacontenttype`:
  - If `datacontenttype` is a JSON media type (subtype `json`, or any
    `+json` structured suffix like `application/ld+json`), `data` is an
    **unrestricted JSON value** embedded directly — an object, array,
    string, number, whatever the payload actually is. Do not
    double-encode it as a JSON-string-containing-JSON.
  - Otherwise, `data` is a JSON string containing the payload encoded
    per `datacontenttype` (e.g. a plain-text or XML body as a string).
  - If `datacontenttype` is absent entirely, decoders **default it to
    `application/json`** for the purpose of interpreting `data`.

```json
// datacontenttype implied/JSON -> data is a raw JSON value
{ "specversion": "1.0", "id": "1", "source": "/x", "type": "t",
  "data": { "count": 3 } }

// binary payload -> data_base64, datacontenttype names the real type
{ "specversion": "1.0", "id": "2", "source": "/x", "type": "t",
  "datacontenttype": "image/png",
  "data_base64": "iVBORw0KGgoAAAANSUhEUgAA..." }

// non-JSON text payload -> data is a string
{ "specversion": "1.0", "id": "3", "source": "/x", "type": "t",
  "datacontenttype": "text/plain",
  "data": "hello world" }
```

## Gotchas

- Picking `data_base64` for a JSON payload (instead of embedding it
  directly under `data`) is a common but wrong shortcut — it works, but
  breaks compatibility with consumers that expect JSON payloads to be
  directly queryable/filterable without a decode step first.
- A `datacontenttype` of `application/json` still means `data` holds a
  raw JSON value, not a JSON-encoded string — same rule as any
  `+json` suffix.
