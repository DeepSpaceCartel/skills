---
name: devcontainer
description: How to write and review Dev Container configuration per the Development Container Specification (https://containers.dev/, implementor detail at https://containers.dev/implementors/spec/ and https://containers.dev/implementors/json_reference/) - project-agnostic. Covers the devcontainer.json file (valid locations, every property, image/Dockerfile/Docker Compose scenarios, lifecycle scripts, variable substitution, port attributes, host requirements, customizations), Dev Container Features (devcontainer-feature.json, the options-to-env-var contract, dependsOn/installsAfter/overrideFeatureInstallOrder install ordering), Dev Container Templates (devcontainer-template.json, options, optionalPaths), OCI/tarball distribution and the devcontainer-lock.json lockfile, and image metadata merge logic. Use when writing or reviewing a devcontainer.json, authoring or publishing a Dev Container Feature or Template, debugging Feature install order or option resolution, or setting up a reproducible containerized dev environment for VS Code, GitHub Codespaces, DevPod, or another supporting tool.
---

# Dev Containers

The **Development Container Specification** defines metadata — chiefly a
`devcontainer.json` file — that enriches an OCI container with what's needed
to develop inside it: how to build or reach the container, environment
variables, mounts, lifecycle commands, and tool-specific customizations.
Full spec at [containers.dev](https://containers.dev/); the implementor-facing
detail this skill is built from lives at
[containers.dev/implementors/spec](https://containers.dev/implementors/spec/)
and [containers.dev/implementors/json_reference](https://containers.dev/implementors/json_reference/).
Reference implementation: [devcontainers/cli](https://github.com/devcontainers/cli).
Spec source/history: [github.com/devcontainers/spec](https://github.com/devcontainers/spec).

Three things share this one spec, and most confusion is about telling them
apart:
- **`devcontainer.json`** — describes one environment directly (this file's
  properties — see [references/json-reference.md](references/json-reference.md)).
- **Dev Container Features** — self-contained, shareable install code +
  config, referenced by ID under `features` — see
  [references/features.md](references/features.md).
- **Dev Container Templates** — a starter `.devcontainer/` folder + options,
  dropped into a new or existing project — see
  [references/templates.md](references/templates.md).

## The core idea

A dev container is described by *scenario* (image, Dockerfile, or Docker
Compose) plus a common set of properties layered on top. Exactly one
scenario applies, and each has its own required property:

| Scenario | Required property | Notes |
|---|---|---|
| Image | `image` | Pull-only, no build step. |
| Dockerfile | `build.dockerfile` | Path relative to `devcontainer.json`. `build.context`/`args`/`options`/`target`/`cacheFrom` control the build. |
| Docker Compose | `dockerComposeFile` + `service` | `service` names the **main** container all tooling attaches to. `image`/Dockerfile properties aren't needed — Compose already has them. |

Everything else — `features`, lifecycle scripts, `remoteEnv`, `mounts`,
`customizations`, etc. — applies on top of whichever scenario is chosen.
The full property table is in
[references/json-reference.md](references/json-reference.md).

## Quick example

```jsonc
// .devcontainer/devcontainer.json
{
  "name": "My Project",
  "image": "mcr.microsoft.com/devcontainers/base:bookworm",
  "features": {
    "ghcr.io/devcontainers/features/node:1": { "version": "20" },
    "ghcr.io/devcontainers/features/github-cli": {}
  },
  "forwardPorts": [3000],
  "postCreateCommand": "npm install",
  "customizations": {
    "vscode": { "extensions": ["dbaeumer.vscode-eslint"] }
  }
}
```

`devcontainer.json` (JSON-with-Comments) is looked up, in order of
precedence, at `.devcontainer/devcontainer.json`, `.devcontainer.json`, or
one level down at `.devcontainer/<folder>/devcontainer.json` — a tool should
let the user pick when more than one exists.

## Where to look

| Reference | Covers |
|---|---|
| [references/json-reference.md](references/json-reference.md) | Every `devcontainer.json` property: general + image/Dockerfile-specific + Compose-specific, lifecycle scripts (string/array/object forms, `waitFor`), port attributes, `hostRequirements` (incl. `gpu`), `${...}` variable substitution, the declarative `secrets` property |
| [references/features.md](references/features.md) | `devcontainer-feature.json` authoring, the `options` → env var contract, referencing a Feature (OCI/tarball/local), install ordering (`dependsOn`, `installsAfter`, `overrideFeatureInstallOrder`), Feature lifecycle hooks, `${devcontainerId}`, renaming/deprecating a Feature |
| [references/templates.md](references/templates.md) | `devcontainer-template.json` authoring, the `options` string-replacement model, `optionalPaths`, referencing a Template |
| [references/distribution.md](references/distribution.md) | Packaging Features/Templates as tarballs, OCI registry distribution, `devcontainer-collection.json`, locally-referenced Features, the `devcontainer-lock.json` lockfile |
| [references/lifecycle-and-tools.md](references/lifecycle-and-tools.md) | The environment lifecycle (init → create → post-create → stop/resume), image metadata (`devcontainer.metadata` label) merge logic, users, environment variable classes, mounts, and the `customizations` namespace pattern (VS Code, Codespaces, secrets) |

## Gotchas

- **`features` values aren't always objects.** A bare string is shorthand
  for `{"version": "<string>"}` — `"go": "1.18"` and
  `"go": {"version": "1.18"}` are equivalent. An empty object `{}` means
  "use this Feature's defaults."
- **A Feature/Template reference without a version tag implicitly means
  `:latest`.** Pin (`:1`, `:1.2.3`, or `@sha256:...`) for reproducibility —
  see the [lockfile](references/distribution.md#lockfile-devcontainer-lockjson).
- **`dependsOn` and `installsAfter` are not interchangeable.** `dependsOn`
  is recursive and *adds* the dependency Feature to the install set even if
  the user never referenced it. `installsAfter` only reorders Features
  already queued for install and is not recursive; a Feature named there
  that nobody asked for is silently ignored, not pulled in.
- **String vs. array vs. object changes execution, not just syntax**, for
  every lifecycle command and `postAttachCommand`/etc.: a string goes
  through `/bin/sh` (so `&&`, quoting, and shell expansion apply); an array
  runs the executable directly with no shell (quotes in arguments are
  passed through literally, not stripped); an object runs each of its
  values in parallel. See
  [references/json-reference.md](references/json-reference.md#formatting-string-vs-array-vs-object-properties).
- **`containerEnv` vs. `remoteEnv` is a rebuild-cost tradeoff, not a
  synonym pair.** `containerEnv` is baked into the container (visible to
  every process, including the entrypoint) and needs a rebuild to change.
  `remoteEnv` is applied by the supporting tool to the processes it starts
  (terminals, tasks, `devcontainer exec`) and can change without a rebuild
  — but isn't visible to the container's own entrypoint.
  `${containerEnv:VAR}` can be read from within a `remoteEnv` value to
  extend rather than replace (e.g. appending to `PATH`).
- **`workspaceMount` requires `workspaceFolder` (and vice versa)** for
  image/Dockerfile scenarios — they're set as a pair, not independently.
  Docker Compose scenarios use the Compose file's own `volumes`/`mounts`
  instead of `workspaceMount`.
- **`forwardPorts` and `appPort` solve different problems.** `forwardPorts`
  makes a port reachable from the host without the app needing to listen
  on anything but `localhost` inside the container. `appPort` *publishes*
  the port (Docker `-p`), which requires the app to listen on `0.0.0.0` —
  and published ports don't behave like `localhost` to an app that only
  trusts loopback callers.
- **Image metadata merge order matters for "last value wins" properties**
  (`remoteUser`, `userEnvProbe`, `shutdownAction`, …): the `devcontainer.json`
  on disk is always applied *last*, after every Feature's metadata — a
  user's local file wins conflicts with any Feature, always.
- **Feature/Template IDs are case-insensitive but should be authored and
  compared as lowercase.** Don't rely on casing to distinguish two
  references — normalize before comparing.
- **The `secrets` property in `devcontainer.json` only *declares* which
  secrets a project wants** (name + description + docs URL) — it never
  holds a secret's value. Actual values are supplied out-of-band by the
  supporting tool (a secrets file, OS keychain, cloud secret store). Don't
  treat a documented `secrets` block as a place to put real credentials,
  and don't treat `remoteEnv` as secret-safe just because it isn't baked
  into the image.
