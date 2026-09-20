# Single Responsibility Principle

A module should have one reason to change. The practical question:
**Why would this code need to change?**

## What it actually says

- Original: "A class should have only one reason to change" (Martin, 2003).
- Restated by Martin: "Gather together the things that change for the same
  reasons. Separate those things that change for different reasons", and
  "This principle is about people"
  ([The Single Responsibility Principle](https://blog.cleancoder.com/uncle-bob/2014/05/08/SingleReponsibilityPrinciple.html)).
- In *Clean Architecture*: a module should be responsible to **one, and only
  one, actor**, where an actor is a group of stakeholders who want the change.

So the test is not size and not "how many things it does". It is *who would
ask me to change this*.

**Common misreading:** "a function/class should do one thing." Martin
explicitly says that is a real guideline for extracting functions but is *not*
the SRP. A 300-line class serving one actor is fine. Three ten-line methods
serving finance, HR and the DBA are a violation.

## Procedure: find the actors

1. For each method or group of fields, name the stakeholder who would
   request a change: finance, HR, ops/DBA, security, design/UX, a partner API.
2. Two or more distinct actors in one module means a violation.
3. Check the evidence:
   - Unrelated change requests keep touching the same file.
   - Two teams collide in merges on the same class.
   - A helper is shared by methods that serve different actors. One actor
     changes it and silently breaks the other's behavior (accidental
     duplication).
   - A change for one stakeholder needs regression checks for another.
4. Split by actor: give each its own class over shared plain data, and add a
   thin facade if callers shouldn't track three classes.
5. Move a shared helper to whichever actor owns it, or duplicate it on
   purpose. Don't leave it shared between actors.

## Example

```ts
// before: three actors in one class
class Invoice {
  total() { /* tax and pricing rules */ }        // finance
  toPdf() { /* layout, uses this.total() */ }    // design
  save(db) { /* INSERT ..., this.total() */ }    // platform / DBA
}

// after: one reason to change each; pricing is computed once
type InvoiceData = { items: Item[]; customer: Customer };
class InvoiceCalculator { total(d: InvoiceData): Money { /* ... */ } }   // finance
class InvoicePdfRenderer { render(d: InvoiceData, total: Money) { /* ... */ } }  // design
class InvoiceRepository { save(d: InvoiceData, total: Money) { /* ... */ } }     // platform
```

A tax-rule change, a logo redesign and a schema migration each touch one
file. Note `InvoiceCalculator` is one class with several methods, not one
class per method.

## Gotchas

- **Over-fragmentation is the typical agent failure**: `UserValidator`,
  `UserSaver`, `UserMapper` for a single actor, or splitting by processing
  step. Parnas warned against decomposing on the flowchart. If everything
  serves one actor, don't split.
- **Split when a second actor actually appears**, not for actors you can
  imagine. Design is discovery.
- **"Reason to change" means an actual stakeholder group**, not "any
  conceivable change".
- **Splitting can lower cohesion** if you cut along an artificial step
  instead of a change axis (see `high-cohesion`).
- **Tensions:** `kiss`, `dry` (duplication between actors is often correct)
  and `yagni` all push against reflexive extraction.

## Review checklist

1. Can I name the one stakeholder group that would ask for a change here?
2. Would a change requested by one actor force edits or retests for another?
3. Is any helper shared by methods that serve different actors?
4. Did I split for actors that don't exist, or by size alone?
5. Do two teams routinely collide in this file?
6. After splitting, is there a single entry point where callers need one?

## Related

- `separation-of-concerns` — separate by *aspect* (I/O vs policy), a thinking technique; SRP separates by *who asks for change*.
- `high-cohesion` — a property of a module's parts; SRP is one criterion for what belongs together.
- `low-coupling` — what splitting must not worsen.
