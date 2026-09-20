# Encapsulation

Keep state and the operations on it together, and let the type enforce its
own rules. The practical question: **Can invalid states be prevented here?**

In the sense used here, encapsulation means a type owns its **invariants**.
Meyer's design by contract: a class invariant "must be satisfied on exit by
any creation procedure" and preserved by every public operation
([Eiffel docs](https://www.eiffel.org/doc/eiffel/ET-_Design_by_Contract_%28tm%29%2C_Assertions_and_Exceptions)).
No caller should be able to observe or produce a state the domain forbids.

## Procedure

1. **State the invariants** as sentences about state, especially across
   fields: "`shipped_at` is set iff status is SHIPPED", "lines sum to
   total", "start is not after end". Ask *what must always be true between
   public calls?*
2. **Choose the strongest enforcement available**, in order:
   1. *Make illegal states unrepresentable*: a variant or type per state
      (`Connecting`, `Connected`, `Disconnected`), instead of a status flag
      plus nullable fields.
   2. *Parse into a refined type once* at the boundary and pass that type
      inward ("parse, don't validate").
   3. *The constructor or factory establishes the invariant*; prefer
      immutability.
   4. Replace multi-field setters with one intention-revealing operation.
   5. Use an explicit state machine (transition methods) for lifecycles.
   6. Return copies or read-only views of collections; expose `add`/`remove`.
   7. Move behavior to the data that owns the invariant ("tell, don't ask").

## Signals of a violation

- Callers must call `init()` or set fields in a particular order
- The same `if x.a and not x.b` guard appears at several call sites
- An `Optional` field that is only meaningful in some states
- A getter returns the internal mutable list or dict
- Objects are built empty and filled in ("half-initialized")
- A caller sets several fields in a row on one object
- An `is_valid()` method exists

## Example

```python
# before: each setter checks only its own half of "start <= end"
class Booking:
    def __init__(self, start, end): self._start, self._end = start, end
    @property
    def start(self): return self._start
    @start.setter
    def start(self, v):
        if v > self._end: raise ValueError
        self._start = v
    # end setter likewise: moving a booking later works only if the caller sets end first

# after: the invariant is checked once; a move is one atomic operation
@dataclass(frozen=True)
class Booking:
    start: date
    end: date
    def __post_init__(self):
        if self.start > self.end: raise ValueError("start after end")
    def moved_to(self, start: date, end: date) -> "Booking":
        return Booking(start, end)
```

The multi-field invariant can no longer be broken, and it doesn't depend on
call order.

## Gotchas

- **`private` field plus `getX()`/`setX()` is not encapsulation.** It is public
  mutable state with ceremony. A class that is only fields and accessors is
  the red flag.
- **Per-field setters can't guard multi-field invariants**, since each sees
  only a partial state.
- **A `validate(order)` called at the edge discards what it learned.** Scattered
  checks ("shotgun parsing") leave later code re-checking; produce a typed value
  instead.
- **Validating in the constructor but leaving fields writable** means the
  invariant holds only at construction.
- **Anemic domain model:** entities as bags of getters and setters, with rules
  in services, get all the cost of a domain model and none of the benefit.
- **Exempt: pure data carriers** (DTOs, wire formats, config, DB rows) and
  immutable transparent data have no invariants to protect. Don't add ceremony.
  Some invariants (cross-aggregate, numeric ranges) can't be encoded in types;
  use a constructor check, and keep aggregates small.
- **"Tell, don't ask" can be over-applied** into contortions to avoid any query
  method. Use it as a stepping stone, not a rule.
- **Terminology is contested.** Some authors treat encapsulation and
  information hiding as the same thing. Treat the split above as a working
  heuristic: hiding is about *change*, encapsulation about *validity*.

## Review checklist

1. Can I state each invariant across this type's fields, and does exactly one place enforce it?
2. Does every constructor or factory return a fully valid object?
3. Can a caller reach an invalid state through setters, a returned mutable collection or public fields?
4. Must callers call methods in a fixed order or repeat a guard for it to work?
5. Could a variant type or refined type make a flag or optional field impossible to misuse?
6. If it's only a data carrier, did I deliberately leave invariant machinery off?

## Related

- `information-hiding` — the change-oriented sibling; a private field with a mirroring getter hides representation but protects no invariant.
- `fail-fast` — where invalid input is rejected; encapsulation is where validity is *kept*.
- `least-surprise` — required call order is both an encapsulation and a surprise problem.
