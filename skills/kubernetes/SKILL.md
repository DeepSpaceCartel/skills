---
name: kubernetes
description: Which Kubernetes tool to reach for and how to run clusters and workloads with it (https://kubernetes.io/docs/) - project-agnostic. Covers picking tools by need (KEDA queue-driven Jobs and scale to zero, Karpenter or Cluster Autoscaler, Kueue, Argo Workflows, Knative), GPUs on and off the cluster, GitOps (Flux vs Argo CD vs CI push), multi-cluster and multi-region setups, Gateway API, operators (CloudNativePG, NATS, RabbitMQ, Strimzi Kafka, MongoDB) and their footprints, Velero and etcd backups, Pod Security, Kyverno v1 policies and cosign, provisioning (Talos, Cluster API, kubeadm, k3s), dev tools, termination and Job semantics, kubectl debugging, and facts that changed recently. Use when choosing between Kubernetes tools or operators, or writing manifests, policies or kubectl commands. Not for choosing a messaging, caching or resilience pattern (see infrastructure-patterns), sizing (see system-design), or backups of data (see data-integrity).
---

# Kubernetes

Kubernetes is a reconciliation engine: you declare objects, controllers
converge the world on them. Most good designs move *decisions* out of
scripts and into objects a controller already reconciles. A CronJob that
polls a queue and decides whether to start workers is a script
pretending to be a controller; a KEDA `ScaledJob` is the controller.

This skill is about **choosing the right tool and using it correctly**.
Workload resilience (probes, requests and limits, PDBs, autoscaling,
topology spread) lives in
[`../infrastructure-patterns/SKILL.md`](../infrastructure-patterns/SKILL.md);
storage and backups of state in
[`../data-integrity/SKILL.md`](../data-integrity/SKILL.md); capacity
budgets in [`../system-design/SKILL.md`](../system-design/SKILL.md);
packaging in [`../helm-charts/SKILL.md`](../helm-charts/SKILL.md);
images in [`../container-images/SKILL.md`](../container-images/SKILL.md).

## Rules for agents acting on a cluster

1. **Name the context and namespace on every command**
   (`kubectl --context prod -n app ...`). Never switch the global
   context with `kubectx` or `kubectl config use-context` as a side
   effect.
2. **Read before you write.** `get`, `describe`, `events`, `logs`
   first. Changes go through Git when the cluster is GitOps-managed: a
   `kubectl apply` or `edit` there is reverted by the controller or
   silently drifts.
3. **Preview every write:** `kubectl diff -f`, `--dry-run=server`,
   `helm template`, `flux diff kustomization`. Prefer server-side apply
   (`kubectl apply --server-side`) for large or shared objects.
4. **Ask before anything destructive or outward-facing:** deleting
   namespaces, PVCs, CRDs (deleting a CRD deletes every object of that
   kind), `drain`, scaling a database, touching Secrets, rotating
   certificates.
5. **Never print Secret values.** `kubectl get secret -o yaml` and
   `describe` on some resources reveal them; check key names with
   `-o jsonpath='{.data}' | jq 'keys'` instead.
6. **Prefer narrow, audited paths to shell access.** `kubectl exec` into
   production is the widest admin interface there is; see
   [`../secure-reliable-systems/SKILL.md`](../secure-reliable-systems/SKILL.md)
   (admin access, break-glass) and the safe-command rules in
   [`../production-operations/SKILL.md`](../production-operations/SKILL.md).

## Pick by need

| Need | Reach for | Not this |
|---|---|---|
| Start workers when a queue has enough work, scale to zero when drained | **KEDA `ScaledJob`** (run-to-completion) or `ScaledObject` (long-lived consumers) on the queue's own scaler | A CronJob that polls and decides in code; an HPA (can't reach zero on its own, kills pods mid-item) |
| Add nodes when pods are Pending | **Karpenter** where the provider has a mature implementation (AWS, AKS); **Cluster Autoscaler** elsewhere or for fixed node groups | Over-provisioning "just in case" |
| Quotas, priorities, fair sharing, all-or-nothing admission between job kinds or teams | **Kueue** (keeps the default scheduler) | Volcano or YuniKorn, unless you need gang scheduling for HPC/Spark |
| A run with several dependent steps, per-step retries, artifacts | **Argo Workflows** | A Job running a shell script of steps |
| Request-driven HTTP service that scales to zero | **Knative Serving**, or the lighter KEDA HTTP add-on | KEDA on CPU metrics |
| GPUs as cluster resources | **NVIDIA GPU Operator** (or the device plugin when the OS ships drivers); **DRA** only for per-claim device selection on new clusters | Hand-installed drivers on mutable nodes |
| Deploy from Git, keep clusters converged | **Flux** (light, one per cluster) or **Argo CD** (UI, hub-and-spoke) | `kubectl apply` from a laptop |
| Secrets in Git | **SOPS + age** (Flux decrypts natively); **External Secrets Operator** when a secret store already exists | Plain `Secret` YAML in Git; base64 is not encryption |
| HTTP ingress | **Gateway API** via your CNI's implementation (Cilium), Envoy Gateway, or Traefik; **cert-manager** for certificates; **external-dns** for records | ingress-nginx (retired) |
| Postgres | **CloudNativePG** | A hand-rolled StatefulSet |
| A work queue next to Postgres | **Postgres itself** (`SKIP LOCKED`, pgmq, outbox) | A broker added "for reliability" |
| Fan-out, replay without touching the database, broker isolation | **NATS JetStream** (smallest footprint) | Kafka below Kafka-scale needs |
| Backup of cluster objects and plain volumes | **Velero** (Kopia data mover) | Velero for databases: use the database's own WAL archiving |
| Admission rules | **Pod Security Admission** first; built-in **ValidatingAdmissionPolicy** for a few rules; **Kyverno** for many rules, mutation, generation and image verification | Gatekeeper unless you already use Rego |
| Local cluster | **kind** (CI, exact upstream versions), **k3d** (fastest dev), the production distro's own local mode when it has one | Pointing dev tools at production |
| Write an operator | Only when state must be continuously reconciled against something outside Kubernetes and no operator exists: **Kubebuilder** (Go), **kopf** (Python), **Metacontroller** (any language, simple parent → children) | An operator where a Helm chart, CronJob or `ScaledJob` would do |

