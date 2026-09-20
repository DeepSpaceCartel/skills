---
name: core-principles
description: Core software design principles for writing, refactoring and reviewing code - project-agnostic. Covers KISS, DRY, YAGNI, Separation of Concerns, Single Responsibility, High Cohesion, Low Coupling, Composition over Inheritance, Information Hiding, Encapsulation, Program to an Interface, Fail Fast, Explicitness, Least Surprise, Least Privilege and Defensive Programming, with a symptom-to-principle lookup, tie-breakers for when they conflict, and one detailed reference per principle. Use when reviewing or planning a design, when asked "is this over-engineered?" or "which principle applies?", or when one change edits many files, a class changes for unrelated reasons, logic can't be tested without a DB, callers depend on internals or vendor types, a subclass is fragile, errors are swallowed or surface far from their cause, objects can reach invalid states, names or behavior surprise readers, an IAM role, grant or token is broader than needed, or remote calls lack timeouts.
---

# Core Principles

Sixteen design heuristics for writing and reviewing code, each with its own
reference. This page helps you pick the right one and reconcile them when they
disagree.

Principles are heuristics, not laws. Fowler notes smells "don't always indicate
a problem", and North's *CUPID* frames properties as a direction of travel, not
compliance checks. Complexity is the common enemy (Ousterhout): ask of any
choice *"what does this make cheaper or costlier to change?"*

## How to use this skill

1. Identify the task (design, write, refactor, review) and what you observe.
   Skip the references for plain bug fixes, routine readability refactors
   (extracting a function, flattening nested conditionals into early returns),
   performance tuning, and choosing between design patterns: no principle is
   at stake.
2. Find it in **Symptom to principle** or the **catalog** below, and read only
   the one or two matching files in `references/`. Don't load all sixteen.
   Each reference names its neighbouring principles under **Related**; open
   one of those (`references/<name>.md`) only if the situation calls for it.
3. If two principles pull in opposite directions, read **When principles
   conflict** before deciding.
4. In review, cite the concrete cost, not the acronym (see **Using principles
   in review**).

## The catalog

| Principle | The practical question | Read when | Reference |
|---|---|---|---|
| KISS | Can I remove complexity? | Code feels over-engineered or hard to follow; clever vs plain | [kiss](references/kiss.md) |
| DRY | If this rule changes, how many places must I modify? | One change means edits in many places; before extracting a helper or writing code that may already exist | [dry](references/dry.md) |
| YAGNI | Do we actually need this now? | Asked to be "future-proof" or "extensible"; hooks, options or abstractions for hypothetical needs | [yagni](references/yagni.md) |
| Separation of Concerns | Does this component have one conceptual job? | I/O mixed with business rules; logic untestable without a DB, network or UI; structuring a feature | [separation-of-concerns](references/separation-of-concerns.md) |
| Single Responsibility | Why would this code need to change? | A class changes for unrelated reasons; one stakeholder's change breaks another's; teams collide in a file | [single-responsibility](references/single-responsibility.md) |
| High Cohesion | Does everything here belong together? | A `utils`/`helpers`/`Manager` grab-bag; a feature scattered across folders; deciding where code lives | [high-cohesion](references/high-cohesion.md) |
| Low Coupling | How much breaks if I change this? | A change ripples across modules or services; heavy mocking; a shared common module; a new cross-module dependency | [low-coupling](references/low-coupling.md) |
| Composition over Inheritance | Can I compose this instead of subclassing? | About to subclass mainly to reuse code; a matrix of variants; an override breaks the parent's assumptions | [composition-over-inheritance](references/composition-over-inheritance.md) |
| Information Hiding | What does the caller actually need to know? | Callers depend on a dependency's types, errors or format; designing a module's public interface | [information-hiding](references/information-hiding.md) |
| Encapsulation | Can invalid states be prevented here? | Objects can reach invalid states; callers must call methods in order; a getter returns a mutable list | [encapsulation](references/encapsulation.md) |
| Program to an Interface | Can I replace the implementation without changing callers? | Swapping a DB or vendor; a fake for something slow or flaky; an interface mirroring one class | [program-to-an-interface](references/program-to-an-interface.md) |
| Fail Fast | Can this error be caught at the boundary? | Silent skips or defaults; swallowed exceptions; bugs surfacing far from their cause; a new entry point | [fail-fast](references/fail-fast.md) |
| Explicitness | Would another engineer understand this without tribal knowledge? | Hidden env, clock or global reads; implied units; effects a name doesn't show; framework magic | [explicitness](references/explicitness.md) |
| Least Surprise | Would a maintainer predict what this does? | Naming or designing an API; a function does more or less than its name says; mutated arguments | [least-surprise](references/least-surprise.md) |
| Least Privilege | What happens if this component is compromised? | IAM, RBAC, DB grants, CI tokens, container users; the quick fix is admin, `*` or root; agent tool access | [least-privilege](references/least-privilege.md) |
| Defensive Programming | What happens when input or a dependency is bad? | Remote calls, files, third-party or LLM output; timeouts and retries; untrusted input | [defensive-programming](references/defensive-programming.md) |

