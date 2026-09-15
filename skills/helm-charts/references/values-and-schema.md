# Values and schema

## Designing values.yaml

Order and group values the way an operator reads them: image, replicas,
resources, then feature toggles, then advanced/override.

```yaml
replicaCount: 1

image:
  repository: ghcr.io/example/mychart
  pullPolicy: IfNotPresent
  tag: ""            # defaults to .Chart.AppVersion when empty

nameOverride: ""
fullnameOverride: ""

serviceAccount:
  create: true
  annotations: {}
  name: ""

service:
  type: ClusterIP
  port: 80

ingress:
  enabled: false
  className: ""
  hosts:
    - host: chart-example.local
      paths:
        - path: /
          pathType: ImplementationSpecific

resources: {}
  # limits:
  #   cpu: 100m
  #   memory: 128Mi

nodeSelector: {}
tolerations: []
affinity: {}
```

Principles:

- **Every value has a working default.** An empty `values.yaml` install
  must succeed.
- **Comment out heavy nesting** (`resources`) rather than inventing
  limits operators didn't ask for.
- **`tag: ""` + `.Chart.AppVersion` fallback** is the standard trick so
  the chart and app versions stay aligned by default:

  ```yaml
  image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
  ```

- **Don't expose internal filenames**; expose domain concepts.
- Empty maps/lists (`{}`, `[]`) let an operator set a whole subtree
  without triggering schema type errors.

## `values.schema.json`

A JSON Schema 2020-07/2020-12 document (see
[`../../json-schema/SKILL.md`](../../json-schema/SKILL.md)) that Helm
validates user values against before rendering:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "replicaCount": { "type": "integer", "minimum": 0 },
    "image": {
      "type": "object",
      "properties": {
        "repository": { "type": "string", "minLength": 1 },
        "tag": { "type": "string" },
        "pullPolicy": { "enum": ["Always", "IfNotPresent", "Never"] }
      },
      "required": ["repository"]
    }
  },
  "required": ["image"]
}
```

Why it's worth it:

- Catches typos and wrong types at `helm install`/`upgrade` time with a
  clear message, instead of rendering a broken manifest.
- Document-as-code: the schema is the authoritative shape of values.
- Set `"additionalProperties": false` on objects you want to freeze, so
  an unknown key (a typo like `replicaCounts`) fails loudly.

Keep the schema and `values.yaml` in sync — a schema that's stricter
than the defaults breaks install; looser than intended lets bad input
through.

## Handling secret values

Never put real secrets in `values.yaml` or pass them with `--set`:

- `--set` values appear in shell history, `ps`, and `helm get values`.
- Secrets committed as defaults ship to everyone who installs the chart.

Patterns instead:

- **`existingSecret`**: reference a Secret managed elsewhere (Vault,
  External Secrets, SOPS):

  ```yaml
  envFrom:
    - secretRef:
        name: {{ .Values.existingSecret | required "existingSecret is required" }}
  ```

- **`secretKeyRef`** for individual keys.
- Let a secret manager create the Secret; the chart only consumes it.
- Terraform's `helm_release` supports `set_sensitive`; prefer it, but
  still prefer a Secret over passing values.

## Required values

Turn missing critical input into an install-time failure:

```yaml
{{- $_ := required "image.repository is required" .Values.image.repository -}}
```

or, for a whole block, guard with `fail`:

```yaml
{{- if and .Values.ingress.enabled (not .Values.ingress.hosts) -}}
{{- fail "ingress.enabled requires ingress.hosts" -}}
{{- end -}}
```

`required`/`fail` produce messages an operator can act on; a rendered
manifest with an empty field does not.
