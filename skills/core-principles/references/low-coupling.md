# Low Coupling

Minimize *unnecessary* dependencies between components. The practical
question: **How much breaks if I change this?**

Coupling is not bad in itself; any working system is coupled. The goal is to
minimize coupling that is unnecessary, strong, far-reaching or high in
degree. Constantine's equivalence, as Kent Beck restates it: the cost of
software is roughly the cost of change, and coupling is what makes changes
big.

## Assess it, don't guess

1. **Blast-radius question.** "If I change this signature, behavior or
   schema, what must change or be retested?" Count files, teams and
   deployables *before* writing code.
2. **Import graph.** Count who depends on the module (afferent) and what it
   depends on (efferent). Many dependents make it costly to change;
   many dependencies make it fragile.
3. **Change together.** Files that co-change in git history are coupled,
   whatever the import graph says. Bulk refactors and squash commits inflate
   this signal, so read it with care.
4. **Score each dependency with connascence**
   ([connascence.io](https://connascence.io/)): *strength* (how hard to find
   and refactor), *locality* (close together is better), *degree* (how many
   parts are involved).

Connascence, weakest to strongest: name, type, meaning (magic values),
position, algorithm; dynamic forms: execution order, timing, value,
identity. Tolerate strong connascence inside one function or class; require
weak forms (name, type) across packages and services.

## Loosening moves

- Position to name: keyword arguments or an options object.
- Stamp to data: pass only the fields needed, not the whole object.
- Control flag to separate functions or polymorphism.
- Hide the volatile decision behind a narrow, consumer-shaped interface.
- Replace shared mutable state with parameters.
- Introduce a stable contract or event between parts.
- Inline or duplicate an over-shared helper (see `dry`).
- Move code next to its only consumer.

## Example

```python
# before: tax logic knows the whole Order -> Customer -> Address graph
def sales_tax(order):
    rate = RATES[order.customer.address.country]
    return order.total * rate

# after: depends on two values; the caller adapts once at the edge
def sales_tax(country: str, subtotal: Decimal) -> Decimal:
    return subtotal * RATES[country]
# caller: sales_tax(order.ship_country, order.subtotal)
```

The tax code no longer changes, or needs retesting, when the order model is
restructured.

## Gotchas

- **An interface is not decoupling.** If it mirrors the implementation (same
  method names, ORM-shaped returns, leaked exceptions), a change to the
  implementation still breaks every caller. Agents add `IFooService` with
  one implementation and call it done: type-level coupling remains, plus a
  file.
- **DRY-driven `common/` or `utils/` modules couple everything.** High
  afferent coupling means a huge blast radius, then flags accumulate as
  callers diverge. Prefer duplicating across boundaries.
- **Coupling hides outside imports:** shared database tables, magic strings
  or key names, required call order, the same algorithm on both sides of a
  wire, global config and singletons.
- **Law of Demeter is not dot-counting.** Wrapper methods like
  `getCustomerAddressCountry` widen interfaces without reducing what the
  caller knows. Fluent builders are fine.
- **A distributed monolith** has services split but coupled by a shared DB,
  chained synchronous calls and lockstep deploys. Crossing a network
  boundary *raises* the cost of strong coupling.
- **Decoupling has a cost.** Speculative decoupling is `yagni`; pursue it
  where a real change would hurt.
- **Stable external contracts** (stdlib, HTTP, SQL) don't need wrapping.
- **Tensions:** `high-cohesion` (over-decoupling yields fragmented, anemic
  modules; keep what changes together in one place), `dry` (sharing is
  coupling).

## Review checklist

1. Can I state the blast radius of this change, and is it confined to one module or team?
2. Does each new dependency use only the fields or methods it needs?
3. Would an implementation change (DB, vendor, algorithm) leave callers untouched?
4. Is any new shared module imported by unrelated areas, or growing flags?
5. Do cross-boundary dependencies rely only on names and types, with no positional arguments, magic values, required call order or shared tables?
6. Does the decoupling remove a real coupling, or just add indirection?

## Related

- `information-hiding` — the cause: hiding likely-to-change decisions is what makes coupling low.
- `program-to-an-interface` — one tool for loosening coupling, not free.
- `dry` and `high-cohesion` — the two principles it most often trades off against.
