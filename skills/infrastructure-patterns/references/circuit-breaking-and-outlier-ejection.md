# Circuit breaking and outlier ejection

## Problem

One slow or broken backend instance keeps receiving its share of traffic, and one slow
dependency ties up every connection a caller has. In a proxy, two different mechanisms handle
these: **outlier ejection** removes individual bad hosts from a pool, and **connection-pool
limits** (Envoy calls them circuit breakers) cap what a caller may have outstanding against a
whole cluster.

## When to use / when NOT to use

- **Outlier ejection:** a pool of interchangeable replicas behind a mesh or L7 balancer, where
  one host can go bad (bad node, stuck process, partial deploy) while the rest are fine.
- **Pool limits:** every upstream cluster, so a slow dependency fails fast with an overflow
  instead of growing an unbounded queue.
- **Not** a substitute for timeouts: a limit of 1024 requests each waiting 60 s is still 1024
  stuck requests.
- **Not** useful on a pool of one or two hosts: there is nothing to eject to.
- A code-level breaker with a **fallback** is still the job of the application (see In code).

## How it works

**Outlier ejection (passive health checking).** The proxy watches real responses per host.
Envoy's detectors and defaults:

| Detector | Trigger | Default |
|---|---|---|
| `consecutive_5xx` | N 5xx (or local errors in default mode) in a row | 5, enforced 100% |
| `consecutive_gateway_failure` | N 502/503/504 in a row | 5, enforced 0% (off) |
| `consecutive_local_origin_failure` | timeouts, resets (split mode only) | 5 |
| success rate | host far below the pool mean | needs 5 hosts, 100 requests each |
| failure percentage | host above a flat threshold | 85% |

Ejection lasts `base_ejection_time` (30 s) times the number of times that host has been
ejected, capped by `max_ejection_time` (300 s). Detection runs every `interval` (10 s). At most
`max_ejection_percent` (10%) of the pool is ejected at once. A successful active health check
un-ejects a host unless `successful_active_health_check_uneject_host` is false.

**Panic threshold.** When the healthy share of a pool falls below 50% (Envoy default), Envoy
ignores health and spreads traffic across all hosts, or fails it if `fail_traffic_on_panic` is
set. Istio's `minHealthPercent` (default 0, disabled) does the same for outlier detection.

**Pool limits (Envoy circuit breakers).** Per cluster and per priority, shared by all workers,
eventually consistent so occasionally exceeded:

| Threshold | Default | Overflow counter |
|---|---|---|
| `max_connections` | 1024 | `upstream_cx_overflow` |
| `max_pending_requests` | 1024 | `upstream_rq_pending_overflow` |
| `max_requests` | 1024 | `upstream_rq_active_overflow` |
| `max_retries` | 3 | `upstream_rq_retry_overflow` |
| `retry_budget` | 20%, min 3 concurrent | (replaces `max_retries`) |

On overflow the router fails the request and sets `x-envoy-overloaded`. Istio's
DestinationRule `connectionPool` defaults are effectively unlimited (2^32-1), so an Istio
service has no pool limit until you set one.

## In code / In infrastructure

**In code.** A closed/open/half-open breaker per dependency that returns a defined fallback
(cached value, default, degraded response), with timeouts underneath it. See
[`engineering-practices` reliability](../../engineering-practices/references/reliability.md).
Azure's pattern adds that a breaker should be per independent backend (one per shard, not one
per database), and that a response saying "overloaded, try in N minutes" can trip it at once.

**In infrastructure.** Ejection works per host, which application code usually can't see behind
a Service VIP. Pool limits protect every caller without code changes. Azure lists "recovery is
already handled by the mesh or load balancer" as a reason not to add an application breaker.

**Agree on one owner per job.** Host-level ejection belongs to the proxy. Dependency-level
fail-fast with a fallback belongs to code. If both trip on the same signal, the client opens
its breaker for a whole service when the mesh would have ejected one bad pod.

## Failure modes and what agents get wrong

- **Copying the 10% ejection cap to a small pool.** With 3 replicas, 10% is 0.3 hosts; whether
  that ejects anyone depends on rounding (unverified). Envoy's `always_eject_one_host`
  (default false) exists for this case; check it, or raise the percentage.
- **Ejecting the whole pool.** A shared dependency fails, every host returns 5xx, and raising
  `max_ejection_percent` to 100 removes all capacity. Keep a cap and rely on the panic threshold.
