# Load balancing

## Problem

Replicas help only if traffic reaches them in proportion to what each can do. Backends differ:
slower, just started, busy with a long request, returning fast errors. Even requests are not
even *load*. Long-lived connections (HTTP/2, gRPC, WebSockets) pin a client's work to whichever
pod an L4 balancer picked. Which balancer sits at which hop is
[`system-design` scaling-and-failure-domains](../../system-design/references/scaling-and-failure-domains.md);
this is how each behaves and how to configure it.

## When to use / when NOT to use

- **L4 (connection) balancing:** any TCP service; cheap; the default for Kubernetes Services.
  Enough when connections are short or many per client.
- **L7 (request) balancing:** HTTP/2 and gRPC, uneven request costs, retries, per-route policy.
  gRPC's docs: an L7 balancer can spread one client's streams across backends.
- **Consistent hashing:** only when the same key should reach the same backend (a cache shard,
  per-key state). It trades evenness for locality.
- **Session affinity:** last resort for in-memory state; a shared store beats affinity (Azure).

## How it works

**Algorithms.**

| Algorithm | Picks | Good at | Weak at |
|---|---|---|---|
| Round robin (weighted) | Next in order, by weight | Identical backends, uniform requests | Slow or heterogeneous backends: CPU can differ about 2x (SRE book ch. 20) |
| Random | Uniform random | No health checks configured (Envoy); no bias after a failed host | Same as round robin |
| Least request / least connections | Fewest active requests | Uneven request cost, slow backends | Fast errors look idle: a failing host attracts traffic (SRE "sinkhole") |
| Power of two choices (P2C) | Fewest active of 2 random picks | Near least-request quality with no global scan; Envoy's default least-request mode | Each client sees only its own requests (SRE) |
| Weighted by reported load | Weight from backend's utilization, QPS, errors | Mixed hardware; Envoy client-side WRR uses ORCA reports | Needs backends to report |
| Ring hash | Nearest host clockwise from the key's hash | Adding or removing 1 of N hosts moves about 1/N of keys (Envoy) | Uneven unless ring size is tuned; hot keys |
| Maglev | Lookup table (65537 entries by default) | Faster to build and pick than ring hash (Envoy) | About double the key movement when hosts are removed (Envoy) |

Envoy's least request with unequal weights uses `weight / (active_requests + 1)^bias`, bias 1.0
by default; with equal weights it is P2C. Counting recent errors as active requests stops the
sinkhole (SRE book). Pair balancing with
[circuit-breaking-and-outlier-ejection](circuit-breaking-and-outlier-ejection.md).

**Slow start.** A new or just-recovered pod gets a fraction of its share that rises over a
window: Envoy's `slow_start_window`, weight scaled by `max(min_weight_percent, t^(1/aggression))`,
floor 10% by default, linear at aggression 1.0. It works for a few new hosts among many; when
every host is new (a fresh deploy) they all ramp together and gain nothing (Envoy).

**Draining.** A backend leaving the pool stops receiving new requests and finishes in-flight
ones (the SRE book's lame-duck state). In Kubernetes that is readiness, preStop and the grace
period, and GOAWAY for HTTP/2: see [disruption-budgets-and-safe-rollouts](disruption-budgets-and-safe-rollouts.md).
Removing a node from a cloud LB's backend set ends its connections immediately; a failing
health check first allows draining (Kubernetes virtual IPs docs).

**Long-lived connections.** HTTP/2 multiplexes every request over one long-lived connection,
so connection-level balancing pins all of a client's requests to one pod (Kubernetes blog,
2018). Fixes: an L7 proxy or mesh sidecar that balances per request; or a headless Service
(DNS returns pod IPs) with a client that balances itself and re-resolves; and a server-side
maximum connection age (gRPC `MAX_CONNECTION_AGE`, off by default) so clients reconnect and
rebalance after scale-out. WebSockets can't be rebalanced per message: cap connections per pod
and shed or redirect new ones instead.

**Session affinity.** Kubernetes `sessionAffinity: ClientIP` (default `None`) pins by source IP
for up to 10800 s by default. Costs: uneven load (many users behind one NAT), a hot pod that
can't shed, and sessions lost anyway when the pod goes. Cookie affinity at L7 is finer but the
same trade.

## In code / In infrastructure

**In code.** A client-side balancer (gRPC `round_robin` over a headless Service, or a lookaside
balancer) avoids an extra hop, but every language's client must implement it and clients must
be trusted (gRPC docs). Report load (utilization, errors) if the balancer can use it.

**In infrastructure.**

| Layer | What it balances | Notes |
|---|---|---|
| kube-proxy (ClusterIP) | Connections, L4 | iptables mode picks a backend at random; IPVS (deprecated since 1.35) offers rr, lc, sh, mh and others; nftables is the recommended successor |
| `trafficDistribution` | Preference, not guarantee | `PreferSameZone`, `PreferSameNode`; `Local` traffic policies take precedence |
| Headless Service | Nothing: DNS returns pod IPs | Client or sidecar balances |
| Ingress / Gateway API | Requests, L7 | `HTTPRoute` and `GRPCRoute`; header matching and traffic weighting without annotations |
| Mesh sidecar (Envoy) | Requests, L7 | Least request, slow start, outlier ejection, per-route policy |

