# Writing Steps

## Given-When-Then integrity and order

Steps run in Given → When → Then order, and each keyword means
something specific:

- **Given** puts the system in a known state — phrase it as a fact, not
  an action. `Given the user is logged in`, not `Given the user logs
  in`. It's fine for a Given to establish that state directly (a
  fixture, a prior event) rather than walking through the UI to arrive
  at it — `Given a customer previously bought a sweater` is a
  legitimate Given even though nothing in the scenario shows that
  purchase happening.
- **When** performs a single action, present tense — the one key
  interaction that causes something to change.
  `When the user submits the form`.
- **Then** verifies a single observable outcome, present tense, and
  checks what a user or downstream system would actually see — a
  report, a UI message, a response body — not internal state like a
  database row or cache entry that only the implementation knows
  about. `Then a confirmation message is shown`.
- **And**/**But** carry the meaning of whichever of Given/When/Then
  they follow — they exist purely so a scenario reads fluently instead
  of repeating the same keyword line after line.

A scenario has exactly **one** When/Then pairing. Seeing a second When
after a Then (or several When/Then pairs strung together) is the
clearest signal a scenario is bundling multiple behaviors — split each
pairing into its own scenario with its own title. Don't relabel a
`Then` as a `When` just to keep the keywords in an order that lets you
cram more into one scenario; that breaks the meaning the keyword is
supposed to carry.

Always start a scenario with a `Given`, even when the file also has a
`Background` (which itself starts with `Given`) — skipping straight to
`When` makes a scenario read like it starts mid-story.

## Point of view and tense

- Write every step in **third person**, consistently, across the whole
  suite: `the user submits the form`, not `I submit the form` in one
  place and `the user submits the form` in another.
- Use **present tense** throughout, including in `Then` steps.

## Subject-predicate completeness

Every step needs a clear subject and predicate. A fragment like
`And image links for "panda"` doesn't say what happens to those
links — it's ambiguous and can't be reused reliably. Write the full
clause: `And image links related to "panda" are shown`.

## Declarative over imperative

This is the single highest-leverage habit in Gherkin. The test: would
this step's wording need to change if the underlying implementation
changed (a different UI, a different API, a redesigned flow)? If yes,
it's imperative and should move up a level of abstraction.

Imperative (exposes mechanics — brittle, verbose):

```gherkin
Scenario: Login
  Given I am on the login page
  When I fill "username" with "ABC"
  And I fill "password" with "XYZ"
  And I click the "Submit" button
  Then I should see the "Welcome" message
```

Declarative (describes behavior — stable, short):

```gherkin
Scenario: Successful login
  Given I have valid credentials
  When I log in
  Then I should see the welcome message
```

The mechanics (which field, which button, which URL) live in step
definitions. The feature file stays true regardless of whether the
login form is a modal, a redirect, or an API call.

## Avoid conjunctive steps

Gherkin has an `And` keyword for exactly this — use it instead of
stuffing multiple actions or conditions into one step joined by a
lowercase "and" mid-sentence.

Bad:

```gherkin
Given I am on the homepage and scrolled down
```

Good:

```gherkin
Given I am on the homepage
And I have scrolled down
```

## Keep test data honest

Prefer asserting on the rule the behavior is supposed to satisfy
rather than a hardcoded value that could drift out from under the
test. `Then results related to the search term are shown` survives a
catalog change; `Then I see "Blue Widget Deluxe v3"` breaks the moment
that exact item is renamed or removed. Where the exact value genuinely
matters, keep it — but don't hardcode incidental values just because
they happened to be on screen when the scenario was written.

## Atomic, independent scenarios

Each scenario must be able to run alone, in any order, without relying
on another scenario's side effects. A `Given` can describe a
precondition state ("Given an item exists") without requiring a prior
scenario to have actually created it during the same run — the state
should be established fresh, not inherited. Independence is also what
makes it possible to run (and debug) a single scenario by itself.

## Cover happy and unhappy paths

Don't stop at the golden path. Most features also need scenarios for
invalid input, empty states, permission failures, or other edge cases
that are actually part of the specified behavior — a feature that only
ever shows success is usually under-specified, not simple. Even a
simple behavior often needs more than one example to pin down — a list
feature usually wants both an empty-list scenario and a populated-list
scenario, not just the one that happens to have data.

A good way to surface a missing scenario while reviewing a draft: for
each Then, ask "does this outcome always follow from this Given/When,
or only sometimes?" A rule like "refunded items are returned to stock"
often turns out to really be "returned to stock, unless faulty" —
the exception is a second scenario, not a footnote in the first one.

## Step count and length

Keep a scenario under roughly 10 steps, and keep each step reasonably
short (many teams cap step text around 80-120 characters). A long
scenario is far more often a symptom of imperative steps or multiple
bundled behaviors than evidence of a genuinely big feature — split it
before accepting the length.
