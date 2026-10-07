# `dependabot.yml` options

Source: [Dependabot options reference](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference).

The file lives at `.github/dependabot.yml` on the default branch.

## Top level

| Key | Notes |
| --- | --- |
| `version` | Always `2`. Required. |
| `updates` | List of update entries. Required. |
| `registries` | Private registry definitions, up to 100; see [`private-registries.md`](private-registries.md). |
| `multi-ecosystem-groups` | Named groups that combine several ecosystems into one PR; see below. |
| `enable-beta-ecosystems` | Not currently in use. |

## Required per-entry keys

| Key | Values |
| --- | --- |
| `package-ecosystem` | See [`ecosystems.md`](ecosystems.md). |
| `directory` / `directories` | Manifest location relative to the repo root. `directory` takes one path. `directories` takes a list and supports globs (`*`, `**`). Use `"/"` for `github-actions` and `devcontainers`. |
| `schedule.interval` | `daily` (Mon–Fri), `weekly`, `monthly` (1st), `quarterly`, `semiannually`, `yearly` (1 Jan), `cron` |

If several entries share an ecosystem and target branch, their
directories must be unique and must not overlap.

## `schedule`

| Key | Notes |
| --- | --- |
| `interval` | As above. `quarterly`/`semiannually`/`yearly` need GHES ≥ 3.19 on Server. |
| `day` | `monday`…`sunday` (weekly only). Default Monday. |
| `time` | `hh:mm`. If unset, Dependabot picks a random time. |
| `timezone` | IANA tz name, default `UTC`. Set the zone here, not in `cronjob`. |
| `cronjob` | Required with `interval: cron`. Five-field cron (`0 9 * * 1-5`) or simple English (`every day at 5pm`). |

## Selecting dependencies

### `allow`

Applied first. Only dependencies that match an `allow` rule are eligible.

| Key | Values |
| --- | --- |
| `dependency-name` | Name or `*` glob. Maven/Gradle `groupId:artifactId`; Docker full repo name. |
| `dependency-type` | `direct`, `indirect` (bundler, pip, composer, cargo, gomod, uv), `all`, `production`, `development` (bundler, composer, mix, maven, npm, pip, uv) |
| `update-types` | `version-update:semver-{patch,minor,major}`. Affects version updates only. |

By default, explicitly declared dependencies get version updates, and
vulnerable lockfile dependencies get security updates.

### `ignore`

Applied after `allow`. A dependency that matches both is ignored.

| Key | Values |
| --- | --- |
| `dependency-name` | Name or `*` glob. |
| `versions` | The package manager's own range syntax: npm `^1.0.0`, Bundler `~> 2.0`, NuGet `7.*`, Maven `[1.4,)`. |
| `update-types` | `version-update:semver-{patch,minor,major}` |

`ignore` also filters **security** updates. Ignoring a package outright
means Dependabot won't fix its vulnerabilities either.

### `exclude-paths`

A list of globs, relative to `directory`, that are skipped when looking
for manifests (`vendor/**`, `src/test/assets`).

## `groups`

```yaml
groups:
  <identifier>:            # letters, "|", "_", "-"; must start/end with a letter
    applies-to: version-updates   # or security-updates
    dependency-type: production   # or development
    patterns: ["*"]
    exclude-patterns: ["eslint"]
    update-types: ["minor", "patch"]
    group-by: dependency-name     # optional, see below
```

- The group identifier shows up in branch names and PR titles.
- A dependency joins the **first** matching group. Outdated
  dependencies that match no group get their own PR.
- If a dependency matches both `patterns` and `exclude-patterns`, it is
  excluded.
- `group-by: dependency-name` makes one PR per dependency across every
  `directories` entry. It needs a single ecosystem and works for
  version updates only. Incompatible constraints still produce
  separate PRs.
- Grouped *security* updates can also be turned on in repo/org
  settings without any group rules. They never cross ecosystems and
  never mix with version updates.

## `multi-ecosystem-groups`

Combines several ecosystems into one PR per group
([how-to](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configuring-multi-ecosystem-updates)).
Applies to version updates only.

