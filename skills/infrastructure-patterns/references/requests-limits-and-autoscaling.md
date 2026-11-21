# Requests, limits and autoscaling

## Problem

Kubernetes schedules by what pods *request*, enforces what they're *limited* to, and evicts by
how far they're over their request. Autoscalers read the same numbers. Wrong requests give
wrong packing, wrong eviction order and wrong scaling decisions; a missing one switches the
autoscaler off. This reference is about choosing the pattern (QoS class, which autoscaler, how
they interact). The numbers themselves (headroom, limits inventory, runway) are in
[`system-design` capacity-planning](../../system-design/references/capacity-planning.md).

## When to use / when NOT to use

- **Requests on every container,** always. They drive scheduling, QoS, eviction and HPA
  utilization.
- **Memory limits** on almost everything; a pod without one can take a node's memory.
- **CPU limits** only where you want hard throttling (noisy batch, untrusted code); on
  latency-sensitive services a CPU limit adds throttling latency (contested; measure).
- **HPA** for stateless services whose load shows up in CPU, memory or a custom metric.
- **KEDA** for queue- or event-driven workers, especially to scale to zero.
- **VPA** to right-size requests from observed use; not together with an HPA on the same
  CPU or memory metric.
- **Cluster autoscaler** (or an equivalent node provisioner) whenever pod autoscalers can ask
  for more than the current nodes hold.

## How it works

**Requests and limits.** The scheduler places a pod only where the node's allocatable fits its
requests. CPU over the limit is throttled; memory over the limit is OOM-killed by the kernel
(enforcement is reactive, so use can briefly exceed the limit), shown as `OOMKilled`.

**QoS classes** (set by Kubernetes from requests and limits):

| Class | Rule | Under node pressure |
|---|---|---|
| Guaranteed | Every container has CPU and memory requests equal to limits | Evicted last |
| Burstable | At least one request or limit, not Guaranteed | After BestEffort |
| BestEffort | No requests or limits at all | Evicted first |

When eviction is due to resource pressure, only pods using more than their requests are
candidates. Ephemeral storage is separate: QoS doesn't protect it, and a pod with no
ephemeral-storage request is an early eviction candidate under disk pressure (see
[`data-integrity` state-and-storage](../../data-integrity/references/state-and-storage.md)).

**HPA.** Every 15 s by default: desired = ceil(current x currentMetric / targetMetric).
Utilization is a percentage of the **request**; if a container lacks the request, the HPA takes
no action on that metric. Changes inside a 10% tolerance are ignored. Defaults: scale up
immediately, by up to 100% or 4 pods per 15 s (whichever is more); scale down with a 300 s
stabilization window. CPU from pods in their first 5 minutes is ignored unless they are ready
(`--horizontal-pod-autoscaler-cpu-initialization-period`), so a startup probe or readiness that
waits out the warm-up spike keeps it out of the decision. If the Deployment manifest still sets
`spec.replicas`, every `kubectl apply` resets the HPA's count.

**VPA** (installed separately). Recommender, updater and admission webhook. Modes: `Off`
(recommend only), `Initial` (set requests at pod creation), `Recreate` (evict to apply),
`InPlaceOrRecreate`, `InPlace`. The project says not to combine it with an HPA on the same CPU
or memory metric; VPA on memory with HPA on CPU or custom metrics is allowed.

**KEDA.** Reads an event source (queue length, lag, cron), handles 0↔1 itself and feeds an HPA
it manages for 1↔N. Defaults: `pollingInterval` 30 s, `cooldownPeriod` 300 s (applies only to
scaling to zero), `minReplicaCount` 0, `maxReplicaCount` 100. Long-running work killed by
scale-down is better run as a ScaledJob.

**Cluster autoscaler.** Adds nodes when pods are unschedulable by their *requests*; removes
nodes that are unneeded for a while and whose pods can move. Restrictive PDBs, bare pods
without a controller and pods with local storage block removal. Pods below the expendable
priority cutoff (default -10) don't trigger scale-up. **Overprovisioning** places pause pods at
-10, the lowest priority that still does: they hold spare nodes, real pods (priority 0 or more)
preempt them instantly, and the autoscaler adds a node for the evicted placeholders.

## Failure modes and what agents get wrong

- **No requests:** BestEffort pods, first to be evicted, invisible to the HPA, packed onto
  nodes without limit.
- **Requests from averages, limits far above:** overcommitted nodes that all burst at peak
  (see capacity-planning).
- **HPA min replicas sized for today,** not for losing a zone (see
  [graceful-degradation-and-static-stability](graceful-degradation-and-static-stability.md)).
