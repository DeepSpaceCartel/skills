# Rate limiting and throttling at the edge

## Problem

Without limits, one client, tenant or bug can consume all of a service's capacity. Throttling
caps what each principal may use so the service keeps its objectives for everyone else. The
limit has to live somewhere every request passes (an ingress, a gateway, a sidecar), be keyed on
the right identity, and tell the caller when to come back.

## When to use / when NOT to use

- **Use** for public and multi-tenant APIs, expensive endpoints (search, export, login), and any
  service with a downstream that has its own hard limit.
- **Use** local limits to absorb bursts cheaply, and a global limit when the same principal
  reaches many replicas.
- **Not** a capacity plan: a rate limit protects a service of a known size; it doesn't make it
  bigger. Azure pairs throttling with autoscaling: throttle while new capacity arrives.
- **Not** DDoS protection. Azure separates the two: edge controls drop volumetric attacks;
  application throttling meters legitimate traffic. Use both.
- **Not** the client side. Pacing your own calls to someone else's limit (a crawler, a batch
  ingest) is a client concern: see [`data-pipelines` failure-isolation](../../data-pipelines/references/failure-isolation.md)
  and Azure's Rate Limiting pattern (queue the work, release it at the allowed rate).

## How it works

1. **Pick the dimension that saturates first.** Azure's Throttling pattern: requests per second
   is the familiar unit, but the real limit is often in-flight concurrency, queue depth, CPU or
   a downstream's quota. A request-rate limit doesn't protect a fan-out point bound by
   concurrency.
2. **Pick the key.** Per API key or tenant for fairness; per source IP only for anonymous
   traffic (NAT puts many users behind one IP); per route for expensive operations. Weight
   requests by cost where costs differ (writes vs reads).
3. **Pick the algorithm.** A token bucket allows bursts up to its size and refills at a steady
   rate. NGINX's `limit_req` is a leaky bucket that delays or rejects the excess.
4. **Place the counter.** Local (per proxy process): fast, no dependency, but a principal
   spread over N replicas gets N times the limit. Global (shared service): exact, adds a call
   per request. Envoy describes combining them as an option: a local bucket first for coarse
   limiting and bursts, then the global service, which then sees less load.
5. **Answer clearly.** 429 for a principal over its rate, 503 for a service that can't take
   anything right now. Send `Retry-After`, name the limit that was hit, and reject before any
   expensive work (auth, parsing).
6. **Change limits at runtime,** without a deploy, and dry-run new limits before enforcing them.

## In code / In infrastructure

**In code.** Honour 429 and `Retry-After`, back off with jitter, and don't retry blindly; see
[`engineering-practices` reliability](../../engineering-practices/references/reliability.md).
Per-tenant quotas that need business data (plan, entitlements) may need the application.

**In infrastructure.** Edge limits per key at the ingress or gateway, local token buckets in
sidecars, and a global rate-limit service for limits shared across replicas.

**Agree:** a limit at the gateway of 100 rps per tenant, an application limit of 50 rps per
tenant and a mesh retry on 429 together produce rejections the client can't reason about.
Enforce each principal's limit in one place, propagate the 429 unchanged, and never
auto-retry a 429 inside the mesh unless the retry waits for the header (Envoy's
`rate_limited_retry_back_off`).

## Failure modes and what agents get wrong

- **Per-IP limits on authenticated APIs.** Corporate NAT and mobile carriers share IPs; key on
  the credential.
- **A local limit treated as global.** 10 replicas with a local 100 rps limit allow 1,000 rps.
- **NGINX's default status.** `limit_req` rejects with 503 unless `limit_req_status 429` is set,
  so clients see "server down" instead of "slow down".
- **Swallowing a downstream 429** and returning 500, or retrying it silently. Azure's Throttling
  pattern says to propagate back-pressure so the whole chain slows down.
- **A cache as the throttle.** Azure: caching lowers average load but not the peak; a popular
  key expiring under load still stampedes the origin.
- **Rejecting after the expensive part.** If refusing costs as much as serving, a flood of
  refusals still saturates the service.
