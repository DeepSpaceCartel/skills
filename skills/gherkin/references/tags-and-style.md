# Tags and Formatting Style

## Tag taxonomy

Group tags by what they're meant to filter on, and keep names short,
lowercase, and hyphenated:

- **Frequency**: `@daily`, `@hourly`, `@nightly`
- **Dependencies**: `@database`, `@external-api`, `@local-only`
- **Progress**: `@wip`, `@todo`, `@blocked`
- **Level**: `@smoke`, `@sanity`, `@functional`, `@acceptance`
- **Environment**: `@integration`, `@staging`, `@production`

A consistent taxonomy is what makes tags useful for filtering a large
suite (e.g. running just `@smoke` scenarios, or excluding
`@external-api` ones on a machine with no network access) rather than
becoming noise. Most runners (Cucumber, behave, SpecFlow, ...) support
boolean tag expressions — `not @wip`, `@smoke and @fast`, `@wip or
@slow` — so design tags as small, composable facts (one tag per axis:
frequency, dependency, level, environment) rather than one big tag per
run configuration; composable tags can be combined at the command
line instead of multiplying into `@nightly-smoke-staging`-style
one-offs.

## Tagging rules

- Tag **Scenarios or Features**, never a `Background`.
- Tagging a `Feature` applies that tag to every scenario inside it
  automatically — don't also tag each individual scenario with the
  same tag; that's redundant and makes it unclear whether a scenario's
  tag came from the feature or was added deliberately.
- A tracking-system tag (e.g. `@PROJ-1234`) on a feature is useful when
  it's worth tracing the file back to a ticket.
- Remove `@wip` once a scenario is finished, and make sure CI excludes
  `@wip` from the runs that gate a build — an unfinished scenario
  should never fail (or silently pass) a pipeline it isn't ready for.

## Formatting checklist

- Capitalize Gherkin keywords (`Given`, `When`, `Then`, `And`, `But`);
  don't capitalize other words in a step unless they're proper nouns.
- Capitalize only the first word of a Feature/Scenario title.
- No trailing punctuation (periods, commas) at the end of step lines.
- Single spaces between words; consistent indentation beneath
  `Feature:`/`Scenario:`/`Background:` headers.
- Two blank lines between Scenarios (and between Features, though a
  file should generally hold only one); one blank line before an
  `Examples:` table.
- No blank lines inside a scenario's own steps.
- Align table pipes (`|`) evenly so columns read cleanly.
- Correct spelling and grammar throughout — a feature file is
  documentation non-engineers will read, not internal scratch notes.
