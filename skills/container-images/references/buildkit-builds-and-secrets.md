# BuildKit builds and build secrets

BuildKit is the modern build engine behind `docker build` (and the
`docker buildx` CLI). It enables cache mounts, secret mounts, multi-arch
builds, and richer attestations. Docs:
<https://docs.docker.com/build/buildkit/>.

## Enabling it

- Recent Docker Desktop / Engine use BuildKit by default.
- In a Dockerfile, opt into the newest frontend for the mount features:

  ```dockerfile
  # syntax=docker/dockerfile:1
  ```

- With `buildx`, create a builder: `docker buildx create --name b --use`,
  then `docker buildx build ...`.

## Build secrets (the important part)

Secrets must never end up in a layer, image config, or `docker history`.
`ARG`/`ENV`/`COPY` all leak somewhere; BuildKit secret mounts do not.

```dockerfile
# syntax=docker/dockerfile:1
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc \
    npm ci
```

```bash
docker build --secret id=npmrc,src=$HOME/.npmrc -t myapp .
```

- The secret is mounted only for that `RUN`, only in the build sandbox;
  it isn't part of any layer or the image config.
- `id` matches the `--secret` flag; `target` is the path inside the
  container; `mode` controls permissions.
- For an env-var-shaped secret, use
  `--mount=type=secret,id=token,env=TOKEN` (available to the command as
  `$TOKEN` without writing a file).
- In CI, pass the secret from the runner's environment/secret store —
  never bake it into the Dockerfile or a committed file.

Same mechanism for SSH:

```dockerfile
RUN --mount=type=ssh git clone git@github.com:org/private.git
```

```bash
docker build --ssh default .
```

(Requires an ssh-agent; the key isn't copied into the image.)

### Secret anti-patterns

| Pattern | Why it leaks |
| --- | --- |
| `ARG TOKEN` + `RUN ... $TOKEN` | value recorded in image history / build metadata |
| `ENV TOKEN` | value persists in the image config |
| `COPY .npmrc` | file is a layer; `rm` later doesn't remove it |
| `curl -H "Authorization: $TOKEN"` | token may appear in logs/cache metadata |

If a secret ever touched a layer, **rotate it** — deleting the layer in a
later commit doesn't remove the old layer from a pushed image.

## Cache mounts

```dockerfile
RUN --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=cache,target=/go/pkg/mod \
    go build -o /out/app .
```

Cache mounts persist across builds and are excluded from the image.
Right for module/build caches. Not a place for secrets.

## Multi-arch builds

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --push -t registry.example.com/app:1.2.3 .
```

- BuildKit can build multiple architectures in one invocation and push a
  multi-arch manifest list.
- Use `--platform=$BUILDPLATFORM` / `$TARGETPLATFORM` (and
  `$TARGETARCH`) in `FROM`/`RUN` for cross-compilation-aware stages.
- You generally need `--push` (or `--load` for single-platform) because
  a multi-arch result can't be a local image.

## Remote builders

`docker buildx create --driver remote` points the build at a remote
BuildKit daemon (useful to offload CI builds or build `linux/amd64`
from an arm laptop).

Two independent concerns that are easy to conflate:

- **Builder state** lives on the daemon (cache, `--local` state).
- **Registry auth** is configured per builder via `DOCKER_CONFIG`; the
  client's credentials are not automatically shared with the daemon.
  Set up the daemon's config or use `--driver-opt` accordingly.

Other gotchas: insecure/HTTP registries are enabled **server-side**
(the daemon's `buildkitd.toml`), not with a client flag; and anonymous
Docker Hub pulls are rate-limited, so authenticate for CI.

## Attestations

```bash
docker buildx build --sbom=true --provenance=true --push ...
```

- `--provenance` records how/when/where the image was built.
- `--sbom` attaches a software bill of materials.
- Stored as attestations in the manifest list; consumers (and admission
  policies) can verify them.

## Verification

`docker buildx build --progress=plain` shows the full build log, which
is the fastest way to see whether a mount actually applied and where a
cache miss occurred.
