# Security and policy

Checked 2026-11-20: Kubernetes 1.37, Kyverno 1.20, Gatekeeper 3.23, cosign 3.1, Cilium 1.20.

## Order of value

1. **Pod Security Admission `restricted`** on application namespaces. It is built in and free.
2. **Default-deny NetworkPolicies**, with explicit egress (DNS first). Your CNI must enforce them:
   Flannel doesn't, while Cilium and Calico do.
3. **RBAC hygiene.**
   - One ServiceAccount per workload, with no token automount.
   - Cluster-admin only through GitOps.
   - Short-lived credentials for humans.
4. **Admission policy for what PSA doesn't cover:**
   - require resource requests;
   - no `:latest` tags;
   - required labels;
   - signed images.
5. **CI supply chain:**
   - an SBOM and provenance;
   - keyless signing;
   - a vulnerability scan;
   - actions pinned by commit SHA and images by digest.
6. **Later:** runtime detection or enforcement (Falco or Tetragon), continuous CVE reports
   (Trivy Operator) and posture scans (Kubescape).

## Pod Security Admission

- **Levels:** `privileged`, `baseline` and `restricted`. Set them per namespace with labels:

```yaml
metadata:
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
```

- **Defaults:** `restricted` for apps, `baseline` for infrastructure.
- **Exceptions:** exempt only namespaces that need host access (CNI, CSI, GPU operator, runtime
  security agents).
- **A chart can't opt out.** PSA is namespace-scoped, so a chart that needs privileges can't get
  around it with `securityContext`. The namespace label must allow it.

## Built-in admission policies

**ValidatingAdmissionPolicy** (GA 1.30) and **MutatingAdmissionPolicy** (GA 1.36) run CEL inside
the API server: there's no webhook to run or keep available.

- **Use them** for a handful of cluster-wide rules.
- **What they lack:** policy reports, image verification and resource generation.
- **`validationActions`:** `Deny`, `Warn` or `Audit` (Audit writes to the audit log).

## Kyverno (1.20+)

**The legacy engine is gone in 1.20.** `ClusterPolicy`, `Policy`, `CleanupPolicy`,
`ClusterCleanupPolicy` and the legacy `PolicyException` no longer execute, and their CRDs are
removed in 1.21. Most examples online, including the old policy library, are legacy: don't copy
them.

- **The current kinds** are all in `policies.kyverno.io/v1`, each with a `Namespaced…` variant:
  - `ValidatingPolicy`
  - `MutatingPolicy`
  - `GeneratingPolicy` (for example, stamp a default-deny NetworkPolicy into every new namespace)
  - `ImageValidatingPolicy`
  - `DeletingPolicy`
  - `PolicyException`
- **Migrating:** `kyverno migrate` rewrites stored legacy objects. The Helm chart blocks upgrades
  while legacy policies exist unless you acknowledge them.
- **Migration guide:** https://kyverno.io/docs/guides/migration-to-cel/

