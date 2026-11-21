# Remote cache and remote execution

Sharing action results between machines (remote cache) and running actions on a worker pool
(remote execution) over the Remote Execution API (REAPI): its action cache, content-addressable
store, platforms and executors; self-hosted and managed services; who may write; cache
poisoning; debugging misses; network and cost. Anchor sources: Bazel's
[remote caching](https://bazel.build/remote/caching),
[debugging remote cache hits](https://bazel.build/remote/cache-remote),
[remote execution](https://bazel.build/remote/rbe) and
[services](https://bazel.build/community/remote-execution-services) pages, the
[remote-apis README](https://github.com/bazelbuild/remote-apis) and
[`remote_execution.proto`](https://github.com/bazelbuild/remote-apis/blob/main/build/bazel/remote/execution/v2/remote_execution.proto)
(Apache-2.0), and Buck2's [remote execution](https://buck2.build/docs/users/remote_execution/) page.

## What agents typically get wrong

- **Turning on a shared cache before the build is hermetic.** Users with different compilers
  in `/usr/bin` can share wrong hits, because Bazel does not track tools outside the workspace.
- **Giving every developer write access.** Anyone who can write to the action cache can make an
  action hash map to any output. Bazel's docs suggest CI writes and developers read.
- **Plain HTTP with credentials in the URL.** Basic auth sends the password in clear text;
  use HTTPS (or gRPCs) only. The cache holds your binaries: treat it as sensitive.
- **Judging hit rate from build output alone.** Count from Bazel's `INFO: N processes: ...`
  line after a `bazel clean`, since local hits are not in that count.
- **Editing sources during a build that uploads.** Bazel can upload results computed from a
  half-edited input; `--experimental_guard_against_concurrent_changes` detects it.
- **Expecting remote execution to work with host-dependent rules.** Every tool must reach the
  worker as a declared input or be in the worker image, called through a toolchain.
- **Ignoring network.** A cache across a slow or metered link can cost more time and money than
  it saves (worked example below).
- **Assuming a cache never needs cleaning.** Storage grows; a poisoned entry needs a way out.

## Procedure

**Adding a remote cache**

1. Prove hermeticity first ([hermeticity-and-reproducibility](hermeticity-and-reproducibility.md)).
2. Start with a local disk cache (`--disk_cache`); it costs nothing and shows hit rates.
3. Run a cache service near the builders: in the same cluster or network as CI.
4. CI writes; everyone else reads (`--remote_upload_local_results=false` by default, switched
   on in a CI-only config).
5. Authenticate every client, encrypt in transit, and restrict who can delete.
6. Set retention: size or age limits on the store (bazel-remote and Bazel's disk cache both
   have garbage collection; object stores have lifecycle rules).
7. Measure hits on CI and on a developer machine; debug misses (below).
8. Write down how to disown poisoned results (a new namespace or salt) before you need it.

**Debugging misses** (Bazel)

1. Build once to fill the cache; `bazel clean`; build again on the same machine. Read the
   `remote cache hit` count in the `INFO` line.
2. Still missing: capture `--execution_log_compact_file` from two clean runs and compare. The
   docs build a parser from the Bazel repo (`//src/tools/execlog:parser`) to sort and diff them.
3. Look for actions without `cacheable` (a `no-cache` tag), and for `--noremote_accept_cached`
   set in some bazelrc (check `remote_accept_cached` in a `--build_event_text_file` dump).
4. Across machines: make a small change so old entries can't hide the issue, then compare logs
   from each machine. Differences point to configuration or leaked host environment.

**Moving to remote execution**

1. The cache works and hits are high on CI.
2. Define the execution platform: OS, CPU, a pinned worker image, as platform properties.
3. Move host-probing and host tools into toolchains or the image (Bazel's remote-rules guide).
4. Run one target family remotely, compare results and time, then widen.

## Techniques

**REAPI in one table**

| Concept | What it is |
|---|---|
| Action | What to run: digests of the Command and of the input root, a timeout, platform, optional `do_not_cache` and `salt`. Identified by its own digest |
| Command | Arguments, environment (sorted by name), relative output paths, working directory |
| Digest | Hash plus size; the size is part of the identity |
| CAS | Blobs (inputs, outputs, Commands, Actions) stored by digest |
| Action cache (AC) | Action digest to ActionResult (outputs, exit code, stdout/stderr) |
| Execution service | Runs an Action on a worker whose properties satisfy the Platform |
| Capabilities | Lets a client ask what the server supports |
| Remote Asset, Logstream | URI-to-digest mapping (fetching sources); streaming an action's output |

Consequences worth knowing: the timeout is in the action digest, so a short-timeout action is
not satisfied by a long-timeout result. Platform properties are in the digest too, so even a
change of letter case makes a new cache entry. A result whose execution status is not `OK`
must not be cached. The proto asks that actions be reproducible so that a cached result is
always correct. `salt` gives an action a separate cache namespace, which is how results from a
buggy tool are disowned.

**Clients and servers** (from the remote-apis README and Bazel's services page; no
recommendation implied; check each project's licence and status):

| Need | Options named in the sources |
|---|---|
| Cache only, self-hosted | bazel-remote (disk-backed, garbage collection, REST and gRPC); nginx WebDAV; an HTTP/1.1 server that supports PUT and GET; object storage (Bazel documents Google Cloud Storage; S3 is reported) |
| Cache and execution, self-hosted | Buildbarn, Buildfarm, BuildGrid, NativeLink |
| Commercial (Bazel's services page) | Aspect Build (self-hosted services), BuildBuddy, EngFlow (hosted or self-hosted), NativeLink, Bitrise (caching), Hermetiq |
| Other servers in the README | Flare Build Execution, Justbuild, Kajiya, Namespace |
| Clients | Bazel, Buck2, BuildStream, Justbuild, Pants, Please, Recc, Reclient, Siso |

**Buck2 configuration.** `.buckconfig` `[buck2_re_client]` takes `engine_address`,
`action_cache_address`, `cas_address`, TLS settings (`tls_ca_certs`, `tls_client_cert`),
`http_headers` and `instance_name`. The execution platform's `CommandExecutorConfig` sets
`remote_enabled`, `local_enabled`, `use_limited_hybrid` and `remote_execution_properties` (for
example a `container-image`). Buck2's docs say it has been tested against EngFlow, Buildbarn
and BuildBuddy. SHA256 is the default digest; BLAKE3 and SHA1 can be configured.

**Who writes.** With a cache only, a client that builds locally must upload its own results;
limit that to CI. With remote execution, workers produce results; Buck2's docs present this as
the way every user can populate the cache through sandboxed execution.

## Example

**`.bazelrc`** (untested: Bazel was not installed; flags are from the Bazel caching and
bazelrc pages; the host name is a placeholder):

```text
# Everyone reads the shared cache; nobody uploads by default.
build --remote_cache=grpcs://build-cache.internal.example:443
build --remote_upload_local_results=false
build --experimental_guard_against_concurrent_changes
build --disk_cache=~/.cache/bazel-disk

# CI uploads: bazel build --config=ci //...
build:ci --remote_upload_local_results=true

# Per-user credentials or overrides, never committed.
try-import %workspace%/user.bazelrc
```

**Cache-hit and cost estimate.** Assumptions, not prices: a CI build has 2,000 actions of 6 CPU
seconds each, on 16 cores; 40 builds a day; 85% hit rate; 0.5 MB downloaded per hit; compute
at 0.05 per vCPU-hour and network egress at 0.09 per GB (pick your own currency and rates).

| Quantity | Arithmetic | Result |
|---|---|---|
| Cold build CPU | 2,000 x 6 s | 12,000 s = 3.33 CPU-h |
| Warm build CPU | 2,000 x 0.15 x 6 s | 1,800 s = 0.5 CPU-h |
| Wall time, cold, 16 cores | 12,000 / 16 | 750 s, 12.5 min |
| Wall time, warm | 1,800 / 16 | 112.5 s |
| Download per warm build | 1,700 hits x 0.5 MB | 850 MB |
| Download time at 1 Gbit/s / 100 Mbit/s | 850 / 125, 850 / 12.5 | 6.8 s / 68 s |
| Compute per day, cold / warm | 40 x 3.33 / 40 x 0.5 CPU-h | 133 / 20 CPU-h |
| Compute saved per 30 days | (133.3 - 20) x 30 x 0.05 | 170 |
| Egress per 30 days | 40 x 0.85 GB x 30 = 1,020 GB, x 0.09 | 91.8 |

The upload flag is a client-side default that anyone can override on the command line. Enforce
write access on the cache server: a read-only credential for people, a write credential held
only by CI. `build:ci` follows the `command:name` form on Bazel's bazelrc page.

The time win is real: about 12.5 minutes down to 2 minutes per build at 1 Gbit/s. The money is
not: if the cache sits across a metered link, egress eats more than half the compute saved,
and at 100 Mbit/s downloads alone take a minute. Put the cache in the same network as the
builders, and download only the outputs you need. The arithmetic was re-run in Python.

## Gotchas and contested points

- **The protocol does not say who may write to the AC.** `UpdateActionResult` requires the
  client to upload the Action and Command first so the server can apply access control by
  action type; the policy is the server's.
- **Hit rate is not the goal; build time is.** A long critical path of uncached actions still
  dominates however many leaves hit.
- **Self-hosted versus managed.** Self-hosted keeps data in your network and costs operators;
  managed costs money and moves your binaries to someone else. Both are reasonable.
- **Containers lose Bazel's in-memory state** between builds, so a containerized CI job pays
  analysis again even with a warm cache (Bazel caching page).
- **Stale system bazelrc files** (such as an old `/etc/bazel.bazelrc`) change action keys.

## Review checklist

1. Is the build proven hermetic on two clean machines before a shared cache is enabled?
2. Is write access to the action cache enforced by the server (CI or worker credentials only), not just by a client flag, with every client authenticated?
3. Is traffic encrypted, and are cache credentials kept out of committed files?
4. Does the cache sit in the same network as the builders, with an estimate of egress and time?
5. Are retention limits set, and is there a written way to disown poisoned results?
6. Has the hit rate been measured after `bazel clean`, and have misses been explained with execution logs?
7. For remote execution, is the platform pinned (image digest, OS, CPU) and are all tools reached through toolchains?
8. Is the choice of service recorded with its licence, data location and operating cost?

## Related

[hermeticity-and-reproducibility](hermeticity-and-reproducibility.md),
[build-principles-and-adoption](build-principles-and-adoption.md),
[tests-and-monorepo-migration](tests-and-monorepo-migration.md),
[`core-principles`](../../core-principles/SKILL.md) (least privilege),
[`container-images`](../../container-images/SKILL.md) (worker images),
[`infrastructure-patterns`](../../infrastructure-patterns/SKILL.md) (running the service on Kubernetes).

## Sources

Bazel: [Remote Caching](https://bazel.build/remote/caching),
[Debugging Remote Cache Hits](https://bazel.build/remote/cache-remote),
[Remote Execution Overview](https://bazel.build/remote/rbe),
[Remote Execution Services](https://bazel.build/community/remote-execution-services),
[Adapting Rules for Remote Execution](https://bazel.build/remote/rules),
[bazelrc](https://bazel.build/run/bazelrc).
[remote-apis README](https://github.com/bazelbuild/remote-apis) and
[remote_execution.proto](https://raw.githubusercontent.com/bazelbuild/remote-apis/main/build/bazel/remote/execution/v2/remote_execution.proto)
(header comments; the last ~25k characters were not read).
Buck2: [Remote Execution](https://buck2.build/docs/users/remote_execution/),
[Benefits compared to Buck1](https://buck2.build/docs/about/benefits/compared_to_buck1/).
Flag names for Bazel's remote executor setting were not on any fetched page and are omitted.