```yaml
multi-ecosystem-groups:
  infrastructure:
    schedule:
      interval: "weekly"
    labels: ["infrastructure", "dependencies"]

updates:
  - package-ecosystem: "docker"
    directory: "/"
    patterns: ["nginx", "redis", "postgres"]   # required with multi-ecosystem-group
    multi-ecosystem-group: "infrastructure"
  - package-ecosystem: "terraform"
    directory: "/"
    patterns: ["*"]
    multi-ecosystem-group: "infrastructure"
```

If no combined PR appears, check two things: every entry needs
`patterns`, and the group names must match exactly. You can confirm
the group under *Insights → Dependency graph → Dependabot*.

## `cooldown`

Version updates only. Never applies to security updates.

```yaml
cooldown:
  default-days: 5
  semver-major-days: 30
  semver-minor-days: 7
  semver-patch-days: 3
  include: ["lodash*"]     # up to 150, globs; limit cooldown to these
  exclude: ["critical-*"]  # up to 150; wins over include, updates immediately
```

`semver-*-days` are ignored for non-semver ecosystems: Bazel,
Devcontainers, Docker, Docker Compose, GitHub Actions, Gitsubmodule,
Helm, Nix, OpenTofu, pre-commit, Terraform, vcpkg. Use `default-days`
for those.

## PR presentation

| Key | Notes |
| --- | --- |
| `commit-message.prefix` | ≤ 50 chars. A `:` is appended if the prefix ends in a letter, digit, `)` or `]`. End the prefix with a space to suppress it. Also sets the PR title. |
| `commit-message.prefix-development` | Prefix for dev-dependency commits (bundler, composer, mix, maven, npm, pip, uv). |
| `commit-message.include: scope` | Appends `(deps)` / `(deps-dev)`. |
| `labels` | Default `dependencies` plus the ecosystem name. A custom list replaces both. Semver labels (`major`/`minor`/`patch`) are still added if they exist in the repo. Labels missing from the repo are skipped. `[]` = no labels. |
| `assignees` | Must have write access. |
| `milestone` | Numeric milestone ID, taken from the milestone URL. |
| `pull-request-branch-name.separator` | `"/"` (default), `"-"`, `"_"` |
| `pull-request-branch-name.*` | `prefix` (default `dependabot`), `max-length` (20–244, default 100), `word-separator`, `branch-name-case`, `template` (`{prefix}`, `{package_manager}`, `{directory}`, `{dependency}`, `{version}`, `{group_name}`, …) |

`prefix: "chore"` with `include: "scope"` produces
`chore(deps): bump x from 1.0 to 1.1`, a valid
[Conventional Commit](../../conventionalcommits/SKILL.md).

## Behaviour

| Key | Notes |
| --- | --- |
| `open-pull-requests-limit` | Version updates only. Default 5 per entry. `0` turns off version updates for the entry; security PRs are unaffected and have no limit. |
| `rebase-strategy: disabled` | Stops automatic rebasing. PRs opened before the change keep rebasing for up to 30 days. |
| `target-branch` | Version updates read manifests from this branch and open PRs against it. **Side effect:** this entry's options (labels, commit-message, assignees…) stop applying to security updates, which always use the default branch. |
| `vendor: true` | `bundler`, `gomod` only. |
| `versioning-strategy` | `auto` (default: `increase` for apps, `widen` for libraries), `increase`, `increase-if-necessary`, `lockfile-only`, `widen`. Supported by bundler, cargo, composer, helm, mix, npm, pip, pub, uv. |
| `registries` | `"*"` or a list of names from the top-level `registries`. Default: public registries only. |
| `insecure-external-code-execution: allow` | bundler, mix, pip. Lets manifest code run during an update. Turned off automatically when `registries` is set; turning it back on can expose registry credentials to a malicious package. |

## Which options also shape security updates

| Applies to security PRs | Version updates only |
| --- | --- |
| `allow`, `ignore`, `directories`, `labels`*, `assignees`*, `commit-message`*, `milestone`, `groups` (`applies-to: security-updates`), `insecure-external-code-execution` | `schedule`, `cooldown`, `open-pull-requests-limit`, `multi-ecosystem-groups`, `target-branch`, `versioning-strategy` |

\* Not when the entry sets `target-branch`.
