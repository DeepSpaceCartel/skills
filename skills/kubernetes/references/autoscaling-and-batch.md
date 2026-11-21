# Autoscaling and batch

Checked 2026-11-20 against the KEDA 2.21, Karpenter, Cluster Autoscaler,
Kueue 0.20, Argo and Knative docs. Re-check field names against the docs
for the installed version. QoS classes, HPA and VPA, and how autoscalers
interact with requests are in
[`../../infrastructure-patterns/references/requests-limits-and-autoscaling.md`](../../infrastructure-patterns/references/requests-limits-and-autoscaling.md);
node and quota ceilings in
[`../../system-design/references/capacity-planning.md`](../../system-design/references/capacity-planning.md).

## KEDA

KEDA scales on external signals (queue depth, a SQL result, a Prometheus
query, a cron window). Two CRDs:

| | `ScaledObject` | `ScaledJob` |
|---|---|---|
| Scales | a Deployment, StatefulSet or anything with `/scale` | creates `batch/v1` Jobs |
| 0 ↔ 1 | KEDA (activation) | KEDA (activation) |
| 1 ↔ N | an HPA that KEDA creates | KEDA computes new Jobs each poll |
| Fits | long-lived consumers that are safe to stop at any time (short, idempotent items, graceful SIGTERM) | run-to-completion work an HPA scale-down must not kill mid-item (GPU batch, encodes, ETL chunks) |
| Extras | `cooldownPeriod` (default 300 s, only for scaling to 0), `fallback`, HPA `behavior` | no cooldown and no `fallback`: Jobs end when the work does |

Docs: https://keda.sh/docs/2.21/concepts/scaling-jobs/,
https://keda.sh/docs/2.21/reference/scaledjob-spec/

### Semantics that matter

- **`pollingInterval`** defaults to 30 s, for both kinds.
- **Target vs activation.** Each scaler has a target value for 1..N
  (`targetQueryValue`, `lagThreshold`, `threshold`, `value`) and an
  activation value (`activation…`, default 0) for 0 ↔ 1.
  - Activation is **strictly greater than**.
  - Activation is ignored when `minReplicaCount >= 1`.
- **ScaledJobs honour activation.** The ScaledJob page doesn't say so,
  but in the KEDA 2.21.1 source (`pkg/scaling/executor/scale_jobs.go`),
  Jobs are created only when a trigger is active.
- **`maxReplicaCount`** (default 100) caps Jobs: new Jobs per poll are
  capped by max minus running.
- **History limits:** `successfulJobsHistoryLimit` and
  `failedJobsHistoryLimit` default to 100. Lower them.
- **Scaling strategies.** `maxScale = min(maxReplicaCount, ceil(queueLength / target))`.
  - `default`: new = `maxScale − running`. Correct when the metric
    counts **all unfinished work, including items running Jobs have
    claimed**.
  - `accurate`: for metrics that **exclude claimed or locked items**.
  - `eager`: fill every free slot up to max.
  - `custom`: subtract a fixed amount or a fraction of running Jobs.
  - The wrong choice doubles or halves the worker count.
- **`rollout.strategy`:** `default` **deletes running Jobs** when the
  ScaledJob spec changes. Use `gradual` for anything expensive, or for a
  Job that owns an external resource such as a rented machine.
- **Pause:** annotate with `autoscaling.keda.sh/paused: "true"`.

### Scalers for job pipelines

| Scaler | Key fields | Gotchas |
|---|---|---|
| `postgresql` | `query` (returns one number), `targetQueryValue`, `activationTargetQueryValue`, auth via `TriggerAuthentication` | Wrap in `COALESCE(…, 0)`. The query runs every poll, so keep it on an index. Connect to Postgres directly, not through a transaction-mode pooler. Thresholds and ages can live in the SQL |
| `nats-jetstream` | `natsServerMonitoringEndpoint` (`host:8222`), `account`, `stream`, `consumer`, `lagThreshold` | Reads the HTTP monitoring port, so KEDA must reach 8222. Needs a durable consumer |
| `kafka` | `bootstrapServers`, `consumerGroup`, `topic`, `lagThreshold` (10) | Replicas never exceed the partition count unless `allowIdleConsumers: true` |
| `rabbitmq` | `host`, `mode` (`QueueLength`, `MessageRate`), `value`, `queueName` | Unacked messages and rate modes need `protocol: http` (the management API) |
| `prometheus` | `serverAddress`, `query`, `threshold` | Empty results are ignored by default; set `ignoreNullValues: false` to fail loudly |
| `cron` | `timezone`, `start`, `end`, `desiredReplicas` | Never `desiredReplicas: 0`. Combine with a queue trigger to allow work only in a window |

