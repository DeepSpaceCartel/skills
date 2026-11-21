# Build principles and adoption

What a build system buys (correctness through hermeticity, incrementality, caching, parallelism,
reproducibility), how artifact-based builds differ from task-based ones, and the decision to
adopt Bazel or Buck2, with the cheaper steps that usually come first. Anchor sources: Bazel's
[artifact-based builds](https://bazel.build/basics/artifact-based-builds) and
[hermeticity](https://bazel.build/basics/hermeticity) pages, *Software Engineering at Google*
[ch. 18](https://abseil.io/resources/swe-book/html/ch18.html) (CC BY-NC-ND 4.0, paraphrased),
Buck2's [Why Buck2](https://buck2.build/docs/about/why/), and the
[pytest fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html) and
[pytest-xdist](https://pytest-xdist.readthedocs.io/en/stable/distribution.html) docs.

## What agents typically get wrong

- **Recommending Bazel for a slow test suite before profiling it.** If 80% of the time is
  per-test setup, a build system caches whole test targets but still pays that setup on every
  miss. Fix the setup first.
- **Treating caching as the feature.** Caching is only safe because each step's declared inputs
  determine its outputs. Without that, a cache serves stale or wrong results quickly.
- **Assuming a task runner (Make, npm scripts, Gradle tasks, tox) gives the same guarantees.**
  A task-based tool cannot see what a script reads or writes, so it cannot safely skip,
  parallelize or share its work (SWE ch. 18).
- **Big-bang migration.** Rewriting every package's build at once, with the old build deleted,
  leaves nothing to compare against.
- **Ignoring the ongoing cost.** BUILD files, rule upgrades, IDE integration, a cache service
  and someone who understands it are a permanent line item, not a one-off.
- **One giant target.** A single target for the whole repo gets no incrementality: every
  change invalidates it. Fine-grained targets are where the speed comes from.
- **Making shared fixtures broader without making them read-only.** A session-scoped database
  that one test mutates makes later tests order-dependent.
- **Running `pytest -n auto` and assuming session fixtures run once.** Each xdist worker is its
  own session and runs session-scoped fixtures again.

## Procedure

**Deciding whether to adopt**

1. Measure. Wall time of the slowest CI job, split into setup, test bodies, dependency install,
   compile and waiting. `pytest --durations=10 --durations-min=1.0` lists the slowest tests.
2. If per-test setup dominates, apply the cheaper steps below and measure again.
3. If install or compile dominates and inputs rarely change, use a CI cache keyed on the
   lockfile hash (see [`github-actions`](../../github-actions/SKILL.md)).
4. Consider an artifact-based build system when most of these hold (a synthesis, not a sourced
   threshold): several languages in one repo; many packages where a change touches a few;
   CI time growing with repo size rather than with the change; repeated "works on my machine"
   failures; and someone who will own the build.
5. If adopting, start with one leaf package, keep the old build, and compare outputs
   ([tests-and-monorepo-migration](tests-and-monorepo-migration.md)).

**The cheaper steps, in order**

1. **Widen fixture scope** for expensive, read-only setup: `scope="module"` or
   `"session"` (pytest). Keep state changes inside the test, with per-test rollback or a fresh
   schema per worker.
2. **Parallelize** with pytest-xdist: `-n auto` uses one worker per physical core. Pick
   `--dist loadscope` or `loadfile` so tests that share a module-level fixture stay on one
   worker; `worksteal` handles uneven durations.
3. **Make session fixtures run once across workers** when they must (a lock file in the
   directory from `tmp_path_factory.getbasetemp().parent`, per the xdist how-to), or give each
   worker its own copy keyed on `worker_id`.
4. **Split slow tests from fast ones.** Fast, reliable tests run before merge; slow and less
   deterministic ones after (SWE ch. 23).
5. **Cache what CI rebuilds:** virtualenvs and package downloads keyed on the lockfile.
6. **Test only what changed**, by path or by dependency graph. This is where a build system
   starts paying, because it knows the graph.

## Techniques

| Property | What it means | What gives it |
|---|---|---|
| Hermeticity | Same source and configuration give the same output, whatever is on the host | Pinned tools and dependencies, content hashes, sandboxed actions |
| Incrementality | Rebuild only what depends on a change; never a stale result | Declared inputs per action, fine-grained targets |
| Caching | Reuse an action's outputs when its inputs hash the same | Hermetic actions; a local disk cache, then a shared one |
| Parallelism | Run independent actions at once | A known action graph; actions that cannot see each other |
| Reproducibility | Anyone can rebuild bit-identical artifacts | All of the above, plus no timestamps or host paths in outputs |

- **Artifact-based, not task-based.** Bazel's BUILD files declare targets, their sources and
  dependencies; the tool decides the commands. Each step behaves like a pure function from
  inputs (including the compiler) to outputs, which is what makes skipping and parallelism
  safe. Bazel's page reports that parallelism alone can give an order-of-magnitude speed-up on
  multicore machines.
- **Tools are dependencies.** A compiler or interpreter version change rebuilds what used it.
- **Small targets.** Fine-grained modules improve caching, parallelism and test selection at
  the cost of more BUILD files; tooling (Gazelle for Go and Python) generates many of them.
- **Strict, explicit dependencies.** Declare what you use directly; private visibility by
  default; external versions pinned in source control, not "latest" (SWE ch. 18).

**What adoption costs** (synthesis):

| Cost | Notes |
|---|---|
| Learning Starlark, the rules, the query language | Days for users, weeks for the owner |
| Writing and maintaining BUILD files | Generators help; hand edits remain |
| Ecosystem gaps | Language rules lag their native tools (packaging, editors, plugins) |
| Services | A cache, later executors, their storage, network and on-call |
| Two builds during migration | The old one stays until the new one is trusted |

## Example

A 3,000-test Python suite on CI takes 44 minutes. Profiling: each test creates a database
schema and loads fixtures, 0.8 s per test; test bodies average 0.08 s.

| Step | Arithmetic | Wall time |
|---|---|---|
| Today | 3,000 x (0.8 + 0.08) s = 2,640 s | 44 min |
| Schema once per module (150 modules), rollback per test at 0.02 s | 150 x 0.8 + 3,000 x (0.02 + 0.08) = 120 + 300 = 420 s | 7 min |
| `pytest -n 8 --dist loadscope`, modules spread over 8 workers | about 420 / 8, plus worker start-up | about 1 min |

A build system's test cache would skip unchanged test targets, but each missed target would
still pay its share of the 0.8 s-per-test setup. The fixture change gave a 6x speed-up before any tool changed. Both arithmetic
rows were checked by hand; the eight-way figure assumes modules of similar size and is an
estimate, not a measurement.

## Gotchas and contested points

- **Bazel or Buck2 for small teams.** SWE ch. 18 argues artifact-based builds help small
  projects too; the costs above argue the other way for one-language repos with a fast native
  tool. Decide from measurements, not fashion.
- **Wider fixtures trade isolation for speed.** Each test must leave shared state as it found
  it, or tests become order-dependent; see `engineering-practices` testing.
- **xdist `-n auto` counts physical cores,** which may over- or under-subscribe a CI container
  with a CPU limit. Set `-n` explicitly there.
- **Buck2 calls itself early-stage software** in its own docs, with a less polished open-source
  remote execution and toolchains that are not open-sourced (see
  [tests-and-monorepo-migration](tests-and-monorepo-migration.md)).

## Review checklist

1. Is there a measurement showing where the time goes, and does the proposal target that part?
2. Have fixture scope, parallel workers and CI caches been tried or ruled out with numbers?
3. Are shared fixtures read-only, or reset per test, so order does not matter?
4. If a build system is proposed, are several of the adoption conditions true, with an owner named?
5. Are targets fine-grained enough that a typical change invalidates a small part of the graph?
6. Are tools and third-party versions declared and pinned, not taken from the host?
7. Does the migration plan keep the old build running and compare results?
8. Are the ongoing costs (services, upgrades, people) written down next to the expected savings?

## Related

[hermeticity-and-reproducibility](hermeticity-and-reproducibility.md),
[remote-cache-and-execution](remote-cache-and-execution.md),
[tests-and-monorepo-migration](tests-and-monorepo-migration.md),
[`engineering-practices`](../../engineering-practices/SKILL.md) (testing, performance),
[`adr`](../../adr/SKILL.md) (record the adoption decision).

## Sources

Bazel: [Artifact-Based Build Systems](https://bazel.build/basics/artifact-based-builds),
[Hermeticity](https://bazel.build/basics/hermeticity).
*Software Engineering at Google*,
[ch. 18 Build Systems and Build Philosophy](https://abseil.io/resources/swe-book/html/ch18.html) and
[ch. 23 Continuous Integration](https://abseil.io/resources/swe-book/html/ch23.html), both
CC BY-NC-ND 4.0 per the pages, paraphrased only.
Buck2: [Why Buck2](https://buck2.build/docs/about/why/).
pytest: [fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html),
[usage](https://docs.pytest.org/en/stable/how-to/usage.html) (`--durations`).
pytest-xdist: [distribution](https://pytest-xdist.readthedocs.io/en/stable/distribution.html),
[how-to](https://pytest-xdist.readthedocs.io/en/stable/how-to.html).
