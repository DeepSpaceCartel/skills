---
name: engineering-practices
description: Time-tested engineering practices for everyday delivery work - project-agnostic: workflows grounded in canonical sources (Fowler, Beck, Google SRE, DORA, OWASP and others). Use when writing or reviewing tests, choosing mocks vs fakes, or chasing flaky tests; diagnosing a bug, crash or intermittent failure; restructuring code or replacing a legacy component incrementally; changing a database schema or backfilling data. Complements core-principles (design heuristics); not for authoring CI workflows, version numbers or changelogs (see github-actions, semver, keepachangelog).
---

# Engineering Practices

Workflows for everyday engineering tasks, each based on long-standing sources
(Fowler, Beck, Google's SRE books, DORA research, OWASP) rather than new ideas.
Each reference leads with what coding agents typically get wrong, then gives a
procedure, techniques, a worked example and a review checklist.

This skill is about *how to do a task*. For judging whether a design is good
(simplicity, coupling, cohesion, failure handling, privilege), use
[`core-principles`](../core-principles/SKILL.md).

## How to use this skill

1. Match the task to a row below and read that one reference, then follow its
   procedure. Don't load them all.
2. Practices compose. A risky schema change needs `database-migrations` and
   `release-engineering`. A refactor of untested code needs the safety-net
   steps first. Read a second reference only when the task crosses into it.
3. Each reference names related practices under **Related**; open one
   (`references/<name>.md`) only when the situation calls for it.

## The catalog

| Practice | Read when | Reference | Anchor sources |
|---|---|---|---|
| Testing | Writing or reviewing tests; choosing unit vs integration; mocks vs fakes; flaky tests; legacy code with no tests | [testing](references/testing.md) | Fowler's bliki, Beck (Test Desiderata), Google Testing Blog, Feathers |
| Debugging | A bug, crash or failing test to diagnose; an intermittent failure; deciding how to reproduce or isolate | [debugging](references/debugging.md) | Zeller (The Debugging Book), Agans, git bisect docs |
| Refactoring | Restructuring code without changing behavior; making a change easy first; replacing a legacy component incrementally | [refactoring](references/refactoring.md) | Fowler (refactoring.com), Beck (Tidy First?), Feathers, the Mikado Method |
| Database migrations | Changing a schema or backfilling data; adding NOT NULL, renaming or dropping a column; indexing a large table | [database-migrations](references/database-migrations.md) | Fowler and Sadalage (evolutionary database design), Stripe, strong_migrations, PostgreSQL docs |

## Working rules shared by every practice

These recur across the references (a synthesis, not a separate source):

1. **Verify, don't assume.** Run the tests, commands or measurements and read the
   output before saying something works, is faster, or is safe. Say plainly what
   you did not verify.
2. **Get a safety net first:** a failing test that reproduces the bug, a baseline
   measurement, a characterization test, or a rollback plan.
3. **Small, reversible steps.** One kind of change per commit or deploy:
   structure vs behavior, schema expand vs contract, flag off vs on.
4. **Change one thing at a time** and observe the result before the next change.
5. **Prefer the additive path** when others depend on what you're changing.

## Related

- [`core-principles`](../core-principles/SKILL.md) — design heuristics and how they conflict.
- [`github-actions`](../github-actions/SKILL.md), [`semver`](../semver/SKILL.md), [`keepachangelog`](../keepachangelog/SKILL.md), [`owasp-asvs`](../owasp-asvs/SKILL.md) — the mechanics and requirements these practices plug into.
