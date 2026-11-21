# Abuse, DoS and good citizenship

Two sides of the same problem. Your services must survive floods of traffic, hostile or not. Your
own crawlers, scrapers and client fleets must never look like an attack on somebody else's.
Edge rate limits and load shedding as patterns are in
[`infrastructure-patterns` rate-limiting-and-throttling](../../infrastructure-patterns/references/rate-limiting-and-throttling.md)
and [load-shedding](../../infrastructure-patterns/references/load-shedding.md); pacing a fleet
per source, 429 handling and cooldowns are in
[`data-pipelines` failure-isolation](../../data-pipelines/references/failure-isolation.md). This
page covers the system-level defence and the outbound conduct. Anchor sources:
[BSRS ch. 10, Mitigating Denial-of-Service Attacks](https://google.github.io/building-secure-and-reliable-systems/raw/ch10.html),
[RFC 9309, Robots Exclusion Protocol](https://www.rfc-editor.org/rfc/rfc9309), and
[RFC 9110](https://www.rfc-editor.org/rfc/rfc9110) sections 10.1.2 (From) and 10.1.5 (User-Agent).

## What agents typically get wrong

- **A robots.txt parser that misses rules.** No `*` or `$` support, first-match instead of
  longest-match, or the full browser-style User-Agent string passed where the product token
  belongs, so the bot's own group never matches.
- **robots.txt served as HTML read as "no rules".** A 200 with an HTML page (a soft 404, or the
  rules wrapped in `<pre>`) parses to nothing, and nothing means allow all.
- **Redirects not followed.** `http` to `https` or apex to `www` returns a 3xx; the crawler treats
  it like a 4xx and crawls everything. RFC 9309 says to follow at least five, across hosts too.
- **Errors read as permission.** A timeout or 5xx on robots.txt means assume complete disallow,
  not "couldn't check, carry on".
- **An anonymous client.** A default library User-Agent, or worse, a browser's, with no page
  that says who you are or how to make you stop. Site operators who can't identify you report
  you instead.
- **Visiting sensitive sectors at all.** One ordinary fetch to a bank, hospital or government
  site can be logged by its security team as an attack and reported to your hosting provider.
- **Treating a block or a challenge as a bug to work around.** It is the operator saying no.
- **Abuse reports with no owner.** The report goes to an unread inbox; the provider suspends the
  account or null-routes the IP before anyone answers.
- **For your own services: blocking the obvious attack signature,** which teaches the attacker
  what to change (BSRS ch. 10).

## Procedure

**Your own fleet as a good citizen** (synthesis; RFC rules noted):

1. **Identify yourself.** A User-Agent with your product token and a URL, e.g.
   `ExampleBot/1.2 (+https://example.org/bot)`. RFC 9110: a robotic agent should send `From` with
   a contact mailbox; don't claim other products' tokens. RFC 9309: the product token (letters,
   `_`, `-`) should appear in the User-Agent.
2. **Publish a bot page:** what you fetch and why, how to opt out (robots token, an email, a
   form), the contact for abuse, and your egress IP ranges. Make the IPs verifiable: a reverse DNS
   name under your domain that resolves forward to the same IP, or a published range file, as
   Google does for its crawlers.
3. **Honour robots.txt per RFC 9309** (edge cases below), cache it no longer than 24 hours, and
   re-check before each crawl cycle. RFC 9309 defines no rate directive; treat a `Crawl-delay`
   line, when present, as an extra limit.
4. **Keep politeness limits per target host** (and per shared provider), with concurrency 1 by
   default, backoff on 429 and 503, and a global ceiling. The mechanics are in `data-pipelines`.
5. **Keep an opt-out list** checked before every fetch, keyed by domain and by IP range. Adding to
   it takes effect within minutes, needs no deploy, and never expires on its own.
6. **Exclude sensitive sectors by default:** banks and payment firms, healthcare, government,
   defence, critical infrastructure, and anything whose security team treats any unknown client as
   hostile. Allow them only with a reason recorded and, ideally, the operator's consent.
7. **Treat blocks as opt-outs.** A firewall block page, a bot challenge or a steady 403 stops
   that host and files it for review. Don't rotate IPs, spoof a browser or solve challenges to get
   past it.
8. **Own abuse reports** (below). Your hosting account and IP reputation depend on it.

**Your own services under DoS** (BSRS ch. 10):

1. **Rank the weak links** in the request path (DNS, network, load balancer, frontends, the
   expensive backend calls) by how little traffic it takes to hurt each.
2. **Filter in layers, early:** edge ACLs for volumetric floods, network load balancing for packet
   floods, application-layer checks for expensive requests. Shared edge defences cover many
   services at once. Avoid stateful firewalls on the inbound path; idle connections exhaust them.
3. **Make requests cheaper:** caching proxies, fewer requests per page, rate limits on large
   responses. Fail expensive requests early.
4. **Monitor request rates beside CPU and memory;** page when demand exceeds capacity and the
   automatic defences have engaged.
5. **Degrade on purpose:** read-only mode, reduced search, priority for critical traffic.
6. **Keep the mitigation system independent** of what it protects, canary its rule changes, and
   have it hold the last policy if its controller fails.
7. **Challenge the whole suspicious population** rather than blocking one signature, so variants
   are caught too.
8. **Plan for self-inflicted surges:** synchronized clients, a news event, or a retry storm from
   your own apps. Clients back off with jitter; the server answers what it can, so clients leave
   their retry loops (BSRS ch. 10).

## Techniques

**robots.txt fetch outcomes** (RFC 9309 section 2.3.1, with this skill's stricter choices marked):

| Result | RFC 9309 | This skill |
|---|---|---|
| 200, `text/plain`, parses | Follow the rules | Same |
| 200 but HTML, or not `text/plain` | Parse what parses (often nothing) | **Unknown: don't crawl, flag the host** |
| 3xx | Follow at least 5 hops, across hosts; rules apply to the original host | Same; still redirecting after 5 is **unknown** (RFC permits allow-all) |
| 404, 410 and other 4xx | Unavailable: may crawl anything | Same |
| 401, 403 | Unavailable | **Disallow all** (a refusal) |
| 429 | Unavailable | **Disallow all and back off** |
| 5xx, timeout, DNS or TLS error | Unreachable: assume complete disallow | Same; never "carry on" |
| Unreachable for a long time (RFC's example: 30 days) | May use a cached copy or treat as unavailable | Keep the cached copy |

**Matching rules** (RFC 9309 section 2.2): user-agent matching is case-insensitive on the product
token; several groups for the same token merge; the `*` group applies only when no group
matches; the longest matching path wins and an equal allow beats disallow; `*` matches any run
of characters and `$` anchors the end; `/robots.txt` is always allowed; parse at least 500 KiB.
The RFC states plainly that robots.txt is not access authorization: honouring it is the floor,
not proof you're welcome.

**Abuse-report handling** (synthesis):

| Step | Within |
|---|---|
| Acknowledge the reporter; add their domain and IPs to the opt-out list | 1 business hour |
| Stop the fleet's traffic to them; confirm from your own logs | same day |
| Reply with what you fetched, when, from which IPs, and that it has stopped | 1 business day |
| Answer the hosting provider's ticket with the same facts | before its deadline |
| Fix the root cause (a missing sector rule, a parser bug) and add a test | next sprint |

**IP reputation** (synthesis). Abuse reports land on whoever owns the IP. On a cloud or hosting
provider that is your account: enough reports can mean suspended instances, a null-routed IP or
a closed account, which takes down everything else on it. Run crawl egress from dedicated,
published IPs, separate from the account and addresses that serve your product, so a reputation
hit doesn't become an outage of your main service.

## Example

A robots.txt fetch classifier and a conformance set to run against whatever parser you ship. All
cases are local strings; nothing is fetched.

```python
import urllib.robotparser
TOKEN = "ExampleBot"          # the product token, not the full User-Agent string

def outcome(status, content_type, body):
    """Final response after following up to 5 redirects (rules apply to the original host).
    status None means timeout or network error."""
    if status is None or 500 <= status <= 599:
        return "disallow-all"                       # RFC: unreachable
    if status in (401, 403, 429):
        return "disallow-all"                       # stricter than the RFC
    if 300 <= status <= 399:
        return "unknown"                            # still redirecting after 5 hops
    if 400 <= status <= 499:
        return "allow-all"                          # RFC: unavailable
    if status == 200:
        html = body.lstrip()[:15].lower().startswith(("<!doctype", "<html"))
        return "unknown" if html or not content_type.startswith("text/plain") else "rules"
    return "unknown"

def allowed(robots_txt, path, agent=TOKEN):
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots_txt.splitlines()); rp.modified()
    return rp.can_fetch(agent, "https://example.org" + path)

CONFORMANCE = [               # fail the build on any mismatch
    ("* wildcard", "User-agent: *\nDisallow: /*.pdf$\n", "/a/b.pdf", False),
    ("$ anchor", "User-agent: *\nDisallow: /*.pdf$\n", "/a/b.pdf?x=1", True),
    ("longest match", "User-agent: *\nDisallow: /shop\nAllow: /shop/public\n", "/shop/public/x", True),
    ("tie -> allow", "User-agent: *\nDisallow: /p\nAllow: /p\n", "/p", True),
    ("groups merge", "User-agent: examplebot\nDisallow: /a\n\nUser-agent: ExampleBot\nDisallow: /b\n", "/b", False),
    ("own group wins", "User-agent: *\nDisallow: /\n\nUser-agent: examplebot\nAllow: /\n", "/x", True),
    ("robots.txt free", "User-agent: *\nDisallow: /\n", "/robots.txt", True),
]
assert not [n for n, txt, p, want in CONFORMANCE if allowed(txt, p) != want]
```

Run on Python 3.13: all seven conformance cases passed. The classifier returned `unknown` for an
HTML 200, `disallow-all` for 503, a timeout, 403 and 429, `allow-all` for 404, `unknown` for a
final 3xx, and `rules` for `text/plain`; redirect following itself was not exercised. Two traps showed up: the same parser
fed the HTML-wrapped `Disallow: /` allowed `/x`, which is why the classifier must run first; and
with `User-agent: examplebot / Disallow: /` plus an open `*` group, passing the full string
`Mozilla/5.0 (compatible; ExampleBot/1.2; ...)` allowed `/x`, while passing `ExampleBot` denied
it. Older parser versions may fail the wildcard or longest-match cases; the conformance set is
how you find out.

## Gotchas and contested points

- **401 and 403 on robots.txt** are "unavailable" (crawl allowed) in RFC 9309, but some parsers
  and many operators read them as disallow. The conservative reading costs you little.
- **robots.txt is public.** It lists paths operators would rather hide; never use disallowed paths
  as a discovery list (RFC 9309 section 3), and treat its contents as untrusted input.
- **Sector exclusion lists are never complete.** Combine a curated list with signals: a security
  vendor's block page, a CERT contact in the site's `security.txt`, a bank or government domain
  suffix.
- **Polite is not the same as permitted.** Terms of service, logins and paywalls are separate
  questions; robots.txt doesn't answer them.
- **DoS defences hit shared IPs** (offices, carriers); BSRS ch. 10 uses challenge-bypass cookies.

## Review checklist

1. Does the fleet send a User-Agent with its own product token and a bot-page URL, plus `From`,
   and never a browser's or another crawler's token?
2. Does the bot page give purpose, opt-out, abuse contact and verifiable egress IPs?
3. Does the robots.txt handling follow redirects (at least 5, across hosts), treat 5xx and
   timeouts as full disallow, and refuse to read an HTML 200 as "no rules"?
4. Does the parser pass a conformance set covering `*`, `$`, longest match, ties, group merging
   and the bot's own group matched by product token?
5. Is there an opt-out list checked before every fetch, effective within minutes without a
   deploy?
6. Are sensitive sectors excluded by default, and are blocks and challenges treated as opt-outs,
   never worked around?
7. Does every abuse report have an owner and a same-day stop, and does crawl egress use IPs and an
   account separate from the product's?
8. For your own services: are defences layered from the edge in, independent of what they
   protect, and is a self-inflicted surge or retry storm in the plan?

## Related

[`data-pipelines` failure-isolation](../../data-pipelines/references/failure-isolation.md)
(per-source pacing), [`infrastructure-patterns` rate-limiting-and-throttling](../../infrastructure-patterns/references/rate-limiting-and-throttling.md)
and [load-shedding](../../infrastructure-patterns/references/load-shedding.md),
[`engineering-practices` reliability](../../engineering-practices/references/reliability.md)
(client retries with jitter), [compromise-recovery-and-forensics](compromise-recovery-and-forensics.md).

## Sources

[BSRS ch. 10](https://google.github.io/building-secure-and-reliable-systems/raw/ch10.html),
paraphrased; [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309); [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.txt)
sections 10.1.2 and 10.1.5; Google Search Central,
[Verifying Googlebot](https://developers.google.com/search/docs/crawling-indexing/verifying-googlebot)
(reverse and forward DNS, published IP ranges). The stricter robots outcomes, sector exclusions,
abuse-report timings and IP-reputation advice are this skill's synthesis, not sourced. The
`security.txt` suggestion (RFC 9116) was not fetched (unverified).