The full comparisons are in the reference files ([where to look](#where-to-look)).

## Facts that changed recently (your memory may be stale)

Checked 2026-11-20. Versions move; see
[`references/versions.md`](references/versions.md) and verify before
relying on any number.

| Stale belief | Now |
|---|---|
| Kyverno `ClusterPolicy` / `Policy` | **No longer run on Kyverno 1.20+** (the legacy engine was removed). Write `policies.kyverno.io/v1` `ValidatingPolicy`, `MutatingPolicy`, `GeneratingPolicy`, `ImageValidatingPolicy`, `DeletingPolicy`. Most examples online are legacy |
| ingress-nginx is the default ingress | **Retired March 2026**: no releases, no security fixes. Use a Gateway API implementation |
| MinIO for in-cluster S3 | **Community repo archived 2026-04-25**, unmaintained. Use managed S3, Garage or SeaweedFS |
| Kueue `kueue.x-k8s.io/v1beta1` | **Not served since Kueue 0.20**: use `v1beta2`, migrate stored objects first |
| Strimzi `v1beta2`, ZooKeeper | **Strimzi 1.x is `kafka.strimzi.io/v1` and KRaft-only** |
| CNPG `barmanObjectStore` backups | **In-tree Barman Cloud is deprecated** (admission warnings), removed in CNPG 1.32. Use the Barman Cloud plugin (`ObjectStore` + `spec.plugins`) |
| MongoDB Community Operator | **Deprecated** in favour of MongoDB Controllers for Kubernetes (MCK) |
| `bitnami/*` images are free | Free images moved to **`bitnamilegacy`**; charts pulling `bitnami/*` need a new image source |
| `vmware-tanzu/velero` | Moved to **`velero-io/velero`**; restic backup removed (Kopia only) |
| `preStop: exec: [sleep, 5]` | Use **`preStop: {sleep: {seconds: 5}}`** (GA 1.34): no shell needed in distroless images |
| Sidecars need hacks to stop with a Job | **Native sidecars are GA (1.33):** an `initContainers` entry with `restartPolicy: Always` |
| Resizing a pod means a restart | **In-place resize is GA (1.35):** `kubectl patch pod --subresource resize` |
| Mutating webhooks for defaults | **MutatingAdmissionPolicy is GA (1.36)** alongside ValidatingAdmissionPolicy (GA 1.30) |
| Security tools are safe to float | `aquasecurity/trivy-action` and `setup-trivy` tags were force-pushed with a credential stealer in March 2026 (CVE-2026-33634). **Pin actions by commit SHA and images by digest, security tools included** |
| RunPod REST v1 | **Retired 2026-11-15**; v2 required |

## Queue-driven batch and scale to zero

The pattern behind "every X minutes, if more than Y items wait (or the
oldest waited longer than T), start workers, drain the backlog, stop":

- **KEDA `ScaledJob`** with the queue's scaler (PostgreSQL, NATS
  JetStream, Kafka, RabbitMQ, Prometheus). `pollingInterval` is X. Put
  Y and T in the trigger: in SQL, return "workers wanted", 0 unless the
  backlog passes Y or the oldest item passes T.
