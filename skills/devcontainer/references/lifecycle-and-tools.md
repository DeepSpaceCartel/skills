# Environment lifecycle, image metadata, and tool customizations

## Environment lifecycle

Four top-level events, from
[containers.dev/implementors/spec](https://containers.dev/implementors/spec/#lifecycle):
**Configuration Validation → Environment Creation → Environment Stop →
Environment Resume.**

### Configuration validation

1. A workspace source folder must be provided (behavior if absent is
   implementation-defined).
2. Search the [standard locations](../SKILL.md#quick-example) for
   `devcontainer.json`.
3. If none is found, behavior is implementation-defined — the spec doesn't
   mandate a fallback.
4. Validate the found metadata has every property its scenario requires
   (`image`, or `build.dockerfile`, or `dockerComposeFile` + `service`).

### Environment creation

1. **Initialization** — validate access to the orchestrator; run
   `initializeCommand` on the host.
2. **Image creation** — pull/build/`docker-compose build` as the scenario
   requires; validate the result. Worth exposing as its own tool command,
   since it's reusable for prebuilding shareable intermediate images.
3. **Container creation** — optional UID/GID sync (Linux only, when
   `updateRemoteUserUID` is true and a `containerUser`/`remoteUser` is
   set — updates that user's UID/GID in the image *before* container
   creation, to avoid bind-mount permission mismatches; implementations
   may skip this if they avoid Linux bind mounts or their engine already
   handles the translation); create the container(s); validate creation.
   [Mounts](#mounts), [container-level env vars](#environment-variable-classes),
   and [container user](#users) apply here — **not** remote user/env yet.
4. **Post container creation** — run `onCreateCommand`,
   `updateContentCommand`, `postCreateCommand` in sequence (first creation
   only); block on `waitFor` (default `updateContentCommand`), then run
   the rest (typically `postCreateCommand`) in the background.
   [Remote env/user](#environment-variable-classes) now apply to every
   process, including `userEnvProbe`.
5. **Implementation-specific steps** — anything the tool itself needs
   (e.g. `devcontainer exec` support), plus applying `customizations`
   (not spec-mandated, but the conventional point to do it — see
   [Customizations](#customizations)). May run in parallel with
   non-blocking background lifecycle commands.

### Environment stop / resume

Stop: shut down all containers per-orchestrator; timing is
implementation-defined. Resume: restart containers, redo the
implementation-specific steps above, then run `postStartCommand` and
`postAttachCommand` — with remote env/user applied throughout, same as
creation.

## Image metadata

Feature and `devcontainer.json` metadata (properties marked 🏷️ in
[json-reference.md](json-reference.md)) can be baked into a prebuilt image
as a `devcontainer.metadata` **label**, so the image is self-describing —
no need to repeat Feature config in every consumer's `devcontainer.json`.
The label's value is a JSON array (one entry per Feature, plus one for
`devcontainer.json` itself), or a single object as shorthand for one
entry:

```json
[{ "id": "...", "init": true, "mounts": [], "customizations": {} }]
```

### Merge logic

At container creation, image-label entries merge with the local
`devcontainer.json`, **which is always applied last** when order matters:

| Property | Merge rule |
|---|---|
| `init`, `privileged` | `true` if *any* entry is `true`. |
| `capAdd`, `securityOpt` | Union, deduplicated. |
| `entrypoint` | Collected list, all entries. |
| `mounts` | Collected list; conflicting mount source → last one wins. |
| `onCreateCommand`, `updateContentCommand`, `postCreateCommand`, `postStartCommand`, `postAttachCommand` | Collected list, all entries, run in order. |
| `waitFor`, `containerUser`, `remoteUser`, `userEnvProbe`, `overrideCommand`, `otherPortsAttributes`, `shutdownAction`, `updateRemoteUserUID` | Last value wins. |
| `remoteEnv`, `containerEnv` | Per-variable, last value wins. |
| `portsAttributes` | Per-port (not per-attribute), last value wins. |
| `forwardPorts` | Union, deduplicated; last mapping wins on conflict. |
| `hostRequirements` | Max value wins (per sub-field: `cpus`, `memory`, `storage`, `gpu`). |
| `customizations` | Left to the consuming tool to merge. |
| `id` | Not merged (Feature identity only). |

Variable substitution happens when a merged value is actually applied, not
at merge time.

### Practical size limits

- As a Dockerfile `LABEL`: Dockerfiles cap around 1.3MB total, 65k chars
  per line — use one line per Feature to make full use of that.
- As a build-time CLI label argument: no documented label-specific limit,
  but the Docker daemon rejects request headers over 500KB total (shared
  across all labels in that build — a second label doesn't buy more room).

## Orchestration options

See [json-reference.md](json-reference.md#imagedockerfile-specific-properties)
for the three scenarios' exact required/optional properties. Only one
applies per `devcontainer.json`; a core design goal of the spec is to
*enrich* an orchestrator format (plain image, Dockerfile, Compose) rather
than replace it, leaving room for future orchestrators.

## Users

Two independent user concepts:

- **Container user** (`containerUser`, or Compose's `user:` / Dockerfile's
  `USER`) — runs everything native to the container, including its
  `ENTRYPOINT`.
- **Remote user** (`remoteUser`) — runs lifecycle scripts and whatever the
  supporting tool itself spawns (terminals, tasks, debuggers). Defaults to
  the container user. This split lets the entrypoint run with different
  permissions than the developer, and lets a developer switch users
  without recreating the container. `remoteUser` is inherited from the
  base image if not overridden — a Template built on an image with a
  custom `remoteUser` keeps that value unless it sets its own.

## Environment variable classes

- **Container** — part of the image/container itself; set via
  `containerEnv` (image/Dockerfile) or the orchestrator's native mechanism
  (Compose `environment:`). Visible everywhere, always, but needs a
  rebuild to change.
- **Remote** — set by the supporting tool as it configures its own
  runtime, via `remoteEnv` (or tool/service-specific mechanisms, e.g.
  secrets injection). Can change without a rebuild; applied after the
  container's `ENTRYPOINT` has already fired.
- **`userEnvProbe`** — has the tool "probe" a shell (per the enum in
  [json-reference.md](json-reference.md#general-properties)) for
  environment set up by the user's own shell rc/profile files, then merges
  the result into Remote env for every process the tool injects
  afterward — without requiring every sub-process launch to pay the cost
  of a full probing shell.

## Mounts

A default bind mount makes the source code available in-container —
conventionally at `/workspace` — kept outside the container so in-flight
edits survive a container recreate. Not required to be a bind mount by the
spec, and cloud environments may not have local-filesystem access the way
a bind mount implies.

`workspaceMount` (image/Dockerfile only; Compose uses its own
`volumes:`/`mounts:`) overrides that default mount point — should point at
the repo root (where `.git` lives) so source control still works
in-container. `workspaceFolder` is the path tooling opens by default —
often the mount point itself, or a sub-folder of it for monorepos, where
`.git` is still needed at the mount root but developers work in a
sub-project.

## Customizations

Each supporting tool gets its own namespace under `customizations`, merged
independently by the tool (the spec doesn't define cross-tool merge
rules):

```jsonc
"customizations": {
  "vscode": {
    "extensions": ["dbaeumer.vscode-eslint"],
    "settings": {}
  },
  "codespaces": {
    "repositories": { "my_org/my_repo": { "permissions": { "issues": "write" } } },
    "openFiles": ["README.md", "src/index.js"],
    "disableAutomaticConfiguration": true
  }
}
```

VS Code's `extensions` (array, default `[]`) and `settings` (object,
default `{}`) are the most widely-supported example — both GitHub
Codespaces and the VS Code Dev Containers extension honor them. Current
supporting tools are tracked at
[containers.dev/supporting](https://containers.dev/supporting) rather than
enumerated in the spec itself; notable ones beyond VS Code/Codespaces
include IntelliJ IDEA, Visual Studio (C++/CMake), DevPod, and Ona (formerly
Gitpod).

## Secrets

Two distinct, non-overlapping mechanisms — don't conflate them:

- **Out-of-band secret injection** (the actual values). Secrets are
  deliberately **not** part of `devcontainer.json` — a conforming tool
  passes real values through its own secure channel (a secrets file, OS
  keychain, cloud secret manager) and exposes them similarly to
  `remoteEnv`, changeable without a rebuild. `remoteEnv` itself carries no
  secret-handling guarantee; treating it as a secrets channel just because
  it's outside the image is a category error.
- **Declarative `secrets` property** (metadata only, no values). An
  optional `devcontainer.json` property describing which secrets a project
  *wants*, so a supporting tool can prompt for them:
  ```json
  {
    "secrets": {
      "CHAT_GPT_API_KEY": {
        "description": "API key for ChatGPT.",
        "documentationUrl": "https://openai.com/api/"
      },
      "STABLE_DIFFUSION_API_KEY": {}
    }
  }
  ```
  Every field is optional; the keys must be valid env var names. Tools
  *may* inject the resulting values as env vars, but the property itself
  never carries a value — it's purely a prompt/documentation hint.

## GPU / host requirements addendum

`hostRequirements.gpu` (see [json-reference.md](json-reference.md#host-requirements))
was added after the base `hostRequirements` shape — `cpus`/`memory`/
`storage` alone predate it. Same image-metadata "max wins" merge rule
applies to `gpu` as to the other `hostRequirements` sub-fields.
