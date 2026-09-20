# KISS — Keep It Simple

Prefer the simplest design that works. The practical question:
**Can I remove complexity?**

## What "simple" means

"Simple" is a property of the artifact, not a feeling of the author.

- **Simple is not easy.** Rich Hickey's distinction
  ([Simple Made Easy](https://github.com/matthiasn/talk-transcripts/blob/master/Hickey_Rich/SimpleMadeEasy.md)):
  *simple* means un-braided (one concern per piece); *easy* means near at
  hand or familiar, which is relative to the reader. A familiar framework
  that braids state, persistence and behavior is easy but not simple.
- **Simple is not short.** A golfed one-liner or a chain of clever
  comprehensions is compact but tangled.
- **Complexity is anything that makes the system hard to understand or
  modify.** Ousterhout's symptoms: change amplification (one change,
  many edits), cognitive load, unknown unknowns. Its causes:
  dependencies and obscurity.
- **Only accidental complexity is removable.** Brooks: *essential*
  complexity comes from the problem itself; *accidental* complexity comes
  from our tools and design. Auth, validation, retries, idempotency and
  migrations are usually essential. Deleting them is unsafe, not simple.

## Is it simple? Four tests

1. Can each piece be understood and changed without reading its callers
   and callees?
2. Does one logical change touch one place?
3. Can you say what it does without "and" or "unless"?
4. Would a new reader predict its behavior after one read, without
   opening more than about three files?

## Smells and the move that fixes each

| Smell | Move |
|---|---|
| Boolean or mode flag that switches behavior | Split into separate functions |
| Interface, factory or strategy with one implementation and one caller | Inline it |
| Method or layer that only forwards | Delete it |
| Option or config value nobody sets | Delete it |
| Shared mutable state, "call A before B" | Pass values; make it one operation |
| `catch` that hides a failure | Let it fail, or handle a specific case (see `fail-fast`) |
| Inheritance used only to reuse code | Plain data plus functions, or composition |
| Custom machinery for something the stdlib or platform does | Use the stdlib |
| Callers need to know a module's internals | Deepen the module: smaller interface, more hidden |

Simplify by **removing or separating** things, never by compressing them.

## Example

```python
# before: "DRY" flag-driven exporter, every flag interacts with the others
def export(rows, fmt, header=True, legacy=False, pretty=False):
    if fmt == "csv":
        out = [",".join(rows[0])] if header else []
        out += [",".join(map(str, r.values())) for r in rows]
        return ("\r\n" if legacy else "\n").join(out)
    if fmt == "json":
        return json.dumps(rows, indent=2 if pretty else None)

# after: two functions, no flag braiding; the unused `legacy` is gone
def to_csv(rows, header=True): ...
def to_json(rows, indent=None):
    return json.dumps(rows, indent=indent)
```

The two versions are about the same length. The second is simpler because
callers can no longer ask which flag combinations are valid.

## Gotchas

- **The smallest diff is not the simplest change.** Bolting a flag or a
  special case onto existing code is often the most complex option.
- **Simple does not mean fewer components.** Separating concerns often
  yields more, smaller parts. But many *shallow* classes (Ousterhout's
  "classitis") add interfaces without hiding anything. Aim for deep
  modules: a small interface over substantial functionality.
- **Gold-plating is the typical AI failure**: wrappers, factories,
  config objects, speculative parameters, defensive `try/except`. For
  every piece ask *"which current requirement needs this?"*
- **The opposite failure**: answering with a tutorial-shaped solution that
  silently drops essential complexity (boundary validation, concurrency,
  idempotency). Remove accidental complexity only.
- **Don't rewrite working code for aesthetics.** Understand why something
  exists before removing it, and follow the local convention even when
  you'd prefer a different style.
- **Performance justifies complexity only with a measurement.**
- **Tensions:** a little duplication is often simpler than a parameterized
  shared helper (`dry`); a slightly more general interface can be simpler
  than several special cases (Ousterhout); applying `single-responsibility`
  literally can fragment code into shallow pieces.

## Review checklist

1. Does every abstraction, parameter and config option have a real current use?
2. Can each unit be understood without reading its callers or callees?
3. Does behavior avoid hidden flag combinations and special cases?
4. Was existing language, library or platform functionality used?
5. Can I state why each remaining piece of complexity is essential?

## Related

- `yagni` — the closest ally: don't build what isn't needed. KISS also covers what *is* needed but built too elaborately.
- `dry` — deduplicating can add complexity; check it first.
- [`engineering-principles`](../SKILL.md) — how KISS trades off against the other principles.