- **Workers claim items under a lease, loop until nothing is left, and
  exit.** Nothing idles, so there is no cooldown to tune.
- **`rollout.strategy: gradual`.** The default deletes running Jobs
  whenever the ScaledJob changes: an edit kills in-flight work.
- **Match `scalingStrategy` to what the number is computed from:**
  `default` when it covers all unfinished work, items running Jobs have
  claimed included; `accurate` when it covers only unclaimed items. The
  wrong one doubles or halves the workers.
- **Hard caps:** `maxReplicaCount` (workers, and therefore spend) and
  `activeDeadlineSeconds` on the Job. Workers stop claiming shortly
  before the deadline.
- **Leases decide what counts.** Items under a live lease count toward
  size but not toward Y or T. An expired lease means its worker died:
  count the item as pending again, and let the claim query take it.

Template and scaler gotchas:
[`references/autoscaling-and-batch.md`](references/autoscaling-and-batch.md).
The pattern itself (leases, heartbeats, priorities, backpressure) is
[`../infrastructure-patterns/references/work-queues-and-competing-consumers.md`](../infrastructure-patterns/references/work-queues-and-competing-consumers.md);
QoS, HPA and VPA are its
[`requests-limits-and-autoscaling`](../infrastructure-patterns/references/requests-limits-and-autoscaling.md).
GPUs that aren't cluster nodes (GPU clouds selling containers) need a
small launcher Job that rents and terminates them:
[`references/gpus.md`](references/gpus.md).

## Workloads: what this skill owns

Probes, requests and limits, QoS, PDBs and topology spread are in
[`../infrastructure-patterns/SKILL.md`](../infrastructure-patterns/SKILL.md).
This skill covers what decides whether a pod stops cleanly and a Job
finishes correctly:

- **Termination:** the pod leaves endpoints asynchronously, then
  `preStop` runs, then SIGTERM, then SIGKILL at
  `terminationGracePeriodSeconds` (counted from the start, *including*
  `preStop`). Handle SIGTERM in PID 1 (exec-form `ENTRYPOINT`, or
  `tini`). Add `preStop: {sleep: {seconds: 5}}` for serving pods.
- **Jobs:** `restartPolicy: Never` plus `podFailurePolicy` (fail fast on
  a deterministic exit code, ignore `DisruptionTarget`),
  `completionMode: Indexed` to shard backfills, `backoffLimitPerIndex`
  so one bad shard doesn't burn the whole Job, `activeDeadlineSeconds`,
  `ttlSecondsAfterFinished`. Every index must be idempotent: a pod can
  run twice.
- **Pod security context:** non-root, `allowPrivilegeEscalation: false`,
  `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]`,
  `seccompProfile: RuntimeDefault`, `automountServiceAccountToken: false`.

