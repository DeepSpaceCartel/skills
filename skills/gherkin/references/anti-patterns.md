# Anti-Patterns Checklist

A consolidated list for reviewing an existing feature file, each with
a short before/after. This is the fuller version of the red-flags list
in `SKILL.md`.

## 1. Procedure-driven steps

Testing "how" instead of "what."

Bad:
```gherkin
When I click the "Search" button
And I type "widget" into the search box
And I press enter
```

Good:
```gherkin
When I search for "widget"
```

## 2. Multiple behaviors crammed into one scenario

Signal: more than one When/Then pair in the same scenario. Split each
pairing into its own `Scenario` with its own descriptive title — a
scenario title should name one behavior.

## 3. Missing subject-predicate

Bad: `And image links for "panda"`

Good: `And image links related to "panda" are shown`

## 4. Mixed tense or point of view

Bad (switches voice mid-feature):
```gherkin
Given I log in
...
Given the user has an account
```

Pick one voice (third person) and one tense (present), and hold it
across the whole suite — not just one feature file.

## 5. Hardcoded, brittle expected data

Bad: `Then I see "Blue Widget Deluxe v3"` — breaks the moment that
exact item is renamed, discontinued, or reordered.

Good: `Then the top result matches the search term`

## 6. Over-tagged or technical Background

A `Background` longer than ~4 lines, containing infrastructure setup
(start a server, clear a cache, seed a table), or carrying its own
tag. Trim it to business-level state, move technical setup to a hook,
and remove any tag.

## 7. Background used for a single-scenario feature

If a feature only has one scenario, `Background` isn't deduplicating
anything — inline the `Given` into that one scenario instead.

## 8. Scenario Outline disguising unrelated behaviors

Each `Examples` row should be the *same* behavior with different
input data — not different behaviors dressed up as table rows. If
varying a column changes what's actually being verified, that column
should be its own scenario.

## 9. No unhappy-path coverage

A feature that only ever shows the golden path is usually
under-specified, not simple — check whether invalid input, empty
states, or permission failures are part of the behavior and, if so,
whether they're missing scenarios.

## 10. Oversized feature files

More than roughly a dozen scenarios in one feature file, or scenarios
well past 10 steps each. Usually means the feature covers more than
one concern and should be split, or the steps are too imperative and
need to move up a level of abstraction.
