# Refactoring

Refactoring is "a change made to the internal structure of software to make it
easier to understand and cheaper to modify without changing its observable
behavior" (Fowler,
[Definition of Refactoring](https://martinfowler.com/bliki/DefinitionOfRefactoring.html)).
As a verb it means applying a *series* of small refactorings. Anything that
changes behavior is not refactoring, whatever the diff is called. Canonical
sources: Fowler and Beck's *Refactoring* (2nd ed., catalog at
[refactoring.com](https://refactoring.com/catalog/)), Beck's *Tidy First?*,
Feathers' *Working Effectively with Legacy Code*, and the Mikado Method.

## What agents typically get wrong

- **Mixing structure and behavior in one diff.** Beck: the two differ in
  reversibility, so put them in separate PRs, or at least separate commits, and
  reviewers can scrutinize the irreversible part
  ([Structure and Behavior](https://newsletter.kentbeck.com/p/structure-and-behavior)).
- **"Refactoring" that quietly changes behavior:** altered error messages,
  ordering, rounding, exception types, or a bug "fixed" in passing.
- **No safety net.** Restructuring code without tests, or with tests written
  afterwards to match the new shape. Feathers: legacy code is code without
  tests, so cover it before changing it.
- **A big-bang rewrite instead of a series of small steps.** The Strangler Fig
  pattern exists as the alternative.
- **Rename and reformat sprees** that bloat the diff. Keep formatter-only
  changes in their own commit.
- **Treating smells as rules.** Fowler: smells "don't always indicate a
  problem. Some long methods are just fine."
- **Refactoring everything nearby "while I'm here".** Take opportunities, but
  keep the scope tight and note the rest for later.
- **Leaving a Parallel Change half done.** Skipping the contract phase leaves
  "a worse state than you started".
- **Claiming "behavior preserved" without running anything.**

## Procedure

1. **Confirm the safety net.** Tests are green before you start. If coverage of
   the area is thin, add characterization tests first (below).
2. **Pick one refactoring** from the catalog and apply it in the smallest step
   that keeps the code working.
3. **Run the tests.** If they fail, revert the step instead of debugging forward.
4. **Commit structural changes on their own,** with a message that says "no
   behavior change". Make the behavior change in a separate commit or PR.
5. **Repeat until the change you actually want is easy,** then make it. Beck:
   "make the change easy (warning: this may be hard), then make the easy change."

**When to refactor**

- **Preparatory:** just before adding a feature or fixing a bug, if the current
  structure makes it hard. Fowler names this the best time.
- **Comprehension:** while working out what code does, capture it in the code.
- **Rule of three:** tolerate duplication the first and second time, extract on
  the third.
- **Don't** refactor code you're about to delete or never need to touch.

## Smell to refactoring (heuristic pairings; names from the catalog)

| Smell | Refactoring |
|---|---|
| Long function | Extract Function, Decompose Conditional, Replace Temp with Query, Split Loop |
| Feature envy | Move Function |
| Shotgun surgery | Move Function or Field, Combine Functions into Class |
| Primitive obsession | Replace Primitive with Object, Introduce Parameter Object |
| Data clumps | Introduce Parameter Object, Extract Class |
| Nested conditionals | Replace Nested Conditional with Guard Clauses |
| Repeated switch on a type | Replace Conditional with Polymorphism |
| Flag argument | Remove Flag Argument |
| Query mixed with side effect | Separate Query from Modifier |
| Loops | Replace Loop with Pipeline (check numeric results: see the example) |
| Dead code | Remove Dead Code |

## Techniques for bigger changes

- **Parallel Change (expand, migrate, contract).** For a signature or contract
  with many or external callers: add the new form beside the old, move callers
  over incrementally, then delete the old form. Finish the contract phase. Skip
  it when you own every caller and an IDE rename can do it atomically.
- **Strangler Fig.** Replace a legacy system gradually: route one piece at a
  time to new code. It needs transitional architecture and organizational
  change, or "new systems will end up in a similar mess". Skip it for small
  modules.
- **Mikado Method.** When a goal is blocked by a tangle of dependencies: try
  the change naively, record what breaks as prerequisites on a graph, revert
  to green, and work leaf-first.
- **Characterization tests and seams (Feathers).** A characterization test pins
  what the code does *now*, not what it should do. A seam is "a place where you
  can alter behavior in your program without editing in that place". Break
  dependencies at a seam, pin current behavior, then refactor. Mask
  non-deterministic values (timestamps, IDs). These tests don't prove the code
  correct.

## Example

Behavior-preserving steps, each followed by a test run and a commit:

```python
# before
def total(items, member):
    t = 0
    for i in items:
        t += i["price"] * i["qty"]
    if member:
        t = t - t * 0.1
    if t > 100:
        t = t - 5
    return t

# steps 1-3: Extract Function (line item), Extract Function (subtotal), Extract Function (discount)
def price(i):
    return i["price"] * i["qty"]

def subtotal(items):
    t = 0
    for i in items:                          # loop kept on purpose (see below)
        t += price(i)
    return t

def member_discount(t, member):
    return t - t * 0.1 if member else t      # same expression: don't "simplify" the arithmetic

# after
def total(items, member):
    t = member_discount(subtotal(items), member)
    return t - 5 if t > 100 else t
```

The discount-then-threshold order and the exact arithmetic are unchanged. If the
ordering is a bug, fix it in a separate behavior commit.

**Two "obviously equivalent" edits that are not** (checked on Python 3.12 with
random float prices):

- `Replace Loop with Pipeline` using `sum(...)`: since Python 3.12, `sum()` uses
  compensated summation for floats, so a `+=` loop over ten `0.1`s gives
  `0.9999999999999999` and `sum` gives `1.0`. The results differed in the last
  digit for a noticeable share of random inputs.
- `t - t * 0.1` rewritten as `t * 0.9`: also differs in the last digit for many
  inputs.

With the loop and the original expression kept, the refactored version matched the
original exactly on every one of 20,000 random cases. A test that compares old and
new outputs on generated inputs is a cheap way to find this kind of drift.

## Gotchas and contested points

- **Rewrite vs incremental.** Fowler favors incremental. Replacing a serious
  system takes a long time either way, and a rewrite is not refactoring.
- **When to stop.** When the change you need is easy, not when the code is
  ideal.
- **Refactoring without tests.** Add characterization tests first. Automated IDE
  refactorings (Rename, Extract Function) are commonly treated as the safe
  exception, but only for what the tool supports: reflection, dynamic dispatch
  and string-based lookups can still break.
- **Public interfaces.** Renaming a published API is a behavior change for its
  consumers. Use Parallel Change with deprecation (see `api-evolution`).
- **Some structural changes are costly to reverse,** such as extracting a
  service. Weigh that before doing them in one go.
- **Long-lived feature branches** are a barrier to refactoring: conflicts make
  every restructuring expensive.

## Review checklist

1. Were the tests green before the first edit?
2. Does every commit either change structure or change behavior, never both?
3. Was each step small enough to revert on a red test?
4. Are observable outputs unchanged (errors, ordering, rounding, public signatures)?
5. Is the diff free of unrelated renames and reformatting?
6. For code without tests, did characterization tests exist before the restructure?
7. If Parallel Change was used, is the contract phase done or ticketed?
8. Does the refactoring serve the change at hand, rather than being open-ended cleanup?

## Related

`testing` (the safety net), `api-evolution` (published interfaces),
`database-migrations` (schema changes), and `core-principles` (what a better
structure looks like).

## Sources

Fowler: [Definition of Refactoring](https://martinfowler.com/bliki/DefinitionOfRefactoring.html),
[Parallel Change](https://martinfowler.com/bliki/ParallelChange.html),
[Strangler Fig](https://martinfowler.com/bliki/StranglerFigApplication.html),
[Opportunistic Refactoring](https://martinfowler.com/bliki/OpportunisticRefactoring.html),
[Code Smell](https://martinfowler.com/bliki/CodeSmell.html),
[Legacy Seam](https://martinfowler.com/bliki/LegacySeam.html); the
[Refactoring catalog](https://refactoring.com/catalog/); Beck,
[Structure and Behavior](https://newsletter.kentbeck.com/p/structure-and-behavior);
the [Mikado Method introduction](https://mikadomethod.wordpress.com/2009/12/09/introduction-to-the-mikado-method/).
The smell-to-refactoring pairings and the IDE-refactoring exception are common
practice rather than quotes from one source.
