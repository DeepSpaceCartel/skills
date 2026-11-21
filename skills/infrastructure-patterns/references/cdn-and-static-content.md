# CDN and static content

## Problem

App servers keep sending the same bytes: scripts, images, downloads, public pages. A CDN or
caching proxy serves them from the edge, even with the origin down. Misconfigured, it serves
one user's page to another, pins old assets for a year, or a purge sends every edge to the origin.

## When to use / when NOT to use

- **Use** static content hosting (object storage behind a CDN) for build outputs, media and
  downloads: it moves load off compute (Azure). Use the CDN for public, shared responses too.
- **Use** the CDN as a degradation layer: `stale-if-error` keeps public pages up through an
  origin outage ([graceful-degradation-and-static-stability](graceful-degradation-and-static-stability.md)).
- **Don't** cache per-user or personalized responses in a shared cache unless the edge checks
  access on every request, cached or not (Azure).
- **Don't** split out a handful of small files (Azure). Data inside a service is [cache-aside](cache-aside.md).

## How it works

**Cache key.** At least method and URI, plus every request header named in `Vary` (RFC 9111).
Anything else that changes the response (cookie, auth, locale, device) must be in the key, or
the response must not be shared. NGINX's default key is scheme, proxy host and request URI.

**Who may store what (RFC 9111).**

| Directive | Effect |
|---|---|
| `no-store` | No cache stores it |
| `private` | Browser may store, shared caches must not |
| `no-cache` | May store, must revalidate before every reuse |
| `max-age=N` | Fresh for N s, for every cache |
| `s-maxage=N` | Overrides `max-age` for shared caches, and implies `proxy-revalidate` there |
| `must-revalidate` | Once stale, never reused without validation; 504 if the origin is unreachable |
| `public` | Allows shared storage even for requests with `Authorization` |
| `immutable` (RFC 8246) | Don't revalidate while fresh, even on reload; for versioned URLs |
| `stale-while-revalidate=N` (RFC 5861) | Serve stale for N s past freshness while refreshing in the background |
| `stale-if-error=N` (RFC 5861) | Serve stale for N s past freshness on 500, 502, 503, 504 or no answer |

With no explicit freshness, caches may guess: a typical heuristic is 10% of the time since
`Last-Modified` (RFC 9111). Always set `Cache-Control` explicitly. A shared cache won't reuse a
response to a request carrying `Authorization` unless `public`, `s-maxage` or `must-revalidate`
allows it (RFC 9111).

**The `s-maxage` trap.** Under RFC 9111 a shared cache must not serve stale when `s-maxage` or
`proxy-revalidate` applies, so `s-maxage` silently cancels `stale-if-error` at the CDN. RFC 9213's
`CDN-Cache-Control` gives the CDN its own directives (the CDN then ignores `Cache-Control`):
browsers get a short `max-age`, the CDN a longer one plus the stale windows. How each CDN
treats the conflict varies (unverified).

**Versioned assets.** Put a content hash in the filename (`app.3f9c2e.js`), serve it with a
one-year `max-age` and `immutable`, and publish new assets *before* the pages that reference
them. Keep old versions while cached pages or a rollback still need them (Azure). HTML entry
points get a short TTL or `no-cache`.

**Purge.** Deleting or changing the origin object doesn't touch cached copies, and a CDN purge
doesn't clear browsers (Azure). Purge is for mistakes; versioned URLs are for deploys. Tag
responses with surrogate keys (one vendor's form: Fastly reads `Surrogate-Key`, purges every
object with a key, and strips the header before clients see it) to purge a group of related
objects without flushing everything.

**Origin shielding.** Edge locations send their misses to one shield location, which fetches
from the origin. The origin sees one fetch per object instead of one per edge (Fastly).

## In code / In infrastructure

**In code.** The app sets `Cache-Control` (and `Vary`) per route, from one policy table, and
never sets cookies on cacheable responses. Asset URLs come from the build manifest.

**In infrastructure.** An explicit cache key, coalesced misses, stale serving, a shield, an
origin only the CDN can reach, and storage writable only by the deploy identity (Azure).

**Agree:** one place decides TTLs per route; the app's headers and CDN overrides never contradict.

## Failure modes and what agents get wrong

- **Cookie or auth variance not in the key.** A logged-in page cached and served to everyone.
  RFC 9111 says `Set-Cookie` doesn't prevent caching; NGINX refuses to cache it by default, and
  `proxy_ignore_headers Set-Cookie` removes that protection.
- **Query strings.** Kept in the key, tracking parameters fragment the cache and anyone can
  bust it with `?x=random`; stripped, a parameter that changes the response is lost.
- **`Vary: User-Agent` or `Vary: Cookie`:** a near-unique key per client, so a near-zero hit rate.
- **Long TTLs on unversioned URLs** (`/app.js`): a fix needs a purge and waits on browsers.
  Pages deployed before their assets, or old assets deleted at deploy, break cached pages.
