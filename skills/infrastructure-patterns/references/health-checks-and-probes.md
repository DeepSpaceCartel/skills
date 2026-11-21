# Health checks and probes

## Problem

Schedulers and load balancers act on health signals: restart the container, stop sending it
traffic, replace the instance. A check that asks the wrong question does damage either way. Too
shallow, and a broken instance stays in service. Too deep, and one shared dependency failing
makes every instance fail its check at once, so the platform removes the whole fleet.

## When to use / when NOT to use

- **Readiness:** every service behind a load balancer or Service. It decides traffic.
- **Startup:** any container that can take longer to start than the liveness budget allows.
- **Liveness:** only for failures the process can't recover from itself, such as a deadlock.
  Kubernetes notes that a process which already exits when it's unhealthy doesn't need one:
  the restart policy handles it.
- **Not** for a dependency the instance shares with every peer, in liveness at all, and in
  readiness only if the instance truly can't do useful work without it.

## How it works

**The three Kubernetes probes:**

| Probe | On failure | Runs | Ask it |
|---|---|---|---|
| Startup | Container killed, then restart policy | Until first success; liveness and readiness wait for it | Has initialization finished? |
| Liveness | Container restarted after `failureThreshold` failures | Whole life | Is this process stuck beyond repair? |
| Readiness | Pod IP removed from Service EndpointSlices; no restart | Whole life | Should this instance get traffic now? |

Probe defaults (Kubernetes API): `periodSeconds` 10, `timeoutSeconds` 1, `failureThreshold` 3,
`successThreshold` 1 (must be 1 for liveness and startup), `initialDelaySeconds` 0. Mechanisms:
`exec`, `httpGet` (200–399 is success), `tcpSocket`, `grpc`. A slow starter that exceeds
`initialDelaySeconds + failureThreshold x periodSeconds` needs a startup probe; its window is
`failureThreshold x periodSeconds`.

