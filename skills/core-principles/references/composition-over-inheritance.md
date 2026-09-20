# Composition over Inheritance

Assemble behavior from parts instead of building deep class hierarchies.
The practical question: **Can I compose this instead of subclassing?**

The Gang of Four's wording is "favor object composition over class
inheritance". Their reason: inheritance is *white-box* reuse (the child sees
and depends on the parent's internals), so it "breaks encapsulation", while
composition is *black-box* reuse through a stable interface. Bloch's
*Effective Java* (Item 18) adds the concrete failure: a subclass is fragile
because it depends on the parent's undocumented self-use of its own methods.

## Decision procedure

Subclass only if **all** hold:

1. **Full contract:** every instance of the child satisfies the parent's
   whole contract (preconditions not strengthened, postconditions and
   invariants not weakened). If not, don't subclass.
2. **Substitution is needed:** callers hold the parent type and receive
   children. If you only want the parent's *code*, compose.
3. **Designed for extension:** the parent documents its hooks and self-use,
   and is tested with subclasses. Otherwise compose (Bloch, Item 19: design
   and document for inheritance, or prohibit it).
4. **The variation is fixed at compile time** and on one axis. If it changes
   at runtime or combines across two or more axes, use a strategy or
   component.
5. A framework may **require** inheritance (a Django `Model`, a
   `unittest.TestCase`): then inherit, and keep the subclass thin.

## Detection signals

- An override that calls `super()` and depends on the order of the parent's
  internal calls
- An override that disables or no-ops inherited behavior (an empty body,
  `raise NotImplementedError`): a substitution violation
- Hierarchy depth above two, or parallel hierarchies (`FooA` / `FooAHandler`)
- A `Base` class full of hook methods and flags
- A subclass using a small fraction of the parent's public API
- Subclassing a built-in collection
- A class-explosion matrix: `EmailAdminNotifier`, `SmsAdminNotifier`, ...

## Moves

1. Add a field of the former parent type.
2. Forward *only* the methods callers need.
3. Extract the varying part into a strategy or interface, injected through
   the constructor.
4. Delete the `extends`.
5. If the wrapper must stay substitutable, implement the interface, not the class.

## Example

```python
# before: passes review, breaks silently (dict's C-level paths bypass the override)
class AuditedDict(dict):
    def __setitem__(self, k, v):
        log.append(k)
        super().__setitem__(k, v)
AuditedDict({"a": 1})      # not logged
d = AuditedDict()
d.update(b=2)              # not logged

# after: owns a dict and exposes only what it audits
class AuditedStore:
    def __init__(self, log):
        self._d, self._log = {}, log
    def set(self, k, v):
        self._log.append(k)
        self._d[k] = v
    def get(self, k):
        return self._d[k]
```

Every write is logged because there is no hidden internal path to bypass,
and the narrow API can't be widened by inherited methods.

## Gotchas

- **"Never inherit" is not the principle.** It is a selectively applicable
  suggestion. True subtyping, sealed hierarchies and sum types (AST nodes,
  `Result`), small documented template methods, and framework extension points
  are legitimate.
- **A wrapper that forwards everything unchanged** is inheritance with more
  boilerplate. Composition should *narrow* the surface to what callers need.
- **Composition has its own trap:** a wrapped object that passes `this` to
  callbacks bypasses the wrapper (Bloch's SELF problem).
- **Go embedding and Rust default trait methods are not inheritance.**
  Promoted methods get the inner value as receiver; the outer type isn't a
  subtype. Don't port class-hierarchy reasoning to them.
- **One `if` or a constructor argument beats a strategy hierarchy** for two
  stable cases (`kiss`, `yagni`).
- **Forwarding boilerplate** is the real cost; use language help (Kotlin
  `by`, Go embedding, traits) rather than falling back to subclassing.

## Review checklist

1. Could the subclass be used everywhere the parent is, with no caller-visible surprise?
2. Does any override depend on the parent's internal call order or disable inherited behavior?
3. Is the parent documented and tested for extension, or sealed?
4. Is the hierarchy two levels or fewer, with no parallel hierarchy?
5. Does any new wrapper forward everything, instead of exposing a narrowed interface?
6. Would a plain `if` or a constructor argument express the variation more simply?

## Related

- `encapsulation` and `information-hiding` — inheritance breaks both.
- `program-to-an-interface` — keep subtyping via an interface while moving code reuse to a delegate.
- `kiss` — don't build a strategy hierarchy for two stable cases.
