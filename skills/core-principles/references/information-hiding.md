# Information Hiding

Hide implementation details behind stable interfaces. The practical question:
**What does the caller actually need to know?**

Parnas ([On the Criteria to Be Used in Decomposing Systems into Modules,
1972](https://blog.acolyer.org/2016/09/05/on-the-criteria-to-be-used-in-decomposing-systems-into-modules/))
proposed decomposing around difficult design decisions, or decisions likely
to change, with each module hiding one of them. Decomposing by processing steps
(read, validate, transform, write) was the approach he argued against. Both
decompositions work; they differ in what happens when a decision changes.

## Find the secret

Ask: *what would I change in a year, or if the vendor or store changed, and
how many files would that touch?* Typical secrets:

- storage engine and schema
- wire or file format
- algorithm choice
- vendor SDK and its error types
- caching, retry and batching policy
- required ordering and initialization sequence

Each module should be able to say, in one sentence, which decision it hides.

## How secrets leak

| Channel | Example | Fix |
|---|---|---|
| Return types | ORM rows, `Response` objects, DataFrames, raw dicts with vendor key names | Return domain types |
| Exceptions | `IntegrityError` or `ClientError` reaching callers | Translate at the boundary (`raise DuplicateOrder from e`) |
| Config and names | `use_redis=True`, `postgres_dsn`, `S3Uploader` | Name for the role, configure by capability |
| Protocol | "call `open()`, `begin()`, then `flush()` or it corrupts" | Collapse into one operation |
| Back door | two modules both know a file format, invisible in either interface | Merge them or extract one owner |

Ousterhout calls the first family *interface leakage*, the last one *back-door
leakage*. Splitting by pipeline phase (a reader and a writer that both know
the format) is *temporal decomposition* and leaks the same knowledge into
several modules.

## Example

```python
# before: fields are private, yet callers know SQL, the ORM row and the commit protocol
class Orders:
    def __init__(self, session): self._session = session
    def find(self, oid) -> OrderRow: return self._session.get(OrderRow, oid)
    def add(self, row): self._session.add(row)   # caller must session.commit()
# caller: except IntegrityError; row.cust_id; orders.add(r); session.commit()

# after: the secret is "how orders are stored"
@dataclass(frozen=True)
class Order: id: str; customer: str; total: Decimal
class DuplicateOrder(Exception): ...

class Orders:
    def place(self, o: Order) -> None:            # one operation, commits inside
        try:
            self._session.add(_to_row(o)); self._session.commit()
        except IntegrityError as e:
            raise DuplicateOrder(o.id) from e
    def get(self, oid: str) -> Order | None: ...
```

Swapping the database or renaming a column now changes one file. Callers
depend only on `Order` and `DuplicateOrder`.

## Gotchas

- **`private` is not information hiding.** A private field with a public
  getter mirroring it hides nothing; the representation is still the contract.
- **A one-to-one wrapper around a library isn't hiding either.** It renames
  the leak and adds a layer. The wrapper must present the *module's*
  vocabulary, not the vendor's.
- **Hyrum's Law:** with enough users, every observable behavior (ordering,
  timing, error text, defaults) becomes depended on, whatever the contract
  says. If callers can observe it, treat it as contract, or make it
  unobservable (deliberately shuffle map order, use opaque tokens).
- **Perfect hiding doesn't exist** ("leaky abstractions": SQL performance,
  TCP). Aim for leaks that are documented and deliberate.
- **Don't hide what callers need for correctness**: retry and timeout
  behavior, errors they must handle, and the cause chain for debugging
  (`raise X from e`). This is the tension with `explicitness`.
- **Over-hiding is `yagni`.** Don't hide decisions that will never change, and
  provide an escape hatch (`raw()`) where hot paths truly need the format.
- **Deep modules beat many small ones:** a simple interface over substantial
  functionality (`kiss`).

## Review checklist

1. Can I state, in one sentence, the design decision this module hides?
2. Would swapping the store, vendor or algorithm leave every caller unchanged?
3. Are all return types, parameters and exceptions in this module's vocabulary?
4. Can callers use it correctly without knowing call order or internal states?
5. Does any other module know the same format, key or constant?
6. Is anything hidden that callers need for correctness or debugging?

## Related

- `encapsulation` — hiding is the *design criterion* (which decision goes behind the boundary); encapsulation protects *validity* (invariants). The two are independent, and sources use the words loosely.
- `low-coupling` — the outcome of hiding well.
- `explicitness` — where hiding must stop.
