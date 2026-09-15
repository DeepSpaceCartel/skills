# Multi-stage builds and caching

## Why multi-stage

One Dockerfile, several `FROM` stages. Only the final stage's filesystem
ships. This keeps compilers, package managers, test tooling, and source
out of the runtime image.

```dockerfile
# 1. dependencies
FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# 2. build
FROM deps AS build
COPY . .
RUN npm run build && npm test

# 3. runtime
FROM node:22-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/dist ./dist
COPY --from=deps /app/node_modules ./node_modules
USER node
ENTRYPOINT ["node", "dist/index.js"]
```

Benefits: smaller images, smaller attack surface, and a cache-friendly
structure (dependency install happens in its own stage).

## Layer-cache ordering

Docker caches a layer if the instruction text and its inputs are
unchanged. A changed layer invalidates every later layer. Order from
stable → volatile:

1. Base image
2. System dependencies / package manifests
3. Dependency install
4. Source code
5. Build

Copying source *before* installing dependencies means every source edit
re-runs the dependency install. Copy manifests first.

## Cache mounts (BuildKit)

For package managers, a cache mount persists the package cache across
builds without baking it into a layer:

```dockerfile
# syntax=docker/dockerfile:1
RUN --mount=type=cache,target=/root/.npm npm ci
```

```dockerfile
# Go
RUN --mount=type=cache,target=/go/pkg/mod go mod download
RUN --mount=type=cache,target=/root/.cache/go-build go build -o /out/app .
```

Cache-mount contents are not part of the image — they're scratch space
that speeds rebuilds. Great for module/build caches; never for secrets
(use `type=secret`, see the secrets reference).

## `--from` and bind mounts

```dockerfile
COPY --from=build /app/dist ./dist
RUN --mount=type=bind,source=.,target=/src,ro ...
```

- `COPY --from=<stage>` pulls artifacts across stages.
- `COPY --from=<image>` can pull from an arbitrary image (e.g. copy a
  binary from a tools image into a minimal runtime).
- `--mount=type=bind` gives a temporary read-only view during a `RUN`,
  without creating a layer.

## Reproducible builds

- Pin base image digests and dependency lockfiles (`package-lock.json`,
  `go.sum`, `poetry.lock`).
- Use `npm ci` (respects the lockfile exactly) over `npm install`.
- Pass the git revision as a build arg and stamp it into a label so the
  image is traceable.
- Deterministic builds make "is production running what I tested?" a
  digest comparison instead of a guess.

## Speeding up CI builds

- Use a persistent BuildKit cache: a registry cache
  (`--cache-to type=registry`, `--cache-from type=registry`) or a shared
  builder with a cache directory.
- Build only the target stage you need (`--target test` in CI, then
  `--target runtime` for the artifact).
- Reuse a remote/builder instance across runs so the cache survives
  ephemeral CI runners — otherwise every run is a cold build.
- A remote BuildKit daemon lets CI push build work off the runner; note
  that registry auth and builder state are separate concerns (see the
  BuildKit reference).

## When the cache is wrong

- If a base image is re-tagged, the cache may be stale — `--pull` forces
  a fresh base.
- `--no-cache` rebuilds everything; usually a symptom that the
  Dockerfile lacks a stable cache key, not a fix.
- Secrets in the build with a cached layer can be a cache-poisoning
  issue; BuildKit secret mounts aren't cached, which is another reason
  to use them over `ARG`.
