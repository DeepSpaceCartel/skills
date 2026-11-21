# Versions and maturity (checked 2026-11-20)

These are snapshots. Before depending on a version or a feature, check the project's releases page
(`https://github.com/<org>/<repo>/releases`) and its compatibility matrix. CNCF stages come from
https://www.cncf.io/projects/ and https://www.cncf.io/sandbox-projects/.

## Kubernetes

- **Current minor:** 1.37 (2026-08-26). Latest patch: 1.37.2.
- **Operators lag Kubernetes minors.** Before upgrading the cluster, check each operator's support
  range. For example, CloudNativePG 1.30 supports 1.34–1.36 and only *tests* 1.37.

| Feature | State |
|---|---|
| ValidatingAdmissionPolicy | GA 1.30 |
| MutatingAdmissionPolicy | GA 1.36 |
| Native sidecars | GA 1.33 |
| Job `backoffLimitPerIndex`, `successPolicy` | Stable 1.33 |
| `preStop` `sleep` action | GA 1.34 |
| DRA (`resource.k8s.io/v1`) | GA 1.34 |
| Structured authentication config (OIDC for the API server) | GA 1.34 |
| In-place pod resize | GA 1.35 |
| User namespaces, ImageVolume | GA 1.36 |
| Memory QoS (cgroup v2) | Beta, on, 1.37 |
| HPA scale to zero | Beta 1.37 |
| kube-proxy `ipvs` mode | Deprecated 1.37 |
| cgroup v1 | Kubelet fails on it by default since 1.35 |

## Tools

| Tool | Latest | Maturity |
|---|---|---|
| KEDA | 2.21.1 | CNCF graduated |
| Karpenter | 1.15.1 | SIG Autoscaling |
| Cluster Autoscaler | 1.36.2 | SIG Autoscaling |
| Kueue | 0.20.7 (serves `v1beta2` only) | SIG Scheduling |
| Volcano | 1.16.0 | CNCF incubating |
| Argo Workflows | 4.1.6 | CNCF graduated |
| Argo CD | 3.6.2 | CNCF graduated |
| Argo Rollouts | 1.10.2 | CNCF graduated |
| Flux | 2.10.1 | CNCF graduated |
| Flagger | 1.45.0 | Flux family |
| Knative | 1.24 | CNCF graduated |
| NVIDIA GPU Operator | 26.7.3 | NVIDIA |
| KubeRay | 1.7.2 | CNCF sandbox |
| KServe | 0.21.0 | CNCF incubating |
| llm-d | 1.0.0 | CNCF sandbox |
| SkyPilot | 0.14.3 | independent |
| Virtual Kubelet | 1.14.1 | CNCF sandbox |
| interLink | 0.6.3 | CNCF sandbox |
| Liqo | 1.3.0 | independent |
| Karmada | 1.19.1 | CNCF graduated |
| Open Cluster Management | 1.4.0 | CNCF incubating |
| vcluster | 0.38.0 | independent |
| Cilium | 1.20.5 | CNCF graduated |
| Submariner | 0.25.0 | CNCF sandbox |
| Istio | 1.32.0 | CNCF graduated |
| Linkerd | edge releases only (stable builds from vendors) | CNCF graduated |
| Gateway API | 1.7.0 | SIG Network |
| Envoy Gateway | 1.10.0 | Envoy (graduated) |
| Traefik | 3.7.19 | independent |
| cert-manager | 1.21.3 | CNCF graduated |
| external-dns | 0.24.0 | SIG Network |
| Helm | 4.3.2 | CNCF graduated |
| Kustomize | 5.8.3 | SIG CLI |
| SOPS | 3.13.3 | CNCF sandbox |
| External Secrets Operator | 2.15.0 | CNCF sandbox |
| Talos Linux | 1.14.6 (Kubernetes 1.33–1.37) | Sidero Labs |
| Cluster API | 1.14.4 | SIG Cluster Lifecycle |
| Crossplane | 2.4.3 | CNCF graduated |
| CloudNativePG | 1.30.2; Barman Cloud plugin 0.16.0 | CNCF incubating |
| Strimzi | 1.3.1 (`v1` API, KRaft only) | CNCF incubating |
| RabbitMQ / Cluster Operator | 4.4.1 / 2.23.3 | Broadcom |
| NATS server / Helm chart | 2.15.3 | CNCF graduated (2026-11) |
| MongoDB Controllers for Kubernetes | 1.15.0 | MongoDB |
| Percona Operator for MongoDB | 1.23.1 | Percona |
| Velero | 1.18.4 (`velero-io/velero`) | CNCF sandbox |
| Kyverno | 1.20.0 (legacy engine removed) | CNCF graduated |
| Gatekeeper | 3.23.1 | OPA, CNCF graduated |
| Falco | 0.45.2 | CNCF graduated |
| Tetragon | 1.8.0 | Cilium |
| Kubescape | 4.0.21 | CNCF incubating |
| Trivy / Trivy Operator | 0.76.2 / 0.36.1 | Aqua |
| cosign | 3.1.4 | Sigstore (OpenSSF) |
| Harbor | 2.15.5 | CNCF graduated |
| Zot | 2.1.23 | CNCF sandbox |
| kind / k3d / minikube | 0.33.0 / 5.9.0 / 1.39.0 | SIG / independent / Kubernetes |
| Tilt / Skaffold | 0.37.9 / 2.25.0 | Docker / Google |
| Kubebuilder | 4.16.0 | SIG API Machinery |
| OpenCost | 1.121.4 | CNCF incubating |
| OpenTelemetry Operator | 0.163.0 | OTel, CNCF graduated |
| ingress-nginx | retired March 2026 (last release 1.15.1) | — |
| MinIO community | archived 2026-04-25 | — |
