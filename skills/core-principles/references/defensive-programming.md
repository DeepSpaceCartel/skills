# Defensive Programming

Assume boundaries and dependencies can fail. The practical question:
**What happens when input or a dependency is bad?**

It means deciding, ahead of time, what happens when input is malformed, a
dependency misbehaves or another programmer makes a mistake, so damage isn't
silent. It does not mean adding checks everywhere. McConnell (*Code Complete*,
ch. 8) frames it with **barricades**: outside a trust boundary nothing is
assumed; inside it, data is assumed clean.

## Where to be defensive, and where not

- **Be defensive at trust boundaries:** user input, HTTP bodies, files,
  env/config, rows written by others, third-party APIs, LLM output. Validate as
  early as possible, parse into a typed object, and use allowlists rather than
  denylists (validate server-side; client-side checks are not security).
- **Don't be defensive inside the barricade.** Internal calls with typed,
  already-validated data get no re-checking. Repeating a null or type check at
  every layer is what design by contract argues against.
- **Assertions vs error handling.** Use error handling for conditions you
  *expect* to occur; use assertions for conditions that should *never* occur
  (invariants, unreachable branches). Never use `assert` on anything an
  external party can trigger: Python strips it under `-O`.

## Failure-mode checklist for every dependency

For each network, disk, third-party or LLM call, decide what happens on:

1. timeout (set connect and read timeouts on *every* remote call)
2. error response
3. slow response
4. garbage or wrong-schema response
5. partial or truncated response
6. duplicate or out-of-order delivery
7. unavailable
8. unbounded response size

## Choosing the response

- **Reject:** malformed or untrusted input, or a correctness-critical value.
  Return a clear error.
- **Sanitize/normalize:** only when a canonical form is well defined, never as a
  substitute for parameterized queries or output encoding.
- **Degrade:** only as an explicit, visible fallback (a stale cache flagged as
  stale), logged and metered.
- **Retry:** only for transient errors on idempotent operations, at **one**
  layer, with backoff and jitter, and under a retry budget. Layers multiply
  (three retries at three layers is 64 attempts), and permanent errors or
  malformed requests are never retried.
- **Otherwise fail fast.**

Rule of thumb: recover only if you can name what a *correct* recovery is.

## Example

```python
# before: no timeout, and a wrong answer that looks right
def rate(cur):
    try:
        return requests.get(URL, params={"c": cur}).json()["rate"]
    except Exception:
        return 1.0

# after: bounded, validated at the boundary, and the failure is named
def rate(cur) -> Decimal:
    try:
        r = requests.get(URL, params={"c": cur}, timeout=(1, 3))
        r.raise_for_status()
        v = Decimal(str(r.json()["rate"]))
    except (requests.RequestException, KeyError, ValueError, InvalidOperation) as e:
        raise RateUnavailable(cur) from e     # caller chooses: stale cache, or fail
    if not v.is_finite() or v <= 0:
        raise RateUnavailable(cur)
    return v
```

A plausible-but-wrong `1.0` becomes a bounded call, validated data and a named
failure. Any fallback is now an explicit decision by the caller.

## Gotchas

- **Defensive is not tolerant.** `except Exception: return default` is
  suppression, not defense; it returns an inaccurate result where correctness
  matters. McConnell's split: *correctness* means never returning an inaccurate
  result, *robustness* means keeping running. Money, safety and data integrity
  favor refusing; a consumer UI may favor degrading.
- **Defending against impossible states** with an unreachable `else` that
  returns a default hides the bug; assert instead.
- **Be liberal in what you accept? Not by default.** RFC 9413 says tolerating
  faulty input entrenches errors and forces bug-for-bug compatibility.
- **Broad catches, `pass` and log-and-continue** are what agents generate; catch
  specific exceptions and translate or re-raise with context.
- **Over-defense has a cost:** dead branches, runtime and maintenance cost, and
  new defects in the defensive code itself (`kiss`, `yagni`).
- **Retry storms:** timeouts set too low, or retries at every layer, cascade
  failures.
- **Performance:** keep checks for important errors; drop trivial ones on hot
  paths.

## Review checklist

1. Is every network, disk or LLM call bounded by a timeout, with its failure path defined?
2. Is untrusted data parsed and validated once at the boundary and trusted inside?
3. Does every `catch` name specific exceptions and handle, translate or re-raise, with none swallowed?
4. Is every fallback visible (logged or metered) and semantically correct, rather than a plausible wrong value?
5. Are retries limited to idempotent, transient errors at one layer with backoff, jitter and a budget?
6. Are internal null checks or impossible branches replaced by types or asserts, and is `assert` never used on external input?

## Related

- `fail-fast` — the reconciliation: defensive programming decides *where to distrust*; fail fast decides *how to respond* when a check fails. The conflict is only with the "tolerant" reading (swallow, default, continue).
- `least-privilege` — the same mindset applied to permissions.
- `kiss` — the brake on over-defense.
