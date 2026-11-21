# GitOps and delivery

Checked 2026-11-20: Flux v2.10, Argo CD v3.6, Helm v4.3, Kustomize v5.8.

## Pull vs push

- **Pull (GitOps).** A controller in each cluster watches Git or an OCI artifact and applies
  what it finds. Cluster credentials never leave the cluster, and CI only needs write access to
  Git or a registry. The controller also corrects drift: manual edits are reverted.
- **Push.** CI runs `kubectl apply` or `helm upgrade`. Nothing runs in the cluster, and the
  deploy is visible in the CI run. But **write access to production lives in CI**, so a
  compromised workflow, action or token can deploy anything. The API server must also be reachable
  from the runners, nothing corrects drift, and a failed run leaves the cluster half-applied
  until someone reruns it.

## Comparison

| | Flux | Argo CD | CI push (e.g. GitHub Actions) |
|---|---|---|---|
| Model | Pull, one install per cluster | Pull, a hub managing many clusters or one per cluster | Push |
| UI | CLI-first. The Flux Operator adds a web UI (AGPL-3.0) | Excellent web UI, SSO, project RBAC | CI logs |
| Footprint | 4 core controllers (+ image automation) | 6–7 components; Argo CD Core is a slimmer controller-only install | None in the cluster |
| Multi-cluster | Each cluster pulls its own path: no credentials shared | The hub holds every cluster's credentials. The inbound agent mode (argocd-agent) is pre-1.0 | One credential or binding per cluster in CI |
| Helm | Real Helm releases (hooks work) | Renders with `helm template`: hooks and `lookup` behave differently | Real Helm |
| Secrets | Native SOPS decryption | Plugins (KSOPS, helm-secrets) or ESO | CI secrets |
| Drift correction | Yes | Yes | No |
| If it fails | Each cluster is independent; the last artifact stays cached | A hub outage stops deploys everywhere | A CI outage or a credential leak |

How to choose:

- **Flux:** few operators, several clusters, secrets in Git, and real Helm semantics.
- **Argo CD:** a UI matters (teammates who click, many apps, app-level RBAC).
- **CI push:** fine for one cluster and a small team. Make it safe:
  - **Credentials:** authenticate with short-lived OIDC tokens, which kube-apiserver accepts
    directly through `AuthenticationConfiguration` (structured authentication, GA in 1.34), not a
    stored kubeconfig.
  - **Scope:** bind the workflow's subject (for example `repo:org/name:environment:prod`) to a
    namespaced Role, never cluster-admin.
  - **Production gate:** protect production with required reviewers.
  - **Pinning:** pin every action by commit SHA.

## Repo layout for several clusters (Flux)

```
clusters/
  eu/          # Flux bootstrap + Kustomizations pointing at the paths below, region patches
  us-east/
infrastructure/
  base/        # CNI add-ons, cert-manager, operators (HelmReleases)
  overlays/<region>/
apps/
  base/<app>/  # Kustomize base per service
  overlays/<region>/<app>/
```

- **Ordering:** use `dependsOn` between Kustomizations (CRDs, then operators, then apps) and
  health checks, so an app waits for its operator.
- **CI's job:** CI builds and pushes an image by digest, then commits the tag bump. Flux image
  automation can make that commit instead, but it then needs a deploy key with write access.
- **OCI artifacts:** `flux push artifact` from CI lets clusters pull manifests from a registry
  instead of Git, and verify them with cosign.
- **Rollouts:** stage them region by region. With one repo, a bad base change breaks every
  cluster at once unless each overlay pins a revision or rollouts are sequenced.

## Secrets

| Tool | What | Choose when | Gotchas |
|---|---|---|---|
| **SOPS + age** (CNCF sandbox) | Encrypts values inside YAML in Git; Flux decrypts | Small teams, no extra infrastructure | Back up the age private key offline. Rotation means re-encrypting. Diffs show ciphertext |
| **Sealed Secrets** | A controller holds the key; `kubeseal` encrypts against it | Argo CD users who want no plugins | Ciphertext is bound to one cluster; back up the controller key |
| **External Secrets Operator** (CNCF sandbox) | Syncs from Vault/OpenBao, cloud secret managers, 1Password, Bitwarden and more into `Secret`s | A secret store already exists, or rotation is needed | Needs a bootstrap credential to the store |
| **OpenBao** (open-source Vault fork) | Dynamic database credentials, PKI, transit encryption | You really need dynamic credentials or PKI | Running an HA, auto-unsealed secret server is real work |

## Packaging

- **Helm** for third-party software and anything you distribute. See
  [`../../helm-charts/SKILL.md`](../../helm-charts/SKILL.md).
- **Kustomize** for your own services: plain YAML plus per-environment overlays. It is built into
  `kubectl` and Flux.
- **Helmfile** is redundant once a GitOps controller is in place.
- **Timoni (CUE)** and **Jsonnet** are niche: choose them deliberately, not by default.

## Progressive delivery

| Tool | How | Notes |
|---|---|---|
| **Argo Rollouts** | A `Rollout` CRD replaces `Deployment` (or references one with `workloadRef`): canary and blue-green, analysis from metrics, traffic shifting through Gateway API, meshes and ingresses | Has its own dashboard and kubectl plugin; works with Flux or Argo CD |
| **Flagger** (Flux family) | Wraps an existing Deployment by creating `-primary` and `-canary` copies; metric-driven canary, A/B, blue-green | Needs a metrics provider and a traffic layer |

Rolling updates with readiness probes and a fast revert in Git are enough until a bad release
costs more than running a canary system.

Related: deploy policy as one admission choke point, signed provenance and break-glass in
[`../../secure-reliable-systems/SKILL.md`](../../secure-reliable-systems/SKILL.md); staging
config changes and reading a canary in
[`../../production-operations/references/config-and-canary-changes.md`](../../production-operations/references/config-and-canary-changes.md);
`maxSurge`, `maxUnavailable` and draining in
[`../../infrastructure-patterns/references/disruption-budgets-and-safe-rollouts.md`](../../infrastructure-patterns/references/disruption-budgets-and-safe-rollouts.md).
