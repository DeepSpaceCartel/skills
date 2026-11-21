# Disruption budgets and safe rollouts

## Problem

Most pod restarts are planned: node drains for upgrades, autoscaler scale-down, rolling
deployments. Each one removes capacity and kills in-flight requests unless the platform is told
how much may go at once and the pod is given time to finish. Without that, routine maintenance
causes the outages: a drain evicts all replicas together, or a rollout drops every connection.

## When to use / when NOT to use

- **PodDisruptionBudget (PDB):** every replicated workload that serves traffic or holds quorum.
- **Graceful termination (preStop, grace period, draining):** every pod that serves requests or
  processes messages.
- **Rolling-update tuning:** every Deployment whose default (25% unavailable, 25% surge) doesn't
  match its capacity headroom.
- **Usually no PDB** for restartable batch Jobs (the controller replaces pods). For a
  single-instance stateful app the docs offer two options: no PDB and accept downtime, or
  `maxUnavailable: 0` so a drain waits until you delete the PDB.
- **Release strategy** (canaries, flags, rollback criteria) is not here: see
  [`engineering-practices` release-engineering](../../engineering-practices/references/release-engineering.md).

## How it works

**Voluntary vs involuntary.** Kubernetes calls drains, scale-downs and pod deletions voluntary;
hardware loss, kernel panics, partitions and node-pressure evictions involuntary. A PDB limits
voluntary disruptions that go through the **Eviction API** (`kubectl drain` and the cluster
autoscaler use it). It does **not** limit direct pod or Deployment deletes, and Deployments and
StatefulSets are **not limited by PDBs during rolling updates**: the rollout's own
`maxUnavailable` governs that. Pods down for any reason still count against the budget.

**PDB fields.** One of `minAvailable` or `maxUnavailable`, plus a selector. Percentages round
up. A budget that allows zero evictions (`maxUnavailable: 0`, or `minAvailable` equal to the
replica count) means drains of those nodes never complete. With one replica and a percentage
`maxUnavailable`, that replica is still evictable. `unhealthyPodEvictionPolicy`:
`IfHealthyBudget` (default) only evicts not-ready pods while the app is within budget, so a
crash-looping app can block a drain; `AlwaysAllow` lets them go, which the docs recommend.

**Rolling update.** `maxUnavailable` (default 25%, rounds down) and `maxSurge` (default 25%,
rounds up); they can't both be 0. `minReadySeconds` (default 0) is how long a new pod must be
ready before it counts as available. `progressDeadlineSeconds` (default 600) marks a stalled
rollout as failed. Readiness gates the whole thing: a rollout only advances on ready pods.

**Termination sequence** (per the Kubernetes docs):

1. Pod marked terminating; in parallel, the control plane marks its endpoints terminating
   (`ready: false`, `serving` still reports real readiness), so balancers stop sending new traffic.
2. The kubelet runs `preStop` if defined (exec, HTTP, or `sleep`), then sends SIGTERM to PID 1.
3. `terminationGracePeriodSeconds` (default 30) covers preStop and shutdown together; if preStop
   is still running when it expires, a one-off 2 s extension.
4. Then SIGKILL.

**Why a preStop delay.** Endpoint removal propagates to every proxy and balancer asynchronously,
while SIGTERM arrives at once. A short preStop `sleep` keeps the process serving while the rest
of the system stops routing to it; then the app's SIGTERM handler stops accepting, finishes
in-flight work and exits. The Kubernetes termination tutorial uses a preStop sleep for exactly
this draining. For HTTP/2 and gRPC, the proxy also sends GOAWAY (Envoy's HCM `drain_timeout`,
default 5 s, is the gap between the first and final GOAWAY).

## Failure modes and what agents get wrong

- **No PDB, three replicas, one drain:** all three pods on the drained node go at once.
- **PDB treated as rollout protection.** It isn't; set the Deployment's `maxUnavailable`.
- **`minAvailable: 100%` "for safety".** Node upgrades hang forever, and the cluster autoscaler
  can't remove the node (its FAQ lists restrictive PDBs as a scale-down blocker).
- **Default `IfHealthyBudget` with a crash-looping app,** blocking every drain on its nodes.
- **No preStop delay.** The pod exits on SIGTERM while proxies still route to it: connection
  resets on every deploy.
- **preStop longer than the grace period.** The sleep eats the budget and the app is SIGKILLed
  mid-request. Grace period = preStop + longest request or message + margin.
- **Shell-form entrypoint.** SIGTERM goes to the shell, not the app, which then gets SIGKILL
  (see [`container-images`](../../container-images/SKILL.md)).
- **`maxSurge` without headroom.** Surge pods need schedulable capacity; with a full cluster the
  rollout waits on the autoscaler or stalls.