## Symptom to principle

Start from what you observe, then open the named reference.

| Symptom | Look at |
|---|---|
| One change edits many files *because the same fact is restated* (a new status or type needs an enum, a validator, a UI list, a DB check and docs) | [dry](references/dry.md) |
| One change edits many files *because one feature's code is scattered* across folders or layers (shotgun surgery) | [high-cohesion](references/high-cohesion.md) |
| One change edits many files *because modules depend on each other's internals* | [low-coupling](references/low-coupling.md), [information-hiding](references/information-hiding.md) |
| One class changes for unrelated reasons (divergent change) | [single-responsibility](references/single-responsibility.md), [separation-of-concerns](references/separation-of-concerns.md) |
| A change requested by one team or department (finance, HR, ops) breaks another's feature or report | [single-responsibility](references/single-responsibility.md) |
| Every stage of a read/parse/validate/write pipeline must change whenever a format or schema changes | [information-hiding](references/information-hiding.md) |
| Missing or malformed config, env vars or startup inputs | [fail-fast](references/fail-fast.md) |
| "Is this over-engineered?", or a design review with no specific symptom | [kiss](references/kiss.md), [yagni](references/yagni.md) |
| A shared helper grows flags or `if caller == X` branches | [dry](references/dry.md) (wrong abstraction: inline it) |
| An unused parameter, hook, or interface with one implementation (speculative generality) | [yagni](references/yagni.md), [kiss](references/kiss.md) |
| A method uses another class's data more than its own (feature envy) | [high-cohesion](references/high-cohesion.md), [encapsulation](references/encapsulation.md) |
| Tests need heavy mocking | [low-coupling](references/low-coupling.md), [program-to-an-interface](references/program-to-an-interface.md) |
| Business logic can't be tested without a DB or network | [separation-of-concerns](references/separation-of-concerns.md) |
| A bug surfaces far from its cause | [fail-fast](references/fail-fast.md) |
| A silent `catch` or default value hides failures | [fail-fast](references/fail-fast.md), [defensive-programming](references/defensive-programming.md) (over-tolerance) |
| Callers must call methods in a fixed order | [encapsulation](references/encapsulation.md), [least-surprise](references/least-surprise.md) |
| The reviewer needs the author to explain it | [explicitness](references/explicitness.md), [least-surprise](references/least-surprise.md) |
| Callers depend on a concrete type, ORM row or vendor exception | [information-hiding](references/information-hiding.md), [program-to-an-interface](references/program-to-an-interface.md) |
| A subclass overrides a method and breaks the parent's assumptions | [composition-over-inheritance](references/composition-over-inheritance.md) |
| A tiny class or method only delegates (shallow module) | [kiss](references/kiss.md), [high-cohesion](references/high-cohesion.md) |
| Writing or reviewing an IAM policy, role, grant or token scope; a service, token or agent has more access than it uses | [least-privilege](references/least-privilege.md) |
| A function behaves differently from its name, or mutates its arguments | [least-surprise](references/least-surprise.md) |
| The same validation is scattered through internal layers | [defensive-programming](references/defensive-programming.md), [kiss](references/kiss.md) |
| Changing internals breaks unknown consumers | [information-hiding](references/information-hiding.md), [low-coupling](references/low-coupling.md) |
| A hierarchy mirrors another hierarchy (parallel inheritance) | [composition-over-inheritance](references/composition-over-inheritance.md) |
| A remote call can hang, or a bad reply is trusted | [defensive-programming](references/defensive-programming.md) |
| A `utils`/`helpers` file keeps growing | [high-cohesion](references/high-cohesion.md) |

