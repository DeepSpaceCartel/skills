---
name: dependabot
description: How to configure and operate GitHub Dependabot (https://docs.github.com/en/code-security/dependabot, options reference at https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference) - project-agnostic. Covers .github/dependabot.yml structure, package-ecosystem values, directory vs directories globs, schedules and cron, grouping updates to cut PR noise, cooldown, allow/ignore rules, versioning-strategy, commit-message prefixes, version updates vs security updates, multi-ecosystem groups, private registries with Dependabot secrets or OIDC, keeping SHA- and digest-pinned actions and images current, Dependabot-triggered Actions restrictions, safe auto-merge with dependabot/fetch-metadata, and @dependabot comment commands. Use when adding or reviewing a dependabot.yml, taming a flood of dependency PRs, wiring up auto-merge, debugging a Dependabot PR or failed Dependabot workflow run, or deciding how a repo should keep its dependencies current.
---

# Dependabot

Dependabot opens PRs that bump your dependencies. It does two different
jobs, enabled in two different places — keep them straight
([docs.github.com](https://docs.github.com/en/code-security/dependabot)):

| | **Version updates** | **Security updates** |
| --- | --- | --- |
| Trigger | your `schedule` | a Dependabot alert with a patched version |
| Enabled by | `.github/dependabot.yml` | repo/org *Advanced Security* settings (needs dependency graph + alerts) |
| Branch | `target-branch` or default | **always** the default branch |
| PR limit | `open-pull-requests-limit` (default 5) | unlimited, not counted |
| `cooldown` | applies | never applies |

`dependabot.yml` *shapes* security PRs (labels, `ignore`, groups with
`applies-to: security-updates`) but does not turn them on.

## Baseline config

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"                   # always "/" for actions
    schedule:
      interval: "weekly"
    groups:
      actions:
        patterns: ["*"]

  - package-ecosystem: "npm"         # also covers yarn, pnpm
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "06:00"
      timezone: "Europe/Prague"      # IANA name; default UTC
    cooldown:
      default-days: 3
      semver-major-days: 14
    commit-message:
      prefix: "chore"
      prefix-development: "chore"
      include: "scope"               # -> "chore(deps): ..." / "chore(deps-dev): ..."
    groups:
      npm-minor-patch:
        update-types: ["minor", "patch"]
      npm-security:
        applies-to: security-updates
        patterns: ["*"]
```

- One `updates[]` entry per **ecosystem × directory set**. The YAML
  value isn't always the tool name: pnpm/yarn → `npm`; pip, pipenv,
  pip-compile, Poetry → `pip`. Full table:
  [`references/ecosystems.md`](references/ecosystems.md).
- `directory` takes one literal path; `directories` takes a list and
  supports globs (`"/services/*"`). Don't let two entries for the same
  ecosystem + target branch overlap.
- `interval`: `daily` (weekdays), `weekly` (Monday unless `day`),
  `monthly`, `quarterly`, `semiannually`, `yearly`, or `cron` +
  `cronjob: "0 6 * * 1"`. Unset `time` = a random time.
- Always include `github-actions` (and `docker`, `devcontainers`,
  `terraform` … where present) — pinned SHAs and digests are only safe
  if something bumps them. See the `github-actions` and
  `container-images` skills.

## Grouping: the main noise control

Default is **one PR per outdated dependency**. Without groups, a
weekly schedule on a real project means a dozen PRs, each re-running
CI and conflicting on the lockfile.

```yaml
groups:
  dev-tooling:
    dependency-type: "development"     # bundler, composer, mix, maven, npm, pip, uv
  aws-sdk:
    patterns: ["@aws-sdk/*"]
  minor-patch:
    update-types: ["minor", "patch"]
    exclude-patterns: ["typescript"]
```

- A dependency goes into the **first** group it matches — order from
  specific to general.
- Leave majors out of catch-all groups. A major bump that breaks the
  build blocks every harmless patch grouped with it.
- `applies-to: security-updates` makes a group for security PRs;
  without it, groups apply to version updates only.
- `group-by: dependency-name` merges one dependency's update across
  all `directories` into a single PR (monorepos).
- To group *across* ecosystems (e.g. Docker + Terraform → one
  "infrastructure" PR), use top-level `multi-ecosystem-groups`; see
  [`references/options.md`](references/options.md#multi-ecosystem-groups).

## Cooldown, allow, ignore

- **`cooldown`** waits N days after a release before proposing it —
  a cheap buffer against compromised or quickly-yanked releases.
  `semver-*-days` work only for semver ecosystems (not Docker,
  Actions, Terraform, Helm…); use `default-days` there.
- **`allow`** runs first and narrows what's eligible; **`ignore`**
  then removes from that set. Matching both = ignored.
- Prefer ignoring a *range* or *update type* over ignoring a package
  forever, and leave a comment saying why:

  ```yaml
  ignore:
    # React 19 migration tracked in #412
    - dependency-name: "react*"
      update-types: ["version-update:semver-major"]
  ```

- Ignore rules created by `@dependabot ignore` comments are stored
  invisibly on the repo. In a team repo, put them in the file instead.

## Version strategy

`versioning-strategy` (bundler, cargo, composer, helm, mix, npm, pip,
pub, uv) controls how the manifest constraint changes. The default is
`auto`, which means `increase` for apps and `widen` for libraries:

| Constraint `^1.0.0`, new `1.2.0` | Result |
| --- | --- |
| `increase` | `^1.2.0` |
| `increase-if-necessary` | `^1.0.0` (already satisfied) |
| `widen` | `^1.0.0`; for `2.0.0` → `>=1.0.0 <3.0.0` |
| `lockfile-only` | lockfile changes only; skips anything needing a manifest edit |

Libraries should widen so they don't force upgrades on consumers. Apps
should increase so the manifest records what they actually run.

## Dependabot PRs in GitHub Actions

Workflows triggered by Dependabot on `push`, `pull_request`,
`pull_request_review` or `pull_request_review_comment` run **like a
fork PR**:

- `GITHUB_TOKEN` is read-only unless you raise it with `permissions:`.
- Only **Dependabot secrets** are available, not Actions secrets. Store
  the same names in both stores so one workflow works for both.
- A re-run keeps the original run's privileges.

That's why CI "fails only on Dependabot PRs". Fix it with secrets and
`permissions`. Don't move to `pull_request_target` while checking out
PR code.

## Auto-merge, safely

```yaml
name: dependabot-auto-merge
on: pull_request
permissions:
  contents: write
  pull-requests: write
jobs:
  auto-merge:
    if: github.event.pull_request.user.login == 'dependabot[bot]'
    runs-on: ubuntu-latest
    steps:
      - id: meta
        uses: dependabot/fetch-metadata@<full-sha> # v3
      - if: steps.meta.outputs.update-type != 'version-update:semver-major'
        run: gh pr merge --auto --squash "$PR_URL"
        env:
          PR_URL: ${{ github.event.pull_request.html_url }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- `--auto` only *queues* the merge. Branch protection must **require
  status checks**, or the PR merges untested.
- Check the PR **author** (`pull_request.user.login`), not
  `github.actor`. The actor is whoever triggered this run.
- For a grouped PR, `update-type` is the *highest* bump in the group.
- `GITHUB_TOKEN` can't add a PR to a merge queue; use a GitHub App token.

More patterns (approve, label, security-only, compatibility score):
[`references/automation.md`](references/automation.md).

## Where to look

| File | Covers |
| --- | --- |
| [`references/options.md`](references/options.md) | every `dependabot.yml` key, values, defaults, which apply to security updates |
| [`references/ecosystems.md`](references/ecosystems.md) | `package-ecosystem` values, support matrix, per-ecosystem caveats |
| [`references/automation.md`](references/automation.md) | Actions restrictions, `fetch-metadata` outputs, auto-merge recipes, `@dependabot` comment commands, rebasing |
| [`references/private-registries.md`](references/private-registries.md) | `registries:` types, Dependabot secrets, OIDC, egress allowlist gotchas |

## What NOT to do

- Don't ship a `dependabot.yml` without `github-actions` while your
  workflows pin SHAs — the pins will silently rot.
- Don't put majors in the same group as patches, and don't auto-merge
  majors.
- Don't enable auto-merge without required status checks on the
  target branch.
- Don't "fix" Dependabot CI failures with `pull_request_target` plus a
  checkout of the PR head — that hands PR code your write token.
- Don't set `open-pull-requests-limit: 0` thinking it disables
  security updates — it only disables *version* updates for that entry.
- Don't commit extra changes onto a Dependabot branch unless you're
  ready to rebase it yourself. Dependabot stops rebasing once someone
  else has pushed to it, unless the commit message has
  `[dependabot skip]`.
- Don't run Dependabot next to another bot (Renovate, a custom bumper)
  on the same ecosystem — they fight over the same lockfiles.
