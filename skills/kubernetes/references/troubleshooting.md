# Troubleshooting

Always pass `--context` and `-n`. Read before you change anything; on GitOps-managed clusters,
fix things in Git. During a live incident, mitigate first and follow
[`../../production-operations/references/incident-response.md`](../../production-operations/references/incident-response.md);
probe design is in
[`../../infrastructure-patterns/references/health-checks-and-probes.md`](../../infrastructure-patterns/references/health-checks-and-probes.md).

## Order of inspection

```bash
kubectl --context C -n NS get pods -o wide
kubectl --context C -n NS describe pod P                 # read Events at the bottom
kubectl --context C -n NS get events --sort-by=.lastTimestamp | tail -30
kubectl --context C -n NS logs P -c CONTAINER --previous # the crash, not the restart
kubectl --context C -n NS get pod P -o jsonpath='{.status.containerStatuses[*].lastState}'
kubectl --context C top pods -n NS --containers           # needs metrics-server
kubectl --context C -n NS debug -it P --image=busybox:1.37 --target=CONTAINER
kubectl --context C get --raw /readyz?verbose             # API server health
```

## Symptom → cause

| Symptom | Likely causes | Check |
|---|---|---|
| `Pending` | No node fits the requests; taints without matching tolerations; affinity or topology too strict; PVC unbound; a quota exceeded; the autoscaler at its limit | `describe pod` (FailedScheduling message), `get pvc`, `describe resourcequota`, autoscaler logs or status |
| `ContainerCreating` for a long time | Volume attach or mount, image pull, CNI, a missing Secret or ConfigMap | `describe pod` events, `get volumeattachment` |
| `ImagePullBackOff` / `ErrImagePull` | Wrong name or tag, a private registry without `imagePullSecrets`, a rate limit, architecture mismatch | Events show the exact registry error |
| `CrashLoopBackOff` | The app exits on start: config, a missing env var, migration, permissions on a read-only root filesystem | `logs --previous`; exit code in `lastState` |
| `OOMKilled` (exit 137) | The memory limit is below the peak | `lastState.terminated.reason`; raise the limit or fix the leak |
| Exit 137 without OOM | SIGKILL after the grace period: the app ignored SIGTERM | Check the app is PID 1 and handles SIGTERM |
| Restarts with `Liveness probe failed` | The probe checks dependencies, or times out during GC or startup | Add a startup probe; keep liveness dependency-free |
| `Running` but no traffic | Readiness failing; Service selector doesn't match the labels; NetworkPolicy; wrong `targetPort` | `get endpointslices -l kubernetes.io/service-name=S`, `describe svc` |
| Rollout stuck | New pods never become Ready; a PDB blocks; `maxUnavailable: 0` with no spare room | `rollout status`, `get rs`, `describe pdb` |
| `Terminating` forever | A finalizer that its controller isn't running to remove; the node is gone | `get pod -o jsonpath='{.metadata.finalizers}'`. Remove a finalizer only after confirming its controller is gone, since it may guard real cleanup |
| Namespace stuck `Terminating` | Leftover objects with finalizers, or an unavailable aggregated API | `get namespace NS -o yaml` (status conditions name the blocker) |
| Node `NotReady` | kubelet down, network partition, disk or memory pressure | `describe node` (conditions), the distro's node logs |
| Evictions | Node pressure (memory, disk, ephemeral storage); BestEffort pods go first | `get events --field-selector reason=Evicted` |
| A Job never finishes | A sidecar that isn't a native sidecar keeps the pod alive; `backoffLimit` retries; `activeDeadlineSeconds` not set | Use native sidecars; describe the Job's conditions |
| Webhook timeouts on every apply | An admission webhook (policy engine, operator) is down with `failurePolicy: Fail` | `get validatingwebhookconfigurations,mutatingwebhookconfigurations`, then the webhook pods |
| GitOps change not applied | A source or Kustomization failure, a suspended object, a dependency not ready | `flux get all -A` / `flux events`; `argocd app get` |

## Safe interventions

- **Restart without changing the spec:** `kubectl rollout restart deployment/D`. On GitOps
  clusters this is fine: it only stamps an annotation.
- **Pause a scaler:** annotate the ScaledObject or ScaledJob with
  `autoscaling.keda.sh/paused: "true"`.
- **Suspend a CronJob:** `kubectl patch cronjob J -p '{"spec":{"suspend":true}}'`. Then do the
  same in Git, or the controller reverts it.
- **Drain a node:** `kubectl drain N --ignore-daemonsets --delete-emptydir-data` after checking
  PDBs. Ask first: it moves every workload on the node.