**Depth.** AWS distinguishes liveness checks (process up, port answers), local health checks
(resources this instance doesn't share: disk read and write, critical sidecar processes) and
dependency checks (can it reach its database). Azure's Health Endpoint Monitoring pattern
gives the same split: shallow checks for liveness, deep checks for readiness, optional
dependencies excluded from the decision.

**Load-balancer checks** are readiness by another name: they remove instances. AWS notes some
balancers fail open (send to all instances if all fail), but advises not to rely on it and to
keep fast-acting balancer checks local, with dependency checks done by a separate system.

## Disk full, probe green: a design bug

A liveness probe that returns 200 from memory says nothing about whether the instance can
write. AWS's disk-full example: when the disk fills, processing and logging fail, so the
instance can't even report its own errors. If the service can't do its job without writing
(a database, a queue consumer, anything with a WAL or a spool), **writability of its own volume
is a local health check** and belongs in readiness: write and fsync a small file, or check free
space against a floor. That is local (not shared), so it can't take the fleet down together.
Pair it with time-to-full alerts from [`data-integrity` state-and-storage](../../data-integrity/references/state-and-storage.md);
the probe removes the instance, the alert gets a human to fix the disk.

## In code / In infrastructure

**In code.** Separate endpoints (`/healthz/live`, `/healthz/ready`), cheap and bounded: run
dependency checks in a background loop that updates a flag, and serve the flag (AWS); give
health checks reserved capacity so they answer under load. Never block a probe on a slow call.

**In infrastructure.** Probe type, path, period, timeout and thresholds per container; balancer
check interval and thresholds; outlier ejection as passive health checking (see
[circuit-breaking-and-outlier-ejection](circuit-breaking-and-outlier-ejection.md)).

**Agree:** the endpoint's cost must fit the probe's timeout (default 1 s) at the probe's rate
across all instances and all checkers; Azure warns that deep checks at high frequency compete
with real traffic.

## Failure modes and what agents get wrong

- **Liveness checks the database.** The database blips, every pod fails liveness, and the
  kubelet restarts the whole fleet into a cold start. The restart fixes nothing; Azure: restarting
  doesn't repair a shared dependency.
- **Liveness and readiness identical with identical thresholds.** Kubernetes suggests the same
  cheap endpoint for both is fine, but with a higher liveness `failureThreshold` so a pod is
  unready for a while before it is killed.
- **Liveness under load.** A 1 s timeout on a busy pod fails, the pod restarts, its load moves
  to the others, which then fail. Kubernetes warns misconfigured liveness causes cascading
  failures; the SRE book says health checks that restart overloaded tasks deepen outages.
- **No startup probe on a slow starter,** so liveness kills it before it finishes, forever
  (CrashLoopBackOff).
- **Readiness depends on an optional dependency** (a recommendations service), so a minor
  outage removes every instance.
- **A probe green while the disk is full** (above).
- **Probe hits an authenticated or redirected path.** A redirect to a login page is a 3xx,
  which counts as success (200–399), and hides breakage (whether the kubelet follows it is
  (unverified)).
- **Expensive deep checks behind a public URL.** Azure: protect health endpoints; return detail
  only to authorized callers.

## Implementation notes

- **Kubernetes:** `startupProbe`, `livenessProbe`, `readinessProbe`; probe-level
  `terminationGracePeriodSeconds` overrides the pod's on probe failure.
- **Envoy/Istio:** active health checking per cluster plus outlier detection; the panic
  threshold (50%) keeps traffic flowing when most hosts look unhealthy.
- **HAProxy:** `check` with `fall` (default 3) and `rise`; `observe layer7` adds passive checks.
- **Managed:** cloud load balancers and DNS failover use HTTP checks with a status range,
  interval and threshold; Azure notes DNS caching delays failover after a check fails.

## Example

A queue consumer that writes a local spool: startup allows 5 minutes, liveness checks only the
process, readiness also checks the spool volume is writable.

```yaml
containers:
- name: consumer
  image: registry.example/consumer:1.8.2
  ports: [{name: http, containerPort: 8080}]
  startupProbe:
    httpGet: {path: /healthz/live, port: http}
    periodSeconds: 10
    failureThreshold: 30          # 300 s to start
  livenessProbe:
    httpGet: {path: /healthz/live, port: http}   # in-process only: event loop alive
    periodSeconds: 10
    timeoutSeconds: 2
    failureThreshold: 6           # 60 s stuck before a restart
  readinessProbe:
    httpGet: {path: /healthz/ready, port: http}  # spool writable + >= 2 GiB free + broker flag
    periodSeconds: 5
    timeoutSeconds: 2
    failureThreshold: 2
  volumeMounts: [{name: spool, mountPath: /var/spool/consumer}]
```

`/healthz/ready` returns 503 if a test write to the spool fails or free space is below 2 GiB,
and reads a broker-connection flag refreshed every 5 s by a background loop. All probe fields
are from the Kubernetes API types; endpoint behaviour is this example's design.

## Review checklist

1. Does liveness check only the process itself, never a shared dependency?
2. Is there a startup probe for any container that can start slower than the liveness window?
3. Does readiness include local resources the instance needs (writable volume, free space), and only the dependencies it can't work without?
4. Is liveness more tolerant than readiness (higher `failureThreshold`), so overload shows up as unready before restarts?
5. Do probe endpoints answer from cached state within the probe timeout, with reserved capacity under load?
6. Does the balancer's check stay local, and is its behaviour known when every instance fails?
7. Is a disk-full or stuck-consumer state visible to a probe *and* to an alert?
8. Are health endpoints protected from public access or limited to minimal output?

## Related

[load-shedding](load-shedding.md) (probes must survive overload),
[circuit-breaking-and-outlier-ejection](circuit-breaking-and-outlier-ejection.md) (passive checks),
[disruption-budgets-and-safe-rollouts](disruption-budgets-and-safe-rollouts.md) (readiness gates rollouts),
[redundancy-and-failover](redundancy-and-failover.md),
[`data-integrity` state-and-storage](../../data-integrity/references/state-and-storage.md),
[`system-design` scaling-and-failure-domains](../../system-design/references/scaling-and-failure-domains.md).

## Sources

Kubernetes: [probes](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/),
[configure probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/),
[pod lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/), and the
[Probe API type](https://github.com/kubernetes/kubernetes/blob/master/staging/src/k8s.io/api/core/v1/types.go)
for defaults. Azure [Health Endpoint Monitoring pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/health-endpoint-monitoring).
AWS Builders' Library, [Implementing health checks](https://builder.aws.com/content/3Ev53O39izHCtWLzp4XU6t8PC1O/implementing-health-checks).
Google SRE book, [Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/).
Envoy [panic threshold](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/load_balancing/panic_threshold).
