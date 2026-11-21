# GPUs

Checked 2026-11-20. NVIDIA GPU Operator 26.7, device plugin 0.20, Kubernetes 1.37.

## GPUs as cluster nodes

- **NVIDIA GPU Operator** installs the driver, container toolkit, device plugin, GPU feature
  discovery, the DCGM exporter and the MIG manager, through a `ClusterPolicy`. When the OS image
  already ships the drivers and toolkit (immutable OSes do this with system extensions), disable
  the operator's own (`driver.enabled=false`, `toolkit.enabled=false`) or run only the device
  plugin.
- **Requesting a GPU:** set `resources.limits: {nvidia.com/gpu: 1}`, tolerate the GPU taint, and
  usually set `runtimeClassName: nvidia`. Taint GPU nodes so CPU pods never land on them.
- **The operator's namespace needs privileged Pod Security** (it runs host-level agents).
  Exempt it explicitly.

### Sharing a GPU

| Method | Isolation | Use for | Not for |
|---|---|---|---|
| **Time-slicing** (device plugin config `sharing.timeSlicing.resources[].replicas`) | none: no memory or fault isolation | several small models or notebooks on one card | vLLM and other servers that preallocate most of the memory |
| **MIG** (A100/H100/H200/B200-class) | hardware partitions | several isolated tenants on a data-centre GPU | consumer and workstation cards |
| **Whole GPU per pod** | full | batch inference, training | — |

### DRA (Dynamic Resource Allocation)

- **Status:** GA since Kubernetes 1.34 (`resource.k8s.io/v1`).
- **The NVIDIA DRA driver** now lives in kubernetes-sigs. GPU Operator 26.7 deploys it through a
  `GPUCluster` resource *instead of* `ClusterPolicy`: not both, no in-place migration, and a new
  cluster is recommended.
  - **GA:** whole-GPU allocation, pre-made MIG devices, multi-node NVLink domains.
  - **Alpha:** dynamic MIG, MPS and time-slicing settings.
- **Use DRA** on new clusters that need per-claim device selection (by memory, model or MIG
  profile) or NVLink domains.
- **Stay on the device plugin** for whole-GPU batch, and wherever an autoscaler adds and removes
  nodes: autoscaler support for DRA is still catching up.

## Serving and distributed GPU stacks

| Tool | For | Skip when |
|---|---|---|
| A **Job running vLLM offline** (`LLM` class or `vllm run-batch`) | Batch inference on one GPU per worker | — |
| **KubeRay** (`RayJob`, `RayCluster`, `RayService`; CNCF sandbox) | One job that spans many GPUs or nodes, Ray Data pipelines. `RayJob` with `shutdownAfterJobFinishes` gives a cluster per job | One-GPU workers: a plain Job is simpler |
| **KServe** (CNCF incubating) | A model-serving platform with many models; `LLMInferenceService` | A batch pipeline |
| **llm-d** (CNCF sandbox), **vLLM production-stack** | Online LLM serving fleets: KV-cache-aware routing, prefill/decode disaggregation | Batch |

## GPUs that are not cluster nodes

Many GPU clouds sell containers or locked VMs, not machines that can join a cluster. The options,
from most to least "native":

| Option | Works when | Caveats |
|---|---|---|
| **A real node from a second autoscaler** (Cluster Autoscaler or Karpenter on a provider with GPU VMs) | The provider sells VMs that can boot your node OS and reach your control plane (often over a WireGuard mesh such as Talos KubeSpan) | One autoscaler per provider. Cold start = VM boot + node join + image pull (vLLM images are large) + model download, so measure it before setting batch windows. GPU spot quota often starts at 0 |
| **A permanent GPU node** (a rented dedicated GPU server) | The GPU is busy most of the month | Setup fees and monthly terms make it fixed capacity, not elastic. Break-even = monthly cost ÷ on-demand hourly price |
| **Virtual Kubelet provider** | A maintained provider exists for that cloud, with a licence you can use | Check the licence (some are noncommercial only) and the features: volumes, init containers and probes are often unsupported |
| **interLink** (CNCF sandbox) | HPC back ends (Slurm, HTCondor) | No GPU-cloud plugins; you'd write one |
| **SkyPilot** | Jobs and pools across many GPU clouds, with spot recovery and vendor fallback | Its API server is a sizeable always-on service with its own state, and its queue isn't yours |
| **Liqo** | The far side is a Kubernetes cluster | Container-only GPU clouds aren't |
| **Launcher Job** (below) | Any GPU cloud with an API | The workload isn't a pod from Kubernetes' point of view |

### Launcher pattern

A KEDA `ScaledJob` (see [autoscaling-and-batch.md](autoscaling-and-batch.md)) starts a small CPU
Job. That Job:

1. Rents a GPU instance through the provider's API, tagged with the Job's name and a deadline.
2. Starts the worker there with the queue's connection details. The worker claims items under a
   lease and exits when the queue is empty or its maximum runtime passes.
3. Waits, then **terminates** the instance in a `finally` block. "Stop" often keeps billing
   storage; terminate deletes everything outside network volumes.

Two backstops, because the launcher can die:
- the worker shuts itself down when the queue is empty or its deadline passes;
- a **reaper CronJob** terminates any tagged instance older than N hours.

Check the bill after the first runs. Provider APIs change: RunPod's REST v1 was retired on
2026-11-15.

Several things argue for this pattern:
- **No idle capacity in the cluster.** The decision logic is declarative in the ScaledJob, and the
  only thing in the cluster is a small pod.
- **No lock-in.** It works with any provider.
- **Easy to retire.** It disappears when GPUs become real nodes: point the same ScaledJob at GPU
  nodes by toleration.
