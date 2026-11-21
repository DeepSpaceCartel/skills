# Tooling

Checked 2026-11-20.

## Local clusters

| Tool | Choose when | Gotchas |
|---|---|---|
| **kind** | CI, multi-node tests, exact upstream versions | No LoadBalancer by default (use cloud-provider-kind); get images in with `kind load` or a local registry |
| **k3d** (k3s in Docker) | The fastest local loop; built-in registry (`k3d registry create`) | k3s isn't upstream: an embedded datastore and bundled Traefik and ServiceLB. Disable what production doesn't use |
| **minikube** | Many drivers (VM, Docker, Podman), add-ons, local GPU | Heavier; one node by default |
| **The production distro locally** (e.g. `talosctl cluster create`) | Production runs that distro and you want the same OS and API | Docker or QEMU only |

One local cluster at a time on a memory-limited machine.

## Inner loop

| Tool | What | Notes |
|---|---|---|
| **Tilt** | A `Tiltfile` (Starlark) builds, deploys and live-syncs many services, with a web UI | Best for multi-service dev; the UI costs memory |
| **Skaffold** | A build → tag → deploy pipeline (`skaffold dev`, `skaffold run`) with Helm and Kustomize | Also usable in CI; less interactive than Tilt |
| **mirrord** | Run a *local* process as if it were inside a pod: mirror or steal its traffic, env, files and DNS | Spawns an agent pod, which needs permission; traffic stealing on shared clusters needs the paid operator |
| **Telepresence** (CNCF sandbox) | Intercept a service's traffic to your laptop | Installs a traffic manager in the cluster |
| **DevSpace** (CNCF sandbox) | Dev containers in the cluster with file sync | Releases have slowed |

Build and deploy into a local cluster with Tilt or Skaffold. Debug against a real non-production
cluster with mirrord. Never point any of these at production.

## Writing an operator

Write one only if all three hold:
- state must be **continuously reconciled** against something outside Kubernetes, or there's
  multi-step lifecycle logic (failover, ordered upgrades, backup orchestration);
- no maintained operator does it;
- you'll maintain it through Kubernetes API changes.

Otherwise use one of these:
- a Helm chart or Kustomize;
- a CronJob or a KEDA `ScaledJob`;
- a Kyverno `GeneratingPolicy`;
- Metacontroller;
- a loop inside the app.

| Framework | Notes |
|---|---|
| **Kubebuilder** (Go, controller-runtime) | The upstream scaffold and reference |
| **Operator SDK** | Wraps Kubebuilder; adds Ansible and Helm operators and OLM bundles. Use it if you target OLM or OpenShift |
| **Metacontroller** | A webhook in any language maps a parent resource to its children; little code |
| **kopf** (Python) | Decorator-based handlers; small operators in Python shops; a small maintainer base |

When you do write one:
1. **Level-based, idempotent reconcile.** React to the current state, not to events.
2. **Finalizers** for cleanup outside the cluster.
3. **Status conditions** to report state.
4. **Owner references** for garbage collection.
5. **Requeue with backoff;** never hot-loop.
6. **Minimal RBAC.**
7. **Conversion webhooks** once a CRD has more than one served version.

## CLI helpers

| Tool | Use |
|---|---|
| **k9s** | A terminal UI for browsing, logs, exec and port-forward. Use `--readonly` against production |
| **stern** | Tail logs from many pods by regex or selector: `stern -n NS app --since 10m` |
| **kubectx / kubens** | Humans switching context. **Agents pass `--context` / `-n` instead** |
| **krew** | The kubectl plugin manager (`who-can`, `neat`, `tree`, `cnpg`). Plugins are unvetted third-party code |
| **Headlamp** (kubernetes-sigs, CNCF sandbox) | A web UI for clusters |

## Registries and image distribution

| Option | Fit |
|---|---|
| **The registry next to your code host** (GHCR, GitLab, a cloud registry) | The default for small teams: CI authenticates natively; the cluster pulls with an `imagePullSecret` or workload identity |
| **Zot** (CNCF sandbox) | A light, single-binary OCI registry with OCI referrers (signatures, SBOMs), mirroring and pull-through caching |
| **Harbor** (CNCF graduated) | A full registry: projects, RBAC, scanning, replication, proxy cache, signatures. Heavy: needs Postgres, Redis and several components |
| **Spegel** | A peer-to-peer layer cache between nodes, configured through containerd mirrors. It cuts pull latency and egress, and keeps already-present images pullable during registry outages. A cache, not a registry |

## Observability

| Tool | Fit | Gotchas |
|---|---|---|
| **kube-prometheus-stack** | The default bundle: Prometheus Operator, Prometheus, Alertmanager, Grafana, node-exporter, rules | Memory grows with series cardinality. Helm doesn't upgrade its CRDs. Trim the default rules |
| **VictoriaMetrics** (single node + vmagent) | Prometheus-compatible with lower memory and disk; reads ServiceMonitors through its operator | The cluster version and some features are enterprise-only |
| **Grafana Loki** | Logs indexed by labels only | **Keep labels low-cardinality.** Promtail is deprecated: use Alloy |
| **Grafana Tempo** | Traces on object storage | Check the 3.x upgrade notes |
| **Grafana Alloy** | One agent: OpenTelemetry Collector, Prometheus scraping, log shipping | Replaces Grafana Agent and Promtail |
| **OpenTelemetry Operator** (OTel is CNCF graduated) | `OpenTelemetryCollector` and auto-instrumentation `Instrumentation` resources | Injection needs cert-manager for its webhook; injected init containers must pass PSA |

Logging conventions: [`../../structured-logging/SKILL.md`](../../structured-logging/SKILL.md).
What to measure and alert on (golden signals, heartbeats, expiry checks):
[`../../production-operations/references/monitoring-and-alerting.md`](../../production-operations/references/monitoring-and-alerting.md).

## Cost

- **OpenCost** (CNCF incubating) allocates cost per namespace, label and pod from Prometheus
  metrics plus cloud pricing. For providers without a pricing integration, supply custom per-node
  prices.
- **Commercial node-automation and FinOps tools** (Kubecost, Cast AI, Vantage) are aimed mostly at
  the hyperscalers. Check that your provider is supported before evaluating one.
- **Most of the savings** on fixed-price nodes come from request-versus-usage efficiency
  (rightsizing). Compare `kube_pod_container_resource_requests` with actual usage, or use VPA
  recommendations.
