# Hermeticity and reproducibility

Making every build action depend only on what it declares: pinned toolchains and
dependencies, lockfiles, sandboxed actions, no network inside actions, and stamping that does
not destroy caching. This is the precondition for every cache and for remote execution.
Anchor sources: Bazel's [hermeticity](https://bazel.build/basics/hermeticity),
[sandboxing](https://bazel.build/docs/sandboxing),
[external dependencies](https://bazel.build/external/overview) and
[lockfile](https://bazel.build/external/lockfile) pages,
[Adapting rules for remote execution](https://bazel.build/remote/rules), the
[user manual](https://bazel.build/docs/user-manual) (stamping), and the Reproducible Builds
[definition](https://reproducible-builds.org/docs/definition/) (CC BY-SA 4.0, paraphrased).

## What agents typically get wrong

- **Calling tools from `PATH`.** A `python3`, `go` or `cc` found on the host differs between
  laptops, CI and workers. Bazel's remote-rules guide says to reach tools through toolchain
  rules instead of `PATH` or variables such as `JAVA_HOME`.
- **Pinning direct dependencies only.** Without a lockfile of the full resolved set (with
  hashes), a transitive release changes the build silently.
- **Embedding the time, host or user in outputs.** A timestamp in every binary turns every
  action downstream into a cache miss and makes the artifact unreproducible.
- **Stamping everything.** Version info belongs in release binaries, not in libraries or tests.
- **Letting actions use the network** (pip installs, `curl` in a genrule, a test calling a
  live API). The result depends on the day it ran.
- **Writing into the source tree during a build.** Later builds of other targets see the file.
- **Assuming the sandbox hides the host.** Bazel's sandbox limits writes and exposes declared
  inputs; it does not stop an action reading host files such as `/usr/bin` tools.
- **Disabling the sandbox to "fix" a failure** instead of declaring the missing input.
- **Silent fallback.** If the requested sandbox cannot run (for example in an unprivileged
  container), Bazel may fall back to a weaker strategy unless the strategy is pinned.

## Procedure

**Making a build hermetic**

1. **Toolchains.** Get compilers and interpreters from the build's rules, downloaded at a
   pinned version (rules_go downloads a Go SDK; rules_rust registers the version given to
   `rust.toolchain`; rules_python registers prebuilt runtimes). Never from the host.
2. **Dependencies.** Declare direct dependencies with exact versions, and commit the lockfile:
   `MODULE.bazel.lock` for Bazel modules, a fully pinned requirements lock for pip (`requirements_lock` in rules_python),
   `Cargo.lock`, and Go's module files. Bazel's docs say to commit `MODULE.bazel.lock` and pin the Bazel
   version with Bazelisk and `.bazelversion`, because the lockfile is Bazel-version specific.
3. **CI checks the lockfile, never rewrites it.** Bazel's `--lockfile_mode=error` fails when the
   lockfile is missing or stale instead of updating it (using it for CI is our inference).
4. **Sandbox every action.** On Linux use `--spawn_strategy=linux-sandbox` explicitly so a
   missing sandbox fails loudly. In a container, the docs list a privileged pod, `SYS_ADMIN`
   with an unconfined seccomp profile, `processwrapper-sandbox`, or remote execution.
5. **Block the network** in actions and tests (`block-network` tag, or the linux-sandbox network
   namespace). Fetching belongs in repository rules or module extensions, which run before the
   build and are recorded in the lockfile. Tag a test that truly needs the network `external`.
6. **Remove non-determinism from outputs:** timestamps, build IDs, absolute paths, random
   ordering of files in archives, host names.
7. **Stamp only release binaries** (below).
8. **Prove it** (below), then turn on a shared cache.

**Proving hermeticity**

1. Null build: run the build twice; the second run must rebuild nothing.
2. Same commit, two clean machines: compare output hashes. Any difference is a leak.
3. Compare execution logs between machines (`--execution_log_compact_file`; see
   [remote-cache-and-execution](remote-cache-and-execution.md)).
4. Build in a container that holds only the checkout and a short, explicit tool list; hidden
   host dependencies become errors.
5. Diff logs and `env` dumps from two runs with
   [`scripts/nondeterminism_diff.py`](../scripts/nondeterminism_diff.py).

## Techniques

**Sandbox strategies (Bazel, Linux and macOS)**

| Strategy | Isolation | Use |
|---|---|---|
| `local` (`standalone`) | None; runs in the execroot | Debugging only |
| `processwrapper-sandbox` | A symlink tree of declared inputs; any POSIX system | Fallback where namespaces are unavailable |
| `linux-sandbox` | User, mount, PID, network and IPC namespaces; read-only filesystem outside the sandbox | Preferred on Linux |
| `darwin-sandbox` | Apple `sandbox-exec` | macOS |

Bazel's docs put Linux sandbox overhead at rarely more than a few percent. `--sandbox_debug`
keeps sandbox directories for inspection and fills the disk if left on.

**Network tags.** `block-network` blocks external access except localhost; `requires-network`
allows it. Both take effect only when sandboxing is on.

**Stamping.** `--workspace_status_command` runs a program before each build. Keys starting
`STABLE_` go to `stable-status.txt` and should change rarely (that a change reruns the stamped
actions is our reading, unverified); other keys go to `volatile-status.txt`, which Bazel treats as never changing, so a new
timestamp alone does not trigger rebuilds. `*_binary` rules default to `stamp = -1` (follow
`--stamp`); `*_test` rules default to `stamp = 0`. Pass `--stamp` only for release builds.

**What "reproducible" means** (Reproducible Builds, paraphrased). Hand a stranger your
revision, a description of the environment and the build steps; if their rebuild of the
release artifacts hashes the same as yours, byte for byte, the build is reproducible. Record
only the environment details that change the result (tool and dependency versions, flags,
variables such as the locale), and keep that list short. Side outputs such as logs don't count.

**Common leaks and fixes**

| Leak | Fix |
|---|---|
| Host compiler or interpreter | Toolchain rule with a pinned, downloaded tool |
| `pip install` or `go get` at build time | Lockfile plus rules that fetch before the build |
| Timestamps, build IDs | Remove, or move to volatile stamping in release binaries only |
| Absolute paths in outputs | Relative paths; strip or map prefixes in the tool's flags |
| Environment variables | Declare the ones an action needs (Bazel `--action_env`); all others stay out |
| Writing to the source tree | Declare outputs; write only to the action's output directory |
| Host-probing repository rules that build or install | Keep probing there; build in normal rules |

## Example

A crawler's URL-normalising library has a test whose log differs between a laptop and CI.
Two runs of the test and two `env` dumps went through the bundled script:

```text
$ python3 scripts/nondeterminism_diff.py laptop.log ci.log
- [temp path] fixture db created at /tmp/pytest-of-ana/pytest-12/db.sqlite
- [home path] config loaded from /home/ana/.config/crawler.toml
- [timestamp] report generated 2026-11-20 09:14:03
+ [temp path] fixture db created at /tmp/pytest-of-ci/pytest-3/db.sqlite
+ [home path] config loaded from /home/ci/.config/crawler.toml
+ [timestamp] report generated 2026-11-20 11:02:47
$ python3 scripts/nondeterminism_diff.py laptop.env ci.env --env
[env var] CI: '<unset>' -> 'true'
[leaky env var] HOME: '/home/ana' -> '/home/ci'
[leaky env var] PATH: '/usr/bin:/home/ana/.local/bin' -> '/usr/bin'
[leaky env var] TZ: 'Europe/Berlin' -> '<unset>'
```

The fixes: the test reads its config from a declared data file, not `$HOME`; the temp
database goes under `TEST_TMPDIR`; the report drops its timestamp; the runner sets `TZ=UTC` (as
Bazel's test runner does). Both commands were run on these sample files; the script exits 1 on
any difference and 0 on identical inputs.

## Gotchas and contested points

- **Sandboxing disables a tool's own incremental cache** (Bazel docs). Persistent workers win
  speed back with weaker isolation guarantees.
- **Nested sandboxes don't work** for linux-sandbox and darwin-sandbox; Bazel falls back. Inside
  CI containers, prefer remote execution or the processwrapper sandbox to a privileged pod.
- **Hermetic is not reproducible.** Hermetic actions can still embed a timestamp; a
  reproducible artifact also needs deterministic tools.
- **Third-party wheels with native code** may still load host libraries; Bazel's remote-rules
  guide warns against pip installs that depend on host-installed libraries.
- **"Latest" in a dependency spec** looks convenient and makes rollback impossible.

## Review checklist

1. Does every tool an action runs come from a pinned toolchain or declared dependency, not `PATH`?
2. Is the full resolved dependency set locked with hashes and committed, and does CI fail on a stale lock?
3. Is the Bazel (or Buck2) version itself pinned?
4. Is the sandbox strategy pinned so that a missing sandbox fails rather than falls back?
5. Is network blocked in actions and tests, with networked tests tagged and excluded from caching?
6. Do outputs contain no timestamps, host names, user names or absolute paths?
7. Is stamping limited to release binaries, with changing values in the volatile set?
8. Did a null build rebuild nothing, and did two clean machines produce identical hashes?

## Related

[build-principles-and-adoption](build-principles-and-adoption.md),
[remote-cache-and-execution](remote-cache-and-execution.md),
[tests-and-monorepo-migration](tests-and-monorepo-migration.md),
[`container-images`](../../container-images/SKILL.md) (digest-pinned execution images),
[`engineering-practices`](../../engineering-practices/SKILL.md) (security-practices: adding dependencies).

## Sources

Bazel: [Hermeticity](https://bazel.build/basics/hermeticity),
[Sandboxing](https://bazel.build/docs/sandboxing),
[External dependencies overview](https://bazel.build/external/overview),
[Lockfile](https://bazel.build/external/lockfile),
[Adapting Bazel Rules for Remote Execution](https://bazel.build/remote/rules),
[User manual](https://bazel.build/docs/user-manual) (stamping, `--action_env`; the last ~7k
characters of the page were not read),
[Common definitions](https://bazel.build/reference/be/common-definitions) (tags).
[Reproducible Builds definition](https://reproducible-builds.org/docs/definition/), CC BY-SA 4.0.
rules_go [README](https://github.com/bazel-contrib/rules_go),
rules_rust [docs](https://bazelbuild.github.io/rules_rust/),
rules_python [getting started](https://rules-python.readthedocs.io/en/latest/getting-started.html).
