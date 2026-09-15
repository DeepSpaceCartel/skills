# Templating and helpers

Helm templates are Go `text/template` plus the Sprig function library
and a set of Helm-specific objects (`.Release`, `.Chart`, `.Values`,
`.Files`, `.Capabilities`). Guide:
<https://helm.sh/docs/chart_template_guide/>.

## `include` vs `template`

```yaml
{{- define "mychart.labels" -}}
app.kubernetes.io/name: {{ include "mychart.name" . }}
{{- end -}}

# Good: include returns a string, composable and pipeable
metadata:
  labels:
    {{- include "mychart.labels" . | nindent 4 }}

# Avoid: template writes in place and cannot be piped
metadata:
  labels:
    {{ template "mychart.labels" . }}
```

Use `include` almost always. Reach for `template` only when you
genuinely want the in-place write.

## Whitespace control

- `{{-` trims preceding whitespace; `-}}` trims following whitespace.
- `nindent N` = newline + indent N spaces; `indent N` = indent only.
  `nindent` is what you usually want under a key.
- Stray blank lines from untrimmed actions are the #1 source of
  noisy, confusing manifest diffs.

## Flow control

```yaml
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
...
{{- end }}

{{- with .Values.nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}

{{- range .Values.extraEnv }}
- name: {{ .name }}
  value: {{ .value | quote }}
{{- end }}
```

- `with` sets `.` to its argument (and skips the block when falsy).
- `range` iterates; `$` refers to the root context inside the loop.
- There is no `else if`-free style rule, but prefer small helpers over
  deep nesting.

## Useful functions

| Function | Use |
| --- | --- |
| `default X Y` | `Y` or `X` when `Y` is empty |
| `quote` | wrap in quotes — mandatory for version-like values |
| `toYaml` | render a map/list as YAML |
| `nindent` / `indent` | indentation for embedded YAML |
| `include` | named template as string |
| `required "msg" val` | fail install if `val` is empty |
| `fail "msg"` | unconditional failure |
| `tpl` | render a string as a template (careful; values become code) |
| `lookup` | query the cluster at render time (breaks `--dry-run`/CI) |
| `printf` / `trunc` / `trimSuffix` | string shaping for names |

Avoid `lookup` and `tpl` unless you must: `lookup` makes rendering
depend on live cluster state (non-reproducible, fails offline), and
`tpl` invites value-injection.

## The numeric-label trap

```yaml
# BAD: renders 1.27 as a YAML float, helm upgrade fails decoding
app.kubernetes.io/version: {{ .Chart.AppVersion }}

# GOOD
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
```

Any value that can look numeric (versions, ports as strings, IDs with
leading zeros) must be quoted. This is a real `map[string]string`
decode failure on labels/annotations.

## Naming and truncation

- DNS-1123 labels are max 63 chars; `fullname` should `trunc 63` and
  `trimSuffix "-"` to avoid invalid trailing dashes.
- Prefer `.Release.Name` over generating a random suffix, so resources
  are predictable and idempotent.
- Don't add a checksum/config value to `selectorLabels` — selectors are
  immutable and the upgrade will be rejected.

## Debugging

```bash
helm template myrelease ./mychart --debug          # full render + errors
helm template myrelease ./mychart -s templates/deployment.yaml
helm install myrelease ./mychart --dry-run --debug
helm get manifest myrelease                        # what's actually deployed
```

When a template fails, `--debug` prints the exact line and the values
in scope. Render locally before ever touching a cluster.
