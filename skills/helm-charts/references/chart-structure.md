# Chart structure

## Chart.yaml

```yaml
apiVersion: v2
name: mychart
description: One line about what this chart deploys
type: application          # application | library
version: 1.4.2             # chart SemVer
appVersion: "2.0.1"        # deployed app version (quote it)
kubeVersion: ">=1.28.0-0"
icon: https://example.com/icon.png
home: https://example.com
sources:
  - https://github.com/example/mychart
maintainers:
  - name: Team Name
    email: team@example.com
dependencies:
  - name: postgresql
    version: "15.x.x"
    repository: https://charts.bitnami.com/bitnami
    condition: postgresql.enabled
```

- `apiVersion` is `v2` for any modern chart (`v1` is Helm 2).
- **`version` is required** and is the *chart's* version. **`appVersion`**
  is informational metadata about the software inside; it does not have
  to be SemVer, but use it as a quoted string regardless.
- `type: library` charts are not installable and expose only named
  templates; use them to share helpers across charts.
- `condition`/`tags` on a dependency lets `--set postgresql.enabled=false`
  disable it.

## `.helmignore`

Like `.gitignore` but for chart packaging. Always ignore `.git/`,
`*.tmproj`, editor cruft, and anything not needed at install time
(tests you don't ship, CI config, large fixtures). Keeping it accurate
shrinks the packaged chart and avoids leaking dev files.

## `templates/_helpers.tpl`

Library templates, typically the `name`, `fullname`, `chart`, `labels`,
and `selectorLabels` helpers:

```yaml
{{- define "mychart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "mychart.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "mychart.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
```

Use `selectorLabels` (just `name` + `instance`) for `spec.selector` and
the fuller `labels` set for metadata — selector labels are **immutable**
on a Deployment, so never add heap-version or config hashes to them.

## Labels and annotations

Recommended common labels (`app.kubernetes.io/*`):

| Label | Value |
| --- | --- |
| `name` | `include "mychart.name" .` |
| `instance` | `.Release.Name` |
| `version` | `.Chart.AppVersion \| quote` |
| `component` | e.g. `web`, per Deployment |
| `part-of` | the larger application, if any |
| `managed-by` | `.Release.Service` |
| `helm.sh/chart` | `include "mychart.chart" .` |

Annotations are for non-identifying metadata (`checksum/config`,
`helm.sh/hook`, ownership notes). Labels are for selection; keep them
low-cardinality and stable.

## Hooks

```yaml
metadata:
  annotations:
    helm.sh/hook: pre-install,pre-upgrade
    helm.sh/hook-weight: "-5"
    helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded
```

- Hooks are ordinary manifests with hook annotations; Helm applies them
  at the named phase instead of during the normal apply.
- `hook-weight` orders multiple hooks (lower runs first).
- `hook-delete-policy` controls cleanup; `before-hook-creation` avoids
  the "Job already exists" failure on re-run.
- Hooks are managed outside the release lifecycle — they are not deleted
  on `helm uninstall` unless you set `hook-delete-policy`.

## CRDs

- `crds/` at the chart root: installed on `install` **only**, never
  upgraded, never deleted. Safe by default, but a schema change is a
  deliberate migration.
- CRDs under `templates/` are full lifecycle citizens (created,
  upgraded, deleted with the chart) — use only when you accept that.
- For operators that ship their own CRDs, prefer managing CRDs
  out-of-band (a separate apply) so the chart doesn't own cluster-scoped
  state.

## Considerations for library charts / subcharts

- A subchart's values are namespaced under its name in the parent.
- Global values (`.Values.global`) propagate to every subchart — use
  them sparingly; they couple charts tightly.
- `alias` renames a subchart's values key without changing the chart.
