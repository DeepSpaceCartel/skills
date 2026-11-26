# Migration: from a monolith or legacy system to services

## Problem

Big-bang rewrites of a working system usually run long, chase a moving target, and deliver
nothing until the end. The alternative is to replace the old system one capability at a time
while it keeps running, putting each new piece into production as soon as it works. Two
patterns carry most of the load: the **strangler fig** (route traffic piece by piece to the new
system) and the **anti-corruption layer** (keep the old model from leaking into the new one).

Code-level techniques (Parallel Change, seams, characterization tests) are in
[`engineering-practices` refactoring](../../engineering-practices/references/refactoring.md).
This reference is the service-scale version.

## Before extracting anything

1. **Name the goal** in delivery terms: which teams are blocked, which part needs different
   scaling, what lead time should drop. If modularising inside the monolith reaches the goal,
   stop there ([style-choice](style-choice.md)).
2. **Draw the target** boundaries ([design-process](design-process.md)). Extraction without a
   target produces services shaped like the monolith's accidents.
3. **Modularise in place first** where you can. A module with a clean API and its own tables is
   cheap to extract; a tangle is not.

## Strangler fig at service scale

1. **Put a routing seam in front:** a reverse proxy, gateway or façade through which all
   traffic for the capability passes. Initially it routes everything to the monolith.
2. **Pick the first capability.** Good first candidates are loosely coupled to the rest, change
   often (so the new pipeline pays off quickly), or have a distinct scaling need. Avoid the
   most tangled core first. New features are also good candidates: build them as services from
   the start, which shows value early.
3. **Build it in the new service** with its own data ([data-ownership](data-ownership.md)).
4. **Shift traffic gradually:** shadow it first (compare responses), then a percentage or a
   user cohort, then all. Keep the route back to the monolith until the new path has run
   through a full business cycle.
5. **Delete the old code path.** A strangler that never removes the old code doubles the
   system instead of replacing it.
6. **Repeat.** Re-check the target after each extraction; you'll have learned something.

For calls *from* the monolith *into* the extracted capability, use **branch by abstraction**:
introduce an interface inside the monolith, implement it first with the existing code and
then with a client for the new service, and switch with a flag.

## Data during extraction

The hard part is usually the data, not the code. Order the steps:

1. The new service reads and writes the monolith's tables through the monolith's module API
   (or temporarily directly, with the tables' ownership clear).
2. The new service gets its own store; data is **synchronised** during the transition. Prefer
   one writer at any moment: either the monolith writes and the service replicates, or the
   reverse. Dual writes from both sides need reconciliation and are a last resort.
3. Ownership flips: the service becomes the writer, and the monolith reads via the service's
   API or events.
4. The monolith's copy is removed.

Each step needs a way back. Backfills and expand-and-contract are in
[`engineering-practices` database-migrations](../../engineering-practices/references/database-migrations.md).

## Anti-corruption layer

When a new service has to talk to a legacy system (or any external model it doesn't control),
put a translation layer between them. The layer maps the legacy concepts, codes and quirks into
the new service's own model and back. The new model stays expressed in its own language, and
the legacy system can change behind one adapter.

- **Where it lives:** inside the new service as an adapter module, or as a small separate
  service when several new services talk to the same legacy system.
- **What it does:** translates data and vocabulary, hides awkward protocols (batch files,
  SOAP, screen scraping), and absorbs legacy invariants that don't apply to the new model.
- **When to drop it:** never while the legacy system lives. It's cheap insurance.

## What agents get wrong

- **Extracting the biggest, most tangled module first.** Start where the coupling is low and
  the payoff is visible.
- **No routing seam,** so each extraction needs client changes.
- **Never deleting the old path.** Two implementations stay alive and drift.
- **Copying the legacy schema into the new service** because it's quick. The service inherits
  the monolith's model; use an anti-corruption layer.
- **Dual writes from both systems** without a single writer or reconciliation.
- **A rewrite branded as a strangler:** building the whole new system before routing any
  traffic.

## Example

A billing module in a monolith is the first candidate: it changes often, its team is blocked by
the monolith's release train, and it touches the rest only through invoices. Steps: put the
billing routes behind the gateway; inside the monolith, add a `BillingPort` interface used by
order code (branch by abstraction); build the billing service with its own schema and an
anti-corruption adapter that maps the monolith's `acct_type` codes to its own plan model; shadow
invoice calculation for two billing cycles and compare totals; switch writes to the service and
have the monolith read invoices via its API; delete the monolith's billing code and tables.

## Review checklist

1. What delivery problem does this extraction solve, and could modularising in place solve it?
2. Is there a routing seam, and can traffic shift gradually and back?
3. Why this capability first (coupling, change rate, distinct need)?
4. At each step of the data transition, which system is the single writer?
5. Is there an anti-corruption layer between the new model and the legacy one?
6. When is the old path deleted, and who checks that it was?

## Related

[style-choice](style-choice.md), [data-ownership](data-ownership.md),
[edge-and-identity](edge-and-identity.md) (the gateway as the routing seam),
[`engineering-practices` release-engineering](../../engineering-practices/references/release-engineering.md)
(flags, canaries, rollback).

## Sources

microservices.io: [Strangler application](https://microservices.io/patterns/refactoring/strangler-application.html),
[Anti-corruption layer](https://microservices.io/patterns/refactoring/anti-corruption-layer.html).
Martin Fowler, [Strangler Fig Application](https://martinfowler.com/bliki/StranglerFigApplication.html),
[Branch By Abstraction](https://martinfowler.com/bliki/BranchByAbstraction.html). Sam Newman,
*Monolith to Microservices*. Eric Evans, *Domain-Driven Design* (anti-corruption layer).
