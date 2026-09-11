# Feature Structure and Narrative

## Feature title

The title is the first — sometimes only — thing a stakeholder reads.
Keep it to one short, sensible sentence describing scope and context,
not implementation:

```gherkin
Feature: Item availability page
```

Long, meandering titles get skipped. If the title needs a paragraph to
explain, the feature is probably too big and should be split.

## Narrative formats

A narrative gives the feature business justification: who wants it and
why. Two equivalent forms are common — pick one and use it
consistently across the whole project. Mixing formats feature to
feature makes the suite harder to scan.

**Connextra format** (most common):

```gherkin
Feature: Item availability page
  As a site visitor
  I want to see whether an item is available
  So that I can decide whether to buy it
```

**Inverted format** (leads with the benefit):

```gherkin
Feature: Item availability page
  In order to decide whether to buy an item
  As a site visitor
  I want to see whether it is available
```

Whichever format you choose, the narrative should name a real role, a
concrete want, and a benefit that justifies the feature's existence —
not a restatement of the title.

## One feature per file

Keep a `.feature` file scoped to a single piece of functionality. This
isn't just tidiness — it's what makes features discoverable by name
and keeps a single file's scenario count manageable (aim for well
under a dozen scenarios per feature; more is a sign the feature is
covering more than one concern).

## Background

`Background` runs before every scenario in the file. Used well, it
removes duplicate setup; used badly, it hides context a reader needs
and makes scenarios harder to understand in isolation.

Rules, in order of how often they're broken:

1. **Keep it short** — a handful of Given steps, generic enough that a
   reader skimming straight to a scenario doesn't need to hold it in
   mind. If Background is growing, that's usually a sign scenarios in
   the file don't actually share enough context to justify one. Don't
   use Background to set up complicated state unless that state is
   actually something the reader needs to know — if a scenario doesn't
   care about a piece of setup, it doesn't belong in a section every
   scenario is forced to read.
2. **Name things vividly.** Prefer a concrete, story-like name over a
   generic placeholder — `Given Priya has an active subscription`
   reads better and stays more memorable than `Given User A is
   logged in`, especially once a feature file has several scenarios
   referring back to the same background actor.
3. **Business-level state only, never technical setup.** Background
   describes a precondition of the world, not infrastructure actions.
   Starting a server, warming a cache, or truncating a table belongs in
   a before-hook or step definition, not in the feature file a
   non-engineer is meant to read.

   Good:
   ```gherkin
   Background: An item is available
     Given a published item exists
   ```

   Bad (leaks implementation detail):
   ```gherkin
   Background: An item is available
     Given a row exists in the items table with status "published" and the cache is warmed
   ```
4. **Never tag a Background.** Tags apply to Features and Scenarios
   only.
5. **Skip Background entirely for a single-scenario feature.** With
   only one scenario, there's nothing being deduplicated — put the
   state directly in that scenario's own Given.
6. **Don't duplicate a before-hook and a Background covering the same
   setup.** Pick one. Two places doing the same setup is a common
   source of confusing, hard-to-debug scenario failures.
7. **One Background per feature, and it comes first.** A feature file
   has at most one `Background:` section, placed before any
   `Scenario:`, never sandwiched between scenarios.
