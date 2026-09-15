---
name: helm-charts
description: How to author and review Helm charts (https://helm.sh/docs/, chart best practices at https://helm.sh/docs/chart_best_practices/) - project-agnostic. Covers chart anatomy (Chart.yaml, values.yaml, templates/, _helpers.tpl, .helmignore, charts/), conventions for naming and the app.kubernetes.io labels, values design and values.schema.json validation, template functions/flow control and the include helper pattern, hooks, CRDs, dependencies, helm lint/template/unittest, upgrade semantics (--wait/--atomic), chart and appVersion versioning, and config-checksum annotations that roll pods on a ConfigMap/Secret change. Use when creating or reviewing a Helm chart, designing values.yaml, packaging a Kubernetes app, or debugging unexpected helm upgrade --install behavior.
---

# Helm charts

A chart is a versioned, parameterized bundle of Kubernetes manifests.
Design it the way you'd design an API: a small, documented set of
`values`, predictable rendering, and an upgrade path that doesn't
surprise the operator. Applies to Helm 3 and Helm 4.

## Chart anatomy

```
mychart/
├── Chart.yaml          # metadata + version
├── values.yaml         # the defaults users override
├── values.schema.json  # optional JSON Schema for values
├── .helmignore
├── templates/
│   ├── _helpers.tpl    # named templates (include), not rendered directly
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── serviceaccount.yaml
│   └── NOTES.txt       # printed after install
├── charts/             # vendored subcharts (or declared in Chart.yaml deps)
└── README.md           # generated from values via helm-docs, ideally
```

- Files under `templates/` render to manifests; files beginning with
  `_` are library templates only.
- `templates/NOTES.txt` is rendered and shown to the user after
  install/upgrade — put the "how to reach it" instructions there.

## Chart.yaml and versioning

```yaml
apiVersion: v2
name: mychart
version: 1.4.2        # the CHART's SemVer — bump on any template change
appVersion: "2.0.1"   # the app it deploys (quoted string)
type: application     # or library
```

- **`version`** is the chart's own SemVer
  ([`../semver/SKILL.md`](../semver/SKILL.md)); **`appVersion`** is the
  deployed app's version. They move independently.
- Bump `version` on **every** chart change, even a values-only default
  change — otherwise `helm upgrade` sees no new chart to install.
- Always **quote** `appVersion` (and any version-like value) so YAML
  doesn't parse `1.27` as a float.

## values.yaml design

- Expose what operators legitimately need to change; hardcode the rest.
- Give every value a sensible default so `helm install mychart ./mychart`
  works with no `-f`.
- Nest by component/concern (`image:`, `resources:`, `ingress:`,
  `serviceAccount:`), not by template filename.
- Include `image.repository`, `image.tag`, and `image.pullPolicy`; default
  `image.tag` to `""` and fall back to `.Chart.AppVersion` in the template
  so an untagged install tracks the chart's app version.
- Validate with `values.schema.json` (see
  [`references/values-and-schema.md`](references/values-and-schema.md)).

## Templating and helpers

- Define reusable snippets in `_helpers.tpl` and call them with
  `include` (which returns a string and can be piped), not `template`
  (which writes in place).
- The near-universal labels helper:

  ```yaml
  app.kubernetes.io/name: {{ include "mychart.name" . }}
  app.kubernetes.io/instance: {{ .Release.Name }}
  app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
  app.kubernetes.io/managed-by: {{ .Release.Service }}
  helm.sh/chart: {{ include "mychart.chart" . }}
  ```

- Use `--` on `{{- ... -}}` to trim whitespace; stray blank lines are a
  common source of confusing diffs.
- Guard optional resources with `{{- if .Values.foo.enabled }}`.
- Use `required`/`fail` to turn a missing critical value into a clear
  install-time error instead of a broken manifest.

## Hooks and lifecycle

- `helm.sh/hook` annotations run Jobs at install/upgrade/delete time
  (`pre-install`, `post-install`, `pre-upgrade`, `pre-delete`,
  `test`).
- Order hooks with `helm.sh/hook-weight`; clean up with
  `helm.sh/hook-delete-policy`.
- `templates/tests/` + `helm test` is the built-in way to smoke-test a
  release; use it for a real connectivity check.

## CRDs

- CRDs in `crds/` are installed but **never upgraded or deleted** by
  Helm. Treat schema changes as an explicit migration step.
- Keep CRDs in `crds/` (not `templates/`) for install-once semantics,
  or manage them outside the chart if you need lifecycle control.

## Dependencies

- Declare in `Chart.yaml` under `dependencies:` (not the legacy
  `requirements.yaml`), then `helm dependency build`.
- Vendor tarballs under `charts/` and commit them if you want
  reproducible rendering without network access at install time.
- Pin dependency versions explicitly; use `condition`/`tags` to make a
  subchart optional.

## Lint, render, test

```bash
helm lint charts/mychart
helm template myrelease charts/mychart            # render manifests locally
helm template myrelease charts/mychart -f prod.yaml --debug
helm unittest charts/mychart                      # helm-unittest plugin
helm install myrelease charts/mychart --dry-run --debug
```

Render in CI on every change; a chart that renders is not the same as a
chart that lints clean.

## Upgrade semantics that bite

- `helm upgrade --install ... --wait` waits for resources to be Ready;
  `--atomic` rolls back automatically on failure. Use both in automation.
- **Changing a ConfigMap/Secret does not restart the pods that consume
  it.** Add a checksum annotation to the pod template so a config change
  triggers a rollout (see
  [`references/testing-and-upgrades.md`](references/testing-and-upgrades.md)).
- PodSecurity admission is namespace-scoped: a chart needing privileged
  execution cannot dodge it by setting `securityContext` — the namespace
  must opt in with a label.
- A label value that looks numeric (`.Chart.AppVersion` = `1.27`) must be
  `| quote`d or `helm upgrade` fails decoding it into `map[string]string`.

## Where to look

| File | Covers |
| --- | --- |
| [`references/chart-structure.md`](references/chart-structure.md) | anatomy, Chart.yaml, .helmignore, labels, hooks, CRDs |
| [`references/values-and-schema.md`](references/values-and-schema.md) | values design, `values.schema.json`, secret values |
| [`references/templating-and-helpers.md`](references/templating-and-helpers.md) | `_helpers.tpl`, `include`, flow control, functions, pitfalls |
| [`references/testing-and-upgrades.md`](references/testing-and-upgrades.md) | lint/template/unittest, `--wait`/`--atomic`, checksum rollouts |

## What NOT to do

- Don't bump `appVersion` when only the chart changed (or vice versa) —
  keep the two version numbers honest.
- Don't template every field "just in case"; an unreadable values tree
  is worse than a hardcoded sensible default.
- Don't put secrets in `values.yaml` defaults or `--set` (they leak into
  release history and `helm get values`) — reference an `existingSecret`
  or use `secretKeyRef` instead.
- Don't edit generated `charts/` tarballs by hand — change the source
  subchart and rebuild.
- Don't rely on `templates/` for CRDs you need to upgrade; that's what
  the out-of-chart CRD lifecycle is for.
