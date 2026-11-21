# Tests at scale and monorepo migration

Running many tests correctly under a build system (sizes, timeouts, sharding, flaky retries,
cached results, what breaks caching), then growing a Python monorepo to include Go and Rust
under one build and migrating to it one target at a time. Anchor sources: Bazel's
[test encyclopedia](https://bazel.build/reference/test-encyclopedia),
[common definitions](https://bazel.build/reference/be/common-definitions),
[user manual](https://bazel.build/docs/user-manual),
[external dependencies](https://bazel.build/external/overview) and
[Maven migration](https://bazel.build/migrate/maven) pages; the
[rules_python](https://rules-python.readthedocs.io/en/latest/getting-started.html),
[rules_go](https://github.com/bazel-contrib/rules_go) and
[rules_rust](https://bazelbuild.github.io/rules_rust/) docs; Buck2's
[Why Buck2](https://buck2.build/docs/about/why/) and
[language support](https://buck2.build/docs/about/language_support/) pages.

## What agents typically get wrong

- **Marking tests `flaky = True` and moving on.** Bazel runs such a test up to three times and
  calls it failed only if every run fails; its docs call the attribute generally discouraged.
- **Raising timeouts to make failures go away.** A test that needs 15 minutes is a `large` test;
  a unit test that needs it has a bug or a hidden dependency.
- **Setting `shard_count` on a runner that doesn't speak the sharding protocol.** Then, per
  Bazel's docs, each shard most likely runs every test.
- **Tests that write to `$HOME`, `/tmp` fixed paths, or the runfiles tree,** or read variables
  the runner does not set. They pass alone and fail in parallel or remotely.
- **Network in a cached test.** A test that calls a live service has a result that depends on
  the day; tag it `external` so it always runs and is never served from cache.
- **Migrating the whole repo at once,** or deleting the old build before the new one matches it.
- **Writing every BUILD file by hand** when Gazelle can generate them for Go (and, through a
  plugin, Python).
- **Copying WORKSPACE-era setup.** Current Bazel uses Bzlmod (`MODULE.bazel`); WORKSPACE was
  replaced between Bazel 6 and 9.

## Procedure

**Making a test suite cache- and shard-friendly**

1. Give each test target a `size` that matches what it does (unit `small`, integration
   `medium`, end-to-end `large`/`enormous`). Override `timeout` only when needed.
2. Run with `--test_verbose_timeout_warnings` to find tests whose size is set too large.
3. Make tests read inputs only from declared files (runfiles) and write only to
   `TEST_TMPDIR` or `TEST_UNDECLARED_OUTPUTS_DIR`.
4. Tag tests that need the outside world `external`; tag tests that cannot share a machine
   `exclusive` (which also disables remote execution for them).
5. Shard large targets with `shard_count` (up to 50) only if the runner reads
   `TEST_TOTAL_SHARDS` and `TEST_SHARD_INDEX` and touches `TEST_SHARD_STATUS_FILE`.
6. Find flaky tests with `--runs_per_test=N` (the `regex@N` form targets a few). Fix them; use
   `flaky` or `--flaky_test_attempts` (at most 10) only as a tracked, temporary measure.
7. Leave `--cache_test_results` at `auto` (the default); `-t-` forces a rerun.

**Migrating incrementally** (Bazel's Maven guide, generalized)

1. Keep the existing build and CI working; run both side by side until the new one is trusted.
2. Start coarse: one target that builds a whole project, and confirm it builds.
3. Split into finer targets in stages, starting with packages that have the fewest
   dependencies; build everything after each step.
4. Restrict visibility as you split, so internals do not become public API by accident.
5. Remember `glob()` stops at package boundaries: a new BUILD file shrinks its parent's glob.
6. Move CI to the new build per package once outputs and test results match.
7. A synthesis, not a sourced step: an existing tool can be wrapped in a rule as a first, coarse
   target, but it is not hermetic, so keep it out of the shared cache (`no-remote` tag) until
   it is replaced by real rules.

## Techniques

**Test sizes and timeouts (Bazel)**

| `size` | Typical test | Default `timeout` | Seconds | Suggested minimum |
|---|---|---|---|---|
| small | Unit | short | 60 | 0 |
| medium (default) | Integration | moderate | 300 | 30 |
| large | End-to-end | long | 900 | 300 |
| enormous | End-to-end | eternal | 3,600 | 900 |

The limit applies to the whole test target. `--test_timeout` overrides it.

**The test environment Bazel provides.** `TZ=UTC`, locale variables unset, `HOME` set to
`TEST_TMPDIR`, a fixed `PATH`, `TEST_SRCDIR` for runfiles, `BAZEL_TEST` set. Tests must not run
as root, read stdin, leak processes, or rely on PASS/FAIL text: only the exit code counts.

**Tags that change caching and execution**

| Tag | Effect |
|---|---|
| `external` | Always runs, regardless of `--cache_test_results` |
| `exclusive` | Runs alone, after other tests; no remote execution |
| `no-cache` / `no-remote-cache` | Never cached / never cached remotely |
| `no-remote-exec` / `no-remote` | Never executed remotely / neither remote cache nor execution |
| `local` | No remote cache, no remote execution, no sandbox |
| `requires-network` / `block-network` | Allow / block external network (sandboxed only) |

**What breaks test caching:** timestamps or random seeds baked into inputs, absolute paths,
undeclared data files, variables passed with `--test_env` or `--action_env` that differ per
machine, and stamped values (tests default to `stamp = 0`).

**Polyglot rules**

| Language | Bazel rules | Dependencies | BUILD generation |
|---|---|---|---|
| Python | rules_python: `py_library`, `py_binary`, `py_test` (Starlark rules on Bazel 7+) | `pip.parse` reads a requirements lock into a hub repo (`@pypi//pkg`) | Gazelle plugin (provided as is) |
| Go | rules_go: `go_library`, `go_binary`, `go_test`; downloads its own Go SDK; v0.65.0+ needs Bazel 7.7.0 or later and Go 1.20 or later | Go modules through Gazelle's `go_deps` extension (see "Go with Bzlmod") | Gazelle |
| Rust | rules_rust: `rust_library`, `rust_binary` (a `rust_test` rule is unverified here); `rust.toolchain` pins the version; tested from Bazel 7.4.1 | crate_universe `crate.from_cargo` reads `Cargo.toml` and `Cargo.lock` | Generated macros (`all_crate_deps`) |

Buck2's prelude has built-in rules for Python, Go and Rust (rated easy to set up) and for C++
(rated complex).

**Bazel versus Buck2, as their docs describe them**

| Aspect | Bazel | Buck2 |
|---|---|---|
| Rules language | Starlark | Starlark; all rules live in the prelude, the same internally and in open source |
| Graph | Not described in the fetched Bazel pages | One incremental graph with no separate target and action phases, on its DICE engine; Buck2's docs say most of its differences from Buck1 also set it apart from Bazel |
| Remote execution | REAPI client; cache and execution optional | REAPI client; "remote execution first", local is a special case |
| File system | Not covered in the fetched pages | Works on a normal file system; can integrate with the Eden virtual file system |
| Dependencies | Bzlmod modules from the Bazel Central Registry, MVS resolution, lockfile | Not covered in the fetched pages |
| Maturity | Not stated in the fetched pages; rule sets cited here (rules_python, rules_go, rules_rust) and the Bazel Central Registry exist | Self-described "early-stage"; open-source RE "may be less polished"; toolchains not open-sourced |
| Implementation | Not covered in the fetched pages | Rust, language-agnostic core |

## Example

A minimal Python library with a test under Bazel and Bzlmod. **Untested:** Bazel is not
installed here. Snippets follow the rules_python getting-started page; the
`py_library.bzl`/`py_test.bzl` load paths follow its documented
`@rules_python//python:<name>.bzl` pattern.

```starlark
# MODULE.bazel
module(name = "crawler", version = "0.1.0")

bazel_dep(name = "rules_python", version = "0.0.0")  # set to the latest release

pip = use_extension("@rules_python//python/extensions:pip.bzl", "pip")
pip.parse(
    hub_name = "pypi",
    python_version = "3.14",          # configure the runtime per rules_python's docs
    requirements_lock = "//:requirements.txt",
)
use_repo(pip, "pypi")
```

```starlark
# urlnorm/BUILD.bazel
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "urlnorm",
    srcs = ["urlnorm.py"],
    visibility = ["//:__subpackages__"],
)

py_test(
    name = "urlnorm_test",
    size = "small",
    srcs = ["urlnorm_test.py"],
    deps = [":urlnorm", "@pypi//pytest"],
)
```

Commit `MODULE.bazel.lock` and `.bazelversion` with them. A Rust service joins with
`bazel_dep(name = "rules_rust", ...)`, `rust.toolchain(...)` and `crate.from_cargo(...)` in the
same `MODULE.bazel`. The test runs `urlnorm_test.py` directly, so the file must call pytest
itself (for example `sys.exit(pytest.main([__file__]))`); that wiring is not from a fetched page.

## Gotchas and contested points

- **Retries hide real bugs.** SWE ch. 23 describes retries and pulling flaky tests from
  pre-merge runs as stopgaps with tracked bugs, not a fix.
- **Exclusive and external tests serialize or rerun,** so a suite full of them gets little
  from the build system.
- **pytest inside Bazel** (unverified): each test target is its own process, so a session-scoped
  fixture is set up once per target, not once per suite. Group tests into targets with that in mind.
- **Crate repinning.** crate_universe needs a repin (`CARGO_BAZEL_REPIN=1 bazel sync --only=crates`)
  before the first build and after `Cargo.toml` changes.
- **rules_go's main branch** is only guaranteed with the latest Bazel; pin a release.

## Review checklist

1. Does every test target have a `size` that matches what it does, without inflated timeouts?
2. Do tests read only declared inputs and write only to `TEST_TMPDIR` or the undeclared-outputs directory?
3. Are networked tests tagged `external`, and is everything else network-free?
4. Is sharding used only with a runner that implements the protocol?
5. Is every `flaky` attribute or retry flag linked to a tracked fix?
6. Are dependencies declared with Bzlmod, with the lockfile and Bazel version committed?
7. Does the migration keep the old build until the new one matches, moving leaf packages first?
8. Are Go and Rust toolchains pinned through their rules, not taken from the host?

## Related

[build-principles-and-adoption](build-principles-and-adoption.md),
[hermeticity-and-reproducibility](hermeticity-and-reproducibility.md),
[remote-cache-and-execution](remote-cache-and-execution.md),
[`engineering-practices`](../../engineering-practices/SKILL.md) (testing: flaky-test diagnosis),
[`github-actions`](../../github-actions/SKILL.md) (CI jobs that call the build).

## Sources

Bazel: [Test encyclopedia](https://bazel.build/reference/test-encyclopedia),
[Common definitions](https://bazel.build/reference/be/common-definitions),
[User manual](https://bazel.build/docs/user-manual),
[External dependencies overview](https://bazel.build/external/overview),
[Lockfile](https://bazel.build/external/lockfile),
[Migrating to Bazel](https://bazel.build/migrate) and [from Maven](https://bazel.build/migrate/maven).
rules_python [docs](https://rules-python.readthedocs.io/) and
[getting started](https://rules-python.readthedocs.io/en/latest/getting-started.html);
rules_go [README](https://github.com/bazel-contrib/rules_go);
rules_rust [docs](https://bazelbuild.github.io/rules_rust/) and
[crate_universe with Bzlmod](https://bazelbuild.github.io/rules_rust/crate_universe_bzlmod.html).
Buck2: [Why Buck2](https://buck2.build/docs/about/why/),
[Language support](https://buck2.build/docs/about/language_support/).
*Software Engineering at Google* [ch. 23](https://abseil.io/resources/swe-book/html/ch23.html)
(CC BY-NC-ND 4.0, paraphrased). `https://buck2.build/docs/about/benefits/` returned 404.