## When principles conflict

| Tension | Usual tie-breaker |
|---|---|
| **DRY vs low coupling / YAGNI**: two similar snippets merged into a shared helper couple unrelated callers | Wait for the third occurrence; duplication is cheaper than the wrong abstraction. If the helper accretes flags, inline it back |
| **KISS vs defensive programming**: every extra guard adds code paths | Validate at trust boundaries, trust internal callers, and prefer designs where the error cannot occur |
| **Fail fast vs defensive programming**: crash loudly or degrade gracefully? | Fail fast on bugs and violated invariants; handle expected environmental failures. If no caller can respond meaningfully, crash |
| **Program to an interface vs YAGNI / KISS**: one implementation is speculative generality | Add the interface at a real seam (I/O boundary, second implementation, needed test double), not by default |
| **SRP vs high cohesion** when over-split: one responsibility scattered over many tiny classes | Split by reasons that change *together*, not by grammatical "and"; prefer deep modules to shallow ones |
| **Encapsulation / information hiding vs explicitness**: hidden behavior is hard to debug | Hide representation, not effects. Cost, side effects and failure modes belong in the interface or its docs |
| **Composition vs DRY**: inheritance is the cheapest reuse | Default to composition; inherit only for a true is-a with a stable base you control |
| **Least privilege vs KISS / usability**: fine-grained permissions add friction | Scale strictness with blast radius: strict for credentials, tokens and CI, pragmatic for low-impact internals; deny by default |
| **Explicitness vs least surprise / idiom**: spelling out everything fights convention | Follow the local convention; make the non-obvious explicit |
| **Separation of concerns / low coupling vs KISS**: layers cost a hop each | Separate along real axes of change; grow from a simple working system |
| **DRY vs explicitness in tests**: shared helpers hide the scenario | Reader clarity wins in tests |

## Prioritizing

1. **Correctness and simplicity first.** Beck's order: passes tests, reveals
   intention, no duplication, fewest elements. Intent outranks DRY.
2. **Cost of change is the currency.** Prefer what makes the likely next change
   cheaper. Don't pay for changes you can't name ([yagni](references/yagni.md)).
3. **Reversibility.** Structure inside a module is cheap to change; public APIs,
   data schemas and security boundaries are not. Deliberate on those, tidy the
   rest quickly.
4. **Blast radius outranks elegance** for least privilege, fail fast and
   defensive programming, where damage is large or irreversible.
5. **Code lifetime.** Throwaway code: don't abstract. Long-lived or public code:
   invest in information hiding and stable interfaces (Hyrum's Law bites at scale).
6. **Proportion.** A bug fix gets proportionate scrutiny, not a redesign.

## Using principles in review

- **Cite the concrete cost, not the acronym.** Say "adding a payment type touches
  six files", not "violates OCP". The acronym invites debate; the cost invites a fix.
- **Mind the AI cargo-cult failure modes** (heuristic, not measured): extracting a
  helper after two occurrences, an interface or factory for one implementation,
  internal try/catch and null checks, config knobs nobody asked for, many tiny
  classes, gold-plating a small change, and "fixing" nearby code that wasn't asked
  about.
- **Don't resolve a DRY-vs-clarity clash by adding duplication alone;** that
  usually masks a deeper design problem.
- **Justify a deliberate violation** with a one-line comment stating the principle
  bent, the cost avoided and the trigger to revisit ("duplicated intentionally;
  revisit at a third use"). For architectural choices, write an ADR (see
  [`adr`](../adr/SKILL.md)).

## Related

- [`adr`](../adr/SKILL.md) — record a deliberate, hard-to-reverse trade-off.
- [`owasp-asvs`](../owasp-asvs/SKILL.md) — where least privilege and defensive programming become concrete security requirements.
- [`github-actions`](../github-actions/SKILL.md), [`container-images`](../container-images/SKILL.md) — least privilege applied to CI and images.
