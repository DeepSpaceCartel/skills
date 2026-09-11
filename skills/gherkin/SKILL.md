---
name: gherkin
description: How to write clear, maintainable Gherkin .feature files for BDD - project-agnostic. Covers feature/narrative structure, Given-When-Then step phrasing, declarative vs imperative style, Background usage, Scenario Outlines and Examples tables, and tagging conventions. Use when writing new .feature files, converting requirements/acceptance criteria into Gherkin, or reviewing existing .feature files for readability, scope, and maintainability.
---

# Gherkin / BDD Feature Files

A `.feature` file is living documentation before it's a test — the same
text a product owner reads to confirm a requirement is also the text
that automates it. Badly written Gherkin (procedure-driven steps,
scenarios that bundle several behaviors, brittle hardcoded data) shows
up as flaky, slow-to-maintain suites that stakeholders stop reading.
Everything here exists to keep the file readable by someone who
doesn't know the feature yet, while staying cheap to maintain as the
implementation changes underneath it.

## The core idea

- **Write for the reader who doesn't know the feature** — the Golden
  Gherkin Rule. If a step only makes sense to whoever wrote the
  automation, it's not done yet.
- **One scenario, one behavior.** A scenario with more than one
  When/Then pairing is actually multiple scenarios wearing a trench
  coat — see [`references/writing-steps.md`](references/writing-steps.md).
- **Declarative, not imperative.** Describe *what* happens at a
  business level; push *how* it happens into step definitions. Test:
  would this step's wording need to change if the implementation
  changed? If yes, it's imperative — see
  [`references/writing-steps.md`](references/writing-steps.md).
- **Outside-in.** A feature exists because of a business outcome, not
  because a page or endpoint exists to test — see
  [`references/structure-and-narrative.md`](references/structure-and-narrative.md).

## Where to look

| Reference | Covers |
|---|---|
| [`references/structure-and-narrative.md`](references/structure-and-narrative.md) | Feature titles, Connextra/inverted narrative formats, one-feature-per-file, full Background rules (length, no tech detail, never tagged, when to skip it) |
| [`references/writing-steps.md`](references/writing-steps.md) | Given/When/Then integrity and order, tense and point of view, declarative vs. imperative in depth, avoiding conjunctive steps, honest test data, atomic scenarios, happy + unhappy paths |
| [`references/scenario-outlines-and-data.md`](references/scenario-outlines-and-data.md) | Scenario vs. Scenario Outline, keeping Examples tables meaningful, inline data tables with/without headers, Doc Strings |
| [`references/tags-and-style.md`](references/tags-and-style.md) | Tag taxonomy and tagging rules, formatting/style checklist (capitalization, spacing, blank lines) |
| [`references/anti-patterns.md`](references/anti-patterns.md) | Consolidated red-flags checklist with before/after examples, for reviewing an existing feature file |

## Quick reference

### Writing a new feature file

1. Title the feature as one sentence describing its scope — not its
   implementation.
2. Write a narrative (`As a / I want / So that`, or the inverted
   `In order to / As a / I want`) — pick one format and use it
   consistently across the project.
3. List the distinct behaviors first, one per scenario, before writing
   any steps.
4. Add a Background only if *every* scenario in the file needs it, and
   keep it to a few purely business-level Given steps.
5. Write each scenario as Given (state) → When (one action) → Then
   (one outcome), third person, present tense.
6. When a scenario would repeat with only the data varying, convert it
   to a Scenario Outline with an Examples table instead of copy-pasting.
7. Tag sparingly and consistently — tag scenarios/features, never
   Background.
8. Make sure the feature covers unhappy paths where they matter, not
   just the golden path.

### Reviewing an existing feature file — red flags to scan for

- More than one When/Then pair in a scenario → split it, one behavior
  each.
- Steps mention UI elements, selectors, URLs, or field names → rewrite
  declaratively.
- Background is longer than ~4 lines or contains technical setup
  (start a server, clear a cache, seed a table) → trim it or move it to
  a hook.
- Background is used in a feature with only one scenario → inline the
  state into that scenario's Given instead.
- Background carries a tag → remove it; only scenarios and features
  are tagged.
- A scenario runs past ~10 steps, or an Examples table past ~10 rows →
  look for a missing split, or steps that are too imperative.
- Expected values are hardcoded and brittle where the underlying data
  could reasonably change → assert on the rule/behavior instead.
- Steps are stitched together with a lowercase "and" mid-sentence
  instead of a separate `And` step → split them.
- The feature has no unhappy-path coverage at all → check whether it
  should.

See [`references/anti-patterns.md`](references/anti-patterns.md) for
the fuller list with before/after examples.

## Worked example

Bad — imperative, exposes UI mechanics:

```gherkin
Scenario: Login
  Given I am on the login page
  When I fill "username" with "ABC"
  And I fill "password" with "XYZ"
  And I check the "Remember me" checkbox
  And I click the "Submit" button
  Then I should see the "Welcome" message
```

Good — declarative, describes the behavior:

```gherkin
Scenario: Successful login
  Given I have valid credentials
  When I log in
  Then I should see the welcome message
```

The second version reads the same whether the login form is a modal, a
redirect, or an API call — the mechanics live in the step definitions,
not the feature file.

## Sources

- [Cucumber: Better Gherkin](https://cucumber.io/docs/bdd/better-gherkin)
- [Automation Panda: BDD 101 — Writing Good Gherkin](https://automationpanda.com/2017/01/30/bdd-101-writing-good-gherkin/)
- [Veltris: Mastering BDD — Best Practices for Writing Effective Feature Files](https://veltris.medium.com/mastering-bdd-best-practices-for-writing-effective-feature-files-31c2e425f766)
- [BBC Internet Blog (archived): BDD — Tips for writing better feature files](https://www.bbc.co.uk/webarchive/https%3A%2F%2Fwww.bbc.co.uk%2Fblogs%2Finternet%2Fentries%2Fff14236d-098a-3565-b678-ff4ba5776a5f)
- [behave documentation: Gherkin support & philosophy](https://behave.readthedocs.io/en/latest/)
