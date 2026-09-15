# Distribution: Features and Templates

[Features](features.md) and [Templates](templates.md) share one
distribution model — a git repo of source, packaged as a tarball, pushed
to an OCI registry. Full specs:
[features-distribution](https://containers.dev/implementors/features-distribution/),
[templates-distribution](https://containers.dev/implementors/templates-distribution/).
Keep Features and Templates in **separate** repositories — even though the
mechanics below are identical for both.

## Source layout (a "collection")

One repo can hold many Features (or many Templates) — called a
**collection**, sharing one namespace (`<owner>/<repo>`) and one
auto-generated `devcontainer-collection.json`.

Features:
```
.
├── src/
│   ├── go/
│   │   ├── devcontainer-feature.json
│   │   └── install.sh
│   └── dotnet/
│       ├── devcontainer-feature.json
│       └── install.sh
└── test/
    ├── go/test.sh
    └── dotnet/test.sh
```

Templates (each with its own ready-to-drop `.devcontainer/`):
```
.
└── src/
    └── go-postgres/
        ├── devcontainer-template.json
        └── .devcontainer/
            ├── devcontainer.json
            └── docker-compose.yml
```

Each sub-directory name must match its `devcontainer-feature.json` /
`devcontainer-template.json` `id`. Only files inside that sub-directory are
packaged — anything outside it is excluded even if present in the repo.

## Versioning

Each Feature/Template is independently [semver](https://semver.org/)ed via
its own `version`. Publishing tooling parses `version` to decide whether
to republish: an exact version already published is skipped, but moving
major/minor tags (`1`, `1.2`) must always be republished to point at the
latest matching patch.

## Packaging

Both are packaged as tarballs containing the entire sub-directory:
`devcontainer-feature-<id>.tgz` or `devcontainer-template-<id>.tgz`. The
[devcontainers/action](https://github.com/devcontainers/action) GitHub
Action is a reference implementation for packaging + publishing.

### devcontainer-collection.json

Auto-generated per collection at publish time:

| Property | Type | Description |
|---|---|---|
| `sourceInformation` | object | Metadata from the packaging tool. |
| `features` / `templates` | array | Every member's full metadata JSON, appended in. |

## OCI registry distribution

Primary distribution path. Naming convention:
`<registry>/<namespace>/<id>[:version]`, with `namespace` conventionally
`<owner>/<repo>` of the source repo (must be lowercase). Uses custom media
types `application/vnd.devcontainers` (config) and
`application/vnd.devcontainers.layer.v1+tar` (the tarball layer). Every
push tags the exact semver *and* rolling `major`, `major.minor`, and
`latest` tags:

```bash
# ghcr.io/devcontainers/features/go:1
for VERSION in 1 1.2 1.2.3 latest; do
  oras push ${REGISTRY}/${NAMESPACE}/${FEATURE}:${VERSION} \
    --manifest-config /dev/null:application/vnd.devcontainers \
    ./devcontainer-feature-go.tgz:application/vnd.devcontainers.layer.v1+tar
done
```

The collection file is pushed to the bare namespace, always tagged
`latest`, with no feature/template name segment:

```bash
oras push ${REGISTRY}/${NAMESPACE}:latest \
  --manifest-config /dev/null:application/vnd.devcontainers \
  ./devcontainer-collection.json:application/vnd.devcontainers.collection.layer.v1+json
```

Features additionally get a `dev.containers.metadata`
[OCI annotation](https://github.com/opencontainers/image-spec/blob/main/annotations.md)
on the manifest — the escaped JSON of the full `devcontainer-feature.json`
as packaged. This lets a consuming tool read a Feature's `dependsOn`/
`installsAfter` (for [install-order resolution](features.md#installation-order))
straight from the manifest, without downloading and extracting the
tarball. If the annotation is absent, tools **must** fall back to
downloading and extracting — skipping that fallback risks installing a
Feature without its declared dependencies.

## Directly referencing a tarball

A Feature (not Template) can be referenced by an `https://` URI straight
to its packaged tarball, which must be named
`devcontainer-feature-<id>.tgz`. No registry involved; the whole tarball
must be downloaded and extracted to read its metadata (no manifest
annotation shortcut available here).

## Locally referenced Features

Useful while authoring. Constraints, all enforced by the referencing tool:

- The project must have a `.devcontainer/` folder at its
  [project workspace folder](https://containers.dev/implementors/spec/#project-workspace-folder) root.
- The Feature's source must live in a sub-folder **of** that
  `.devcontainer/` folder, named to match the Feature's `id`.
- Referenced with a relative, unix-style path (e.g. `./myFeature`) —
  **never** an absolute path.
- The sub-folder needs at least `devcontainer-feature.json` and
  `install.sh`, same as any packaged Feature.

```
.devcontainer/
├── localFeatureA/
│   ├── devcontainer-feature.json
│   └── install.sh
└── devcontainer.json
```
```jsonc
// devcontainer.json
{ "features": { "./localFeatureA": {} } }
```

A local Feature is never considered equal to any other Feature (local or
published) for [install-order dedup purposes](features.md#installation-order)
— each reference is unique.

## Lockfile: devcontainer-lock.json

Records exact resolved versions and checksums for every Feature in a
`devcontainer.json`, next to it, keyed by the Feature reference exactly as
written (lowercased). Improves reproducibility (pins "latest" to what was
actually installed), build cache stability, and gives "trust on first use"
integrity checking — a changed checksum on a pinned Feature is detectable.

| Field | Description |
|---|---|
| `resolved` | OCI: qualified ID + `@sha256:...` digest (not the version tag). Tarball: the `https:` download URL. |
| `version` | Full resolved version number. |
| `integrity` | `sha256:` + hex SHA-256 of the downloaded artifact. |
| `dependsOn` | Array of that Feature's own `dependsOn` keys (with version/checksum suffix); omitted if empty. Every listed dependency also gets its own top-level record. |

Local Features and deprecated GitHub-release-based Features are never
recorded in the lockfile.

```jsonc
{
  "features": {
    "ghcr.io/devcontainers/features/node:1": {
      "version": "1.0.4",
      "resolved": "ghcr.io/devcontainers/features/node@sha256:567d704b...",
      "integrity": "sha256:567d704b..."
    }
  }
}
```
