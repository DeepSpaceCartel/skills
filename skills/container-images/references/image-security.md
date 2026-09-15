# Image security

## Base image choice

Ranked roughly from most to least minimal (pick the smallest that runs
your app):

| Base | Contents | Use when |
| --- | --- | --- |
| `scratch` | nothing | static binary (Go/Rust with no libc deps) |
| `distroless/*` | runtime libs + CA certs, no shell | most compiled apps |
| `alpine` | musl + busybox, tiny | small images, need a shell |
| `*-slim` (Debian) | glibc, apt | glibc-dependent runtimes |
| full distro | everything | last resort |

- **No shell/package manager in the runtime image** removes a whole
  class of post-exploitation tooling. Distroless/scratch are ideal.
- Rebuild regularly on top of updated bases; a digest pin without a
  bump process ages into known CVEs.

## Pin base images by digest

```dockerfile
FROM node:22-bookworm-slim@sha256:6f2e...
```

- A tag is mutable; a digest is immutable. Pinning the digest makes the
  build reproducible and defeats tag-repointing supply-chain attacks.
- Automate the bump (Dependabot `docker` ecosystem, Renovate) so you
  actually get security updates.
- Keep the human-readable tag next to the digest in a comment.

## Run as non-root

- Create or use an existing non-root user and `USER` it before the
  runtime command.
- In Kubernetes, reinforce with a `securityContext`
  (`runAsNonRoot: true`, `runAsUser`, `allowPrivilegeEscalation: false`,
  `readOnlyRootFilesystem: true`, dropped capabilities).
- Distroless images have a built-in `nonroot` user (`USER nonroot`).
- Set a high numeric UID if the platform uses `runAsNonRoot` — it can't
  resolve a bare username to verify non-root.

## Least privilege at runtime

- Don't mount the Docker socket into a container unless it's genuinely a
  builder; the socket is root-equivalent on the host.
- Drop Linux capabilities (`--cap-drop ALL`, add back only what's
  needed).
- Mark the filesystem read-only and mount writable scratch paths
  explicitly (`emptyDir`) — makes persistence harder for an attacker.
- Avoid `--privileged`. If a workload genuinely needs it (BuildKit's
  default mode, for example), isolate it in a dedicated namespace with a
  deliberate PodSecurity label, not next to normal workloads.

## Scanning and SBOM

- Scan images in CI (`trivy`, `grype`, `docker scout`) and fail on high/
  critical fixable CVEs.
- Generate an SBOM (`syft`, or BuildKit `--sbom`) and attach it as an
  attestation so consumers can verify contents.
- Sign images (cosign) and verify signatures at admission if your
  platform supports it.
- Scan the **final** image, not just the base — your own dependencies
  are the usual source of findings.

## Build-time supply chain

- Pin action/tool versions in CI (see
  [`../../github-actions/SKILL.md`](../../github-actions/SKILL.md)) —
  a compromised build action can tamper with the image.
- Fetch dependencies over TLS from a pinned registry with lockfile
  integrity (`npm ci`, `go mod verify`, `pip --require-hashes`).
- Never run `curl | sh` from an unpinned URL in a build; download,
  verify a checksum/signature, then execute.

## Multitenancy / registry auth

- Treat registry credentials as secrets; use short-lived tokens and
  `--secret`/`secretKeyRef`, never `ARG` or a committed `.docker/config.json`.
- A push token should have push-only scope for the target repo, not
  admin.
- Pull-through caches can reduce external dependency and centralize
  scanning, at the cost of one more credential to manage.

## Runtime image hygiene

- Remove build artifacts, test files, docs, and package caches from the
  runtime image.
- Don't include a package manager (`apt`, `apk`, `npm`) you don't need
  at runtime.
- Set `ENV NODE_ENV=production` (or equivalent) so frameworks skip dev
  behavior.
- Keep `.git` out — secrets can live in history (`.dockerignore`).
