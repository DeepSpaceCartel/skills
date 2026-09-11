# Scenario Outlines, Examples, and Data

## Scenario vs. Scenario Outline

Use a plain `Scenario` for one illustrative example of a behavior. Use
`Scenario Outline` with an `Examples` table when you need to exercise
the *same* behavior across multiple, meaningfully different inputs —
not as a way to sneak unrelated behaviors into one scenario.

Gherkin has no "Or" step and no branching. Don't try to simulate
conditional logic inside a scenario ("this OR that happens"); if a
behavior genuinely varies by input, that's exactly what a Scenario
Outline's Examples table is for — one row per case.

```gherkin
Scenario Outline: Search returns results for a valid term
  Given the catalog contains items
  When the user searches for "<term>"
  Then results related to "<term>" are shown

  Examples:
    | term    |
    | widget  |
    | gadget  |
    | gizmo   |
```

## Keeping Examples meaningful

- Each row should represent a distinct **equivalence class** — a case
  that could plausibly behave differently — not an arbitrary extra
  data point that happens to also pass.
- Cap an Examples table around 10 rows. Past that, question whether
  every row earns its place in this feature file, or whether some
  belong in a lower-level (unit/integration) test instead.
- Don't add a column that actually represents a *different behavior*.
  If varying one column changes what's being verified rather than just
  the input, that's a sign it should be its own scenario, not a table
  column.
- Name/describe the Examples table where the tooling supports it, so a
  failing row is identifiable without cross-referencing line numbers.

## Data tables

An inline data table attached directly to a single step (as opposed to
a Scenario Outline's `Examples`) is for structured example data
supporting *one* execution of a scenario — not a data-driven loop.

Headers are optional; omit them when the data is self-explanatory as a
plain list:

```gherkin
Then the results include
  | Example Item A |
  | Example Item B |
  | Example Item C |
```

Use headers when columns need to be told apart:

```gherkin
Then the invoice lines are
  | item            | quantity | price |
  | Example Item A  | 2        | 9.99  |
  | Example Item B  | 1        | 4.50  |
```

## Doc strings

Use a Doc String (a triple-quoted block) for a chunk of free text a
step needs to check or pass along — page copy, an email body, a
message — rather than cramming it into the step's own text:

```gherkin
Then the profile shows the bio
  """
  Short bio text goes here,
  possibly spanning multiple lines.
  """
```
