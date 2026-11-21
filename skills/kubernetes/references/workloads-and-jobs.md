# Workloads and Jobs

Checked against kubernetes.io for v1.37 on 2026-11-20. Probes, requests and limits, QoS, PDBs and
topology spread are in [`../../infrastructure-patterns/SKILL.md`](../../infrastructure-patterns/SKILL.md).

## Termination

Docs: https://kubernetes.io/docs/concepts/containers/container-lifecycle-hooks/ and
https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination

1. The pod is marked Terminating and removed from EndpointSlices. Removal is asynchronous, so
   requests can still arrive for a moment.
2. `preStop` runs (`exec`, `httpGet` or `sleep`).
3. SIGTERM goes to PID 1 of each container.
4. At `terminationGracePeriodSeconds` (default 30, counted from step 1 and **including**
   `preStop`), SIGKILL.

What this means for the app:

- **Handle SIGTERM:** stop taking new work, finish or hand back in-flight work, close connections,
  exit 0.
- **Make sure the app is PID 1.** Use exec-form `ENTRYPOINT ["app"]`, or `tini` / `--init`.
  Shell-form `ENTRYPOINT app` runs under `/bin/sh`, which doesn't forward signals.
- **Serving pods:** cover endpoint propagation with `preStop: {sleep: {seconds: 5}}`. The `sleep`
  action is GA since 1.34, so distroless images need no `/bin/sleep`.
- **Queue consumers:** either set the grace period to the longest item you're willing to finish,
  or make items resumable (a lease or visibility timeout), so a SIGKILL only causes a redelivery.

```yaml
spec:
  terminationGracePeriodSeconds: 60
  containers:
  - name: api
    lifecycle:
      preStop:
        sleep: {seconds: 5}
```

## Jobs

Docs: https://kubernetes.io/docs/concepts/workloads/controllers/job/

| Field | Status | Use |
|---|---|---|
| `completionMode: Indexed` | stable | Each pod gets `JOB_COMPLETION_INDEX`: shard a backfill by index → key range |
| `backoffLimitPerIndex`, `maxFailedIndexes` | stable 1.33 | One bad shard doesn't burn the whole Job's retries |
| `podFailurePolicy` | GA | `FailJob` on a deterministic exit code; `Ignore` the `DisruptionTarget` condition (preemption, drain) so it isn't counted as a failure |
| `successPolicy` | stable 1.33 | Finish early when chosen indexes succeed |
| `podReplacementPolicy: Failed` | stable 1.34 | No overlap between an old pod still terminating and its replacement |
| `managedBy` | stable 1.35 | Hand a Job to an external controller (Kueue, MultiKueue) |
| `suspend` | stable | Pause or queue (what Kueue toggles) |
| `activeDeadlineSeconds` | stable | Hard stop for the whole Job |
| `ttlSecondsAfterFinished` | stable | Clean up finished Jobs |

```yaml
apiVersion: batch/v1
kind: Job
metadata: {name: backfill}
spec:
  completionMode: Indexed
  completions: 50
  parallelism: 5
  backoffLimitPerIndex: 3
  maxFailedIndexes: 5
  activeDeadlineSeconds: 86400
  ttlSecondsAfterFinished: 86400
  podFailurePolicy:
    rules:
    - action: FailIndex          # a bug, not a flake: stop retrying this shard
      onExitCodes: {containerName: worker, operator: In, values: [42]}
    - action: Ignore             # evicted or preempted: retry without counting it
      onPodConditions: [{type: DisruptionTarget}]
  template:
    spec:
      restartPolicy: Never
      priorityClassName: batch-low
      containers:
      - name: worker
        image: registry.example.com/backfill@sha256:...
        env:
        - {name: SHARDS, value: "50"}
```

Gotchas:
- **Prefer `restartPolicy: Never`** with a failure policy. `OnFailure` with `backoffLimit` counts
  container restarts in confusing ways.
- **Make every index idempotent.** A pod can run twice.
- **Give backfills a low PriorityClass,** so they yield to serving workloads.

## Native sidecars

GA since 1.33. A sidecar is an `initContainers` entry with `restartPolicy: Always`:
- it starts before the app containers and keeps running;
- it stops *after* them;
- it doesn't block Job completion;
- it supports probes.

Use it for log shippers, proxies and backup agents.

```yaml
spec:
  initContainers:
  - name: proxy
    image: registry.example.com/proxy@sha256:...
    restartPolicy: Always
  containers:
  - name: app
    image: registry.example.com/app@sha256:...
```

## In-place resize

- **Status:** GA since 1.35. Init-container resize is GA in 1.37; pod-level resize is beta.
- **How:** `kubectl patch pod P --subresource resize --patch '{"spec":{"containers":[{"name":"app","resources":{"requests":{"cpu":"2"}}}]}}'`.
- **Restart behaviour:** set per container with `resizePolicy` (`NotRequired` or
  `RestartContainer`).
- **Deferred resizes:** if the node can't fit the new size, the resize stays `Deferred`.
- **Lowering memory** below current usage needs a restart.
- **It changes the Pod, not its template.** The next rollout reverts it unless the template (or
  VPA) changes too.

## Pod security context

PSA `restricted` enforces most of these. Set them explicitly so the manifest is portable:

```yaml
spec:
  automountServiceAccountToken: false      # unless the pod calls the API
  serviceAccountName: app                  # one per workload
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    seccompProfile: {type: RuntimeDefault}
  containers:
  - name: app
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities: {drop: ["ALL"]}
    volumeMounts:
    - {name: tmp, mountPath: /tmp}
  volumes:
  - name: tmp
    emptyDir: {}
```

- **User namespaces** (`hostUsers: false`) are GA since 1.36. They map container root to an
  unprivileged host user, which is worth turning on where the runtime supports it.
- **Secrets:** mount them as files rather than env vars where you can. Env vars leak into crash
  dumps and child processes.
