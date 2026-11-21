# Cache-aside and caching strategies

## Problem

A cache in front of a store cuts latency and load for repeated reads, but adds a copy that can
be stale, a system that can fail, and a new way to overload the store: a hot key expires, or the
cache restarts empty, and every request hits the store at once. *Whether* to cache is
[`engineering-practices` performance](../../engineering-practices/references/performance.md)
(measure first; invalidation rule, size bound, hit rate). This is the mechanics after a yes.

## When to use / when NOT to use

- **Use** for read-heavy data reused across requests that tolerates some staleness (Azure; AWS).
  Cache-aside fits when the cache has no read-through support, or demand is unpredictable (Azure).
- **Don't** when most requests miss: the check-and-fill overhead outweighs the benefit (Azure).
- **Don't** for sensitive data in a shared cache (Azure), or reads that must see the latest
  write (a balance before a debit). A fully static data set is primed at startup instead (Azure).

## How it works

| Strategy | Read | Write | Stale window | Cost |
|---|---|---|---|---|
| Cache-aside (side cache) | App reads cache; on a miss reads store, then fills cache | App writes store, then deletes the key | Until the next miss after the delete, or TTL | Caching logic in every caller |
| Read-through (inline) | Cache library or proxy loads on a miss | Separate | TTL | A cache outage looks like a store outage (AWS) |
| Write-through | As read-through | Store and cache updated in one operation | Near zero after a successful write (Azure) | Every write pays two writes |
| Write-behind | As read-through | Cache acknowledges, store written later | None in cache; store lags | Writes lost if the cache dies first |

