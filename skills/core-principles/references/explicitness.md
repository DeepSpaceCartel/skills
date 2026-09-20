# Explicitness

Make important behavior visible instead of implicit. The practical question:
**Would another engineer understand this without tribal knowledge?**

The source is PEP 20 ("Explicit is better than implicit"); Go's proverbs say
the same ("Clear is better than clever"). The rule is about behavior that
changes *correctness, cost or safety*: what the code depends on, what it does
to the world, what units and defaults it assumes, and how it can fail. A reader
should be able to discover these at the point of use.

## Where implicitness hides

| Hiding place | Cheap fix |
|---|---|
| Dependencies: globals, singletons, `now()`, env reads, service locators | Pass them as parameters or constructor arguments; read env once at the entry point and pass typed config inward |
| Side effects: I/O, mutation, network, logging | Name the function for the effect (`save_`, `send_`); separate pure computation from effects; return values instead of mutating arguments |
| Units, timezones, formats | Types (`timedelta`, `Duration`, branded types) or name suffixes (`timeout_ms`, `price_cents`) |
| Ordering and preconditions | Encode in types or builders, or assert with a message naming the requirement |
| Defaults | Make them a visible named constant; make dangerous or environment-dependent ones required arguments |
| Error paths | Put failure in the signature (`Result`, an error return, documented `raises`); never swallow errors |
| Config | Validate at startup and fail loudly; no silent fallback |
| Ownership and lifetimes | State who closes or frees; use context managers; document whether an argument is mutated or retained |
| Framework magic and reflection | Confine it to one visible seam (register routes, handlers, beans in one file) |

## The new-hire test

1. Pick a function or diff hunk.
2. List what it reads, writes, assumes and can fail on.
3. Check which of those a stranger could learn from the signature, name,
   types and adjacent lines alone.
4. Anything needing Slack history, an env var or "read the other module" is
   hidden. Fix it with the cheapest move from the table.
5. Stop when the remaining implicit items are conventions the language,
   framework or team already documents.

## Example

```python
# before: ambient clock, naive time, unit hidden, config read at import
def is_expired(token):
    return token.expires_at < datetime.now()
def fetch(url, timeout=int(os.environ.get("TIMEOUT", 30))): ...

# after: the clock, the timezone contract and the unit are visible at the call site
def is_expired(token: Token, now: datetime) -> bool:   # now: tz-aware UTC
    return token.expires_at < now
def fetch(url: str, *, timeout: timedelta) -> Response: ...  # config read once in main()
```

`is_expired` is now testable without patching the clock, and `fetch` makes no
assumption about the environment at import time. The platform-dependent
default is a real hazard: `open()` without `encoding=` varies by locale
(PEP 597), so write `encoding="utf-8"`.

## Gotchas

- **Explicit is not verbose.** Show the few facts that matter. An agent that
  adds parameters, wrappers and comments everywhere buries them.
- **Comments restating code aren't explicitness.** A comment that states a
  unit, an invariant or *why* is.
- **Don't surface what callers can't meaningfully choose.** Passing twelve
  parameters to expose internals violates `information-hiding`.
- **A documented convention counts as explicit.** Rails-style
  convention-over-configuration is explicit *by convention* when it's
  discoverable. Follow the local convention rather than spelling out everything.
- **Swallowed errors are the classic violation.** "Errors should never pass
  silently. Unless explicitly silenced." (PEP 20), with the reason stated.
- **Hidden fallbacks** (`os.environ.get("X", "prod")`) mask misconfiguration.
- **Explicitness has diminishing returns:** don't add ceremony for behavior
  that's harmless, identical everywhere and documented (`sort()` is ascending).
- **Tensions:** `information-hiding`, `kiss`, and `dry` (repeating ceremony at
  every call site means the abstraction is wrong: fix it with one visible
  seam).

## Review checklist

1. Can a new hire tell what this code reads (globals, clock, env, network) from its signature?
2. Are units, timezone and encoding visible in types or names?
3. Can every failure path be seen, and is nothing swallowed without a stated reason?
4. Are defaults harmless or visibly named, and dangerous ones required?
5. Does any side effect happen that the function name doesn't signal?
6. Does framework or reflection magic have a single discoverable registration point?

## Related

- `least-surprise` — explicitness asks "can I *see* it?"; least surprise asks "would I *predict* it?" A clearly written `getX()` that writes to disk is visible but surprising; a well-known framework default is implicit but unsurprising.
- `information-hiding` — the counterweight: hide the irrelevant, show the consequential.
- `fail-fast` — validating config at startup is explicitness applied.
