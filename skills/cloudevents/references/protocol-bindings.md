# CloudEvents Protocol Bindings

Spec index:
[github.com/cloudevents/spec/tree/main/cloudevents/bindings](https://github.com/cloudevents/spec/tree/main/cloudevents/bindings).
Every binding defines the same two modes; only the transport mechanics
(headers vs. properties vs. record fields) differ.

- **Binary mode** — `data` goes in the transport's body/value as-is;
  `datacontenttype` becomes the transport's native content-type field;
  every other context attribute (core or extension) becomes a
  transport-native metadata field, name-prefixed per binding.
- **Structured mode** — the whole event (metadata + data) is serialized
  by an event format (usually JSON) into a single body/value; the
  transport's content-type field names the *event format's* media type
  (e.g. `application/cloudevents+json`), not the data's.

A compliant implementation **should** support both modes. Structured
mode is what lets an intermediary forward an event across protocols
without understanding its extensions — binary mode is cheaper to
produce/consume when both ends speak the same protocol natively.

## HTTP

Spec:
[.../bindings/http-protocol-binding.md](https://github.com/cloudevents/spec/blob/main/cloudevents/bindings/http-protocol-binding.md).

- **Binary mode**: every context attribute, including extensions, maps
  to an HTTP header named `ce-<attribute>` (e.g. `ce-id`, `ce-time`,
  `ce-specversion`). `datacontenttype` is the one exception — it maps to
  the real `Content-Type` header, and a `ce-datacontenttype` header
  **must not** appear. Header name matching is case-insensitive, per
  HTTP.
- **Structured mode**: `Content-Type` is set to the event format's media
  type (`application/cloudevents+json`); the full event is the body. No
  `ce-*` headers are used.
- **Batched mode**: `Content-Type` is the batch format's media type
  (`application/cloudevents-batch+json`); body is the JSON array.
  Batching **must not** be used unless the receiver solicited it, and
  the receiver should be able to bound the batch size it accepts.
- Header-size limits are the practical ceiling on how many/how large
  extension attributes you can add in binary mode — many HTTP servers
  reject requests once total headers exceed ~8 KiB.

## Kafka

Spec:
[.../bindings/kafka-protocol-binding.md](https://github.com/cloudevents/spec/blob/main/cloudevents/bindings/kafka-protocol-binding.md).

- **Binary mode**: context attributes map to Kafka record headers
  prefixed `ce_` (not `ce-`) — e.g. `ce_id`, `ce_time`. The `content-type`
  header carries `datacontenttype`.
- **Structured mode**: the `content-type` header alone (e.g.
  `application/cloudevents+json; charset=UTF-8`) identifies the format;
  `ce_*` headers are optional/unused.
- **Record key**: independent of mode. Defaults to whatever key the
  producer already sets; implementations may optionally offer a "Key
  Mapper" that derives the Kafka key from an event attribute — commonly
  the `partitionkey` extension (see
  [`extensions.md`](extensions.md)) — without removing that attribute
  from the transmitted event.

## AMQP, MQTT, NATS, WebSockets

Same binary/structured split, with these bindings' own prefix/property
conventions (AMQP application properties, MQTT user properties, NATS
headers). Read the specific binding doc before implementing one you
haven't used before — don't assume the HTTP `ce-` prefix or Kafka `ce_`
prefix carries over:
[.../bindings/amqp-protocol-binding.md](https://github.com/cloudevents/spec/blob/main/cloudevents/bindings/amqp-protocol-binding.md),
[.../bindings/mqtt-protocol-binding.md](https://github.com/cloudevents/spec/blob/main/cloudevents/bindings/mqtt-protocol-binding.md),
[.../bindings/nats-protocol-binding.md](https://github.com/cloudevents/spec/blob/main/cloudevents/bindings/nats-protocol-binding.md),
[.../bindings/websockets-protocol-binding.md](https://github.com/cloudevents/spec/blob/main/cloudevents/bindings/websockets-protocol-binding.md).

## Gotchas

- The header prefix is **not** uniform across bindings: HTTP uses
  `ce-` (hyphen), Kafka uses `ce_` (underscore). Copying one binding's
  convention to another silently produces headers no compliant consumer
  recognizes.
- In binary mode, `datacontenttype`/`content-type` is always carried by
  the transport's *native* content-type field, never as a `ce-*` /
  `ce_*` metadata field — it's the one attribute that isn't
  prefix-mapped.
- Structured mode's content-type names the **event format**
  (`application/cloudevents+json`), not the underlying data's type —
  the data's real `datacontenttype` is still inside the serialized
  event body as a regular attribute.
