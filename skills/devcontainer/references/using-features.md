# Using Features: finding, trusting, pinning

A Feature is third-party code that runs **as root during your image
build**. Its metadata is also merged into the container's runtime config,
including `privileged`, `capAdd`, `securityOpt`, `mounts` and
`entrypoint`. Adding one line under `features` is equivalent to adding
someone else's script to your Dockerfile and their flags to your
`docker run`. Choose Features the way you'd choose a dependency, not
the way you'd pick a VS Code theme.

## Where to find Features

| Source | What it is |
| --- | --- |
| [containers.dev/features](https://containers.dev/features) | The public index. It's built by crawling every collection registered in [`collection-index.yml`](https://github.com/devcontainers/devcontainers.github.io/blob/gh-pages/_data/collection-index.yml) (300+ entries). |
| VS Code *Dev Containers: Configure Container Features* | A picker over the same index. |
| [`devcontainers/features`](https://github.com/devcontainers/features) | The reference collection, `ghcr.io/devcontainers/features/*`. |
| `devcontainer features info verbose <ref>` | Fetches a published Feature's manifest, tags and dependencies without installing it. |

**Being listed is not a review.** A collection gets onto the index
through a PR that adds its repo and OCI namespace to
`collection-index.yml`. The site makes no claim of vetting or
endorsement. It says to report a problematic Feature "through the
registry hosting the Feature". Treat the index as a search engine, not
an app store.

## Trust tiers

Prefer the highest tier that has what you need:

1. **Reference collection: `ghcr.io/devcontainers/features/*`.** It's
   maintained by the Dev Container spec maintainers, published from CI
   with `devcontainers/action`, and tested against several base images.
   Its install scripts verify what they download where upstream allows
   it (for example, `github-cli` checks the upstream GPG key). This is
   the default choice.
2. **Vendor-published.** The project that owns the tool publishes the
   Feature from its own org, e.g. `ghcr.io/azure/azure-dev/*`,
   `ghcr.io/dapr/cli/*`, `ghcr.io/rocker-org/devcontainer-features/*`
   (R). Trusting it is about the same as trusting the tool.
3. **Community collections.** Examples:
   - `ghcr.io/devcontainers-extra/features/*`: hundreds of small
     Features. It's a fork that continues the abandoned
     `devcontainers-contrib`, so references to
     `ghcr.io/devcontainers-contrib/...` are stale and should be moved.
   - `ghcr.io/devcontainers-community/features/*`.

   These are convenient, but each Feature is only as good as its
   individual maintainer. Many just wrap a generic installer (pipx, npm,
   a GitHub release download).
4. **Individual namespaces (`ghcr.io/<someone>/...`).** Vet each one
   before use, or vendor it (see below).

## Vetting a Feature before adding it

- **Read `install.sh`** in the source repo, at the tag you'll pin.
  Red flags:
  - `curl … | sh` from a moving URL.
  - No checksum or signature check on downloaded binaries.
  - Added apt sources without a pinned keyring.
  - Disabled TLS verification (`-k`, `--insecure`).
- **Read its runtime metadata**, which you inherit silently:

  ```sh
  devcontainer features info manifest ghcr.io/owner/repo/feature:1
  ```

  The `dev.containers.metadata` annotation is the full
  `devcontainer-feature.json`. Check for:
  - `privileged: true`
  - `capAdd`, e.g. `SYS_PTRACE` from the official `go` and `rust`
    Features
  - `securityOpt` such as `seccomp=unconfined`, also from the official
    `go` and `rust` Features
  - a host bind mount, especially `/var/run/docker.sock`
  - an `entrypoint`
  - `containerEnv`, which can override `PATH`
  - `dependsOn` pulling in further Features
- **Check that the source matches the artifact.** The OCI namespace
  should belong to the repo's owner, and publishing should happen from
  CI. A repo that publishes by hand from a laptop is lower assurance.
- **Check maintenance.** Look at recent releases, open issues about
  broken installs, and whether the Feature is marked `deprecated`.
- **Ask whether you need it at all.** If the base image already ships
  the tool (`mcr.microsoft.com/devcontainers/*` images include
  `common-utils` and git), the Feature is redundant. For a single
  static binary, three lines in a Dockerfile you own may be easier to
  audit than a third-party Feature.

## Pinning and updates

```jsonc
"features": {
  // major tag: picks up fixes, never breaking changes. The usual choice.
  "ghcr.io/devcontainers/features/node:1": { "version": "22" },
  // exact version
  "ghcr.io/devcontainers/features/github-cli:1.1.3": {},
  // digest: immutable, for low-trust sources
  "ghcr.io/someone/features/tool@sha256:<digest>": {}
}
```

- **Never leave a Feature unpinned.** No tag means `:latest`, which
  includes the next major version.
- The Feature tag and the Feature's own `version` *option* are
  different things. `node:1` pins the installer script. `"version":
  "22"` pins the Node.js it installs. Pin both for reproducibility.
  Many options default to `"latest"`.
- **Commit `devcontainer-lock.json`.** It records the resolved digest
  and `integrity` hash for every Feature, so a re-pushed tag can be
  detected (see [distribution.md](distribution.md#lockfile-devcontainer-lockjson)).
  Use these CLI commands:
  - `devcontainer upgrade --workspace-folder .` writes or refreshes
    the lockfile. Add `--dry-run` to print it instead.
  - `devcontainer outdated --workspace-folder .` shows current and
    available versions.
- **Automate the bumps.** Dependabot's `devcontainers` ecosystem
  updates Feature tags in `devcontainer.json` and the lockfile in one
  PR, for public Features. See the `dependabot` skill.

  ```yaml
  - package-ecosystem: "devcontainers"
    directory: "/"
    schedule:
      interval: "weekly"
  ```

- **Vendor what you can't trust upstream.** Copy the Feature folder
  into `.devcontainer/<feature>/` and reference it as `"./<feature>"`
  (a local Feature). Or republish it to a registry you control. You
  then own updates, but nothing changes underneath you.
- Registry credentials: the CLI's `--oci-auth-hardening` flag restricts
  bearer-auth realms and stops it forwarding credentials to other
  hosts. Use it in CI that pulls from private registries.

## The reference collection at a glance

`ghcr.io/devcontainers/features/<id>:<major>`. Majors were current as of
2026-10; check with `devcontainer features info tags <ref>`.

| Feature | Major | Notes |
| --- | --- | --- |
| `common-utils` | 2 | Creates the non-root user, sudo, zsh/Oh My Zsh. Defaults include `upgradePackages: true`, which makes builds non-reproducible, so turn it off for pinned images. Already in `devcontainers/base` images. |
| `git`, `git-lfs` | 1 | `git` may build from source and is slow. Skip it if the image's git is fine. |
| `github-cli` | 1 | GPG-verified install. |
| `copilot-cli` | 1 | |
| `node` | 2 | nvm, plus yarn and pnpm (via options). |
| `python` | 1 | pipx and linters (`installTools`). Can build from source, which is slow. |
| `go`, `rust` | 1 | Add `SYS_PTRACE` + `seccomp=unconfined` for debuggers. |
| `java` | 1 | Via SDKMAN!. |
| `dotnet` | 2 | |
| `ruby` | 2 | ruby-build, plus optional rbenv or rvm. |
| `php`, `hugo`, `powershell`, `conda`, `anaconda` | 1–2 | |
| `aws-cli`, `azure-cli`, `terraform` | 1 | `terraform` can also add TFLint and Terragrunt. |
| `kubectl-helm-minikube` | 1 | Mounts a `minikube-config` volume. |
| `docker-in-docker` | 4 | **`privileged: true`**. Runs its own dockerd, with volumes per `${devcontainerId}`. Isolated from the host, but privileged. |
| `docker-outside-of-docker` | 1 | Bind-mounts the **host** Docker socket, which is effectively root on the host. Unprivileged, but not isolated. |
| `sshd`, `desktop-lite` | 1 | Add an `entrypoint` and listening services. |
| `nix` | 1 | Adds an `entrypoint`. |
| `nvidia-cuda` | 3 | Needs a GPU host (`hostRequirements.gpu`). |
| `oryx` | 2 | Build tool from the Codespaces universal image. |

**Docker inside the dev container:** choose `docker-in-docker` when the
container must not touch the host daemon, e.g. in Codespaces or shared
hosts. Choose `docker-outside-of-docker` for speed and shared image
cache on a machine you own. Never use either for untrusted code: one is
privileged, and the other hands over the host.

## What NOT to do

- Don't add a Feature because it showed up in the VS Code picker. The
  index lists anything that was registered.
- Don't reference Features without a tag, and don't skip committing
  `devcontainer-lock.json`.
- Don't stack Features that install the same tool (the `node` Feature
  on a `typescript-node` image, two Python Features). Install order
  decides which one wins, often silently.
- Don't use `docker-outside-of-docker` or `docker-in-docker` in a
  container that runs untrusted PR code.
- Don't keep `ghcr.io/devcontainers-contrib/*` references. That
  project is unmaintained; move to its `devcontainers-extra`
  continuation, or replace it.