**Agree:** the hop that balances per request also owns retries and ejection for that path
([timeouts-and-retries-infra](timeouts-and-retries-infra.md)).

## Failure modes and what agents get wrong

- **Scaling out a gRPC service behind a ClusterIP** and seeing the new pods idle.
- **Round robin with one slow node:** its queue grows without bound (example).
- **Least request with fast-failing hosts:** the broken pod gets the most traffic.
- **Affinity "for performance"** that turns one popular tenant into one hot pod.
- **Slow start expected to protect a full redeploy.** It only helps a few new hosts at a time.
- **Ring hash with default sizes:** Envoy says set min and max ring size and watch the spread.
- **`PreferSameZone` with unequal zones** overloads the small zone (Kubernetes docs).
- **Removing backends before draining:** connections reset on every deploy.

## Implementation notes

- **Envoy:** least request (P2C over 2 random hosts by default), ring hash, Maglev, slow start
  per cluster. Istio's `DestinationRule` exposes them (field names unverified here).
- **NGINX** `least_conn`, `hash ... consistent`; **HAProxy** `leastconn` (unverified here).
- **Managed:** cloud L4 network load balancers and L7 application load balancers fill the same
  roles; check what they balance (connections or requests) and how they drain.

## Example

Ten backends, one at half speed, offered load about 84% of capacity (run on Python 3.13):

```python
import itertools, random

def simulate(pick, ticks=20_000, seed=1):
    """10 backends, one at half speed; arrivals at ~85% of total capacity."""
    rng = random.Random(seed)
    speed = [1.0] * 9 + [0.5]                      # requests finished per tick
    queue = [0.0] * 10
    peak = [0.0] * 10
    for _ in range(ticks):
        for _ in range(rng.choices([7, 8, 9], k=1)[0]):       # ~8 arrivals per tick
            i = pick(queue, rng)
            queue[i] += 1
        for i in range(10):
            queue[i] = max(0.0, queue[i] - speed[i])
            peak[i] = max(peak[i], queue[i])
    return max(peak), round(sum(queue), 1)

rr = itertools.cycle(range(10))
policies = {
    "round robin": lambda q, r: next(rr),
    "random": lambda q, r: r.randrange(10),
    "least request, P2C": lambda q, r: min(r.sample(range(10), 2), key=q.__getitem__),
    "least request, all": lambda q, r: min(range(10), key=q.__getitem__),
}
for name, pick in policies.items():
    worst, backlog = simulate(pick)
    print(f"{name:20} worst queue {worst:7.1f}   backlog at end {backlog}")
```

Output: round robin and random let the slow backend's queue reach about 6000 (it gets a tenth of
the traffic, can serve a twentieth); P2C keeps the worst queue at 3.5, global least request at 0.
Real clients see only their own requests, so they land between P2C and that ideal.

## Review checklist

1. Is each hop's balancer named, with whether it balances connections or requests?
2. Do HTTP/2, gRPC and WebSocket services get per-request balancing or a max connection age?
3. Is the algorithm load-aware (least request or P2C) where request cost or backend speed varies?
4. Are fast errors counted as load, or ejected, so a failing host can't become a sinkhole?
5. Do new pods ramp in (slow start or readiness warm-up), and do leaving pods drain first?
6. Is session affinity justified, with its timeout and hot-spot cost written down?
7. For consistent hashing: is the ring or table sized, and are hot keys handled?
8. Is per-backend load (requests, latency, errors) visible so imbalance shows up?

## Related

[`system-design` scaling-and-failure-domains](../../system-design/references/scaling-and-failure-domains.md),
[disruption-budgets-and-safe-rollouts](disruption-budgets-and-safe-rollouts.md),
[circuit-breaking-and-outlier-ejection](circuit-breaking-and-outlier-ejection.md),
[health-checks-and-probes](health-checks-and-probes.md), [sharding](sharding.md) (consistent
hashing for data), [cells-and-shuffle-sharding](cells-and-shuffle-sharding.md).

## Sources

Envoy: [load balancers](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/load_balancing/load_balancers),
[slow start](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/load_balancing/slow_start).
Google SRE book: [Load Balancing in the Datacenter](https://sre.google/sre-book/load-balancing-datacenter/),
[Load Balancing at the Frontend](https://sre.google/sre-book/load-balancing-frontend/).
Kubernetes: [Service](https://kubernetes.io/docs/concepts/services-networking/service/),
[Virtual IPs and Service proxies](https://kubernetes.io/docs/reference/networking/virtual-ips/),
[Gateway API](https://kubernetes.io/docs/concepts/services-networking/gateway/),
[gRPC load balancing on Kubernetes](https://kubernetes.io/blog/2018/11/07/grpc-load-balancing-on-kubernetes-without-tears/).
gRPC: [load balancing](https://grpc.io/blog/grpc-load-balancing/), [keepalive](https://grpc.io/docs/guides/keepalive/).
