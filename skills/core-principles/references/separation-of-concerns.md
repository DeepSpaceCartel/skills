# Separation of Concerns

Keep different kinds of questions independent, so each can be reasoned
about and changed on its own. The practical question:
**Does this component have one conceptual job?**

Dijkstra ([EWD447, 1974](https://www.cs.utexas.edu/~EWD/transcriptions/EWD04xx/EWD447.html))
introduced it as a discipline of thought: study one aspect "in isolation for
the sake of its own consistency", knowing the other aspects exist but are
irrelevant *from this aspect's point of view*. It is a way to order thinking.
It is not a prescription for layers.

## Choosing the axis

Ask in this order:

1. **What forces mixed reasoning?** Policy vs mechanism; deciding *what* vs
   doing it; domain rules vs display; correctness vs performance.
2. **What will change independently?** Separate along that line.
3. **Only then** consider technical layers.

Default at the top level to **feature (vertical) slices** with the
inside/outside split *inside* each feature. Fowler warns against making
presentation/domain/data the top-level split of a big system
([PresentationDomainDataLayering](https://martinfowler.com/bliki/PresentationDomainDataLayering.html)).

## Signals of mixed concerns

- A function you can't test without a DB, network or clock, although its
  interesting part is a decision or calculation
- SQL, ORM calls or HTTP clients in a handler or component that also
  branches on business rules
- A UI component deciding eligibility, pricing or permissions
- Domain code returning HTTP status codes or formatted strings
- A function whose description needs "decide what... and do it"

## The main move: decide, then act

Extract the decision as a pure function from values to values. Keep I/O in a
thin shell that fetches, calls the function, then acts (Bernhardt's
[functional core, imperative shell](https://www.destroyallsoftware.com/screencasts/catalog/functional-core-imperative-shell)).
The axis is inside (domain) vs outside (devices), as in Cockburn's
[hexagonal architecture](https://alistair.cockburn.us/hexagonal-architecture/).

```python
# before: policy tangled with I/O; untestable without a DB and SMTP
def send_overdue_reminders(db, mailer, today):
    for inv in db.query("SELECT * FROM invoices WHERE paid=0"):
        days = (today - inv.due).days
        if days > 30 or (days > 14 and inv.customer_tier == "gold"):
            mailer.send(inv.email, f"Invoice {inv.id} is {days} days late")

# after: same file, no new layers; just "decide" vs "act"
def reminders_due(invoices, today):              # pure: values in, values out
    out = []
    for inv in invoices:
        days = (today - inv.due).days
        if days > 30 or (days > 14 and inv.customer_tier == "gold"):
            out.append((inv.email, f"Invoice {inv.id} is {days} days late"))
    return out

def send_overdue_reminders(db, mailer, today):   # thin shell
    for to, body in reminders_due(db.unpaid_invoices(), today):
        mailer.send(to, body)
```

The rule is now testable with plain lists and no mocks, and the storage and
mail concerns can change independently.

## Gotchas

- **Layers are not the goal.** Agents create `controllers/ services/
  repositories/ dtos/ mappers/` for a 20-line feature, and each layer passes
  data through unchanged. A layer that isolates no concern that changes
  independently is ceremony.
- **The anemic split.** Moving all logic into `*Service` classes and leaving
  entities as bags of getters and setters separates data from behavior
  that belong together (`encapsulation`).
- **An interface with one implementation, or a wrapper that only delegates,
  isn't separation.** It adds indirection without isolating anything.
- **Some concerns cut across** (logging, auth, transactions). Handle them at
  one boundary (middleware, a decorator) rather than duplicating inline, and
  don't force them into a layer.
- **Separation costs.** Splitting can lose atomicity or add N+1 queries when
  a pure core needs its data loaded up front. Weigh it.
- **Tensions:** `kiss`/`yagni` (don't add layers "for later"), `high-cohesion`
  (slicing by layer scatters one feature across folders), `dry` (mapping
  between layers is the price of layers).

## SoC, SRP and cohesion in one line each

- **Separation of Concerns:** am I forced to think about two unrelated kinds
  of things at once here? (a thinking technique; the axis is the *aspect*)
- **Single Responsibility:** who would
  ask me to change this? (the axis is the *actor*)
- **High Cohesion:** do these members belong
  together? (a *property* of a module; the outcome both aim for)

## Review checklist

1. Can the business rule be exercised without a DB, network, clock or UI?
2. Does any handler or component both perform I/O and branch on domain policy?
3. Does each new layer or wrapper isolate a concern that changes independently?
4. Is the top-level grouping by feature, with layering inside?
5. Do domain functions return domain values, not HTTP codes, SQL rows or display strings?
6. Are cross-cutting concerns handled at one boundary?

## Related

- `single-responsibility`, `high-cohesion` — the neighbours above.
- `information-hiding` — what to hide behind the boundary once you've drawn it.
