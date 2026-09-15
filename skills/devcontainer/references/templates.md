# Dev Container Templates

A **Template** is a packaged starter `.devcontainer/` folder (plus
optional boilerplate) that a supporting tool drops into a new or existing
project, prompting the user for any declared `options` first. Full spec:
[containers.dev/implementors/templates](https://containers.dev/implementors/templates/).
Quick start for authoring:
[template-starter](https://github.com/devcontainers/template-starter).

Unlike a Feature (installed into an existing container build), a Template
is a one-time scaffold: its files are copied and string-substituted into
the target project, then the Template is done — there's no ongoing
reference to it afterward.

## Folder structure

```
template/
├── devcontainer-template.json
├── .devcontainer/
│   ├── devcontainer.json
│   └── (other files)
└── (other files)
```

## devcontainer-template.json properties

| Property | Type | Description |
|---|---|---|
| `id` | string | Unique within the repo; must match the Template's directory name. |
| `version` | string | Semver. |
| `name` | string | Display name. |
| `description` | string | Description. |
| `documentationURL` | string | Docs link. |
| `licenseURL` | string | License link. |
| `options` | object | Prompted config values — see [below](#the-options-property). |
| `platforms` | array | Supported languages/platforms. |
| `publisher` | string | Maintainer name. |
| `keywords` | array | Search keywords. |
| `optionalPaths` | array | Files/dirs the user may opt out of — see [below](#the-optionalpaths-property). |

### The `options` property

```json
{
  "options": {
    "imageVariant": {
      "type": "string",
      "description": "Specify version of the base image.",
      "proposals": ["17-bullseye", "17-buster", "11-bullseye"],
      "default": "17-bullseye"
    },
    "installMaven": { "type": "boolean", "description": "Install Maven.", "default": "false" }
  }
}
```

| Property | Type | Description |
|---|---|---|
| `optionId.type` | string | `boolean` or `string`. |
| `optionId.description` | string | Shown to the user when prompting. |
| `optionId.proposals` | array | Suggested string values; free-form still allowed. Mutually exclusive with `enum`. |
| `optionId.enum` | array | Allowed string values only. Mutually exclusive with `proposals`. |
| `optionId.default` | string | Default value. |

Option IDs must be unique within one `devcontainer-template.json`.

**Resolution:** the supporting tool prompts for each option (or uses the
default), then does a literal string replacement of `${templateOption:id}`
across every file under the Template's sub-directory — most commonly
inside `.devcontainer/devcontainer.json`:

```json
{
  "image": "mcr.microsoft.com/devcontainers/java:0-${templateOption:imageVariant}",
  "features": {
    "ghcr.io/devcontainers/features/node:1": {
      "installMaven": "${templateOption:installMaven}"
    }
  }
}
```

selecting `imageVariant: "17-bullseye"` and the default for `installMaven`
rewrites that file to a literal `mcr.microsoft.com/devcontainers/java:0-17-bullseye`
and `"installMaven": "false"` before it's dropped into the target project.

### The `optionalPaths` property

Before applying the Template, tooling must ask the user, per entry,
whether to include it. A path is relative to the Template's root:

```jsonc
"optionalPaths": [
  "GETTING-STARTED.md",                 // single file
  "example-project-1/MyProject.csproj", // nested single file
  ".github/*"                           // whole directory, recursively
]
```

Trailing `/*` marks a directory (and everything under it); no trailing
slash means a single file.

## Referencing a Template

`<oci-registry>/<namespace>/<template>[:<semver>]`, e.g. `ghcr.io/user/repo/go:1`.
The registry must implement the
[OCI Artifact Distribution Spec](https://github.com/opencontainers/distribution-spec).

## Versioning

Each Template is independently [semver](https://semver.org/)-versioned via
its own `version`; publishing tooling must not republish an identical
version twice but must republish moving major/minor tags.

See [distribution.md](distribution.md) for packaging and publishing.
