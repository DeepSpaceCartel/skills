# Supported ecosystems

Source: [Supported ecosystems and repositories](https://docs.github.com/en/code-security/dependabot/ecosystems-supported-by-dependabot/supported-ecosystems-and-repositories).
This list changes often, so check the live page before telling someone
an ecosystem isn't supported.

VU = version updates, SU = security updates, Reg = private registries,
Vend = vendoring.

| Package manager | `package-ecosystem` | VU | SU | Reg | Vend |
| --- | --- | --- | --- | --- | --- |
| Bazel | `bazel` | ✓ | ✗ | ✗ | ✗ |
| Bun | `bun` | ✓ | ✗ | ✓ | ✗ |
| Bundler | `bundler` | ✓ | ✓ | ✓ | ✓ |
| Cargo | `cargo` | ✓ | ✓ | ✓ | ✗ |
| Composer | `composer` | ✓ | ✓ | ✓ | ✗ |
| Conda | `conda` | ✓ | ✓ | ✗ | ✗ |
| Deno | `deno` | ✓ | ✓ | ✗ | ✗ |
| Dev containers | `devcontainers` | ✓ | ✗ | ✗ | ✗ |
| Docker | `docker` | ✓ | ✗ | ✓ | — |
| Docker Compose | `docker-compose` | ✓ | ✗ | ✓ | — |
| .NET SDK | `dotnet-sdk` | ✓ | ✗ | — | — |
| Elm | `elm` | ✓ | ✗ | ✓ | ✗ |
| Git submodules | `gitsubmodule` | ✓ | ✗ | ✓ | — |
| GitHub Actions | `github-actions` | ✓ | ✓ | ✓ | — |
| Go modules | `gomod` | ✓ | ✓ | ✗ | ✓ |
| Gradle | `gradle` | ✓ | ✓ | ✓ | ✗ |
| Helm | `helm` | ✓ | ✗ | ✓ | — |
| Hex (Elixir) | `mix` | ✓ | ✗ | ✓ | ✗ |
| Julia | `julia` | ✓ | ✗ | ✗ | ✗ |
| Maven | `maven` | ✓ | ✓ | ✓ | ✗ |
| Nix flakes | `nix` | ✓ | ✗ | — | — |
| npm / pnpm / Yarn | `npm` | ✓ | ✓ | ✓ | Yarn v2+ only |
| NuGet | `nuget` | ✓ | ✓ | ✓ | ✗ |
| OpenTofu | `opentofu` | ✓ | ✗ | — | — |
| pip / pipenv / pip-compile / Poetry | `pip` | ✓ | ✓ | ✓ | ✗ |
| pre-commit | `pre-commit` | ✓ | ✗ | ✓ | ✗ |
| pub (Dart/Flutter) | `pub` | ✓ | ✓ | ✓ | — |
| Rust toolchain | `rust-toolchain` | ✓ | ✗ | ✓ | — |
| sbt | `sbt` | ✓ | — | — | — |
| Swift | `swift` | ✓ | ✓ | git only | ✗ |
| Terraform | `terraform` | ✓ | ✗ | ✓ | — |
| uv | `uv` | ✓ | ✓ | ✓ | — |
| vcpkg | `vcpkg` | ✓ | ✗ | ✓ | — |

✗ in SU means you still get **alerts**, but no automatic fix PR. A
scheduled version update is the only way that ecosystem gets bumped.

## Caveats worth knowing

- **One YAML value, many tools.** `npm` covers npm, pnpm and Yarn, and
  `pip` covers pip, pipenv, pip-compile and Poetry. Dependabot detects
  the tool from the lockfile, so keep the lockfile committed.
- **`uv` is separate from `pip`.** A uv project (`uv.lock`) uses
  `package-ecosystem: "uv"`.
- **GitHub Actions** updates `uses: owner/repo@ref` references in
  `.github/workflows/` and in composite actions. It doesn't support
  `docker://` references. If a SHA pin has a version comment, the
  comment is updated together with the SHA. Security updates bump a
  vulnerable action to the minimum patched version.
- **Docker** treats tags as semver and only proposes tags with the
  same pre-release suffix (`-alpine` stays `-alpine`). Digest pins
  written as `image:tag@sha256:…` are updated as a pair.
- **Dev containers** update Features in `devcontainer.json` to the
  latest major version.
- **Terraform** updates modules from the public Registry or public
  Git, plus providers. A private registry needs a `terraform-registry`
  or `git` registry entry.
- **vcpkg** updates the `builtin-baseline` commit in `vcpkg.json`.
- **Rust toolchain** updates `rust-toolchain.toml` channels: versioned
  (`1.xx`) and dated (`nightly-YYYY-MM-DD`).
- **Indirect dependencies.** For npm, a security fix may bump a parent
  dependency or drop an unneeded sub-dependency. For other ecosystems,
  Dependabot can't fix a transitive vulnerability that needs a parent
  bump.
- **Resolution needs reachability.** Some ecosystems resolve the whole
  dependency tree to verify an update. A private dependency the
  updater can't reach makes the job fail; see
  [`private-registries.md`](private-registries.md).
- **Turn off overlapping tools.** Before enabling Dependabot for an
  ecosystem, disable any other integration that already updates it.