Example from the Kyverno docs (https://kyverno.io/docs/policy-types/validating-policy/):

```yaml
apiVersion: policies.kyverno.io/v1
kind: ValidatingPolicy
metadata:
  name: check-labels
spec:
  validationActions:
    - Deny
  matchConstraints:
    resourceRules:
      - apiGroups: ['']
        apiVersions: [v1]
        operations: [CREATE, UPDATE]
        resources: [pods]
  validations:
    - message: label 'environment' is required
      expression: "'environment' in object.metadata.?labels.orValue([])"
```

Requiring CPU and memory requests is the same shape with a different expression. This one is
adapted from the example above, not copied from the docs, so test it with `kyverno apply` or a
dry-run first:

```yaml
apiVersion: policies.kyverno.io/v1
kind: ValidatingPolicy
metadata:
  name: require-requests
spec:
  validationActions: [Audit]          # Kyverno policy reports; switch to Deny once they are clean
  matchConstraints:
    resourceRules:
      - apiGroups: ['']
        apiVersions: [v1]
        operations: [CREATE, UPDATE]
        resources: [pods]
  validations:
    - message: every container and init container must request cpu and memory
      expression: >-
        (object.spec.containers + object.spec.?initContainers.orValue([])).all(c,
          ['cpu', 'memory'].all(r, r in c.?resources.?requests.orValue({})))
```

**Pod policies and controllers.** A policy that matches only `pods` rejects a bad Deployment late:
the Deployment is accepted, and its ReplicaSet then fails to create pods. Kyverno can also apply a
pod policy to the controllers' pod templates (Deployments, Jobs, CronJobs and others) through the
policy's `autogen` settings, so the bad object is rejected at apply time. Check the
`ValidatingPolicy` page for the current `autogen` fields and defaults before relying on it.

**Two kinds of "Audit".** In a Kyverno policy, `Audit` records violations in Kyverno policy reports
(`kubectl get policyreports -A`). In a built-in ValidatingAdmissionPolicy binding, `Audit` writes
to the API server's audit log.

Verifying keyless cosign signatures from a CI workflow identity. This is the docs' example with
its attestation check removed (https://kyverno.io/docs/policy-types/image-validating-policy/):

```yaml
apiVersion: policies.kyverno.io/v1
kind: ImageValidatingPolicy
metadata:
  name: verify-ci-signatures
spec:
  validationActions: [Deny]
  matchConstraints:
    resourceRules:
      - apiGroups: ['']
        apiVersions: ['v1']
        resources: ['pods']
        operations: ['CREATE', 'UPDATE']
  matchImageReferences:
    - glob: 'ghcr.io/myorg/myrepo:*'
  attestors:
    - name: cosign
      cosign:
        keyless:
          identities:
            - subject: 'https://github.com/myorg/myrepo/.github/workflows/*'
              issuer: 'https://token.actions.githubusercontent.com'
        ctlog:
          url: 'https://rekor.sigstore.dev'
  validations:
    - expression: >-
        images.containers.map(image, verifyImageSignatures(image, [attestors.cosign])).all(e, e > 0)
      message: 'Failed image signature verification'
```

Running Kyverno:
- **Availability:** it is a webhook, so run 3 admission replicas with a PDB.
- **`failurePolicy`** decides whether a Kyverno outage blocks the cluster.
- **Exclusions:** exclude `kube-system` and Kyverno's own namespace.

## Gatekeeper

OPA Gatekeeper uses Rego, through `ConstraintTemplate` and `Constraint`, and audits existing
objects. Choose it when Rego and OPA are already used elsewhere (API authorization, conftest);
otherwise Kyverno is easier.

## NetworkPolicy

- **Default deny per namespace,** then allow DNS (kube-dns on UDP and TCP 53), then each flow the
  app needs. Policies are additive allow-lists: vanilla NetworkPolicy has no deny rule.
- **Cilium** adds `CiliumNetworkPolicy`: L7 HTTP and gRPC rules, FQDN egress (`toFQDNs`), and
  entities such as `kube-apiserver` and `world`. Egress to the API server needs an explicit allow.
  Test with Hubble before enforcing.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: default-deny}
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: allow-dns}
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
  - to:
    - namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: kube-system}}
      podSelector: {matchLabels: {k8s-app: kube-dns}}
    ports:
    - {protocol: UDP, port: 53}
    - {protocol: TCP, port: 53}
```

## RBAC

Guidance: https://kubernetes.io/docs/concepts/security/rbac-good-practices/

- **Prefer namespaced** `Role` / `RoleBinding`, and no `*` in verbs or resources.
- **Avoid these verbs:** `escalate`, `bind` and `impersonate`.
- **Avoid these resources:**
  - `create` on pods, workloads or `pods/exec`: it equals reading every Secret mountable in the
    namespace.
  - `list` / `watch` on Secrets: `list` returns their values.
  - `nodes/proxy`.
- **Audit with** `kubectl auth can-i --list --as=system:serviceaccount:NS:SA`, plus the krew
  plugins `who-can` and `rakkess`.

## Scanning, signing, runtime

| Tool | Use | Notes |
|---|---|---|
| **Trivy** (+ Trivy Operator) | Scan images, file systems, IaC and clusters; make SBOMs | Its actions and some releases were compromised in March 2026 (CVE-2026-33634). Pin by SHA and digest |
| **Kubescape** (CNCF incubating) | Posture against NSA/CISA, MITRE and CIS controls; RBAC checks | Good in CI and for periodic scans |
| **kube-bench** | CIS benchmark of node files and flags | Mostly irrelevant on immutable OSes such as Talos |
| **cosign** (Sigstore) | Sign and verify OCI artifacts; keyless via CI OIDC; `cosign attest` for SBOMs and provenance | Verify in-cluster with Kyverno `ImageValidatingPolicy`. Sigstore's policy-controller releases slowly |
| BuildKit attestations | `docker buildx build --sbom=true --provenance=mode=max` | Stored with the image |
| **Falco** (CNCF graduated) | Syscall and eBPF threat detection with rules | Tune the noisy defaults; a DaemonSet on every node |
| **Tetragon** (Cilium) | eBPF observability **and in-kernel enforcement** (`TracingPolicy` can kill processes) | Enforcement policies can break workloads; start in observe mode |
