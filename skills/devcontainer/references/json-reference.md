# devcontainer.json reference

Full property reference, condensed from
[containers.dev/implementors/json_reference](https://containers.dev/implementors/json_reference/).
Properties marked 🏷️ can also live in the `devcontainer.metadata` **image
label**, so a prebuilt image can carry its own config — see
[lifecycle-and-tools.md](lifecycle-and-tools.md#image-metadata) for the
merge rules.

## General properties

| Property | Type | Description |
|---|---|---|
| `name` | string | Display name for the dev container. |
| `forwardPorts` 🏷️ | array | Port numbers or `"host:port"` values (e.g. `[3000, "db:5432"]`) always forwarded from the primary container to the local machine. Useful for ports a supporting tool can't auto-detect, or a non-primary service in a Compose setup. Defaults to `[]`. |
| `portsAttributes` 🏷️ | object | Maps a port number, `"host:port"`, range, or regex to [port attributes](#port-attributes). E.g. `"portsAttributes": {"3000": {"label": "App"}}`. |
| `otherPortsAttributes` 🏷️ | object | Default [port attributes](#port-attributes) for ports not matched by `portsAttributes`. |
| `containerEnv` 🏷️ | object | Name/value pairs baked into the container itself — every process (including the entrypoint) sees them, but changing a value needs a rebuild. Prefer this over `remoteEnv` unless the value must be dynamic. |
| `remoteEnv` 🏷️ | object | Name/value pairs applied only to the supporting tool's own processes (terminals, tasks, `devcontainer exec`) — not the container's entrypoint. Changeable without a rebuild. |
| `remoteUser` 🏷️ | string | User the supporting tool (and sub-processes) runs as. Defaults to the container user. Doesn't change the container's own user — see `containerUser`. |
| `containerUser` 🏷️ | string | User for all in-container operations. Defaults to `root` or the Dockerfile's last `USER`. |
| `updateRemoteUserUID` 🏷️ | boolean | Linux only. If `containerUser`/`remoteUser` is set, updates that user's UID/GID to match the local user's, avoiding bind-mount permission problems. Default `true`. |
| `userEnvProbe` 🏷️ | enum | Shell used to "probe" for user env vars to merge into the tool's processes: `none`, `interactiveShell`, `loginShell`, `loginInteractiveShell` (default). `loginInteractiveShell` sources all of `/etc/profile`, `~/.profile`, `/etc/bash.bashrc`, `~/.bashrc`. |
| `overrideCommand` 🏷️ | boolean | If `true`, run `/bin/sh -c "while sleep 1000; do :; done"` instead of the image's default command, so the container survives a failing default command. Default `true` for image/Dockerfile, `false` for Compose. |
| `shutdownAction` 🏷️ | enum | What happens to the container(s) when the supporting tool disconnects: `none`, `stopContainer` (default, image/Dockerfile), `stopCompose` (default, Compose). |
| `init` 🏷️ | boolean | Adds the [tini](https://github.com/krallin/tini) init process (`--init`) to reap zombie processes. Default `false`. |
| `privileged` 🏷️ | boolean | Runs the container `--privileged` (needed for Docker-in-Docker; security implications, especially on bare Linux). Default `false`. |
| `capAdd` 🏷️ | array | Extra container capabilities, e.g. `["SYS_PTRACE"]` for native debuggers (C++/Go/Rust). Default `[]`. |
| `securityOpt` 🏷️ | array | Security options, e.g. `["seccomp=unconfined"]`. Default `[]`. |
| `mounts` 🏷️ | array | Extra mounts. Each entry accepts the same fields as the [Docker CLI `--mount` flag](https://docs.docker.com/engine/reference/commandline/run/#mount); [variables](#variables-in-devcontainerjson) may be used in values. |
| `features` | object | Map of [Dev Container Feature](features.md) IDs to their options. |
| `overrideFeatureInstallOrder` | array | Overrides automatic Feature install ordering — see [features.md](features.md#installation-order). |
| `customizations` 🏷️ | object | Tool-specific config, namespaced per tool — see [lifecycle-and-tools.md](lifecycle-and-tools.md#customizations). |
| `secrets` | object | *Declares* (not stores) secrets the project needs — see [lifecycle-and-tools.md](lifecycle-and-tools.md#secrets). |

## Image/Dockerfile-specific properties

Used only when neither `dockerComposeFile` scenario applies.

| Property | Type | Description |
|---|---|---|
| `image` | string | **Required for the image scenario.** Registry image reference. |
| `build.dockerfile` | string | **Required for the Dockerfile scenario.** Path relative to `devcontainer.json`. |
| `build.context` | string | Docker build context, relative to `devcontainer.json`. Default `"."`. |
| `build.args` | object | Build args; [variables](#variables-in-devcontainerjson) allowed in values. |
| `build.options` | array | Extra `docker build` CLI options. Default `[]`. |
| `build.target` | string | Build target stage. |
| `build.cacheFrom` | string \| array | Image(s) to use as build cache (`--cache-from`). |
| `appPort` | integer \| string \| array | Port(s) *published* (Docker `-p`) when the container runs. Requires the app to listen on `0.0.0.0`, not just `localhost` — prefer `forwardPorts` unless you specifically need publishing semantics. |
| `workspaceMount` | string | Overrides the workspace's local mount point. Requires `workspaceFolder` be set too. Same value grammar as `--mount`. |
| `workspaceFolder` | string | Path inside the container that tooling should open. Requires `workspaceMount` be set too. Defaults to the automatic source mount location. |
| `runArgs` | array | Extra [Docker CLI run arguments](https://docs.docker.com/engine/reference/commandline/run/), e.g. `["--cap-add=SYS_PTRACE", "--security-opt", "seccomp=unconfined"]`. |

## Docker Compose-specific properties

Used only when `dockerComposeFile` is set.

| Property | Type | Description |
|---|---|---|
| `dockerComposeFile` | string \| array | **Required.** Path(s) to Compose file(s), relative to `devcontainer.json`. An array's *later* files can override earlier ones (same as [Compose's own multi-file extension](https://docs.docker.com/compose/extends/#multiple-compose-files)). |
| `service` | string | **Required.** The Compose service that is the **main** container tooling connects to. |
| `runServices` | array | Compose services to start/stop with the environment. Default: all services. Stopped on disconnect unless `shutdownAction` is `"none"`. |
| `workspaceFolder` | string | Path tooling should open (often a volume mount inside the service). Default `"/"`. |

`image`/Dockerfile properties aren't used here — Compose already expresses
them natively per-service.

## Lifecycle scripts

Run, in this order, at the points named: `initializeCommand` (host, on
every start) → `onCreateCommand` → `updateContentCommand` →
`postCreateCommand` (all three: in-container, only meaningfully on first
creation) → `postStartCommand` (every start) → `postAttachCommand` (every
tool attach).

| Property | Description |
|---|---|
| `initializeCommand` | Runs on the **host** (not in the container) during initialization, including every subsequent start. For cloud services, "host" means wherever the source is — i.e. in the cloud. |
| `onCreateCommand` 🏷️ | First of three container-setup commands, run in-container right after first start. Cloud prebuild/cache steps use this; it typically lacks user-scoped secrets. |
| `updateContentCommand` 🏷️ | Second of three; runs after `onCreateCommand` whenever new source content is available (at least once, and periodically for cloud prebuild refresh). Only repo/org-scoped secrets available. |
| `postCreateCommand` 🏷️ | Third of three; runs after `updateContentCommand`, once the container is assigned to a user for the first time. User-scoped secrets available here. |
| `postStartCommand` 🏷️ | Runs every successful container start. |
| `postAttachCommand` 🏷️ | Runs every time a tool successfully attaches. |
| `waitFor` 🏷️ | Which command in the create sequence a tool should block on before connecting. Default `updateContentCommand`. |

If any lifecycle script fails, every later one in the sequence is skipped
(`postCreateCommand` failing skips `postStartCommand`, etc.).

### Formatting: string vs. array vs. object properties

Applies to every lifecycle command above, plus `runArgs` (array only):

- **String** — goes through `/bin/sh`, so `&&`, quoting, and shell parsing
  apply. `"apt-get update && apt-get install -y curl"`.
- **Array** — the OS execs the first element directly, **no shell**.
  Quotes inside array elements are passed through literally, not stripped:
  `["echo", "foo='bar'"]` prints `foo='bar'` including the quotes, whereas
  the string form `"echo foo='bar'"` would have the shell strip them.
- **Object** — added for [parallel execution](https://containers.dev/implementors/spec/#parallel-lifecycle-script-execution).
  Each key names a sub-command; each value is a string or array command;
  all entries run **in parallel**, and the whole group must succeed before
  the lifecycle stage is considered complete:
  ```json
  { "postCreateCommand": { "server": "npm start", "db": ["mysql", "-u", "root", "-p", "my database"] } }
  ```

## Host requirements

| Property | Type | Description |
|---|---|---|
| `hostRequirements.cpus` 🏷️ | integer | Minimum CPUs/vCPUs/cores. |
| `hostRequirements.memory` 🏷️ | string | Minimum memory, `tb`/`gb`/`mb`/`kb` suffix, e.g. `"4gb"`. |
| `hostRequirements.storage` 🏷️ | string | Minimum storage, same suffix grammar. |
| `hostRequirements.gpu` 🏷️ | `boolean` \| `"optional"` \| object | `true` requires a GPU, `"optional"` uses one if available, `false` (default) requires none. As an object: `{"cores": 2, "memory": "4gb"}`. |

Cloud services can use these to auto-pick compute; other tools may just
warn when unmet. This is advisory sizing, not VM/hardware provisioning.

## Port attributes

Options settable per-port (or as a default) via `portsAttributes` /
`otherPortsAttributes`:

| Property | Type | Description |
|---|---|---|
| `label` 🏷️ | string | Display name in the ports UI. |
| `protocol` 🏷️ | enum: `http`, `https` | Unset = raw TCP. `https` ignores in-container SSL/TLS certs and uses the correct cert for the forwarded URL instead. |
| `onAutoForward` 🏷️ | enum: `notify` (default), `openBrowser`, `openBrowserOnce`, `openPreview`, `silent`, `ignore` | What happens when the port auto-forwards. |
| `requireLocalPort` 🏷️ | boolean | `true` = notify if the same local port can't be used; `false` (default) = silently remap. |
| `elevateIfNeeded` 🏷️ | boolean | Auto-elevate permissions to forward low ports (22/80/443) to the same local port. Default `false`. |

## Variables in devcontainer.json

Referenced as `${variableName}` in string-valued properties:

| Variable | Description |
|---|---|
| `${localEnv:VAR}` | Host env var value (cloud: "host" is in the cloud). Unset → blank. Default: `${localEnv:VAR:default_value}`. Some tools need a restart to pick up newly-set host vars. |
| `${containerEnv:VAR}` | Existing in-container env var, once running — usable only in `remoteEnv` values, e.g. `"PATH": "${containerEnv:PATH}:/extra"`. Default: `${containerEnv:VAR:default_value}`. |
| `${localWorkspaceFolder}` | Local folder path opened by the tool. |
| `${containerWorkspaceFolder}` | In-container path of the workspace. |
| `${localWorkspaceFolderBasename}` | Basename of the local workspace folder. |
| `${containerWorkspaceFolderBasename}` | Basename of the in-container workspace path. |
| `${devcontainerId}` | Stable-across-rebuilds ID unique to this dev container. Supported on `name`, `runArgs`, all lifecycle commands, `workspaceFolder`, `workspaceMount`, `mounts`, `containerEnv`, `remoteEnv`, `containerUser`, `remoteUser`, `customizations`. Computation is implementation-defined (a reference SHA-256-of-sorted-labels scheme is described in [features.md](features.md#devcontainerid)). |

## Publishing vs. forwarding ports

Docker "publishing" (`appPort`/`-p`) behaves like exposing a port on the
local network — an app that only accepts `localhost` calls will reject
published-port connections just as it would reject a real network call.
Forwarded ports (`forwardPorts`) look like `localhost` to the app itself.

## Schema

Machine-readable schema:
[devContainer.base.schema.json](https://github.com/devcontainers/spec/blob/main/schemas/devContainer.base.schema.json).
