---
name: github-actions
description: How to write and harden GitHub Actions workflows (https://docs.github.com/en/actions, security hardening at https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions) - project-agnostic. Covers workflow/job/step structure, triggers and event contexts, least-privilege permissions, pinning third-party actions to a full commit SHA, GITHUB_TOKEN scoping, pull_request vs pull_request_target and fork-PR safety, self-hosted runner risk, OIDC to cloud providers instead of long-lived secrets, secret masking, concurrency controls, caching, matrix builds, and reusable workflows/composite actions. Use when adding or reviewing a CI/CD workflow, debugging a failed run, or deciding how much access a workflow (especially a self-hosted runner) should have.
---

# GitHub Actions workflows

A workflow is executable infrastructure with access to your repo, your
secrets, and often your cloud. Treat `.github/workflows/*.yml` as
security-sensitive code, not YAML config. Reference:
<https://docs.github.com/en/actions>.

## Structure

```yaml
name: ci

on:                          # triggers
  pull_request:
  push:
    branches: [main]

permissions:                 # least privilege, default deny
  contents: read

concurrency:                 # cancel superseded runs
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<full-sha>
      - run: npm ci && npm test
```

- **`permissions`** should be set explicitly and narrowly. If you don't
  set it, the repo/org default applies — often broader than needed.
- **`concurrency`** prevents pile-ups and wasted minutes; use a group
  per branch/PR, and `cancel-in-progress` for CI (not for releases).
- Prefer small, single-purpose jobs; use `needs:` for ordering.

## Triggers and contexts

- `pull_request` runs with a **read-only** `GITHUB_TOKEN` and **no
  secrets** for fork PRs — this is the safe default.
- `push` runs in the base repo with secrets; gate on branches.
- `workflow_dispatch` for manual runs (`inputs:` for parameters).
- `schedule` for cron; be aware of delayed/queued runs and UTC.
- `pull_request_target` runs in the context of the **base** repo *with
  secrets* and can check out the PR's code — extremely dangerous, see
  [`references/workflow-security.md`](references/workflow-security.md).
- Contexts (`github`, `env`, `secrets`, `matrix`, `needs`) are not all
  available in every field; `secrets` is unavailable in `if:` at the
  job level in some triggers — pass via `env:`.

## Supply chain: pin actions

```yaml
# BAD: a moving tag an attacker can re-point
- uses: some-org/some-action@v1

# GOOD: immutable full commit SHA, with a version comment for humans
- uses: some-org/some-action@a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2 # v1.2.3
```

- Third-party actions execute arbitrary code with your workflow's
  access. Pin every action to a full 40-char commit SHA.
- Keep the human-readable version in a trailing comment; let Dependabot
  (`github-actions` ecosystem) update the SHA and the comment together.
- First-party `actions/*` are lower risk but pinning them too is cheap
  and avoids surprise tag moves.

## Secrets and OIDC

- Never echo secrets; GitHub masks known secret values in logs, but
  masking is best-effort (re-encoded, split, or base64 values can leak).
- Prefer **OIDC** (`id-token: write`) to assume a short-lived cloud role
  over storing a long-lived cloud key as a secret — no static
  credential to rotate or leak:

  ```yaml
  permissions:
    id-token: write      # required for OIDC
    contents: read
  ```

- Use **environments** with protection rules (required reviewers,
  branch restrictions) for deploy jobs so secrets are only available
  to approved runs.
- Pass secrets to a step via `env:`, not on the command line (argv is
  visible in `ps` and error output).

## Fork-PR safety

- Assume a fork PR's code and its workflow file are attacker-controlled.
- `pull_request` from a fork: no secrets, read-only token — safe.
- `pull_request_target`: runs the *base* workflow with secrets; if it
  also checks out `github.event.pull_request.head.sha`, the attacker's
  code runs with your secrets. Only use it when you never execute PR
  code (e.g. labelling), or with an explicit, reviewed sandbox.
- Self-hosted runners must **never** run untrusted fork PRs — a runner
  has network and often cluster access. Gate with
  `github.event.pull_request.head.repo.full_name == github.repository`
  or skip fork PRs entirely.

## Caching and matrix

```yaml
strategy:
  fail-fast: false
  matrix:
    node: [20, 22]
steps:
  - uses: actions/setup-node@<sha>
    with:
      node-version: ${{ matrix.node }}
      cache: npm
```

- Use the setup action's built-in `cache:` where available; otherwise
  `actions/cache` keyed on lockfile hash.
- Never cache secrets, tokens, or `~/.docker/config.json` in a cache
  shared across branches/PRs.
- `fail-fast: false` to see all matrix failures; `include`/`exclude`
  to tune the grid.

## Where to look

| File | Covers |
| --- | --- |
| [`references/workflow-security.md`](references/workflow-security.md) | permissions, SHA pinning, `pull_request_target`, OIDC, secret masking |
| [`references/triggers-and-contexts.md`](references/triggers-and-contexts.md) | events, contexts, conditional execution, environments |
| [`references/reusable-workflows.md`](references/reusable-workflows.md) | `workflow_call`, composite actions, sharing steps |
| [`references/self-hosted-runners.md`](references/self-hosted-runners.md) | runner trust, scoping, ephemeral runners, in-cluster runners |

## What NOT to do

- Don't use `pull_request_target` to run PR code — that's the classic
  secret-exfiltration vulnerability.
- Don't grant `permissions: write-all` (or leave an unrestricted
  default) to a job that only reads.
- Don't reference actions by a mutable tag (`@v1`, `@main`) when a
  commit SHA is available.
- Don't put secrets in `if:` expressions, `run:` command lines, or
  artifacts — pass through `env:` and write to the step's stdin.
- Don't let a self-hosted runner accept untrusted fork PRs.