**Invalidate on write, in this order:** update the store, *then* delete the cache key. Delete
first and a reader can miss, load the old row and put it back before the store changes (Azure).
Delete rather than set: two writers that each set the cache can finish in the opposite order to
their store commits. Even store-then-delete leaves a race: reader misses and reads the old row,
writer commits and deletes, reader then sets the old value (delete-vs-set and this race are
this skill's reasoning). A TTL bounds every such race; keep one on every key.

**TTL.** From staleness tolerance and change rate (AWS); too short wastes the cache, too long
serves old data (Azure). Add jitter so keys filled together don't expire together. AWS's soft
TTL triggers a refresh; the hard TTL bounds how long the old value is served if it fails.

**Stampede (thundering herd) protection.** Many requests miss one key at once (AWS).

| Technique | How | Scope |
|---|---|---|
| Request coalescing (single-flight) | One load per key in flight; other callers wait for it (AWS; NGINX `proxy_cache_lock`) | Per process, unless built on a shared lease |
| Shared lease | `SET lock:<key> <token> NX PX <ms>`; the winner loads; losers wait, retry or serve stale | Fleet-wide |
| memcached meta protocol | On a miss with `N` (vivify), one client gets `W` (won the recache), others get `Z`; `R` grants an early recache below a TTL threshold | Fleet-wide |
| Serve stale while refreshing | Return the old value; one background refresh (NGINX `proxy_cache_use_stale updating`) | Per cache |
| Probabilistic early expiry (XFetch) | Refresh when `now - delta * beta * ln(rand) >= expiry`; `delta` = recompute time, `beta` defaults to 1 | Per request, no coordination |

Vattani et al. prove the exponential rule optimal when the request rate is unknown; `beta = 1`
needs no tuning. Redis discourages the `SET NX` lock for mutual exclusion; a lost cache-fill lease
only costs a duplicate load, so it's fine here, released by a compare-token script, not `DEL`.

**Negative caching.** Cache "not found" and errors with a shorter TTL of their own, or a missing
key is fetched on every request and amplifies outages (AWS).

**Cold cache.** A new instance, a deploy flush, or a cache restart or failover bursts the store
(AWS): warm up first, cap the miss rate or shed, and test with caching disabled (AWS).

## In code / In infrastructure

**In code.** One module owns keys, TTLs, serialization and invalidation. Version cached formats,
since old and new code read each other's entries mid-deploy (AWS). A cache error is a miss.

**In infrastructure.** A shared cache with a memory limit and an eviction policy; replicas if a
cold restart would overload the store; metrics for hits, misses, evictions and store load.

**Agree:** size the store, its pool and its rate limit for the miss rate after a cold restart.

## Failure modes and what agents get wrong

- **No TTL, "we invalidate on write".** One missed path (migration, admin script, another
  service) and the entry is wrong forever (Azure: external writers).
- **Delete-then-write,** or set-on-write from several writers: stale values that stick.
- **Coalescing only in-process:** 200 pods each send one load, still 200 queries.
- **Local caches on many replicas:** copies disagree and store load grows with fleet size
  (Azure; AWS). Use short TTLs or a shared cache.
- **Redis's default `maxmemory` 0** (no limit on 64-bit): the host runs out instead of evicting.
- **`volatile-*` with keys lacking a TTL:** behaves like `noeviction`; writes fail when full.
- **Cache keys missing a dimension** (tenant, locale, permission): one user's data served to another.

## Implementation notes

- **Redis / Valkey:** set `maxmemory` below RAM, leaving room for replication and AOF buffers
  (not counted toward it); `allkeys-lru` is Redis's suggested default; separate instances for
  cache and persistent keys. Hit rate from `INFO stats` (`keyspace_hits`, `keyspace_misses`);
  watch `evicted_keys`, `expired_keys`. Valkey documents the same directive and LRU/LFU policies.
- **memcached:** meta commands (`mg` with `N`, `R`; `md <key> I` marks stale) give fleet-wide
  win/lose recache without a separate lock.
- **NGINX:** `proxy_cache_lock on` (default off; after the 5 s lock timeout the request passes
  through uncached), `proxy_cache_use_stale updating`, `proxy_cache_background_update on`.
- **Managed:** managed Redis/Valkey or memcached; inline caches play the read-through role (AWS).

## Example

Per-key single-flight plus XFetch, standard library only (run on Python 3.13):

```python
import math, random, threading, time

class Cache:  # cache-aside with per-key single-flight and XFetch early refresh
    def __init__(self, loader, ttl, beta=1.0, now=time.monotonic):
        self.loader, self.ttl, self.beta, self.now = loader, ttl, beta, now
        self.data, self.locks, self.guard = {}, {}, threading.Lock()  # key -> (value, delta, expiry)

    def fresh(self, entry):  # XFetch: refresh early, more likely as expiry nears
        return entry and self.now() - entry[1] * self.beta * math.log(1 - random.random()) < entry[2]

    def get(self, key):
        if self.fresh(self.data.get(key)):
            return self.data[key][0]
        with self.guard:
            lock = self.locks.setdefault(key, threading.Lock())
        with lock:                                   # one load per key per process
            if self.fresh(self.data.get(key)):       # refreshed while we waited
                return self.data[key][0]
            start = self.now(); value = self.loader(key)
            self.data[key] = (value, self.now() - start, self.now() + self.ttl)
            return value

calls = 0
def slow_query(key):
    global calls; calls += 1; time.sleep(0.05); return f"value of {key}"
naive = {}
def naive_get(key):
    if key not in naive: naive[key] = slow_query(key)

for name, get in [("naive", naive_get), ("single-flight", Cache(slow_query, ttl=60).get)]:
    calls = 0; ts = [threading.Thread(target=get, args=("report:42",)) for _ in range(50)]
    [t.start() for t in ts]; [t.join() for t in ts]
    print(f"{name}: {calls} load(s) for 50 concurrent misses")

random.seed(7); clock = [0.0]                        # XFetch on a simulated clock
c = Cache(None, ttl=10.0, now=lambda: clock[0]); c.data["hot"] = ("v", 0.5, 10.0)
refreshes = late = 0
for ms in range(60_000):                             # a read every 1 ms for 60 s
    clock[0] = ms / 1000; late += clock[0] >= c.data["hot"][2]
    if not c.fresh(c.data["hot"]):                   # recompute takes 0.5 s
        refreshes += 1; c.data["hot"] = ("v", 0.5, clock[0] + 0.5 + c.ttl)
print(f"xfetch: {refreshes} refreshes in 60 s, {late} reads past expiry")
```

Run output: naive 50 loads, single-flight 1, XFetch 8 refreshes in 60 s (a 10 s TTL needs at
least 6) and 0 reads past expiry. In a fleet, swap the in-process lock for a shared lease.

## Review checklist

1. Was the cache justified by a measurement, and does every key have a jittered TTL?
2. Does every write path update the store first, then delete the key (not set it)?
3. Is there stampede protection that works across replicas (lease, meta protocol, or early expiry)?
4. Are misses and errors cached with their own shorter TTL, and can the store survive a cold cache at peak?
5. Is `maxmemory` set, with an eviction policy that matches whether keys have TTLs?
6. Do cache keys include every dimension that changes the answer (tenant, locale, permission)?
7. Are hit rate, evictions and store load on a dashboard, and cached formats versioned?

## Related

[`engineering-practices` performance](../../engineering-practices/references/performance.md)
(whether to cache), [cdn-and-static-content](cdn-and-static-content.md) (the HTTP layer),
[read-replicas](read-replicas.md), [cqrs-and-materialized-views](cqrs-and-materialized-views.md)
(precomputed reads), [graceful-degradation-and-static-stability](graceful-degradation-and-static-stability.md)
(serving stale on failure), [load-shedding](load-shedding.md) (protecting the store).

## Sources

Azure Architecture Center, [Cache-Aside pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside).
AWS Builders' Library, [Caching challenges and strategies](https://builder.aws.com/content/3K9TeXp6strMiJ4vhakpRD7BQWO/caching-challenges-and-strategies).
Vattani, Chierichetti, Lowenstein, [Optimal Probabilistic Cache Stampede Prevention](https://www.vldb.org/pvldb/vol8/p886-vattani.pdf) (VLDB 2015).
Redis, [key eviction](https://redis.io/docs/latest/develop/reference/eviction/), [SET](https://redis.io/docs/latest/commands/set/).
Valkey, [LRU cache](https://valkey.io/topics/lru-cache/). memcached, [meta protocol](https://docs.memcached.org/protocols/meta/).
NGINX, [proxy module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).