### Template: backlog-triggered batch on a Postgres work table

```yaml
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata: {name: pipeline-db, namespace: pipeline}
spec:
  secretTargetRef:                        # a Secret holding a libpq connection string
  - {parameter: connection, name: pipeline-db, key: url}   # check names against the scaler docs
---
apiVersion: keda.sh/v1alpha1
kind: ScaledJob
metadata: {name: batch-worker, namespace: pipeline}
spec:
  pollingInterval: 300                    # X: check every 5 minutes
  maxReplicaCount: 2                      # hard cap on workers (and spend)
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 5
  rollout: {strategy: gradual}            # edits never kill running Jobs
  scalingStrategy: {strategy: default}    # the number covers all unfinished work, running Jobs included
  jobTargetRef:
    backoffLimit: 2
    activeDeadlineSeconds: 14400          # no runaway Job
    ttlSecondsAfterFinished: 3600
    template:
      spec:
        restartPolicy: Never
        automountServiceAccountToken: false
        securityContext: {runAsNonRoot: true, seccompProfile: {type: RuntimeDefault}}
        containers:
        - name: worker
          image: registry.example.com/worker@sha256:...
          env:
          - {name: STOP_CLAIMING_AFTER_SECONDS, value: "13500"}   # finish before the deadline
          resources: {requests: {cpu: 500m, memory: 512Mi}, limits: {memory: 512Mi}}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: {drop: [ALL]}
  triggers:
  - type: postgresql
    authenticationRef: {name: pipeline-db}
    metadata:
      # Returns "workers wanted": 0 unless more than Y items wait or the oldest waited longer than T.
      # A claimed row whose lease expired counts as pending again (its worker died), so it can
      # fire a new start. A row with a live lease counts toward size but not toward Y or T.
      query: >
        WITH q AS (
          SELECT enqueued_at,
                 (state = 'claimed' AND lease_until > now()) AS live
          FROM work_items WHERE state IN ('pending', 'claimed'))
        SELECT CASE WHEN count(*) FILTER (WHERE NOT live) > 5000
                      OR min(enqueued_at) FILTER (WHERE NOT live)
                         < now() - interval '6 hours'
                    THEN ceil(count(*) / 20000.0) ELSE 0 END
        FROM q
      targetQueryValue: "1"
      activationTargetQueryValue: "0"
```

The worker:
1. **Claims a batch** with `SELECT … FOR UPDATE SKIP LOCKED`. The claim query takes rows that are
   `pending` *or* `claimed` with an expired lease, and sets `state = 'claimed'` and a new
   `lease_until`.
2. **Processes it and marks it done.**
3. **Repeats until nothing is left,** then exits 0.

It stops claiming new batches shortly before `activeDeadlineSeconds`, so the deadline never lands
mid-item. Keep the trigger query on an index over `(state, enqueued_at)`.

**How the strategy follows from the query.** Here the number is computed from *all* unfinished
rows, claimed ones included, so the Jobs already working are part of it, and `default` subtracts
the running Jobs. If the number came from pending rows only, the running Jobs would not be part of
it, and `accurate` would be the right strategy.

### KEDA with Kueue

ScaledJob Jobs can carry `kueue.x-k8s.io/queue-name`, and Kueue then
suspends them until quota frees. It's unclear whether KEDA counts
suspended Jobs as running: test before relying on it.

## Node autoscaling

### Karpenter

- **What it does:** watches unschedulable pods and creates the cheapest
  fitting node from the provider's whole catalogue (a `NodeClaim`). It
  removes or replaces empty and under-used nodes (consolidation). There
  are no node groups.
- **Objects:** a `NodePool` (`karpenter.sh/v1`: requirements, taints,
  `limits`, `disruption`, `expireAfter`, `nodeClassRef`) plus a provider
  NodeClass (for example `EC2NodeClass`).
- **Providers:** AWS is the reference. Azure documents itself for AKS
  only. Community providers exist for others (GCP, Hetzner Cloud, OCI,
  Proxmox, Cluster API and more); check that the instance types you need
  are covered, since a provider may have no GPU types.
- **Disruption settings:**
  - `consolidationPolicy`: `WhenEmpty` or `WhenEmptyOrUnderutilized`
    (the default).
  - `consolidateAfter`: the stability window.
  - Budgets.
  - The pod annotation `karpenter.sh/do-not-disrupt: "true"` protects
    batch pods from consolidation and drift (not from expiry).
