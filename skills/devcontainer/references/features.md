# Dev Container Features

A **Feature** is a self-contained, shareable unit of install code + dev
container config, referenced by ID under the top-level `features` object in
`devcontainer.json`. Full spec:
[containers.dev/implementors/features](https://containers.dev/implementors/features/).
For authoring from scratch, start from the
[feature-template](https://github.com/devcontainers/feature-template) repo
rather than this reference.

## Folder structure

```
feature/
├── devcontainer-feature.json   # required
├── install.sh                  # required entrypoint
└── (other files)               # optional, packaged alongside
```

## devcontainer-feature.json properties

Everything is optional **except `id`, `version`, `name`**.

| Property | Type | Description |
|---|---|---|
| `id` | string | **Required.** Unique within the repo; must match the Feature's directory name; lowercase. |
| `version` | string | **Required.** Semver, e.g. `1.0.0`. |
| `name` | string | **Required.** Human-friendly display name. |
| `description` | string | Description. |
| `documentationURL` | string | Docs link. |
| `licenseURL` | string | License link. |
| `keywords` | array | Search keywords. |
| `options` | object | Options passed as env vars to `install.sh` — see [below](#the-options-property). |
| `containerEnv` | object | Env vars set/overridden when the Feature is used. |
| `privileged` | boolean | Requires `--privileged` (e.g. Docker-in-Docker) when used. |
| `init` | boolean | Requires the tini init process when used. |
| `capAdd` | array | Extra container capabilities required when used. |
| `securityOpt` | array | Security options required when used. |
| `entrypoint` | string | An entrypoint script that must fire at container startup. |
| `customizations` | object | Tool-specific properties, namespaced like `devcontainer.json`'s `customizations`. |
| `dependsOn` | object | **Hard** dependencies — Features that must be installed first. See [Installation order](#installation-order). |
| `installsAfter` | array | **Soft** dependency — Feature IDs (no version) that should install before this one, *if already queued*. See [Installation order](#installation-order). |
| `legacyIds` | array | Prior `id`s this Feature was published under (for renames). |
| `deprecated` | boolean | Marks the Feature as receiving no further updates. |
| `mounts` | array | Extra mounts, same grammar as `devcontainer.json`'s `mounts`; may reference `${devcontainerId}`. |

### Lifecycle hooks

A Feature may declare `onCreateCommand`, `updateContentCommand`,
`postCreateCommand`, `postStartCommand`, `postAttachCommand` — same
[string/array/object formatting](json-reference.md#formatting-string-vs-array-vs-object-properties)
and semantics as `devcontainer.json`'s versions. For each hook, Features'
commands run in [Feature install order](#installation-order), each
blocking the next — **always before** the user's own `devcontainer.json`
command for that hook. A Feature's object-syntax hook still runs its own
entries in parallel, while blocking subsequent Features/the user's command.
These are stored in [image metadata](lifecycle-and-tools.md#image-metadata).

### The `options` property

```json
{
  "options": {
    "version": {
      "type": "string",
      "enum": ["latest", "3.10", "3.9"],
      "default": "latest",
      "description": "Select a Python version to install."
    },
    "pip": { "type": "boolean", "default": true, "description": "Installs pip" }
  }
}
```

| Property | Type | Description |
|---|---|---|
| `optionId.type` | string | `boolean` or `string`. |
| `optionId.proposals` | array | Suggested string values; free-form still allowed. Mutually exclusive with `enum`. |
| `optionId.enum` | array | Allowed string values; free-form **not** allowed. Mutually exclusive with `proposals`. |
| `optionId.default` | string \| boolean | Default when the user omits the option. |
| `optionId.description` | string | Shown to the user. |

**Option resolution:** the option ID is upper-cased into an env var name
(non-word chars → `_`, leading digits/underscores stripped to a single
`_`, everything upper-cased) and written to `devcontainer-features.env`,
sourced by `install.sh` at build time. Options the user omits are exported
at their declared default. Given
`"ghcr.io/devcontainers/features/python:1": {"version": "3.10", "pip": false}`
against the schema above, `install.sh` sees `VERSION=3.10`, `PIP=false`,
plus any other declared option at its default.

### User environment variables

Feature scripts run as `root`, but often need to know which user the dev
container will actually be used with. `_REMOTE_USER` / `_CONTAINER_USER`
(and `_REMOTE_USER_HOME` / `_CONTAINER_USER_HOME`) env vars are passed into
every Feature script. If no `remoteUser` is configured, `_REMOTE_USER`
equals `_CONTAINER_USER`. Use `su ${USERNAME} -c "..."` to run a step as
the non-root user even without `sudo` present.

### `${devcontainerId}`

An identifier stable across rebuilds and unique among dev containers on
the same host, usable in a Feature's `entrypoint`, `mounts`, and
`customizations` (not in properties that affect image build, since the ID
isn't known yet at build time). One reference computation: hash the dev
container's identifying container labels as a sorted-key JSON object with
SHA-256, then base-32-encode left-padded to 52 chars:

```js
const crypto = require('crypto');
function uniqueIdForLabels(idLabels) {
  const stringInput = JSON.stringify(idLabels, Object.keys(idLabels).sort());
  const hash = crypto.createHash('sha256').update(Buffer.from(stringInput, 'utf-8')).digest();
  return BigInt(`0x${hash.toString('hex')}`).toString(32).padStart(52, '0');
}
```

## devcontainer.json properties

Under `features`, each key is a Feature ID and each value is its options
(or `{}` for defaults):

```jsonc
"features": {
  "ghcr.io/user/repo/go": {},
  "ghcr.io/user/repo1/go:1": {},
  "https://github.com/user/repo/releases/devcontainer-feature-go.tgz": { "optionA": "value" },
  "./myGoFeature": { "optionA": true, "optionB": "hello", "version": "1.0.0" }
}
```

A bare string value is shorthand for the `version` option:
`"ghcr.io/owner/repo/go": "1.18"` ≡ `"ghcr.io/owner/repo/go": {"version": "1.18"}`.
A version tag is implicitly `:latest` if omitted.

### Referencing a Feature

| Format | Example |
|---|---|
| `<oci-registry>/<namespace>/<feature>[:<semver>]` | `ghcr.io/user/repo/go:1` |
| `https://<uri-to-tgz>` | `https://github.com/user/repo/releases/devcontainer-feature-go.tgz` |
| `./<path-to-feature-dir>` | `./myGoFeature` (relative to the `devcontainer.json` that references it) |

OCI registries must implement the
[OCI Artifact Distribution Spec](https://github.com/opencontainers/distribution-spec).
Identifiers are case-insensitive; normalize to lowercase.

## Installation order

Three properties, applied in this priority (dependencies first, always):

1. **`dependsOn`** (Feature metadata) — hard, **recursive** dependency.
   Adds the dependency to the install set even if the user never
   referenced it; must be satisfied (recursively) before the Feature
   installs; a broken/circular chain fails the whole build.
2. **`installsAfter`** (Feature metadata) — soft dependency, **not
   recursive**, and only reorders Features **already queued**. A Feature
   named here that isn't otherwise going to be installed is simply
   ignored. Can't carry options or a pinned version — only affects order.
3. **`overrideFeatureInstallOrder`** (user's `devcontainer.json`) — an
   array of Feature IDs (no version/options) in descending priority.
   Assigns each a `roundPriority` of `n - idx`; can only "pull forward" a
   Feature after its own dependencies are already satisfied — it can
   never violate the dependency graph from (1)/(2).

Two Features are **equal** (and thus deduplicated) only if they resolve to
identical content *and* identical options — same OCI manifest digest, same
tarball hash, or (for local Features) never equal to anything else. This
means the *same* Feature ID with different options is treated as two
separate installs.

Implementations build a dependency graph from `dependsOn`/`installsAfter`,
then do round-based topological sort: each round commits every Feature
whose dependencies are already installed, preferring higher
`roundPriority`; ties break by a defined stable sort (fully-qualified name,
then tag age, then option count/keys/values, then canonical digest). An
empty round with unresolved work means a circular dependency — the build
must fail with diagnostics, not silently drop Features.

```json
{
  "name": "My Feature",
  "id": "myFeature",
  "version": "1.0.0",
  "dependsOn": {
    "foo:1": { "flag": true },
    "bar:1.2.3": {}
  }
}
```

## Versioning

Each Feature is independently [semver](https://semver.org/)-versioned via
its own `version`. Publishing tooling must not republish an exact version
twice, but must republish moving major/minor tags per semver rules.

## Renaming or deprecating a Feature

1. Update the source folder name and `id` to the new value.
2. Add the old `id` to `legacyIds`.
3. Bump `version` — **continue** the existing version sequence, don't
   restart at `1.0.0`.
4. Republish. Tooling dual-publishes under both the new `id` and every
   `legacyIds` entry, and honors `legacyIds` when resolving other
   Features' `installsAfter` references to the old name.

Set `deprecated: true` to signal "no further updates" without unpublishing
— existing configs referencing it keep working; a security fix can still
bump the version later.

## Execution

`install.sh` runs as `root` during image build (so it can modify the OS,
then `su ${USERNAME} -c "..."` for non-root steps even without `sudo`).
Make it executable and invoke it directly (`chmod +x install.sh &&
./install.sh`) rather than via `sh install.sh`, so a non-`bash` shebang
(e.g. for Alpine's `sh`) is honored. Applications default to `/bin/sh` if
a Feature doesn't specify what it needs. Each Feature installs in its own
image layer, aiding build caching.

See [distribution.md](distribution.md) for packaging and publishing.
