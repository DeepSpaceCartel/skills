# Dockerfile essentials

Instruction reference: <https://docs.docker.com/reference/dockerfile/>.

## The instructions that shape an image

| Instruction | Notes |
| --- | --- |
| `FROM` | Base; one per stage. Pin tag, optionally digest. |
| `WORKDIR` | Sets cwd for later instructions; creates it. Prefer over `cd`. |
| `COPY` | Copy from build context or `--from=<stage>`. Prefer over `ADD`. |
| `ADD` | Like `COPY` plus URL/tar handling — avoid unless you need it. |
| `RUN` | Execute at build time; each is a layer. |
| `ENV` | Runtime environment variable; persisted in image config. |
| `ARG` | Build-time variable; not available at runtime. |
| `USER` | Switch user for subsequent instructions and the runtime. |
| `EXPOSE` | Documents the port (doesn't publish it). |
| `ENTRYPOINT` / `CMD` | The runtime command (see below). |
| `HEALTHCHECK` | Docker-level health check (K8s overrides it). |
| `LABEL` | OCI metadata. |
| `VOLUME` | Declares a mount point. |
| `ONBUILD` | Trigger in a child image — legacy, avoid. |

## `COPY` vs `ADD`

Use `COPY` for everything. `ADD`'s extra behaviors (fetch a URL,
auto-extract a local tarball) are surprising and non-obvious; if you need
to fetch, do it explicitly with `RUN curl` (or better, a build stage).

## `RUN` and layer hygiene

Combine related commands into one layer and clean up in the same layer:

```dockerfile
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*
```

- `rm -rf` in a *later* `RUN` does not shrink the image — the earlier
  layer is immutable. Clean up in the same `RUN`.
- `--no-install-recommends` avoids pulling unnecessary packages.
- Prefer a package/manifest install (`npm ci`, `go mod download`,
  `pip install -r requirements.txt`) over `install everything`.

## `ENTRYPOINT` vs `CMD`, exec vs shell

```dockerfile
# exec form (recommended)
ENTRYPOINT ["node", "dist/index.js"]
CMD ["--port", "8080"]        # default args, overridable at `docker run`
```

| Form | Result |
| --- | --- |
| `ENTRYPOINT ["a","b"]` | `a b <cmd args>`; args appended |
| `ENTRYPOINT a b` | runs via `/bin/sh -c "a b"` — no signal forwarding |
| `CMD ["x"]` alone | default command, replaced by `docker run` args |
| `ENTRYPOINT [...]` + `CMD [...]` | ENTRYPOINT is fixed, CMD is defaults |

**Why exec form matters:** with shell form, PID 1 is `/bin/sh`, which
doesn't forward `SIGTERM` to your process, so `docker stop` / Kubernetes
termination waits for the grace period and then `SIGKILL`s you —
breaking graceful shutdown and draining.

If you need shell features (variable expansion) with signal handling, use
exec form pointing at a shell script that `exec`s the real process:

```dockerfile
ENTRYPOINT ["/entrypoint.sh"]
# entrypoint.sh: exec "$@"
```

## Signals and PID 1

- The process at PID 1 receives signals. Your app must handle `SIGTERM`
  and exit gracefully; if it spawns children, it must reap them (or use
  `tini`/`--init`).
- `docker run --init` injects a tiny init; in Kubernetes, `shareProcessNamespace`
  or an init binary in the image are the equivalents.
- Node/Java/Python all need explicit `SIGTERM` handling (Node does not
  exit on `SIGTERM` by default in older versions).

## `HEALTHCHECK`

- `HEALTHCHECK` is a Docker/Compose concept; Kubernetes ignores it and
  uses its own probes. If you deploy to K8s, configure probes there.
- Keep health endpoints cheap and dependency-free (don't have liveness
  call the database).

## Environment and build args

- `ENV` persists and is visible via `docker inspect` — never put
  secrets there.
- `ARG` is build-time only and **also persisted in the image history**
  for the layer that uses it (and the image config in some cases). Not a
  secret store — see
  [`buildkit-builds-and-secrets.md`](buildkit-builds-and-secrets.md).
- Set `ENV LANG`, `ENV PATH`, etc. deliberately; don't inherit surprises.

## `WORKDIR` and ownership

- Set `WORKDIR` once; it persists and creates the directory.
- When running as a non-root user, ensure the app's working directory is
  writable by that user (copy with `--chown`, or create and chown the
  dir explicitly).