- **Batch node pools:** `WhenEmpty` with `consolidateAfter` set to a few
  minutes, so the node goes as soon as its last Job ends.
- **Pick Karpenter** when the provider has a mature implementation and
  you want instance-type flexibility.
- **Pick Cluster Autoscaler** otherwise, for fixed node groups, and for
  Kueue `ProvisioningRequest`, which Karpenter doesn't implement.

### Cluster Autoscaler

- **What it does:** resizes predefined node groups when pods are Pending
  or nodes are under-used.
- **One cloud provider per process.** A cluster with nodes from two
  providers needs two instances, each with its own groups. Running two
  side by side is not a documented recipe, so prototype it first.
- **Scale from zero** works when the provider can describe a template
  node for an empty group. Label and taint the group so the simulation
  matches real nodes.
- **GPU groups:** taint them. The provider must report GPU capacity in
  the template for scale from zero. Until the device plugin reports
  `nvidia.com/gpu`, a GPU node counts as not ready.

## Kueue

Kueue (v0.20, Kubernetes SIG Scheduling) does job-level admission on top
of the default scheduler:

- **Queues and quotas:** a `LocalQueue` per namespace feeds a
  `ClusterQueue`, with quotas per `ResourceFlavor`.
- **Sharing:** cohorts and borrowing, fair sharing, priorities and
  preemption.
- **Gang admission:** all or nothing.
- **AdmissionChecks** that wait for capacity.
- **Workload types:** Job, JobSet, RayJob and RayCluster, Kubeflow jobs,
  plain Pods, Deployments and more.

It does not create nodes.

- **API:** 0.20 **no longer serves `v1beta1`**. Use
  `kueue.x-k8s.io/v1beta2`, and run the migration before upgrading.
- **ProvisioningRequest admission check** (GA since 0.14): Kueue asks
  Cluster Autoscaler (1.29 or later) for capacity, all or nothing.
- **MultiKueue** (beta): a manager cluster holds the quota and dispatches
  workloads to worker clusters, each of which runs Kueue.
- **Pick it** when several teams or job kinds share scarce accelerators.
  For one job kind it mostly adds a quota knob (for example
  `nominalQuota: {nvidia.com/gpu: 2}` as a spend cap). It has no
  "backlog > Y" trigger, so something still has to create the Jobs.

```yaml
apiVersion: kueue.x-k8s.io/v1beta2
kind: ClusterQueue
metadata: {name: gpu}
spec:
  namespaceSelector: {}
  resourceGroups:
  - coveredResources: ["cpu", "memory", "nvidia.com/gpu"]
    flavors:
    - name: gpu-flavor
      resources:
      - {name: cpu, nominalQuota: 32}
      - {name: memory, nominalQuota: 256Gi}
      - {name: nvidia.com/gpu, nominalQuota: 2}
```

**Kueue, Volcano or YuniKorn?**
- **Kueue:** admission control, and it keeps kube-scheduler.
- **Volcano** (CNCF incubating): a second scheduler with gang
  scheduling, for HPC and distributed training.
- **YuniKorn** (Apache): multi-tenant Spark platforms.

Don't run several schedulers casually.

## Workflows and eventing

| Tool | Use when | Not when |
|---|---|---|
| **Job / CronJob** | One run-to-completion task, or a fixed schedule. CronJob: `concurrencyPolicy: Forbid`, `startingDeadlineSeconds`, `timeZone` | The CronJob's code decides *whether* work exists (that's a scaler's job) |
| **Argo Workflows** (v4, CNCF graduated) | DAGs and steps with artifacts, per-step retries, fan-out and fan-in, exit handlers, a UI. The Python SDK is now Hera | A single-step worker: a ScaledJob is simpler |
| **Argo Events** | Start workflows from external events (webhooks, NATS, Kafka, S3, calendar) | Triggering on backlog depth: it reacts per event |
| **Knative Serving** (CNCF graduated) | Request-driven HTTP with scale to zero through the activator | Multi-hour batch: request timeouts |
| **Knative Eventing `JobSink`** | One Job per CloudEvent, deduplicated on (`source`, `id`) | Batching many events into one run |
| **KEDA HTTP add-on** (beta) | Lighter HTTP scale to zero than Knative | Rich traffic splitting |

v4 of Argo Workflows validates CRDs fully by default; convert old
manifests with `argo convert`.
