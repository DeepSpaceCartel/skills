# Testing and upgrades

## Static checks

```bash
helm lint charts/mychart
helm lint charts/mychart --strict
helm template myrelease charts/mychart
helm template myrelease charts/mychart -f values-prod.yaml --debug >/dev/null
```

Run all of these in CI on every chart change. `lint` catches
convention/schema problems; `template` proves it renders; neither
proves it works against a cluster.

## Unit testing rendered output

The `helm-unittest` plugin asserts on the rendered YAML:

```yaml
# tests/deployment_test.yaml
suite: deployment
templates:
  - deployment.yaml
tests:
  - it: renders the app version label
    asserts:
      - equal:
          path: metadata.labels["app.kubernetes.io/version"]
          value: "2.0.1"
      - isKind:
          of: Deployment
```

Install the plugin once (`helm plugin install
https://github.com/helm-unittest/helm-unittest`) and run
`helm unittest charts/mychart`. This is the closest thing to a Helm unit
test and runs with no cluster.

## Schema/contract testing

`helm template | kubeconform -strict -summary` (or `kubeval`) validates
rendered manifests against the Kubernetes API schemas. This catches a
typo'd `apiVersion`/field that `helm lint` won't.

## Cluster smoke tests

- `helm test <release>` runs Pods annotated with
  `helm.sh/hook: test` and reports pass/fail. Use it for a real
  connectivity check against the deployed release.
- In CI, install into a throwaway namespace, run the smoke test,
  uninstall, and assert the namespace is empty.

## Upgrade semantics

```bash
helm upgrade --install myrelease ./mychart \
  --namespace myns --create-namespace \
  --wait --timeout 5m --atomic
```

- `--install` makes the command idempotent for first-run-or-upgrade.
- `--wait` blocks until Deployments/StatefulSets/DaemonSets/PVCs/Jobs
  are ready, so a failed rollout fails the command.
- `--atomic` implies `--wait` and **rolls back** to the previous
  revision on failure. Essential in automation; be aware it deletes and
  recreates changed resources during rollback.
- `--cleanup-on-fail` deletes newly created resources if the upgrade
  fails.
- `--force` recreates resources instead of updating — a last resort;
  it can cause downtime and is not a substitute for a correct update
  strategy.

## Changing config must roll the pods

Kubernetes does **not** restart pods when a mounted/consumed
ConfigMap or Secret changes. Mounted files eventually update, but env
vars do not, and in both cases the process is not restarted. The
standard fix is a checksum annotation on the pod template:

```yaml
# templates/deployment.yaml
spec:
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```

On the next upgrade, a changed ConfigMap changes the checksum, which
changes the pod template, which triggers a normal rolling update. Put
the same pattern on Secrets (careful: never print the secret itself into
an annotation — hash it, as above, which produces a digest not the
plaintext).

## Immutable field pitfalls on upgrade

- `spec.selector` on a Deployment is immutable — changing selector
  labels requires deleting/recreating the Deployment.
- `spec.clusterIP`, `spec.volumeName` (bound PVCs), and several Service
  fields are immutable.
- `Job`s are effectively immutable; a changed Job spec needs a new name
  (e.g. suffix with the chart version).
- Helm 3+ uses a three-way merge patch; `--force` can paper over a
  failed merge but re-creates resources.

## Uninstall

- `helm uninstall` removes resources it tracks; resources managed by
  hooks without `hook-delete-policy` and CRDs in `crds/` survive.
- `PVC`s are retained unless a `helm.sh/resource-policy: delete`
  annotation is set — decide deliberately, data loss is easy here.
- Cluster-scoped resources (ClusterRole, CRD) owned by the chart are
  deleted on uninstall — be careful with shared ones.
