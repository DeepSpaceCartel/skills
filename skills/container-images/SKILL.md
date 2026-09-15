---
name: container-images
description: How to write and review Dockerfiles and container image builds (https://docs.docker.com/build/building/best-practices/, OCI image spec at https://github.com/opencontainers/image-spec) - project-agnostic. Covers Dockerfile instructions and ordering, multi-stage builds, build-cache and layer layout, .dockerignore, minimal base images (distroless/alpine/scratch) and digest pinning, running as non-root, exec-form ENTRYPOINT/CMD and signal handling, OCI labels, build secrets via BuildKit (--secret, never ARG/ENV/COPY), multi-arch builds, image tagging, and SBOM/provenance. Use when writing or reviewing a Dockerfile, shrinking an image, debugging build caching, choosing a base image, or handling credentials during a build.
---

# Container images

A Dockerfile is a program that produces the artifact you ship. Optimize
for three things in order: **correct and reproducible**, **secure**,
then **small**. Reference:
<https://docs.docker.com/build/building/best-practices/>.

## Dockerfile essentials

```dockerfile
# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules
USER node
EXPOSE 8080
ENTRYPOINT ["node", "dist/index.js"]
```

- **Order instructions from least- to most-frequently changing.** Copy
  manifests and install dependencies *before* copying source, so a code
  change doesn't invalidate the dependency layer.
- **One logical thing per layer**, combined with `&&` where they're a
  single unit (e.g. apt install + cleanup) to avoid leftover cache.
- Use the **exec form** (`["node", "dist/index.js"]`) for
  `ENTRYPOINT`/`CMD`, not the shell form — the shell form wraps your
  process in `/bin/sh -c`, which won't receive `SIGTERM` and breaks
  graceful shutdown.
- End with a **single** `ENTRYPOINT` (the executable) and let `CMD`
  supply default args.

## Base images

- **Pin the version tag**, never `:latest`. For reproducibility, pin the
  **digest** too: `FROM node:22-bookworm-slim@sha256:...`.
- Prefer **minimal** bases: `-slim`/`-alpine` over full Debian,
  `distroless` or `scratch` when you can. Fewer packages = fewer CVEs
  and a smaller artifact.
- Alpine uses musl libc; a native dependency built for glibc won't work.
  Match the base to your runtime's needs.
- Rebuild regularly and let a scanner/Dependabot bump the pinned base —
  a digest pin without a bump process goes stale and vulnerable.

## Multi-stage builds

Use stages to keep build toolchains out of the runtime image:

```dockerfile
FROM golang:1.25 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /out/app .

FROM gcr.io/distroless/static-debian12
COPY --from=build /out/app /app
ENTRYPOINT ["/app"]
```

- Name stages and `COPY --from=<stage>` only the artifacts you need.
- The final stage is the only one that ships; intermediate layers are
  discarded.
- Never copy a build stage's shell/package manager into the runtime
  stage unless you need it.

## `.dockerignore`

Always ship one. It shrinks the build context (faster, less network) and
prevents leaking local files into the image:

```
.git
node_modules
dist
*.log
.env
.env.*
Dockerfile
.dockerignore
```

A missing `.dockerignore` can accidentally `COPY . .` your `.env`,
`node_modules`, or `.git` into the image.

## Run as non-root

```dockerfile
RUN groupadd -r app && useradd -r -g app app
USER app
```

- Create/switch to a non-root user in the final stage. Many official
  images already provide one (`USER node`, `USER nobody`).
- Set a numeric UID (or ensure the platform's `runAsNonRoot` can verify
  it) — Kubernetes can't always tell a named user is non-root.
- Don't `chown` huge trees; copy with `--chown=user:group` instead.

## Secrets in builds

Never bake credentials into an image:

```dockerfile
# BAD: the secret is a layer, visible in image history forever
ARG NPM_TOKEN
RUN echo "//registry.npmjs.org/:_authToken=$NPM_TOKEN" > ~/.npmrc && npm ci
```

Use BuildKit build secrets (mounted, never in a layer):

```dockerfile
# syntax=docker/dockerfile:1
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc npm ci
```

```bash
docker build --secret id=npmrc,src=$HOME/.npmrc .
```

- `ARG`/`ENV`/`COPY` all persist the value somewhere recoverable
  (`docker history`, image config, or a layer). BuildKit
  `--mount=type=secret` does not.
- Same for SSH agent forwarding (`--mount=type=ssh`) for private git
  over SSH.
- A secret that ever touched a layer must be rotated, not just removed
  in a later commit.

## Labels and provenance

Add OCI annotations via `LABEL`:

```dockerfile
LABEL org.opencontainers.image.title="myapp" \
      org.opencontainers.image.version="1.2.3" \
      org.opencontainers.image.source="https://github.com/org/repo" \
      org.opencontainers.image.revision="<git-sha>" \
      org.opencontainers.image.base.digest="sha256:..."
```

- `source` links the image to its repo (used by registries to show the
  README and by scanners for provenance).
- `revision` ties the image to the exact commit that built it.
- Consider `--sbom` and `--provenance` (BuildKit) to attach an SBOM and
  provenance attestation — supply-chain hygiene.

## Tags and publishing

- Tag immutably: a version tag (`1.2.3`) and a digest. Avoid relying on
  `latest` in any deployment.
- Prefer one image promoting through environments over rebuilding per
  environment — the same digest in staging and production is what makes
  promotion meaningful.
- Include the git SHA in a tag/label so you can map an image back to
  source.

## Where to look

| File | Covers |
| --- | --- |
| [`references/dockerfile-essentials.md`](references/dockerfile-essentials.md) | instructions, ordering, ENTRYPOINT/CMD, signals, healthcheck |
| [`references/multi-stage-and-caching.md`](references/multi-stage-and-caching.md) | stages, cache mounts, BuildKit cache, layer strategy |
| [`references/image-security.md`](references/image-security.md) | bases, non-root, scanning, digests, supply chain |
| [`references/buildkit-builds-and-secrets.md`](references/buildkit-builds-and-secrets.md) | BuildKit, build secrets, multi-arch, remote builders |

## What NOT to do

- Don't use `:latest` (or no tag) as a base or in a deployment — it's
  not reproducible and changes under you.
- Don't put secrets in `ARG`/`ENV`/`COPY`; use BuildKit secrets.
- Don't `apt-get upgrade` a base image to "fix" CVEs — rebuild on a
  newer, patched base instead, so the fix is reproducible.
- Don't run the app as root, and don't `chmod 777` to work around
  permissions.
- Don't ship a build toolchain in the runtime image; multi-stage it out.
- Don't shell-form your `ENTRYPOINT` if you want signals handled.
