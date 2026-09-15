# Self-hosted runners

A self-hosted runner is a machine (often inside your network or
cluster) that executes whatever a workflow tells it to. That is a much
larger trust surface than a GitHub-hosted runner.

## The core risk

- Hosted runners are ephemeral and isolated; a self-hosted runner
  persists between jobs and has whatever network/file/cloud access the
  host has.
- GitHub's own guidance: **never use self-hosted runners for public
  repositories** (untrusted fork PRs), because a workflow can run
  arbitrary code on the runner and pivot into your infrastructure.
- Even for private repos, a contributor who can open a PR can often
  trigger a workflow. Gate carefully.

## Required gating for fork PRs

```yaml
jobs:
  test:
    # Only run for pushes or same-repo PRs; never a fork PR.
    if: >
      github.event_name == 'push' ||
      github.event.pull_request.head.repo.full_name == github.repository
    runs-on: [self-hosted, linux, x64, mycluster]
```

- The label list is an AND: a runner must match **all** labels. Use
  custom labels (`mycluster`) to target a specific pool.
- Prefer **ephemeral** runners: one job per runner instance, destroyed
  after. GitHub's Actions Runner Controller (ARC) or the ephemeral
  runner mode eliminates cross-job contamination — a previous job's
  files, tokens, or processes can't leak into the next.

## Scoping the runner's access

- Give the runner the **minimum** cloud/cluster identity its jobs need.
  A runner that can only touch a test namespace is far safer than one
  with `cluster-admin`.
- Prefer the runner's **own workload identity** (an in-cluster
  ServiceAccount, an instance profile, a federated identity) over a
  long-lived kubeconfig or cloud key stored as a repo secret.
- If a workflow needs broader access (e.g. deploying to prod), make that
  a separate job on a separate, more restricted runner or a
  GitHub-hosted runner with OIDC — don't widen the shared runner.

## In-cluster runners (ARC pattern)

- The runner runs as a Pod with a ServiceAccount; RBAC is bound to that
  ServiceAccount cluster-side.
- Because it's inside the cluster, CI reaches `kubernetes.default.svc`
  without exposing the API server publicly.
- Use a dedicated namespace, a dedicated ServiceAccount, and a
  namespace-scoped Role/RoleBinding for almost everything. Reserve
  `cluster-admin` for the one identity that genuinely needs it, and
  document why.
- Keep the runner's namespace's PodSecurity and NetworkPolicy strict;
  the runner executes arbitrary build steps.

## Operational hygiene

- Patch/update the runner host or image regularly — it's CI, but it's
  also an internet-connected machine with credentials.
- Log and monitor what runs (`kubectl get pods -n <runner-ns>` history,
  workflow logs); unexpected runs are a signal.
- Set `timeout-minutes` on jobs so a stuck job doesn't hold a runner.
- Use `concurrency` to serialize jobs that share fixed resources (a
  single test namespace, a single database), and make test resources
  unique per run where you can.

## When not to self-host

- Public repos with fork PRs: use GitHub-hosted runners.
- Simple lint/test/build: GitHub-hosted is cheaper and safer.
- Only self-host when you need private network/cluster access or
  specialized hardware/software, and then scope it tightly.
