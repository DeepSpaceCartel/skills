# Program to an Interface

Depend on contracts, not concrete implementations. The practical question:
**Can I replace the implementation without changing callers?**

The Gang of Four principle
([Gamma interview](https://www.artima.com/articles/design-principles-from-design-patterns)):
"An interface distills the collaboration between objects... free from
implementation details, and it defines the vocabulary of the collaboration."
"Interface" means *the type a client relies on*: an abstract class, a
Protocol, a function signature or a structural shape. It is not the
`interface` keyword.

## Is a seam warranted?

Add one when at least one of these is true:

- It is an I/O or nondeterminism boundary (DB, network, clock, RNG,
  filesystem, payment gateway).
- There are two or more real implementations, or a concrete second one is
  scheduled.
- It is a plugin or extension point.
- A test double is needed for something slow or flaky.
- It is a published-library boundary.

Otherwise don't. Extracting an interface later is cheap in application code.

## Design it

1. **The consumer owns it.** Define the interface where it's *used*, shaped by
   what that consumer calls (dependency inversion). Go's guidance: define
   interfaces in the consuming package, and don't define them before there is
   a realistic use. Producers return concrete types.
2. **Small and role-based**: one to three methods named for the role
   (`ReportSink.save`), not `IUserManager` copying every public method.
3. **Write the contract, not just signatures:** preconditions and
   postconditions, which errors are raised (domain-level, not the vendor's),
   idempotency and retry safety, ordering and blocking, thread-safety, who
   owns returned resources.
4. **Substitution test.** Sketch a second, differently shaped implementation
   (in-memory, remote, read-only). If it forces changes in callers, the
   interface leaks.
5. **Run one contract-test suite against every implementation**, including the
   fake.

## Example

```python
# before: the "interface" exists (S3Store), but callers reach through it
class ReportService:
    def __init__(self, store: S3Store): self.store = store
    def publish(self, r):
        try:
            self.store.client.put_object(Bucket="reports", Key=r.id, Body=r.pdf)
        except botocore.exceptions.ClientError: ...
        return self.store.client.generate_presigned_url("get_object", Params={"Bucket": "reports", "Key": r.id})

# after: consumer-owned role interface plus a written contract
class ReportSink(Protocol):
    def save(self, report_id: str, data: bytes) -> str:
        """Idempotent per report_id. Returns a URL that resolves to data.
        Raises SinkUnavailable (retryable) or SinkRejected (not retryable)."""

class ReportService:
    def __init__(self, sink: ReportSink): self.sink = sink
    def publish(self, r): return self.sink.save(r.id, r.pdf)
# S3ReportSink adapts boto3 and translates errors; InMemorySink is the test fake.
```

Swapping S3 for GCS, disk or a fake needs no change to `ReportService`: the
bucket, vendor calls and vendor errors are no longer in the caller.

## Signals that callers are secretly coupled to an implementation

- `isinstance` checks, downcasts, or `if it's the Postgres one, call X`
- Callers catching vendor exceptions
- Reliance on ordering, on lazy vs eager evaluation, or on the returned
  object being "live"
- An `as_sqlalchemy()` or `raw()` escape hatch on the interface
- Tests that only pass with the real implementation

## Gotchas

- **`IFoo` for every `Foo`** (Fowler's "InterfaceImplementationPair") is extra
  effort to keep in sync and hides the places you really do have several
  implementations. Agents produce this by default.
- **A header interface** (mirrors a class's whole public API) is the opposite of
  a role interface. Design around clients' needs.
- **Leaky interfaces:** parameters or returns that are implementation types
  (`Row`, `Response`), or implementation exceptions.
- **An interface next to its implementation and mirroring it** decouples
  nothing.
- **Prefer fakes at real I/O boundaries over mock-verifying call sequences**,
  which couples tests to the implementation.
- **Published interfaces are hard to evolve** (adding a method breaks all
  implementers); another reason not to publish speculative ones.
- **Not everything needs one:** pure logic and value objects take data or
  functions, not service interfaces. A function type is often the right seam.
- **Tensions:** `yagni` and `kiss` (one implementation, no boundary: no interface).

## Review checklist

1. Can I write a plausible second implementation without editing any caller?
2. Do signatures avoid implementation types, including exceptions, and does the contract state errors and idempotency?
3. Is the interface owned by the consumer and shaped by what it calls?
4. Do callers avoid `isinstance`, downcasts and vendor-specific branches?
5. Is there a real boundary or second implementation?
6. Does one contract-test suite run against every implementation?

## Related

- `low-coupling` — the goal; an interface is one tool, and only lowers coupling if it hides volatile decisions.
- `information-hiding` — decides *what* the interface must hide.
- `yagni` — decides *whether* you need one yet.