Details and YAML:
[`references/workloads-and-jobs.md`](references/workloads-and-jobs.md).

## GitOps in one paragraph

Pull-based GitOps keeps cluster credentials inside the cluster; CI only
needs to push an image and a commit. **Flux** is the light choice: four
controllers per cluster, native SOPS, real Helm releases, each cluster
independent. **Argo CD** gives the best UI and RBAC, but one hub holding
every cluster's credentials (its agent mode is pre-1.0). **Push deploys
from CI** (`helm upgrade` in GitHub Actions) are fine for one cluster:
nothing to run, but production write access lives in CI, nothing
corrects drift, and the API server must be reachable from runners. If
you push, authenticate with short-lived OIDC tokens bound to a
namespaced Role, never a stored admin kubeconfig. Comparison table:
[`references/gitops-and-delivery.md`](references/gitops-and-delivery.md).

## Multi-cluster and multi-region in one paragraph

**One independent cluster per region; never stretch a control plane
across regions.** etcd wants members in one data centre and an election
timeout of at least 10 × RTT, so every write would wait a WAN round
trip. Regions share only what you connect on purpose: database
replication, a few service calls over HTTPS or a private overlay, and
DNS. The hard part of multi-region is data, not Kubernetes: one writer,
replica lag, read-your-writes, and failover that operators like
CloudNativePG explicitly won't automate across clusters. Federation
tools (Karmada, OCM) and cross-cluster meshes pay off at fleet scale,
not at two or three clusters:
[`references/multi-cluster-and-networking.md`](references/multi-cluster-and-networking.md).

## Stateful services and messaging

Every stateful system you add is another thing to back up, upgrade,
monitor and fail over. Start from the database you already run:

- **Postgres as the queue** handles hundreds to low thousands of
  messages a second, transactionally with the data it describes.
- **Cursor trap:** a poller reading `WHERE id > :cursor` skips rows,
  because sequence values commit out of order. Claim rows instead, or
  read only below the oldest open transaction.
- **NATS JetStream** when you need independent fan-out, replay, or to
  isolate consumers from the database.
- **Kafka or Redpanda** for sustained high throughput, many consumer
  groups over long retention, or the Connect/Debezium ecosystem.
- **RabbitMQ** for rich routing and many AMQP or MQTT clients.
- **MongoDB** only when documents are the product or day-one sharding is
  real; Postgres JSONB covers flexible records.

Operators, footprints and decision tables:
[`references/stateful-and-messaging.md`](references/stateful-and-messaging.md).
Choosing the messaging *pattern* (pub/sub, work queue, transactional
outbox, idempotent consumer, dead-letter queue, CQRS) is
[`../infrastructure-patterns/SKILL.md`](../infrastructure-patterns/SKILL.md);
this skill covers running the broker or database on Kubernetes.

## Debugging in order

```bash
kubectl --context C -n NS get pods -o wide            # phase, restarts, node
kubectl --context C -n NS describe pod P              # events: scheduling, pulls, probes, OOM
kubectl --context C -n NS get events --sort-by=.lastTimestamp
kubectl --context C -n NS logs P -c CONTAINER --previous   # the crash, not the restart
kubectl --context C -n NS debug -it P --image=busybox:1.37 --target=CONTAINER
kubectl --context C auth can-i --list --as=system:serviceaccount:NS:SA
```

A symptom-to-cause table (Pending, CrashLoopBackOff, ImagePullBackOff,
OOMKilled, Terminating forever, stuck rollout):
[`references/troubleshooting.md`](references/troubleshooting.md).

## What NOT to do

- Don't write a CronJob that decides whether work exists; let a scaler
  decide.
- Don't stretch one cluster across regions, or put remote workers under
  a far control plane and call it a region.
- Don't add Kafka, RabbitMQ or MongoDB for "reliability" at a load
  Postgres handles; each is a second durability domain.
- Don't back up a database with volume copies when it has WAL
  archiving; don't keep the only backup inside the cluster it protects.
