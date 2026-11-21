# Load shedding and admission control

## Problem

Past a certain load, latency climbs until most responses arrive after the client has given up.
The server is then busy doing work nobody will use: throughput stays high while goodput (useful,
timely responses) falls toward zero. Load shedding refuses some work early and cheaply so the
work it accepts still finishes in time.

## When to use / when NOT to use

- **Use** on every service that can receive more than it can serve: user-facing APIs, shared
  internal services, anything behind autoscaling (which is slower than a spike).
- **Use** at several layers: the edge, the proxy, the server process.
- **Not** instead of rate limiting. Rate limits enforce per-principal fairness at any load;
  shedding protects the service as a whole when it is full, whoever is asking.
- **Not** instead of capacity. A service that sheds every day at peak needs more capacity, not
  better shedding.

## How it works

**Admission control.** Each layer has a bounded amount of work it will hold: in-flight requests,
queued requests, connections. Beyond that, reject immediately with an overload status.

**Signal.** Shed on the resource that actually saturates. The SRE book's Handling Overload
chapter argues queries per second is a poor capacity measure because request cost varies, and
uses CPU (executor load) instead; Azure's Throttling pattern suggests p99 latency against the
SLO as the trigger, since averages look fine after the tail has breached.

**Priority.** Not all requests are equal. The SRE book's scheme tags each request with a
criticality that propagates to downstream calls and sheds the lowest first. AWS's ordering
favours load-balancer health checks first (failing them removes capacity), then human traffic
over crawlers, then finishing started work over starting new work.

**Bounded, short queues.** A queue only helps with bursts shorter than the client's timeout.
Bound its length and the time an item may wait; drop requests whose caller has already given
up. AWS prefers spillover (fail fast) to surge queues at load balancers, which it says can
cause brownouts.

**Reject cheaply.** If rejecting costs nearly as much as serving, the service still drowns.
Reject before authentication, parsing or fan-out where possible.

**Tell the caller.** 503 (or 429 when a principal is over its limit) with `Retry-After`. An
explicit "overloaded, don't retry" signal stops retries at every layer above (SRE book).

## In code / In infrastructure

**In code.** Per-request criticality, deadline checks before each stage, in-process
concurrency limits, and adaptive client-side throttling (the SRE book's accepts-vs-requests
ratio). See [`engineering-practices` reliability](../../engineering-practices/references/reliability.md).
Only the process knows its executor load and the request's remaining deadline.

**In infrastructure.** Connection and request caps at the proxy (Envoy circuit breakers,
HAProxy `maxconn` with a short `timeout queue`), connection caps at the OS, and edge limits.
These are coarse and hard to prioritize: AWS calls proxy max-connection limits a last resort.

**Agree:** the proxy's limit must sit above the server's own shedding point, so the server
sheds by priority first and the proxy only catches what the server can't. If the proxy limit
is lower, it rejects health checks and critical requests as readily as crawlers. And the
readiness probe must not fail just because the server is shedding: that removes capacity at
the worst moment (see [health-checks-and-probes](health-checks-and-probes.md)).

## Failure modes and what agents get wrong

- **Unbounded queues.** Accept queue, proxy pending queue, thread-pool queue all default large;
  each adds latency until every request times out. HAProxy's `maxqueue` defaults to 0, which
  means unlimited.
- **Shedding health checks.** The balancer sees failures, removes the instance, and the rest
  get its load. Health checks need reserved capacity.
- **Fast failures in latency metrics.** Rejected requests are fast; AWS warns they make median
  latency look better than real service. Track rejected and served latency separately.
- **No overload test.** AWS: if availability drops to zero as offered load rises, the service
  needs more shedding. Test well past the knee and check goodput stays flat.
- **Liveness tied to load.** A liveness probe that times out under load restarts busy pods,
  which turns overload into a crash loop.
- **Retrying 503s at every layer.** Each layer's retry turns one shed request into several.
- **Degraded mode never exercised.** The SRE book: unused degraded paths break; test them.

## Implementation notes

- **Envoy:** circuit breakers (`max_requests`, `max_pending_requests`) are per-cluster
  admission control; overflowed requests get `x-envoy-overloaded`. Envoy's overload manager
  can shed by the proxy's own resource use (unverified).
- **HAProxy:** server `maxconn` (in HTTP mode it caps concurrent requests), `maxqueue`
  (redispatch beyond it), `timeout queue`.
- **NGINX:** per-upstream `max_conns` (named by AWS as a last-resort limit); `limit_conn`
  (unverified).
- **Kubernetes:** keep readiness independent of shedding; scale with HPA in parallel; reserve
  headroom with an overprovisioning pod at low priority (see
  [requests-limits-and-autoscaling](requests-limits-and-autoscaling.md)).
- **Managed:** load balancers and API gateways offer request caps and spillover or 503
  behaviour; check what each does when its backend is full.

## Example

HAProxy in front of 6 API servers that each sustain 40 concurrent requests at their SLO
(measured: 400 rps per server at 100 ms). Shed at the proxy just above that, with a short queue.

```haproxy
backend api
    balance leastconn
    timeout queue 200ms                 # wait at most 200 ms for a slot, then 503
    option httpchk GET /healthz/ready
    default-server check inter 2s fall 3 rise 2 maxconn 48 maxqueue 20
    server api1 10.0.1.11:8080
    server api2 10.0.1.12:8080
    server api3 10.0.2.11:8080
    server api4 10.0.2.12:8080
    server api5 10.0.3.11:8080
    server api6 10.0.3.12:8080
```

Little's law: 400 rps x 0.1 s = 40 in flight per server; `maxconn 48` gives 20% headroom so the
servers' own priority shedding acts first. 20 queued for 200 ms covers a short burst; anything
longer gets a fast 503. `maxconn`, `maxqueue`, `timeout queue`, `fall` and `rise` are from the
HAProxy manual; `inter`, `option httpchk` and `default-server` are (unverified).

## Review checklist

1. Does every layer (edge, proxy, server, OS) have a bounded queue and a bounded number of in-flight requests?
2. Is the shed signal the resource that saturates (CPU, concurrency, p99 latency), not raw request rate?
3. Is there a request priority, propagated downstream, with health checks and critical traffic shed last?
4. Is rejection cheap and early, and does it return 503/429 with `Retry-After` or an explicit "don't retry"?
5. Is the proxy's cap above the server's own shedding point?
6. Are probes independent of shedding, so overload doesn't remove capacity?
7. Has an overload test shown goodput staying flat well past the knee?
8. Are rejected requests excluded from served-latency metrics and counted on their own?

## Related

[rate-limiting-and-throttling](rate-limiting-and-throttling.md),
[graceful-degradation-and-static-stability](graceful-degradation-and-static-stability.md),
[circuit-breaking-and-outlier-ejection](circuit-breaking-and-outlier-ejection.md),
[health-checks-and-probes](health-checks-and-probes.md),
[`engineering-practices` reliability](../../engineering-practices/references/reliability.md),
[`system-design` capacity-planning](../../system-design/references/capacity-planning.md).

## Sources

AWS Builders' Library, [Using load shedding to avoid overload](https://builder.aws.com/content/3Eun1EEyX6p2e3VYNyRLSJzLuMV/using-load-shedding-to-avoid-overload).
Google SRE book, [Handling Overload](https://sre.google/sre-book/handling-overload/) and
[Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/).
Azure [Throttling pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/throttling).
Envoy [circuit breaking](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/circuit_breaking).
HAProxy [configuration manual](https://raw.githubusercontent.com/haproxy/haproxy/master/doc/configuration.txt).
