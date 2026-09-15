# Workflow security

Source: [Security hardening for GitHub Actions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions).

A workflow has, at minimum: read access to its repo, a `GITHUB_TOKEN`
whose scope you control, and whatever secrets you expose to it. On a
self-hosted runner it also has the runner's network and credentials.
Minimize all three.

## Least-privilege `permissions`

Set `permissions` explicitly at the workflow (or job) level:

```yaml
permissions:
  contents: read        # default for most CI
```

Common needs:

| Scope | When |
| --- | --- |
| `contents: read` | checkout |
| `contents: write` | push commits/tags, create releases |
| `pull-requests: write` | comment on / label PRs |
| `issues: write` | comment on issues |
| `id-token: write` | OIDC token for cloud auth |
| `packages: write` | push to GHCR |
| `security-events: write` | upload SARIF/code scanning |

Start from `permissions: {}` (deny all) and add only what a job needs.
Job-level `permissions` fully overrides workflow-level — set the narrow
scope per job.

## Pin actions to a commit SHA

Tags and branches are mutable; a compromised or re-pointed tag is
arbitrary code execution in your workflow. Pin to the full 40-char SHA:

```yaml
- uses: docker/build-push-action@4f58ea79222b3b9dc2c8bbdd6debcef730109a75 # v6.9.0
```

- Add a trailing comment with the version so humans can read it.
- Enable Dependabot for the `github-actions` ecosystem to bump SHAs and
  comments automatically.
- A compromised action in a workflow with `id-token: write` or secrets
  can exfiltrate them; SHA pinning bounds *which* code runs.

## `pull_request` vs `pull_request_target`

| | `pull_request` | `pull_request_target` |
| --- | --- | --- |
| Runs workflow from | the PR's merge/head ref | the base repo's default branch |
| `GITHUB_TOKEN` | read-only for forks | read/write, base repo scope |
| Secrets | not available for forks | **available** |
| Common safe use | normal CI | labelling, triage that never runs PR code |

The dangerous pattern:

```yaml
# VULNERABLE: checks out and builds untrusted PR code WITH secrets
on: pull_request_target
jobs:
  build:
    steps:
      - uses: actions/checkout@<sha>
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - run: make            # attacker's Makefile runs with repo secrets
```

If a workflow triggered by `pull_request_target` (or `workflow_run`)
executes or even imports code from the PR, an attacker can exfiltrate
secrets. Keep PR code and privileged contexts in separate workflows (`workflow_run` should treat artifacts as untrusted input).

## OIDC instead of long-lived cloud secrets

Instead of storing an AWS/GCP/Azure access key in `secrets`:

```yaml
permissions:
  id-token: write
  contents: read
jobs:
  deploy:
    steps:
      - uses: aws-actions/configure-aws-credentials@<sha>
        with:
          role-to-assume: arn:aws:iam::123456789012:role/gha-deploy
          aws-region: us-east-1
```

- GitHub mints a short-lived OIDC token; the cloud provider exchanges it
  for temporary credentials scoped to a role.
- Restrict the role's trust policy on `repo:org/repo:ref:refs/heads/main`
  and, ideally, `environment`.
- Nothing long-lived to rotate or leak.

## Secret handling

- Secrets are masked in logs by exact value. That is best-effort:
  a secret embedded in a longer string, JSON-encoded, base64-encoded,
  split across lines, or transformed will not be masked.
- Never `echo`/`printf` a secret, never write it to an artifact, never
  pass it on a command line (visible to `ps` and in error output).
- Pass via `env:` and let the tool read the environment variable.
- Use `${{ secrets.X }}` only where the expression is evaluated in the
  runner, not in contexts that end up in the log.
- Prefer environments + required reviewers so a deploy's secrets are
  only unsealed for approved runs.

## Artifacts and caches

- Treat downloaded artifacts (including from `workflow_run`) as
  untrusted input; don't feed them into privileged steps.
- Never cache credential files (`~/.aws`, `~/.docker/config.json`,
  `~/.netrc`) — caches can be restored across branches and PRs.

## Untrusted input

Any `github.event.*` string (PR title, branch name, issue body, commit
message) is attacker-controlled. Never interpolate it directly into a
`run:` shell block:

```yaml
# VULNERABLE: shell injection via branch name
- run: echo "Building ${{ github.head_ref }}"

# SAFE: pass through env, reference the variable
- env:
    BRANCH: ${{ github.head_ref }}
  run: echo "Building $BRANCH"
```

The `${{ }}` expands before the shell parses the command, so metacharacters
(`;`, `$()`, backticks) in the value become shell code.
