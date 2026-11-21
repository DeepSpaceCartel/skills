# Multi-cluster, multi-region and edge networking

Checked 2026-11-20: Cilium 1.20, Karmada 1.19, Istio 1.32, Gateway API 1.7, cert-manager 1.21,
CloudNativePG 1.30.

## One cluster per region

- **etcd:** keep members in one data centre where possible. If they span sites, tune the
  heartbeat to the round-trip time and set the election timeout to at least 10 × RTT
  (https://etcd.io/docs/v3.6/tuning/). Across an ocean (90–150 ms), every write would wait a
  transatlantic round trip for quorum, and a partition costs one side its API server.
  Kubernetes' multi-zone guidance covers zones within a region, not regions.
- **Remote workers under a far control plane** (easy with a WireGuard node mesh) are a different
  case: no etcd traffic crosses the WAN.
  - **What breaks:** kubelet heartbeats and watches still cross it. During a partition the remote
    nodes go `NotReady` and their pods are evicted after the default 300 s toleration, and the
    remote site can't schedule or roll out anything.
  - **Use it for:** a single edge node.
  - **Don't use it for:** a region meant to keep serving during an outage.
- **The standard pattern:** an independent cluster per region, all from the same GitOps repo with
  per-region overlays. Clusters share only what you connect on purpose.

## How services talk across clusters, simplest first

1. **Public HTTPS with mTLS or tokens.** No extra infrastructure, and it works with any CNI. The
   right default for two to four clusters.
2. **A private overlay for a few endpoints.** The Tailscale operator (ingress and egress proxies,
   an API-server proxy) or plain WireGuard carries database replication and an internal API.
3. **Multi-cluster service discovery**, where names resolve across clusters: Cilium ClusterMesh,
   Submariner (MCS API), Istio or Linkerd multicluster, Liqo. These need unique pod CIDRs and a
   flat or gateway-connected network, plus a mesh-level control plane to run.
4. **Federation**, one API placing workloads on many clusters: Karmada, Open Cluster Management,
   Liqo virtual nodes. Pays off at fleet scale.

| Tool | Solves | WAN | Burden |
|---|---|---|---|
| **Cilium ClusterMesh** (CNCF graduated) | Flat pod network, global services, cross-cluster policy | Needs every node's internal IP reachable (peering or VPN underneath) | Medium: unique cluster IDs and pod CIDRs, the same datapath, Cilium versions within one minor |
| **Submariner** (sandbox) | L3 tunnels plus MCS discovery; Globalnet for overlapping CIDRs | Built for it (gateway nodes, NAT traversal) | Medium–high; Cilium isn't among its listed CNIs |
| **Liqo** | Peering; a remote cluster appears as a virtual node | Tunnels regardless of CNI | Medium; hides where pods actually run |
| **Karmada** (CNCF graduated 2026) | Federation: `PropagationPolicy`, cross-cluster failover | Push or pull agents | High: its own etcd and API server |
| **Open Cluster Management** (incubating) | Hub-and-spoke fleet management, placement, add-ons | Pull agents | Medium–high |
| **vcluster** | Virtual clusters *inside* one host cluster (tenancy, ephemeral environments) | n/a: not multi-region | Low–medium |
| **Istio multicluster** (graduated) | mTLS identity, locality failover. Ambient multicluster is beta ("production ready"), multi-primary only | East-west gateways | High: shared root CA, version skew |
| **Linkerd multicluster** (graduated) | Gateway, flat and federated modes | Gateway mode | Medium. The open-source project ships edge releases only; stable builds come from vendors |
| **Tailscale operator** | Ingress and egress to a tailnet, API-server proxy, subnet routers | Excellent (NAT traversal, relays) | Low; a SaaS control plane. A self-hosted Headscale isn't supported by the operator |
| **Talos KubeSpan** | WireGuard mesh between the nodes of **one** cluster | Built for hybrid sites | Very low; doesn't connect separate clusters |

## Global traffic steering

- **Who steers:** health-checked geo or latency steering lives in a DNS or CDN provider, for
  example Cloudflare Load Balancing (Geo or Dynamic steering), Bunny DNS Smart Records or AWS
  Route 53 (latency, geolocation, failover). Plain authoritative DNS can't do it.
- **external-dns** writes the per-region names from Services and Gateway routes. Give each cluster
  its own `txtOwnerId`. The global name belongs to the steering provider.
- **A CDN first:** a CDN in front of one region removes most of the latency for static and
  cacheable content for very little. Measure dynamic-request latency before adding regions.

## Databases across regions (CloudNativePG)

- **One writer.** "Applications can only write inside a single Kubernetes cluster." A replica
  cluster is a separate `Cluster` resource in continuous recovery, usually in another Kubernetes
  cluster.
- **Sources:**
  - streaming (seconds of lag; needs the primary reachable over TLS or an overlay);
  - the WAL archive in object storage (no network between clusters; lag bounded by
    `archive_timeout`, default 5 minutes);
  - both: streaming, falling back to the archive.
- **Distributed topology** (`spec.replica.primary` / `source` / `self`, the same in every
  cluster): a controlled switchover is *demote, then promote with the demotion token*, with no
  data loss and no re-clone.
- **"CloudNativePG cannot perform any cross-cluster automated failover."** Promotion is a human
  decision or a Git commit.
- **Writes from far regions:**
  - **Route writes through an API in the writer's region:** one request per user action. Better
    than chatty SQL across the ocean.
  - **Handle read-your-writes:** pin the user to the primary region's reads for a few seconds
    after a write, or compare replica LSNs.
- **Backups:** if the archive lives in one region, a restore elsewhere crosses the ocean.
- **Patterns:** read-your-writes and replica lag in
  [`../../infrastructure-patterns/references/read-replicas.md`](../../infrastructure-patterns/references/read-replicas.md);
  active-passive failover and split brain in
  [`redundancy-and-failover`](../../infrastructure-patterns/references/redundancy-and-failover.md).

## The real cost of more regions

- **Every operation multiplied:** each cluster is another upgrade (OS, Kubernetes, CNI,
  operators), monitoring stack, backup, set of certificates and set of secrets.
- **Staged rollouts:** roll changes out region by region.
- **Data is the hard part:** one writer, replica lag, read-your-writes, manual failover drills.
- **A read region is a latency optimisation, not write HA.**
- **Networking:** cross-region traffic crosses the public internet encrypted, and is often billed.
  Keep it to replication, the write path and observability shipping.

## Ingress, certificates, DNS

- **ingress-nginx is retired** (March 2026: no releases and no security fixes). The Ingress *API*
  remains GA and frozen. `ingress2gateway` helps migrate.
- **Gateway API** (v1.7; GA: GatewayClass, Gateway, HTTPRoute, GRPCRoute, ReferenceGrant,
  BackendTLSPolicy; 1.7 made HTTPRoute retries standard).
  - **Cilium Gateway:** built into the CNI, no extra controller. The default when Cilium is
    already installed.
  - **Envoy Gateway:** a dedicated Envoy per Gateway, with rich policies (rate limits, OIDC/JWT,
    external auth).
  - **Traefik:** simple, with the easiest migration from ingress-nginx annotations.
  - **Istio, NGINX Gateway Fabric, kgateway:** only if you're already in that ecosystem.
- **cert-manager** (CNCF graduated) issues ACME certificates, including Gateway listener
  certificates through the `cert-manager.io/issuer` annotation on the Gateway. Use **DNS-01** for
  wildcards and for multi-region names, where HTTP-01 can be answered by the wrong region.
