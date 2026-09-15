# Triggers and contexts

## Event triggers

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]
    branches: [main]
    paths: ["src/**", "package.json"]
  push:
    branches: [main]
    tags: ["v*"]
  schedule:
    - cron: "0 6 * * 1"      # Mondays 06:00 UTC
  workflow_dispatch:
    inputs:
      environment:
        type: choice
        options: [staging, production]
  workflow_call: {}           # reusable workflow
```

- **`pull_request`** is the safe CI trigger: no secrets for forks,
  read-only token. Use `paths`/`branches` filters to avoid running on
  unrelated changes.
- **`push`** runs in the base repo with secrets; restrict `branches`/
  `tags`.
- **`schedule`** runs on the default branch, at best-effort timing
  (delays are common under load), in UTC.
- **`workflow_dispatch`** for manual runs; declare typed `inputs` rather
  than inventing env-var parsing.
- **`workflow_run`** runs after another workflow completes — useful for
  privileged follow-ups, but treat the triggering run's artifacts/branch
  as untrusted.
- **`pull_request_target`** — see
  [`workflow-security.md`](workflow-security.md); nearly always the
  wrong choice.

## `paths` filters

`paths`/`paths-ignore` accept glob patterns. A job with a `paths` filter
that is skipped still reports success — if a required check must run
regardless (e.g. a branch-protection required status), don't path-filter
it, or add an always-run gate job.

## Contexts

| Context | Contains |
| --- | --- |
| `github` | event payload, refs, SHAs, repo, actor |
| `env` | workflow/job/step environment variables |
| `secrets` | repository/environment/org secrets |
| `vars` | non-secret repository/environment config variables |
| `matrix` | current matrix combination |
| `needs` | outputs/results of upstream jobs |
| `runner` | runner OS/temp/arch |
| `steps` | outputs of earlier steps in the job |

Availability differs by field: for example, `secrets` is not available
in a job-level `if:` on some triggers; pass it into `env:` first. `env`
is not available in `jobs.<id>.if` either — use `github.event.*` or
`vars` there.

## Conditional execution

```yaml
jobs:
  deploy:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - run: make deploy
        if: success()
      - run: echo "always"
        if: always()
      - run: echo "only on failure"
        if: failure()
```

- `success()`/`failure()`/`cancelled()`/`always()` are status checks;
  default is `success()`.
- Use `fromJSON(needs.x.outputs.matrix)` to fan out from a computed
  matrix.
- Guard optional steps with `if:` rather than making a separate job.

## Job outputs

```yaml
jobs:
  build:
    outputs:
      version: ${{ steps.meta.outputs.version }}
    steps:
      - id: meta
        run: echo "version=1.2.3" >> "$GITHUB_OUTPUT"
  release:
    needs: build
    steps:
      - run: echo "${{ needs.build.outputs.version }}"
```

Write step outputs to `$GITHUB_OUTPUT` (not the deprecated `::set-output`
command). Outputs are strings.

## Environments

```yaml
jobs:
  deploy:
    environment:
      name: production
      url: https://example.com
```

Environments provide: protection rules (required reviewers, wait
timers, branch restrictions), environment-scoped secrets/vars, and a
deployment URL. Route any job that needs production secrets through an
environment so a reviewer must approve it.

## Concurrency

```yaml
concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: false
```

- Same `group` + `cancel-in-progress: true` cancels the older run —
  right for CI, wrong for deploys (you'd cancel a live deployment).
- A release job should use `cancel-in-progress: false` to serialize.

## Timeouts and defaults

```yaml
jobs:
  test:
    timeout-minutes: 30
    defaults:
      run:
        shell: bash
        working-directory: ./app
```

Set `timeout-minutes` so a hung step doesn't burn the 6-hour default.
Set explicit `shell` when relying on `pipefail` (the default shell for
`run:` is `bash -e`, not `-o pipefail`).