- **Purge-all during an incident:** every edge refetches at once. Purge by key, keep a shield.
- **`s-maxage` plus `stale-if-error`** expecting the CDN to cover an outage (above).
- **Origin reachable directly:** bypasses the CDN's caching, limits and protections (Azure).

## Implementation notes

- **NGINX:** `proxy_cache_key` (include what varies), `proxy_cache_lock on`,
  `proxy_cache_use_stale error timeout updating http_500 http_502 http_503 http_504`,
  `proxy_cache_background_update on`; it honours `stale-while-revalidate` and `stale-if-error`
  headers since 1.11.10.
- **Object storage:** set `Content-Type`, `Content-Encoding` and `Cache-Control` per object at
  upload (Azure); serve private files through short-lived signed URLs, never the public endpoint.
- **Managed:** any CDN in front of a storage bucket or an origin; check its cache-key, purge
  (by URL, prefix or tag) and shield options, and whether it honours `CDN-Cache-Control`.

## Example

A shared cache's decision for a stored response, from RFC 9111 and RFC 5861 (run on Python 3.13):

```python
def parse(cc):
    d = {}
    for part in filter(None, (p.strip() for p in cc.split(","))):
        name, _, value = part.partition("=")
        d[name.lower()] = int(value) if value.isdigit() else True
    return d

def shared_cache(cc, age, origin_ok):
    """What a shared cache may do with a stored response of this age (RFC 9111, RFC 5861)."""
    d = parse(cc)
    if "no-store" in d or "private" in d:
        return "not stored"
    fresh_for = d.get("s-maxage", d.get("max-age", 0))
    if age < fresh_for and "no-cache" not in d:
        return "fresh hit"
    if "must-revalidate" in d or "proxy-revalidate" in d or "s-maxage" in d:
        return "must revalidate (504 if origin down)"      # s-maxage implies proxy-revalidate
    stale_by = age - fresh_for
    if origin_ok:
        return "stale hit, refresh in background" if stale_by < d.get("stale-while-revalidate", 0) else "wait for origin"
    return "stale hit on error" if stale_by < d.get("stale-if-error", 0) else "pass the error"

cases = [
    ("max-age=600, stale-if-error=1200", 900, False),   # RFC 5861's example: stale 200 wins
    ("max-age=600, stale-if-error=1200", 1900, False),  # past 600 + 1200 s: error goes through
    ("max-age=600, stale-while-revalidate=30", 615, True),
    ("max-age=600, stale-while-revalidate=30", 640, True),
    ("max-age=60, s-maxage=600, stale-if-error=86400", 700, False),   # s-maxage cancels it
    ("max-age=600, stale-while-revalidate=60, stale-if-error=86400", 7200, False),  # as CDN-Cache-Control
    ("private, max-age=60", 5, True),
    ("max-age=31536000, immutable", 10**7, True),
]
for cc, age, ok in cases:
    print(f"{age:>8} s  origin {'up  ' if ok else 'down'}  {cc[:58]:58} -> {shared_cache(cc, age, ok)}")
```

Output: stale on error at 900 s, error passed at 1900 s (RFC 5861's example); background refresh
at 615 s, not 640 s; `s-maxage` forces a 504 where the same windows as `CDN-Cache-Control` serve
stale; `private` not stored. Checked against the RFC text; real CDNs add their own rules.

## Review checklist

1. Does every route set `Cache-Control` explicitly, from one policy?
2. Does the cache key include everything that changes the response, and nothing that doesn't?
3. Are personalized or authenticated responses `private` or `no-store` at the shared cache?
4. Are static assets content-hashed, `immutable`, published before pages, and kept for rollback?
5. Is there `stale-if-error` the CDN actually honours (not cancelled by `s-maxage`)?
6. Are purges by key or URL, with a shield and request coalescing to protect the origin?
7. Can the origin be reached only through the CDN?
8. Are the hit rate and origin request rate monitored, with an alert on a hit-rate drop?

## Related

[cache-aside](cache-aside.md), [graceful-degradation-and-static-stability](graceful-degradation-and-static-stability.md),
[load-shedding](load-shedding.md), [rate-limiting-and-throttling](rate-limiting-and-throttling.md),
[`engineering-practices` performance](../../engineering-practices/references/performance.md).

## Sources

IETF: [RFC 9111 HTTP Caching](https://www.rfc-editor.org/rfc/rfc9111), [RFC 5861](https://www.rfc-editor.org/rfc/rfc5861)
(stale-while-revalidate, stale-if-error), [RFC 8246](https://www.rfc-editor.org/rfc/rfc8246) (immutable),
[RFC 9213](https://www.rfc-editor.org/rfc/rfc9213) (CDN-Cache-Control). Azure Architecture Center,
[Static Content Hosting pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/static-content-hosting).
Fastly, [surrogate keys](https://www.fastly.com/documentation/guides/full-site-delivery/purging/working-with-surrogate-keys/),
[shielding](https://www.fastly.com/documentation/guides/concepts/shielding/). NGINX,
[proxy module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).