- **Counting only 5xx.** Timeouts and resets are local-origin errors; in split mode they need
  `consecutive_local_origin_failure` or they are invisible to ejection.
- **Istio defaults treated as protection.** Unlimited connection pools mean no circuit breaking.
- **Limits sized from defaults, not Little's law.** Concurrency = rate x latency. 400 rps at
  50 ms is 20 in flight; a limit of 1024 never trips before the upstream melts.
- **No alerts on overflow counters.** A breaker that trips silently looks like random 503s.
- **A fast-failing host attracts traffic.** A host returning instant errors looks fast to
  least-request balancing; AWS calls this a black hole. Ejection on errors is the fix.

## Implementation notes

- **Envoy:** cluster `outlier_detection` and `circuit_breakers.thresholds`; per-host limits
  support only `max_connections`.
- **Istio:** DestinationRule `trafficPolicy.outlierDetection` (`consecutive5xxErrors` 5,
  `interval` 10 s, `baseEjectionTime` 30 s, `maxEjectionPercent` 10) and `connectionPool`.
- **HAProxy:** server `observe layer7` with `error-limit` (default 10) and `on-error`
  (`fail-check` default, `mark-down`); `maxconn` per server (0 = unlimited) and `maxqueue`.
- **NGINX:** passive failure counting on upstream servers exists; verify the directives for
  your version (unverified).
- **Managed:** cloud load balancers do active health checks; passive ejection usually needs a
  mesh or an L7 proxy you run (unverified).

## Example

An Istio DestinationRule for a 12-replica API: eject a pod after 3 gateway errors, never more
than a quarter of the pool, and cap concurrency at what the pods can serve.

```yaml
apiVersion: networking.istio.io/v1
kind: DestinationRule
metadata:
  name: search-api
spec:
  host: search.shop.svc.cluster.local
  trafficPolicy:
    connectionPool:
      tcp: {maxConnections: 200}
      http:
        http2MaxRequests: 120        # 12 pods x 10 in flight each
        http1MaxPendingRequests: 20  # short queue, then fail fast
        maxRetries: 10               # cluster-wide active retries
    outlierDetection:
      consecutiveGatewayErrors: 3
      consecutive5xxErrors: 5
      interval: 5s
      baseEjectionTime: 30s
      maxEjectionPercent: 25         # at most 3 of 12 pods out at once
```

120 = 12 pods x 10 concurrent requests, from 200 rps at 50 ms per pod measured in a load test.
Field names are from the Istio DestinationRule reference; the numbers are this example's own.

## Review checklist

1. Does every upstream cluster have explicit connection, pending and request limits sized from measured concurrency?
2. Is outlier ejection on, with detectors for gateway errors and local-origin failures, not 5xx only?
3. Does the ejection cap leave enough hosts to carry peak load, and does it make sense at the pool's smallest size?
4. Is there a panic threshold (or `minHealthPercent`), and what happens when it trips?
5. Are retries capped by a budget or `max_retries`?
6. Are overflow and ejection counters on a dashboard and alerted on?
7. Is the code-level breaker reserved for dependency-wide failure with a real fallback, so it doesn't duplicate host ejection?

## Related

[timeouts-and-retries-infra](timeouts-and-retries-infra.md),
[health-checks-and-probes](health-checks-and-probes.md) (active checks),
[bulkheads-and-isolation](bulkheads-and-isolation.md),
[`engineering-practices` reliability](../../engineering-practices/references/reliability.md).

## Sources

Envoy: [outlier detection](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/outlier),
[outlier_detection.proto](https://www.envoyproxy.io/docs/envoy/latest/api-v3/config/cluster/v3/outlier_detection.proto),
[circuit breaking](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/circuit_breaking),
[circuit_breaker.proto](https://www.envoyproxy.io/docs/envoy/latest/api-v3/config/cluster/v3/circuit_breaker.proto),
[panic threshold](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/load_balancing/panic_threshold).
Istio [DestinationRule](https://istio.io/latest/docs/reference/config/networking/destination-rule/).
Azure [Circuit Breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker).
AWS Builders' Library, [Implementing health checks](https://builder.aws.com/content/3Ev53O39izHCtWLzp4XU6t8PC1O/implementing-health-checks).
HAProxy [configuration manual](https://raw.githubusercontent.com/haproxy/haproxy/master/doc/configuration.txt).