- Don't write Kyverno `ClusterPolicy` (dead on 1.20+) or deploy
  ingress-nginx or community MinIO (unmaintained).
- Don't float tags for images or actions, security tools included.
- Don't `kubectl edit` a GitOps-managed object; change Git.
- Don't set a PDB allowing 0 disruptions on a single replica: node
  drains and OS upgrades block forever.
- Don't point Tilt, Skaffold, mirrord or Telepresence at production.

## Related

- [`infrastructure-patterns`](../infrastructure-patterns/SKILL.md): probes, PDBs and safe rollouts, requests, limits and autoscalers, redundancy across zones, read replicas, and every messaging pattern.
- [`system-design`](../system-design/SKILL.md): sizing nodes, autoscaler ceilings, the limits inventory, failure domains.
- [`data-integrity`](../data-integrity/SKILL.md): RPO and RTO, backups and restore drills, volume sizing and WAL growth, safe deletion.
- [`data-pipelines`](../data-pipelines/SKILL.md): backfills, idempotent stages, per-source limits for crawler and worker fleets.
- [`production-operations`](../production-operations/SKILL.md): monitoring, alerting, on-call, incidents, runbooks, config canaries.
- [`secure-reliable-systems`](../secure-reliable-systems/SKILL.md): admin access, credential lifecycle, signed provenance and deploy policy.
- [`architecture-review`](../architecture-review/SKILL.md): failure-mode analysis and production readiness for a cluster or migration.
- [`helm-charts`](../helm-charts/SKILL.md), [`container-images`](../container-images/SKILL.md), [`github-actions`](../github-actions/SKILL.md): packaging, images, CI.

## Where to look

| File | Covers |
|---|---|
| [`references/autoscaling-and-batch.md`](references/autoscaling-and-batch.md) | KEDA (ScaledJob vs ScaledObject, activation, strategies, scalers, template), Karpenter, Cluster Autoscaler, Kueue, Volcano/YuniKorn, Argo Workflows/Events, Knative |
| [`references/gpus.md`](references/gpus.md) | GPU Operator, device plugin, time-slicing, MIG, DRA, Ray/serving stacks, GPUs outside the cluster and the launcher pattern |
| [`references/workloads-and-jobs.md`](references/workloads-and-jobs.md) | Termination and lifecycle hooks, Jobs (Indexed, failure and success policies), native sidecars, in-place resize, security context |
| [`references/gitops-and-delivery.md`](references/gitops-and-delivery.md) | Flux vs Argo CD vs CI push, repo layout, secrets (SOPS, Sealed Secrets, ESO, OpenBao), Helm vs Kustomize, progressive delivery |
| [`references/multi-cluster-and-networking.md`](references/multi-cluster-and-networking.md) | Region patterns, cross-cluster connectivity options, ClusterMesh/Submariner/Liqo/Karmada/meshes/Tailscale, global DNS steering, Postgres across regions, Gateway API, cert-manager, external-dns |
| [`references/provisioning.md`](references/provisioning.md) | Talos (and Omni), Cluster API, kubeadm/kubespray, k3s/RKE2, Metal3, Terraform/OpenTofu, Crossplane, a provider example (Hetzner) |
| [`references/stateful-and-messaging.md`](references/stateful-and-messaging.md) | CloudNativePG, Postgres queues and the cursor trap, NATS, RabbitMQ, Kafka/Redpanda, MongoDB, Valkey, object storage, Velero, etcd backups, decision tables |
| [`references/security-and-policy.md`](references/security-and-policy.md) | Pod Security Admission, VAP/MAP, Kyverno v1 policies with examples, Gatekeeper, NetworkPolicy, RBAC, runtime security, scanning, signing |
| [`references/tooling.md`](references/tooling.md) | Local clusters, inner-loop tools, operator frameworks, CLI helpers, registries and image caches, observability stacks, cost tools |
| [`references/troubleshooting.md`](references/troubleshooting.md) | Symptom → cause → command table |
| [`references/versions.md`](references/versions.md) | Versions and CNCF maturity checked 2026-11-20 |
