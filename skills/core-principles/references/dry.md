# DRY — Don't Repeat Yourself

Every piece of *knowledge* should have a single, unambiguous, authoritative
representation in the system (Hunt & Thomas, *The Pragmatic Programmer*).
The practical question:
**If this rule changes, how many places must I modify, and would I have to
remember them?**

The definition says *knowledge*, never *code*. DRY is about facts and rules,
not about text that happens to look alike.

## Decision procedure

1. **Search first.** Before writing new code, grep for the existing concept
   by meaning (constants, error messages, route names, domain terms), not
   only by identical text. Agents duplicate mostly by not looking.
2. **Name the shared knowledge in one domain sentence.** If you can't
   ("valid order statuses", "retry limit for the payments API"), stop.
3. **Same reason to change, at the same time?** If the two sites could
   diverge under any plausible requirement, it's coincidence, not
   duplication.
4. **Count the sites.** Two: tolerate it, unless it's a hard invariant
   (money, auth, validation, protocol). Three or more with the same reason
   to change: extract (the rule of three).
5. **Take the lightest move that gives one source of truth**, in order:
   1. a named constant
   2. a table or data loop
   3. derive one representation from another (type from schema, client
      from an API description, labels from an enum)
   4. a function that takes data, not behavior flags
   5. code generation

## True duplication vs coincidence

| True duplication of knowledge | Coincidental similarity |
|---|---|
| Blocks must change together | Blocks diverge under plausible requirements |
| Same domain rule, even if written differently | Same syntax, different rule |
| A fix in one obviously applies to the other | Different owners or stakeholders |
| Derived facts restated (list, format, schema) | Only a generic name in common (`process`, `handle`) |

Two validators with identical bodies (integer, at least 0) for *age* and for
*quantity* are different knowledge: they change for different reasons.
Merging them couples things that are independent.

DRY also covers non-code: an enum in the DB, a type union, a UI dropdown
and a table in the docs are one fact in four shapes. The same rule written
differently in two places is the *worse* violation, and no clone detector
will find it.

## Example: one fact in four shapes

```ts
// before: "valid statuses" restated in code, labels, and SQL
type Status = "draft" | "paid" | "shipped";
const isStatus = (s: string) => ["draft", "paid", "shipped"].includes(s);
const LABELS = { draft: "Draft", paid: "Paid", shipped: "Shipped" };
// SQL: CHECK (status IN ('draft','paid','shipped'))

// after: one list; the compiler flags a missing label
const STATUSES = ["draft", "paid", "shipped"] as const;
type Status = typeof STATUSES[number];
const isStatus = (s: string): s is Status => (STATUSES as readonly string[]).includes(s);
const LABELS: Record<Status, string> = { draft: "Draft", paid: "Paid", shipped: "Shipped" };
// the SQL check is generated from, or tested against, STATUSES
```

Adding "refunded" is now one edit, and the compiler or a test finds every
site that was missed. No code was merged for merely looking alike.

## Gotchas

- **The wrong abstraction is costlier than duplication** (Sandi Metz,
  [The Wrong Abstraction](https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction)).
  The tell: a shared helper that grows boolean flags, callbacks or
  `if caller == X` branches. **To undo it:** inline it back into every
  caller, delete each caller's dead branches, then re-extract only what
  still matches.
- **Don't extract on the second sighting.** This is the classic agent
  failure. Waiting for the third occurrence shows what actually varies.
- **Sharing is coupling.** A common module imported by unrelated areas
  ties them together (see `low-coupling`). Across service or team
  boundaries, duplicating a DTO is often cheaper than a shared library with
  version coordination. Keep DRY *inside* a boundary.
- **Tests should read as scenarios.** Repeated setup in tests is often
  fine. Restating production knowledge inside test expectations is not:
  derive it from the same source.
- **A dense parameterized helper can be less readable than two plain
  blocks** (`kiss`). Duplication is not cured by making things obscure.
- **A single point of truth needs enforcement.** If two representations must
  stay in sync and can't be derived, add a test that ties them together.

## Review checklist

1. If this rule changes, can I name every place that must change, and is it exactly one?
2. Did I search the repo for an existing implementation before writing a new one?
3. Are the two blocks I want to merge the same concept with the same reason to change?
4. Does the proposed helper need flags or callbacks to serve different callers? If so, it is probably the wrong abstraction.
5. Is any fact restated across code, schema, config, docs or tests with nothing tying the copies together?
6. Would the merge create a dependency between modules or teams that were independent?

## Related

- `yagni` and `kiss` — brakes on premature deduplication.
- `low-coupling` — the cost side of sharing.
- `single-responsibility` — different actors mean different knowledge, even when the code looks the same.