- **Queue consumers killed mid-message** with no ack/lease handling, so the message is redelivered
  (fine if idempotent; see [`data-pipelines` idempotent-stages](../../data-pipelines/references/idempotent-stages.md)).

## Implementation notes

- **Kubernetes:** `policy/v1` PodDisruptionBudget; Deployment `strategy.rollingUpdate`,
  `minReadySeconds`, `progressDeadlineSeconds`; pod `terminationGracePeriodSeconds`;
  `lifecycle.preStop.sleep.seconds`; probe-level `terminationGracePeriodSeconds` for liveness kills.
- **Envoy/Istio:** HCM `drain_timeout`; sidecars must outlive the app container during shutdown
  (native sidecar containers stop after app containers, per the termination docs).
- **HAProxy/NGINX:** reload gracefully and drain servers (set to drain/maintenance) before
  removing them; check your version's directives.
- **Managed:** managed node upgrades honour PDBs up to a provider timeout, after which some force
  the drain (unverified).

## Example

A 6-replica HTTP API: drains take one pod at a time, rollouts never drop below 6 ready, and
each pod drains for 10 s before shutdown.

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: {name: orders-api}
spec:
  maxUnavailable: 1
  selector: {matchLabels: {app: orders-api}}
  unhealthyPodEvictionPolicy: AlwaysAllow
---
apiVersion: apps/v1
kind: Deployment
metadata: {name: orders-api}
spec:
  replicas: 6
  minReadySeconds: 10
  strategy:
    type: RollingUpdate
    rollingUpdate: {maxUnavailable: 0, maxSurge: 2}
  selector: {matchLabels: {app: orders-api}}
  template:
    metadata: {labels: {app: orders-api}}
    spec:
      terminationGracePeriodSeconds: 45   # 10 s preStop + 30 s longest request + 5 s margin
      containers:
      - name: api
        image: registry.example/orders-api@sha256:<digest>
        lifecycle:
          preStop:
            sleep: {seconds: 10}          # keep serving while endpoints propagate
        readinessProbe:
          httpGet: {path: /healthz/ready, port: 8080}
          periodSeconds: 5
```

`maxUnavailable: 0` with `maxSurge: 2` keeps full capacity during rollouts at the cost of two
extra pods of headroom; the PDB keeps drains to one pod at a time. Field names are from the
Kubernetes docs and API types; the app must stop accepting on SIGTERM and exit when in-flight
requests finish.

## Review checklist

1. Does every replicated serving or quorum workload have a PDB that allows at least one eviction?
2. Is `unhealthyPodEvictionPolicy: AlwaysAllow` set, so broken pods don't block drains?
3. Do the Deployment's `maxUnavailable` and `maxSurge` match its capacity headroom, and is there room for surge pods?
4. Is there a preStop delay covering endpoint propagation, and does the grace period cover preStop plus the longest request?
5. Does the app handle SIGTERM as PID 1: stop accepting, finish in-flight work, exit?
6. Do long-lived connections (HTTP/2, gRPC, websockets) get a GOAWAY or close during drain?
7. Has a drain of a busy node been tested under load with zero client errors?
8. Is the release strategy (canary, rollback trigger) defined separately per release-engineering?

## Related

[health-checks-and-probes](health-checks-and-probes.md) (readiness gates rollouts),
[redundancy-and-failover](redundancy-and-failover.md),
[requests-limits-and-autoscaling](requests-limits-and-autoscaling.md) (scale-down drains),
[timeouts-and-retries-infra](timeouts-and-retries-infra.md) (drain timeouts),
[`engineering-practices` release-engineering](../../engineering-practices/references/release-engineering.md),
[`container-images`](../../container-images/SKILL.md) (signals and PID 1).

## Sources

Kubernetes: [disruptions](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/),
[configure a PDB](https://kubernetes.io/docs/tasks/run-application/configure-pdb/),
[pod lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/),
[pod termination](https://kubernetes.io/docs/concepts/workloads/pods/pod-termination/),
[pods and endpoint termination flow](https://kubernetes.io/docs/tutorials/services/pods-and-endpoint-termination-flow/),
[container lifecycle hooks](https://kubernetes.io/docs/concepts/containers/container-lifecycle-hooks/),
[Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/), read from
the [website source](https://github.com/kubernetes/website/tree/main/content/en/docs); `SleepAction`
from the [API types](https://github.com/kubernetes/kubernetes/blob/master/staging/src/k8s.io/api/core/v1/types.go).
Cluster autoscaler [FAQ](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/FAQ.md).
Envoy [timeouts FAQ](https://www.envoyproxy.io/docs/envoy/latest/faq/configuration/timeouts).
