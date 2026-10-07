# Automating Dependabot PRs

Sources: [Automating Dependabot with GitHub Actions](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/automating-dependabot-with-github-actions),
[Troubleshooting Dependabot on GitHub Actions](https://docs.github.com/en/code-security/dependabot/troubleshooting-dependabot/troubleshooting-dependabot-on-github-actions),
[`dependabot/fetch-metadata`](https://github.com/dependabot/fetch-metadata),
[comment commands](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-pull-request-comment-commands).

## How Dependabot-triggered runs differ

Runs triggered by Dependabot on `push`, `pull_request`,
`pull_request_review` and `pull_request_review_comment` are treated
like runs from a fork:

- `GITHUB_TOKEN` is **read-only** by default. You can raise it with an
  explicit `permissions:` block, which does take effect for Dependabot.
- **Only Dependabot secrets** are available. Actions secrets resolve
  to empty strings. Create Dependabot secrets under *Settings →
  Secrets and variables → Dependabot*, using the same names as your
  Actions secrets so one workflow serves both actors.
- A re-run keeps the original privileges, whoever clicks re-run.
- Workflows still run for Dependabot even when Actions policy would
  otherwise block external actions.

Typical symptom: a job that writes (comments, pushes, logs into a
registry) passes on human PRs and fails on Dependabot PRs. Fix it with
`permissions` and Dependabot secrets, or skip the step:

```yaml
if: github.actor != 'dependabot[bot]'
```

### Avoid `pull_request_target` + checkout

`pull_request_target` runs with a write token and full Actions
secrets. That's fine for a job that only reads PR **metadata**
(`fetch-metadata`, `gh pr merge`, `gh pr edit`). Combined with
`actions/checkout` of the PR head, it runs PR-supplied code with your
secrets. A malicious package bump can then exfiltrate them. Prefer
`on: pull_request` plus `permissions:`. See the `github-actions`
skill's workflow-security reference.

### Identify Dependabot correctly

| Check | Meaning |
| --- | --- |
| `github.event.pull_request.user.login == 'dependabot[bot]'` | The **PR author** is Dependabot. Use this for auto-merge. |
| `github.actor == 'dependabot[bot]'` | The actor of *this run*. It's a human if someone pushed to the branch or re-ran the workflow. |

Also gate on `github.repository == 'owner/repo'` so forks of your repo
don't run the job.

## `dependabot/fetch-metadata`

Parses the Dependabot PR and exposes:

| Output | Example |
| --- | --- |
| `dependency-names` | `lodash, @types/node` (comma-separated) |
| `dependency-type` | `direct:production`, `direct:development`, `indirect` |
| `update-type` | `version-update:semver-patch` / `-minor` / `-major`; the **highest** bump in the PR |
| `previous-version`, `new-version` | |
| `package-ecosystem`, `directory`, `target-branch` | the config that produced the PR |
| `dependency-group` | group identifier, or empty |
| `updated-dependencies-json` | full per-dependency detail |
| `maintainer-changes` | whether the PR body notes a maintainer change |
| `compatibility-score` | needs `compat-lookup: true` and a PAT |
| `alert-state`, `ghsa-id`, `cvss` | needs `alert-lookup: true` and a PAT or App token |

Pin it to a full commit SHA like any other action.

## Recipes

All of these assume:

```yaml
on: pull_request
permissions:
  contents: write
  pull-requests: write
jobs:
  dependabot:
    if: >-
      github.event.pull_request.user.login == 'dependabot[bot]' &&
      github.repository == 'owner/repo'
    runs-on: ubuntu-latest
    steps:
      - id: meta
        uses: dependabot/fetch-metadata@<full-sha> # v3
      # ...recipe steps...
```

**Auto-merge patch and minor, never major:**

```yaml
      - if: steps.meta.outputs.update-type != 'version-update:semver-major'
        run: gh pr merge --auto --squash "$PR_URL"
        env:
          PR_URL: ${{ github.event.pull_request.html_url }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Auto-merge dev dependencies only:**

```yaml
      - if: >-
          steps.meta.outputs.dependency-type == 'direct:development' &&
          steps.meta.outputs.update-type != 'version-update:semver-major'
        run: gh pr merge --auto --squash "$PR_URL"
```

**Approve (required reviews) then auto-merge:**

```yaml
      - run: gh pr review --approve "$PR_URL"
      - run: gh pr merge --auto --squash "$PR_URL"
```

An approval from `GITHUB_TOKEN` counts as a review by
`github-actions[bot]`. Decide whether that's acceptable under your
review policy. If you require CODEOWNERS review, it usually won't
satisfy it.

**Label production dependencies for human attention:**

```yaml
      - if: steps.meta.outputs.dependency-type == 'direct:production'
        run: gh pr edit "$PR_URL" --add-label "production"
```

### Preconditions for auto-merge

1. *Allow auto-merge* is enabled in the repo settings.
2. The target branch's protection or ruleset **requires status
   checks**. `--auto` waits for them. Without required checks, the PR
   merges immediately.
3. Merge queue: `GITHUB_TOKEN` can't enqueue. Use a GitHub App
   installation token with merge permission.
4. Don't auto-merge majors, `0.x` minors (often breaking in
   practice), or PRs flagged with `maintainer-changes`.

## `@dependabot` comment commands

Dependabot reacts with 👍 when it picks up a command. It may take
minutes if it's busy.

**Single-dependency PR:**

| Command | Effect |
| --- | --- |
| `@dependabot rebase` | Rebase the PR. |
| `@dependabot recreate` | Rebuild the PR from scratch, discarding edits. |
| `@dependabot ignore this dependency` | Close; never update this dependency. |
| `@dependabot ignore this major version` / `minor` / `patch` | Close; skip this version line. |
| `@dependabot show <name> ignore conditions` | Post the stored ignore rules for `<name>`. |

**Grouped PR:**

| Command | Effect |
| --- | --- |
| `@dependabot ignore <name>` | Close; stop updating `<name>`. |
| `@dependabot ignore <name> major version` / `minor` / `patch` | Close; skip that version line of `<name>`. |
| `@dependabot unignore <name>` | Clear `<name>`'s ignore rules; open a fresh PR. |
| `@dependabot unignore <name> <condition>` | Clear one rule, e.g. `[< 1.9, > 1.8.0]` (get it from `show`). |
| `@dependabot unignore *` | Clear all ignore rules for the group; open a fresh PR. |

Comment-based ignores are invisible to anyone reading the repo. In a
shared repo, express them as `ignore:` entries in `dependabot.yml` with
a reason in a comment. Merging is done with native auto-merge (above),
not comment commands.

## Rebasing and edits

- Dependabot rebases its PRs automatically when they conflict or on
  each scheduled run. It stops 30 days after the PR was opened.
- Once anyone else pushes a commit to the branch, Dependabot stops
  rebasing it, so you own the conflicts from then on. Put
  `[dependabot skip]` (or `[skip dependabot]`) in your commit message
  to let Dependabot force-push over your commit.
- `rebase-strategy: disabled` turns automatic rebasing off. It
  reduces CI churn on busy repos, but you'll rebase by hand.
- Dependabot pauses version updates on repos where its PRs are
  ignored for a long time. Merging or closing them resumes updates.
