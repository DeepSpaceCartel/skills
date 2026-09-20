# YAGNI — You Aren't Gonna Need It

Don't build capabilities for *presumed* future needs. The practical
question: **Do we actually need this now?**

The rule comes from Extreme Programming (Kent Beck, Ron Jeffries): implement
things when you actually need them, never when you merely foresee that you
will ([Fowler](https://martinfowler.com/bliki/Yagni.html),
[Jeffries](https://ronjeffries.com/xprog/articles/practices/pracnotneed/)).

## Why "cheap to add now" is wrong

Fowler names four costs of a presumptive feature:

1. **Build**: the effort spent on it.
2. **Delay**: the needed feature you didn't build in that time.
3. **Carry**: the complexity it adds to every other change.
4. **Repair**: it turns out wrong once you understand the real need.

Even a correct guess pays the delay and carry costs. Code generation is fast
for an AI agent, but reading, testing and maintaining the result is not.

## Decision procedure

1. **Name the current caller, story, test or requirement** that needs it. If you can't, cut it.
2. **Ask what changing your mind would cost later.**
   - Additive, internal changes are cheap: a new parameter, a new class,
     extracting an interface when a second implementation appears. Defer them.
   - Some things are expensive to retrofit. Decide those now, deliberately:
     public API and wire contracts, persisted data formats and schema,
     authorization boundaries.
3. **Prefer a cheap seam over the feature.** Small functions and injected
   dependencies keep options open; you don't need the plugin system itself.
4. **Put future ideas in a note or issue, not in code.**

## Smells of speculative generality

- An interface, factory or registry with a single implementation or entry
- A parameter, flag or option no caller sets to a non-default value
- Config for values that have never changed
- `Base*`, `Generic*`, `*Manager` classes with one child
- Fallback branches for scenarios no one has observed
- Hooks or callbacks with no subscribers

## Example

```python
# before: built for "other channels someday"
class Notifier(ABC):
    @abstractmethod
    def send(self, to, msg, *, retries=3, channel="email", priority=0): ...
class EmailNotifier(Notifier): ...
NOTIFIERS = {"email": EmailNotifier}
def notify(kind, to, msg, **opts):
    return NOTIFIERS[kind]().send(to, msg, **opts)

# after: what the one caller needs, with the dependency injected
MESSAGES = {"welcome": "Welcome, {name}!"}      # cheap seam for later translation
def send_welcome_email(user, smtp):
    smtp.send(user.email, MESSAGES["welcome"].format(name=user.name))
```

The interface, registry and unused parameters had one implementation and no
callers. The injected `smtp` and the message table stay: they make the code
easier to change and test, and that is *not* speculation.

## What YAGNI does NOT excuse

- **Skipping tests, refactoring or cleanup.** Fowler: YAGNI "requires (and
  enables) malleable code". It presumes changeable code and does not apply to
  effort that makes software easier to modify.
- **Skipping validation at trust boundaries or security controls.** These are
  current requirements, not future features.
- **Refusing a stated requirement**, or hard-coding what the spec already
  says varies.
- **Ignoring things that are costly to retrofit** (see step 2).

## Gotchas

- **Legitimate exceptions:** library and public-API code, where "unused"
  functionality serves external users; test-support hooks; a known upcoming
  requirement (it is then not *presumed*).
- **The precondition matters.** Without tests and a refactoring habit, deferring
  design just produces debt, not simplicity.
- **Not the same as premature optimization.** That is a different
  principle (measure first); don't cite YAGNI for performance choices.
- **Tensions:** the rule of three in `dry` is YAGNI applied to abstraction;
  `defensive-programming` at trust boundaries and `least-privilege` are
  not speculation; `program-to-an-interface` says to add an interface at a
  real seam, not by default.

## Review checklist

1. Can I name the current requirement or caller for each new parameter, option, interface or hook?
2. Does any abstraction have exactly one implementation with no second use in this change?
3. Would adding this later be a cheap, additive, internal change?
4. Did I keep the tests, validation and security checks the current behavior needs?
5. Are the retrofit-expensive decisions (public contract, schema, auth boundary) made deliberately?

## Related

- `kiss` — simplify what *is* needed.
- `program-to-an-interface` — when a seam is warranted.
- `dry` — the rule of three.
