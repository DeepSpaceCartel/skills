---
name: build-systems
description: Fast, correct builds and tests with an artifact-based build system - project-agnostic. Covers what hermeticity, incrementality, caching and reproducibility buy; when to adopt Bazel or Buck2 and the cheaper steps first (fixture scope, pytest-xdist, CI caches); pinned toolchains, lockfiles, sandboxing, network-free actions and stamping; remote caching and execution over the Remote Execution API, self-hosted versus managed, cache poisoning and cost; test sizes, timeouts, sharding, flaky retries and what breaks cache hits; polyglot monorepos with rules_python, rules_go, rules_rust or Buck2, Bzlmod, and incremental migration. Use when a build or test suite is slow, when considering Bazel, Buck2 or remote execution, setting up a remote cache, making builds hermetic, or adding Go or Rust services to one build. Not for CI workflow YAML (see github-actions), container image builds (see container-images), test design or flaky-test diagnosis in general (see engineering-practices), or version numbers (see semver).
---

# Build Systems

Getting fast builds and tests *without* giving up correctness: declare what to build, let the
tool work out how, and reuse every result whose inputs have not changed. The references are
grounded in the Bazel docs, the Remote Execution API, the Buck2 docs, the rules_python,
rules_go and rules_rust docs, *Software Engineering at Google* (ch. 18 and 23), the
Reproducible Builds definition, and the pytest and pytest-xdist docs. Each leads with what
agents get wrong, then gives a procedure, a worked example and a numbered review checklist.

The skill is about the **build graph and where actions run**. Test design, mocks and general
flaky-test diagnosis belong to [`engineering-practices`](../engineering-practices/SKILL.md)
(testing). CI workflow files belong to [`github-actions`](../github-actions/SKILL.md); image
builds to [`container-images`](../container-images/SKILL.md).

## How to use this skill

1. Find the task or symptom below and read that one reference. Don't load all four.
2. **Before recommending Bazel or Buck2, read
   [build-principles-and-adoption](references/build-principles-and-adoption.md)** and measure.
   A suite that is slow because of per-test setup is usually fixed in the test code first.
3. Before turning on a shared cache or remote execution, run the checklist of
   [hermeticity-and-reproducibility](references/hermeticity-and-reproducibility.md). A shared
   cache of a non-hermetic build serves wrong results to everyone.
4. Say what you did not run. Build files written without the tool installed are marked untested.

## The catalog

| Topic | Read when | Reference |
|---|---|---|
| Principles and adoption | Slow build or test suite; "should we use Bazel or Buck2?"; costs of adopting; the cheaper steps first | [build-principles-and-adoption](references/build-principles-and-adoption.md) |
| Hermeticity and reproducibility | Builds differ between machines; pinning toolchains and dependencies; lockfiles; sandboxing; network in actions; stamping version info | [hermeticity-and-reproducibility](references/hermeticity-and-reproducibility.md) |
| Remote cache and execution | Setting up a shared cache or remote execution; REAPI concepts; self-hosted versus managed; who may write; cache poisoning; network and cost | [remote-cache-and-execution](references/remote-cache-and-execution.md) |
| Tests and monorepo migration | Test sizes, timeouts, sharding, flaky retries, cached test results; Python with Go and Rust in one build; Bzlmod; migrating one target at a time; Bazel versus Buck2 | [tests-and-monorepo-migration](references/tests-and-monorepo-migration.md) |

## Symptom to reference

| Symptom or situation | Look at |
|---|---|
| The test suite takes 30+ minutes and most of it is fixture setup or database resets | [build-principles-and-adoption](references/build-principles-and-adoption.md) (cheaper steps) |
| "Let's move to Bazel" with a team of a few people and one language | [build-principles-and-adoption](references/build-principles-and-adoption.md) |
| A clean rebuild on the same commit produces different output hashes | [hermeticity-and-reproducibility](references/hermeticity-and-reproducibility.md) |
| It builds on one laptop and fails on CI, or the other way round | [hermeticity-and-reproducibility](references/hermeticity-and-reproducibility.md) |
| A test downloads from PyPI, calls a live API, or reads `$HOME` | [hermeticity-and-reproducibility](references/hermeticity-and-reproducibility.md), then [tests-and-monorepo-migration](references/tests-and-monorepo-migration.md) |
| Version strings or build timestamps embedded in binaries | [hermeticity-and-reproducibility](references/hermeticity-and-reproducibility.md) (stamping) |
| A remote cache is configured but hits are low on CI or between developers | [remote-cache-and-execution](references/remote-cache-and-execution.md) (debugging misses) |
| Choosing between a self-hosted cache in the cluster and a managed service | [remote-cache-and-execution](references/remote-cache-and-execution.md) |
| Developer laptops can write to the shared cache | [remote-cache-and-execution](references/remote-cache-and-execution.md) (security) |
| Tests time out, are sharded badly, or are retried until green | [tests-and-monorepo-migration](references/tests-and-monorepo-migration.md) |
| A Go or Rust service joins a Python monorepo | [tests-and-monorepo-migration](references/tests-and-monorepo-migration.md) |

## Working rules shared by every reference

A synthesis of the sources, not a separate source:

1. **Measure before choosing a tool.** Profile where the time goes (setup, compute, waiting,
   network). Fix the biggest cost with the cheapest change that removes it.
2. **Correct first, then fast.** An action may be cached only if its declared inputs fully
   determine its outputs. Every speed-up here depends on that.
3. **Declare everything.** Tools, interpreters, compilers and third-party code are inputs,
   pinned by version and hash. Anything read from the host is a hidden input.
4. **Narrow writers, wide readers.** Trusted CI writes to a shared cache; people read.
5. **Migrate in small steps that keep the old build working** until the new one is trusted.
6. **Never hide a flaky test behind retries for good.** Retries buy time; a tracked fix ends it.

## Bundled script

[`scripts/nondeterminism_diff.py`](scripts/nondeterminism_diff.py) compares two text outputs
of the same step (logs, generated files, `env` dumps from two machines) and classifies each
differing line as a timestamp, home path, temp path, other absolute path, pid or port, random
id, or other; with `--env` it compares two `KEY=VALUE` dumps and flags variables that commonly
leak (HOME, PATH, TZ, locale, TMPDIR). Standard library only. Run it with
`python3 scripts/nondeterminism_diff.py a.txt b.txt [--env]`.

## Related

- [`engineering-practices`](../engineering-practices/SKILL.md): testing (test design, fakes,
  flaky-test diagnosis), performance (measuring before optimizing), security-practices
  (adding dependencies, supply chain).
- [`github-actions`](../github-actions/SKILL.md): CI workflows, caches and runners that call the build.
- [`container-images`](../container-images/SKILL.md): images that may serve as execution platforms.
- [`core-principles`](../core-principles/SKILL.md): least privilege (cache write access), explicitness.
- [`semver`](../semver/SKILL.md): version numbers for what the build stamps.
- [`infrastructure-patterns`](../infrastructure-patterns/SKILL.md), [`system-design`](../system-design/SKILL.md): running a cache or worker pool on Kubernetes and sizing it.
