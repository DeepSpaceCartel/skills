# Principle of Least Surprise

Behavior should match reasonable expectations. The practical question:
**Would a maintainer predict what this does?**

"A component of a system should behave in a way that most users will expect
it to behave" (see [Wikipedia](https://en.wikipedia.org/wiki/Principle_of_least_astonishment)),
or in Bloch's API-design version: "Every method should do the least
surprising thing it could, given its name"
([How to Design a Good API](https://www.infoq.com/articles/API-Design-Joshua-Bloch)).
Surprise is relative to an audience, so the first step is deciding who that is.

## Procedure

1. **Audience and reference conventions**, in order of authority: this
   codebase, then the framework, then the language's stdlib, then the platform
   (CLI, HTTP).
2. **Name vs behavior.** `get*`, `is*`, `has*`, `to*`, `calc*` and properties
   should be pure and cheap. `save` shouldn't also publish; `validate`
   shouldn't mutate. Avoid throwing from getters.
3. **Side effects.** Does it mutate an argument, touch global state, do hidden
   I/O, or log in a way that changes behavior?
4. **Command-query separation.** A query returns a value and doesn't change
   observable state; a command changes state and returns nothing. Mix them only
   for a known idiom (`pop`) and let the name signal it.
5. **Defaults.** Safe, the common case, and evaluated per call.
6. **Return and error shape.** The same failure mode across sibling functions
   (not `None` here, raise there, `-1` elsewhere). Return empty collections, not
   null.
7. **Symmetry.** open/close, add/remove, encode/decode: same argument order and
   naming.
8. **Repeatability.** Where the name implies it, calling twice equals calling once.

## Grep patterns for the top surprises

- Mutable defaults: `=\[\]`, `={}`
- Getters with writes: `def get_.*` bodies with `.save(`, `.commit(`, writes
- Predicates that throw: `is_`/`has_` functions containing `raise` or `throw`
- Mutating a parameter (`.sort()`, `.append(`, `pop`, `del`) and then returning it
- `save`/`update` hidden inside `to_*` or `format_*`
- Mixed `return None` and `raise` in one module
- Operator overloads (`__add__`, `__eq__`) with side effects

## Example

```python
# before: shaped like sorted(), but it reorders the caller's list and returns it
def order_by_priority(tasks):
    tasks.sort(key=lambda t: t.priority)
    return tasks            # the call site hides that the input was mutated

# after: follows the stdlib pairing (sorted() returns new, list.sort() returns None)
def order_by_priority(tasks):
    return sorted(tasks, key=lambda t: t.priority)
```

The first has the shape of a pure function but the effect of a command.
Returning the same object hides the mutation from anyone reading the call site.

## Gotchas

- **Your taste is not the audience's expectation.** Neither is the model's
  prior. Copying a nearby function that is itself surprising, or an idiom from
  another language (returning `null` where the codebase raises, camelCase in a
  snake_case repo), is not least surprise.
- **Familiar-looking constructs can mislead.** Python's `def f(x=[])`
  looks fresh per call but is evaluated once. Avoid constructs whose syntax
  suggests the wrong semantics.
- **A docstring doesn't fix a lying name.** Callers read the name and signature.
- **The local convention beats the language norm.** If the project returns
  `Result` types everywhere, don't introduce exceptions; raise the bad
  convention separately.
- **Changing an existing surprise is itself a surprise** (Hyrum's Law: callers
  depend on every observable behavior). Provide a migration path.
- **Deliberately surprise only for correctness or safety**: refuse a silent
  overwrite, default to the safe option ("in the face of ambiguity, refuse the
  temptation to guess").
- **Don't over-apply:** adding flags and overloads so nothing can astonish
  contradicts "when in doubt, leave it out" (`yagni`).

## Review checklist

1. Does every name (verb, `get`, `is`, `to`) predict what the body does, including side effects?
2. Would a maintainer using the language and framework conventions guess the return value, failure mode and defaults?
3. Are arguments and shared state left unmutated unless the name says otherwise?
4. Do sibling functions fail the same way, and are paired operations symmetric?
5. Is every default evaluated per call and safe for the common case?
6. If I copied a local pattern, is that pattern itself unsurprising to this audience?

## Related

- `explicitness` — route by the question: "can I *see* it?" goes there; "would I *predict* it?" goes here.
- `encapsulation` — required call order is a surprise and an invariant problem.
- `fail-fast` — a lenient "helpful" fallback is unsurprising in the moment but hides bugs.
