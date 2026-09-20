# Fail Fast

Detect invalid conditions as early as possible and stop loudly. The practical
question: **Can this error be caught at the boundary?**

Jim Shore ([Fail Fast, IEEE Software 2004](https://martinfowler.com/ieeeSoftware/failFast.pdf)):
some code tries to be robust "by working around problems automatically",
which is failing *slowly*: the defect surfaces far away, in strange ways.
Fail-fast code fails "immediately and visibly", which makes bugs easier to
find and fix. Hunt & Thomas put it as "Crash Early": a dead program does much
less damage than a crippled one.

## Where to check

- **Process start:** config, env, secrets, connectivity, schema versions.
  Verify all of it before serving traffic and refuse to start with a specific
  message.
- **Request or input edge:** parse into a typed object and reject with a 4xx
  ("parse, don't validate": get data into the most precise representation
  you need, at the boundary, before anything acts on it).
- **A module's public API:** preconditions on arguments. Shore: assertions
  belong at the seams between components, not in every method.
- **Deserialization and I/O edges.**

After the boundary, pass precise types and don't re-check.

## Bug or expected failure?

Ask *could a correct program ever see this?*

- **No** (invariant violated, impossible state, programmer error): assert or
  raise loudly.
- **Yes** (bad user input, a timeout, a missing file the user named, a 404):
  handle it with a specific, typed response, an explicit retry or an
  explicit degrade. That's ordinary error handling, not a violation.

## What a good failure looks like

- Raised at the earliest point the problem can be named.
- States the expectation and the offending value, and the source:
  `maxConnections must be an int in [1,500], got "abc" (from /etc/app.toml)`.
  Don't just restate the condition.
- Stops the current unit of work (request, batch item), and no more.
- Is never swallowed downstream. Keep the cause chain when re-raising.

## Example

```ts
// before: every bad input becomes a plausible number
const limit = Number(req.query.limit) || 50;   // "abc" -> 50, "-5" -> -5, "0" -> 50
const rows = await db.page(userId, limit);

// after: absent gets a documented default; malformed is rejected at the edge
const limit = parseLimit(req.query.limit);
function parseLimit(raw: unknown): number {
  if (raw === undefined) return 50;
  const n = Number(raw);
  if (!Number.isInteger(n) || n < 1 || n > 500)
    throw new BadRequest(`limit must be an integer in [1,500], got ${JSON.stringify(raw)}`);
  return n;
}
```

The fix separates *absent* (a documented default) from *malformed* (a client
bug that gets a 400 naming the value), and it fails the request, not the
process.

## Anti-patterns (agents produce these by default)

- `except Exception: log(...); continue` or `return None` / `[]` / `0` on error
- `os.getenv("X", "localhost")` or `int(x or 50)` on *required* config
- `.get(key, default)` and `??` fallbacks on data that must be present
- Optional chaining on values that should never be null
- Logging an error and returning normally (a success-shaped result on a
  failure path)
- Catch-all handlers deep in the code, which stop errors reaching the one
  place that reports them
- Validation scattered through business logic

The test for a fallback: can the caller still tell "no result" from "the call
failed"? A documented `parse_int -> None` is a contract; a fetch that maps 404,
500 and network errors all to `None` is a cover-up.

## Gotchas

- **Fail the request, not the process** in a long-running service: one global
  handler reports the error and continues with the next item. Crash the whole
  process only with isolation and a supervisor.
- **Over-correction is a misreading.** Don't crash on user input or on
  recoverable runtime failures (a timeout, an unavailable dependency).
- **Fallbacks are allowed when deliberate.** Optional features may degrade
  (a cached value marked stale), as a documented, observable decision (log or
  metric), never silently.
- **Availability- or safety-critical systems** may need to continue or enter a
  safe state; that choice is a product decision.
- **Lenient parsing of a public interop format** may be forced by legacy
  clients (Postel), a real tension with strictness.
- **Don't build correctness on a detector.** Fail-fast iterators are
  best-effort, meant to find bugs.

## Review checklist

1. Is every external input parsed into a typed value at the boundary, with later code not re-checking?
2. Does startup verify required config, secrets and dependencies and refuse to run with a clear message?
3. Can any `catch`, `.get(default)` or `??` turn a bug or failed call into a plausible-looking value?
4. Does each caught error get handled with a real recovery, or re-raised with context?
5. Is the blast radius right: the failing request stops, the process doesn't?
6. Is every intentional fallback documented and visible?

## Related

- `defensive-programming` — the reconciliation: defensive programming decides *where to distrust*; fail fast decides *how to respond* when a check fails. At a trust boundary the two agree: validate, then fail loudly.
- `encapsulation` — where validity is kept once input is accepted.
- `explicitness` — silent defaults are also an explicitness failure.