- **HPA max beyond what downstreams take:** 60 pods x 20 connections against a database with a
  max of 500.
- **VPA in `Recreate` on a workload with no PDB:** it evicts pods to resize them.
- **Scaling a queue worker on CPU:** a worker blocked on I/O shows low CPU while the backlog
  grows; scale on queue depth or lag (KEDA).
- **Scale-to-zero without cold-start budget:** the first message waits for pod start plus image
  pull.
- **`spec.replicas` in a GitOps manifest with an HPA,** so every sync fights the autoscaler.

## Implementation notes

- **Kubernetes:** `resources.requests/limits`, `LimitRange` for defaults, `ResourceQuota` per
  namespace; HPA `autoscaling/v2` with `behavior`; VPA CRD; KEDA `ScaledObject`/`ScaledJob`;
  cluster autoscaler or another node provisioner.
- **Mesh:** sidecars have their own requests; include them in pod sizing.
- **Managed:** managed Kubernetes offers node-pool autoscaling and often a VPA add-on; check the
  provider's node-provisioning limits and quotas (inventory in capacity-planning).

## Example

A queue worker that scales on backlog, never on CPU, with Burstable QoS and a memory limit.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: {name: thumbnailer}
spec:
  # no spec.replicas: KEDA's HPA owns it
  selector: {matchLabels: {app: thumbnailer}}
  template:
    metadata: {labels: {app: thumbnailer}}
    spec:
      containers:
      - name: worker
        image: registry.example/thumbnailer@sha256:<digest>
        resources:
          requests: {cpu: 500m, memory: 768Mi, ephemeral-storage: 2Gi}
          limits:   {memory: 768Mi, ephemeral-storage: 4Gi}   # no CPU limit
---
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata: {name: thumbnailer}
spec:
  scaleTargetRef: {name: thumbnailer}
  minReplicaCount: 1        # keep one warm; 0 would add cold-start to the first job
  maxReplicaCount: 40       # 40 x 4 DB connections = 160, under the pool's 200
  pollingInterval: 15
  cooldownPeriod: 300
  triggers:
  - type: <queue-scaler>    # e.g. the scaler for your broker; target ~50 messages per replica
    metadata: {}
```

Memory request equals the limit so OOM behaviour is predictable; the ephemeral-storage request
keeps the pod off the front of the disk-pressure eviction queue. The trigger type and its
metadata depend on the broker and are left as a placeholder. ScaledObject fields are from
KEDA's spec reference; resource fields from the Kubernetes docs.

## Review checklist

1. Does every container set CPU and memory requests (and ephemeral storage where it writes locally)?
2. Is the QoS class chosen on purpose for each workload, and are memory limits set?
3. Is the HPA metric one that tracks the real bottleneck (CPU for compute-bound, queue lag for workers)?
4. Is `minReplicas` sized for losing a domain, and `maxReplicas` within downstream limits?
5. Is `spec.replicas` absent from manifests of autoscaled workloads?
6. Is VPA kept off the HPA's metric, and are VPA evictions covered by a PDB?
7. Can the cluster autoscaler add nodes fast enough, and is there overprovisioning for spikes?
8. Are startup CPU spikes kept out of HPA decisions (startup probe or readiness timing)?

## Related

[bulkheads-and-isolation](bulkheads-and-isolation.md) (quotas, priority),
[disruption-budgets-and-safe-rollouts](disruption-budgets-and-safe-rollouts.md),
[graceful-degradation-and-static-stability](graceful-degradation-and-static-stability.md),
[load-shedding](load-shedding.md) (throttle while scaling),
[`system-design` capacity-planning](../../system-design/references/capacity-planning.md),
[`data-integrity` state-and-storage](../../data-integrity/references/state-and-storage.md).

## Sources

Kubernetes: [resource management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/),
[pod QoS](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/),
[HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/)
(the old `/tasks/run-application/horizontal-pod-autoscale/` path has moved),
[VPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/vertical-pod-autoscale/),
[autoscaling overview](https://kubernetes.io/docs/concepts/workloads/autoscaling/), read from the
[website source](https://github.com/kubernetes/website/tree/main/content/en/docs).
VPA [README](https://github.com/kubernetes/autoscaler/blob/master/vertical-pod-autoscaler/README.md).
Cluster autoscaler [FAQ](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/FAQ.md).
KEDA [scaling deployments](https://keda.sh/docs/latest/concepts/scaling-deployments/) and
[ScaledObject spec](https://keda.sh/docs/latest/reference/scaledobject-spec/).
