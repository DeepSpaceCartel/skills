# Timeouts and retries in the infrastructure

## Problem

Proxies, meshes, gateways and load balancers each carry their own timeouts and retry policies,
and most of them ship with defaults. A request crosses several of them, so its real deadline
and its real retry count come from settings nobody chose. The usual results are a gateway that
gives up before the backend does, or one user click that becomes dozens of attempts at the
database.

## When to use / when NOT to use

- **Use** whenever traffic passes an ingress, a gateway, a sidecar mesh or an L7 load balancer.
  Every hop has a timeout whether you set one or not.
- **Retry in the infrastructure** when a request is idempotent, the application doesn't retry,
  and the failure is at the connection level (connect failure, refused stream, reset before any
  response).
- **Don't retry in the infrastructure** when the application client already retries, for
  non-idempotent requests without an idempotency key, or for a timeout of the whole request
  (Envoy doesn't retry its own route timeout, which is correct).

## How it works

The timeouts at every proxy hop:

| Kind | What it bounds | Envoy name (default) |
|---|---|---|
| Route / request | Whole request including all retries | route `timeout` (15 s; 0 disables) |
| Per try | One attempt | `per_try_timeout` (unset: the route timeout applies) |
| Idle / stream | Silence on a connection or stream | HCM `idle_timeout` (1 h), `stream_idle_timeout` (5 min) |
| Connect | TCP plus TLS handshake | cluster `connect_timeout` (5 s) |
| Drain | Between first and last HTTP/2 GOAWAY on shutdown | HCM `drain_timeout` (5 s) |

Envoy leaves `request_timeout`, `request_headers_timeout` and `max_connection_duration`
disabled by default. Istio's VirtualService HTTP `timeout` is disabled by default, so an Istio
route has no request deadline until you set one.

Retries at a proxy are a policy: which conditions trigger one, how many, the per-try timeout,
backoff, and which hosts to try. Envoy's back-off is fully jittered exponential, 25 ms base and
a 250 ms cap by default. Its `rate_limited_retry_back_off` can read a `Retry-After`-style
header and falls back to exponential back-off when the header is missing. A retry budget caps
active retries as a share of active requests (Envoy: `budget_percent` 20%,
`min_retry_concurrency` 3, under circuit breakers).

**Defaults that already retry.** Envoy retries nothing unless a policy or header asks for it.
Istio applies a mesh-wide default of 2 retries (`attempts: 2`, so up to 3 requests) on `connect-failure,refused-stream,unavailable,cancelled`
to every route without its own policy. A service in Istio is therefore already retried at the
sidecar before anyone writes a retry loop.

## In code / In infrastructure

**In code.** Per-attempt timeouts derived from the dependency's latency, an overall deadline
passed downstream, at most 3 attempts with full jitter, a retry budget, and idempotency keys:
all in [`engineering-practices` reliability](../../engineering-practices/references/reliability.md).
Code knows which operations are idempotent and how much deadline is left. The proxy knows
neither.

**In infrastructure.** The proxy knows connection state, which hosts it already tried and
whether request headers left the building (`reset-before-request`). It retries without
redeploying the service and covers clients you don't control.

**Pick one layer per call path.** Retries multiply: Istio's default (up to 3 requests per call) under a client
that makes 3 attempts is 9 upstream requests per user action, and each extra layer multiplies again.
Choose the layer, then explicitly turn the other off (`attempts: 0` in Istio disables retries).
Timeouts must nest the other way round: each outer hop's timeout is longer than the inner hop's
timeout times its attempts plus backoff, or the outer hop cuts off a retry that is still running.

## Failure modes and what agents get wrong

- **Not knowing the mesh already retries.** Adding a client retry loop under Istio's default
  policy multiplies attempts without anyone seeing it in the code.
- **Inverted timeouts.** A gateway at 30 s in front of a backend at 60 s: the gateway returns
  504, the backend keeps working, the client retries, and the backend now runs the job twice.
- **Assuming a default deadline exists.** Istio's request timeout is off; a hung upstream holds
  the stream until an idle timeout (Envoy's stream idle default is 5 minutes).
- **Long requests killed by Envoy's 15 s default.** Exports, uploads and streaming endpoints
  need their own route timeout (or 0 with a stream idle timeout).
- **Retrying on 5xx for POSTs.** Envoy's `5xx` condition covers any 5xx and resets; a
  non-idempotent write that failed after the server committed runs twice.
- **`retriable-4xx` for 409.** Envoy warns this can loop on optimistic-locking conflicts.
- **Per-try timeout equal to the route timeout.** Envoy ignores a per-try header that isn't
  shorter than the route timeout, so there is no room for a second attempt.
- **Retries against the same bad host.** Without a previous-hosts predicate (Istio:
  `retryIgnorePreviousHosts`, default true) the retry may land where it just failed.
- **Idle timeouts out of order.** A load balancer that drops idle connections sooner than the
  client pool expects produces resets on the next request; keep the client's idle timeout
  shorter than every proxy's on the path (inferred from how idle timeouts work, not a vendor rule).

## Implementation notes

- **Envoy:** route `timeout`, `retry_policy` (`retry_on`, `num_retries` default 1,
  `per_try_timeout`, `per_try_idle_timeout`, `retry_back_off`, `rate_limited_retry_back_off`),
  `x-envoy-attempt-count` upstream (`include_request_attempt_count`) so the backend can see a retry.
- **Istio:** VirtualService `timeout`, `retries.attempts` (0 disables), `perTryTimeout`,
  `retryOn`, `retryIgnorePreviousHosts`, `backoff`; mesh default via `defaultHttpRetryPolicy`.
- **NGINX / HAProxy:** both have connect and server timeouts and a retry-next-upstream setting;
  HAProxy's `timeout queue` bounds time waiting for a server slot. Check each directive in your
  version's docs.
- **Managed:** cloud load balancers and API gateways each have an idle timeout and a backend
  timeout; read both before setting the service's own.

## Example

An Istio route for an idempotent read API: one retry layer (the mesh), the client told not to retry.

```yaml
apiVersion: networking.istio.io/v1
kind: VirtualService
metadata:
  name: catalog-read
spec:
  hosts: ["catalog.shop.svc.cluster.local"]
  http:
  - match:
    - method: {exact: GET}
    route:
    - destination: {host: catalog.shop.svc.cluster.local}
    timeout: 3s                # whole request, all attempts
    retries:
      attempts: 2              # 1 + 2 = at most 3 upstream requests
      perTryTimeout: 900ms     # 3 x 900ms + backoff fits inside 3s
      retryOn: connect-failure,refused-stream,reset,gateway-error
  - route:                     # writes: no mesh retries; client uses idempotency keys
    - destination: {host: catalog.shop.svc.cluster.local}
    timeout: 10s
    retries: {attempts: 0}
```

Reads get three bounded tries inside a 3 s deadline; writes get no proxy retry, so the client's
keyed retries are the only layer. The gateway in front should allow a little more than 3 s and
10 s. All field names are from the Istio VirtualService reference; the values are illustrative.

## Review checklist

1. For each call path, which single layer retries, and is retrying explicitly disabled at the others?
2. Does every outer hop's timeout exceed the inner hop's per-try timeout times attempts plus backoff?
3. Is there a request deadline on every route (Istio's default is none), and do long-running routes override Envoy's 15 s default deliberately?
4. Are proxy retries limited to idempotent methods and connection-level failures?
5. Is there a retry budget or retry circuit breaker so retries can't exceed a fixed share of traffic?
6. Do retries skip the host that just failed?
7. Are idle timeouts ordered so the client closes idle connections before any proxy does?
8. Can the backend see the attempt count, and do retries honour `Retry-After` or an overloaded signal?

## Related

[circuit-breaking-and-outlier-ejection](circuit-breaking-and-outlier-ejection.md) (retry budgets
live with circuit breakers), [rate-limiting-and-throttling](rate-limiting-and-throttling.md)
(429 and `Retry-After`), [load-shedding](load-shedding.md),
[`engineering-practices` reliability](../../engineering-practices/references/reliability.md).

## Sources

Envoy: [router filter](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/router_filter),
[route components](https://www.envoyproxy.io/docs/envoy/latest/api-v3/config/route/v3/route_components.proto),
[timeouts FAQ](https://www.envoyproxy.io/docs/envoy/latest/faq/configuration/timeouts),
[circuit breaker proto](https://www.envoyproxy.io/docs/envoy/latest/api-v3/config/cluster/v3/circuit_breaker.proto).
Istio [VirtualService](https://istio.io/latest/docs/reference/config/networking/virtual-service/).
AWS Builders' Library, [Timeouts, retries and backoff with jitter](https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter)
(retry at one point in the stack; layers multiply). Google SRE book,
[Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/).
HAProxy [configuration manual](https://raw.githubusercontent.com/haproxy/haproxy/master/doc/configuration.txt) (`timeout queue`).
