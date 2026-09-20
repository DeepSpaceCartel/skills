# High Cohesion

Related functionality belongs together. The practical question:
**Does everything here belong together?**

Cohesion is the degree to which the elements of a module belong together
(Stevens, Myers & Constantine, *Structured Design*, 1974). It applies at every
level, but it has no built-in criterion for what "belongs". You supply the
criterion: shared data or invariant, shared reason to change, shared
knowledge.

## The scale (worst to best)

coincidental, logical, temporal, procedural, communicational, sequential,
**functional**. Coincidental ("`utils`") and logical ("all the validators")
are the weak ones; functional (everything contributes to one well-defined
task or concept) is the goal. Treat the scale as vocabulary, not a score.

## Judging cohesion without a metric

1. **Naming test.** Can you name the module in one noun phrase from the
   domain, without "and", "Manager", "Util", "Helper", "Common", "Misc"?
2. **Data test.** Do its methods use the same fields or the same invariant?
   Two disjoint clusters of methods and fields means it can be split.
3. **Change test.** For a realistic feature request, do these files change
   together? Do parts change alone or for different reasons? Shotgun
   surgery means cohesion is too *low* across files; divergent change means
   a module serves several reasons.
4. **Conjoined test.** Can you understand one part without opening the
   other? If not, they belong together.
5. **Import test.** Do callers use most of the module, or a small fraction?

## Moves

- Move a function next to the data it uses.
- Extract a class along the disjoint cluster.
- Merge over-split shallow classes back together.
- Replace `utils/` with modules named for the domain concept.
- Reorganize layer folders into feature folders, so one feature's code
  lives together.
- Introduce a value object to own a scattered representation.

## Example

```python
# before: knowledge of "integer cents" scattered by technical type
# utils/money.py      def to_cents(x): ...      def fmt_usd(c): ...
# validators.py       def valid_amount(c): ...
# report.py           uses c / 100 directly and forgets the rounding rule

# after: one module owns the "integer cents" invariant
@dataclass(frozen=True)
class Money:
    cents: int
    def __post_init__(self):
        if self.cents < 0:
            raise ValueError("negative amount")
    @classmethod
    def from_decimal(cls, d): return cls(round(d * 100))
    def __add__(self, o): return Money(self.cents + o.cents)
    def __str__(self): return f"${self.cents / 100:,.2f}"
```

Every function that depends on the cents representation now lives with it.
A change to it touches one file, not three.

## Gotchas

- **Grouping by technical type isn't cohesion.** `utils/`, `helpers/`,
  `validators/`, `types/`, `services/` are logical or coincidental
  cohesion. Package-by-layer scatters a feature across folders; you add
  features far more often than you swap a layer's technology. Agents
  default to dropping new code into the nearest `utils` file, so ask where
  the code's *data* lives.
- **More splitting is not more cohesion.** Ousterhout calls the result
  "classitis": many small classes, each with its own interface. Temporal
  decomposition (FileReader, FileModifier, FileWriter that all know the
  format) leaks shared knowledge across pieces.
- **"Does one thing" is a weak test.** Acquire-lock plus critical section
  is two "things" that belong together.
- **LCOM misleads.** Getters and setters skew it; stateless classes score
  0 or undefined; base-class attributes are ignored. Use it as a prompt to
  look, not a verdict.
- **A small, genuinely generic, stateless helper module is fine** (string or
  date helpers), if it stays small and isn't a dumping ground.
- **Don't reorganize a repo mid-task** to chase cohesion; follow the existing
  layout and note the issue.
- **Package level tension:** things reused together and things released
  together pull toward different package sizes. Favor grouping what changes
  together early on.

## Review checklist

1. Can I name this module in one domain noun phrase?
2. Do its members share the same data, invariant or knowledge?
3. For a plausible feature change, do these files change together?
4. Did a split produce pieces I can't understand without each other?
5. If I put new code in a shared or `utils` module, is there really no better home next to its data?

## Related

- `single-responsibility` — supplies one criterion (one actor); cohesion also covers shared data and knowledge.
- `separation-of-concerns` — the "separate" half; cohesion is the "gather" half that pushes back.
- `low-coupling` — the mirror property between modules.