- **No dry run.** A new limit enforced on day one blocks a legitimate integration.
  NGINX has `limit_req_dry_run`; Envoy's local limiter has `filter_enabled` vs
  `filter_enforced` fractions.
- **Global limiter as a single point of failure.** Decide whether the edge allows or denies when
  the rate-limit service is down, and test it (Envoy has a failure-mode setting; its default
  is (unverified)).

## Implementation notes

- **Envoy:** local rate limit HTTP filter (token bucket: `max_tokens`, `tokens_per_fill`,
  `fill_interval`; 429 by default; `enable_retry_after_header`; shared across workers by
  default); global rate limit filter calling a gRPC service (reference implementation in Go on
  Redis), with descriptors built from route actions such as `request_headers`,
  `remote_address` and `generic_key`.
- **NGINX:** `limit_req_zone` (1 MB holds about 8,000 states on 64-bit, 16,000 on 32-bit),
  `limit_req burst= nodelay`, `limit_req_status`, `limit_req_dry_run`.
- **Istio:** uses Envoy's local and global limiters via EnvoyFilter or the mesh's rate-limit
  integration (unverified).
- **Managed:** API gateways and web application firewalls offer per-key and per-IP rate rules;
  check whether their counters are per region or global.

## Example

NGINX in front of a SaaS API: per-key limit with a small burst, a per-server ceiling, 429s,
dry-run first.

```nginx
http {
    map $http_x_api_key $api_key { default $http_x_api_key; "" $binary_remote_addr; }
    limit_req_zone $api_key     zone=per_key:20m rate=20r/s;   # ~160k keys (64-bit)
    limit_req_zone $server_name zone=per_srv:1m  rate=800r/s;  # node ceiling
    limit_req_status 429;
    limit_req_dry_run on;            # week one: count, don't reject

    server {
        location /v1/ {
            limit_req zone=per_key burst=40 nodelay;
            limit_req zone=per_srv burst=200;
            proxy_pass http://api_upstream;
        }
        location /v1/export {
            limit_req zone=per_key burst=2;   # expensive route: tiny burst, queued
            proxy_pass http://api_upstream;
        }
    }
}
```

Each key gets 20 rps with a 40-request burst; anonymous callers fall back to their IP; the
server zone caps one NGINX at 800 rps. 20 MB at 128 bytes per state (64-bit) is about
160,000 keys. `limit_req` directives are from the NGINX module docs; the `map` fallback is
(unverified). `limit_req` sends no `Retry-After`; add it only on the 429 path (for example via
an `error_page 429` location, (unverified)), since a header on every response would be wrong.

## Review checklist

1. Is the limit on the dimension that saturates first (concurrency, queue, a downstream quota), not just requests per second?
2. Is the key the authenticated principal where one exists?
3. Is the limit local, global, or both, and does the local limit account for the replica count?
4. Do rejections return 429 (or 503 for whole-service overload) with `Retry-After`, before expensive work?
5. Is each principal's limit enforced in exactly one layer, and are 429s from downstream propagated, not swallowed or auto-retried?
6. Can limits change at runtime, and was the limit dry-run before enforcement?
7. What happens when the global limiter is down?

## Related

[load-shedding](load-shedding.md) (shedding by priority when the whole service is full),
[bulkheads-and-isolation](bulkheads-and-isolation.md), [timeouts-and-retries-infra](timeouts-and-retries-infra.md),
[`data-pipelines` failure-isolation](../../data-pipelines/references/failure-isolation.md) (the client side),
[`engineering-practices` reliability](../../engineering-practices/references/reliability.md).

## Sources

Azure [Throttling pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/throttling)
and [Rate Limiting pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/rate-limiting-pattern).
Envoy [global rate limiting](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/other_features/global_rate_limiting),
[local rate limit filter](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/local_rate_limit_filter),
[route components](https://www.envoyproxy.io/docs/envoy/latest/api-v3/config/route/v3/route_components.proto).
NGINX [ngx_http_limit_req_module](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html).
Google SRE book, [Handling Overload](https://sre.google/sre-book/handling-overload/) (per-customer quotas).
