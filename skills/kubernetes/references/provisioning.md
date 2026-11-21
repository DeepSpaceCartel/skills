# Provisioning clusters

Checked 2026-11-20: Talos v1.14, Omni v1.13, Cluster API v1.14, k3s and RKE2 v1.37, Crossplane v2.4.

| Tool | What | Choose when | Watch out |
|---|---|---|---|
| **Talos Linux** | An immutable, API-managed Kubernetes OS: no SSH or shell. KubeSpan (WireGuard node mesh), disk encryption, `talosctl upgrade` | You want minimal node maintenance and declarative machines | Back up the machine configs **and the secrets bundle**, or you can't add nodes to the same cluster later. Drivers come as system extensions |
| **Omni** | Sidero's SaaS or self-hosted manager for Talos fleets: registration, templates, upgrades, an OIDC kubeconfig proxy, etcd backups | Several Talos clusters and you want one place to run them | Paid per node above the hobby tier; self-hosting for production needs a commercial licence. Check pricing. Its etcd backups never expire, so set a bucket lifecycle |
| **Cluster API** (SIG Cluster Lifecycle) | Clusters as CRDs, reconciled from a management cluster | Many clusters, or cluster-per-tenant | Needs a management cluster. Check that your OS and provider combination is documented: most providers are kubeadm-based |
| **kubeadm / kubespray** | DIY clusters on mutable Linux (kubespray adds Ansible) | You need full control of a conventional distro | You own OS patching, configuration drift and upgrades |
| **k3s / RKE2** | A single-binary lightweight Kubernetes / a hardened variant | Edge, small VMs, mutable OSes | k3s defaults (embedded datastore, bundled ingress and load balancer) differ from upstream; disable what production doesn't use |
| **Metal3** (CNCF incubating) | Cluster API on bare metal through Ironic (PXE, BMC) | You control BMCs and provisioning networks | Rented dedicated servers rarely expose those |
| **Proxmox** (CAPI provider) | VMs on your own Proxmox hosts | You already run Proxmox | Another layer to operate |
| **Terraform / OpenTofu** with the cloud and Talos providers | Servers, networks, load balancers, firewalls, plus machine configs | Most small and medium setups | Keep state remote and locked |
| **Crossplane** (CNCF graduated) | Cloud resources as Kubernetes CRDs; compositions as internal platform APIs | A platform team offering self-service infrastructure | Overkill for a few clusters; Terraform is simpler |

## Back up a cluster's identity

- **etcd:** `etcdctl snapshot save` / restore (https://kubernetes.io/docs/tasks/administer-cluster/configure-upgrade-etcd/).
  On Talos, `talosctl etcd snapshot`, and recover with `talosctl bootstrap --recover-from`.
- **Machine configs and PKI or secrets bundles,** stored offline.
- **Credentials are data:** see
  [`../../data-integrity/references/disaster-recovery.md`](../../data-integrity/references/disaster-recovery.md)
  for recovery copies and the order of recovery.
- **The real recovery plan:** with GitOps, rebuilding from Git plus restoring databases from their
  own backups is the actual disaster-recovery path. etcd snapshots are the fast whole-cluster
  rollback. Rehearse it.

## Example: mixing cloud VMs and dedicated servers (Hetzner)

Provider facts change, so verify these against the provider's current docs. This shows the kind
of constraint to check before designing a hybrid cluster.

- **Coupling rules:**
  - Dedicated (Robot) servers can join a cloud private network through a vSwitch, but only in the
    `eu-central` network zone. The VLAN interface has MTU 1400.
  - A cloud network can't span zones, so US locations (cloud only) are always separate clusters.
- **Cloud controller manager:** `hcloud-cloud-controller-manager` supports Robot nodes, with
  these conditions:
  - **Routing:** its Routes controller must be off, and the CNI must encapsulate (Cilium
    `routingMode: tunnel`).
  - **Matching:** the node's hostname must equal its Robot server name.
  - **Private IPs:** they aren't discovered, so set them with kubelet `--node-ip`.
  - **Load balancers:** IP targets work only in `eu-central`.
  - **No other vendors:** nodes from another vendor in the same cluster aren't supported.
- **Storage:** `hcloud-csi` has no VolumeSnapshot support. Snapshot-based backups (CNPG
  `volumeSnapshot`, Velero CSI snapshots) are unavailable on its volumes, so use WAL archiving and
  Velero's file-system backup.
- **Object Storage** exists only in the EU locations.
- **No GPU cloud servers:** GPUs are dedicated servers only, with a setup fee. Cloud autoscalers
  (Cluster Autoscaler, the community Karpenter provider) can't create GPU nodes.
