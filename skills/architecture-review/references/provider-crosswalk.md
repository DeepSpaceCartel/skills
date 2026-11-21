# Provider crosswalk: well-architected frameworks

Google, AWS and Azure each publish a "well-architected" framework with about six pillars
(Azure has five). The pillars mostly line up, and the practices mostly agree, under different
names. This file maps them onto one neutral list. Read it when you review an architecture
against "the pillars", when someone quotes one provider's framework at a system that runs
elsewhere (for example Hetzner plus Kubernetes), or when you need a provider's product name
for a neutral practice.

The neutral practice is what matters. Product names are only a lookup column. Each practice is
tagged with the providers whose source states it: **G** Google, **A** AWS, **Z** Azure. A
missing tag means the inputs did not say it, not that the provider disagrees. Every
"Neutral" product line is this file's own mapping for self-run infrastructure; no source
names those tools.

## Pillar alignment

| Neutral pillar | Google | AWS (Cloud Workloads) | Azure |
|---|---|---|---|
| Operations | Operational Excellence | Operational excellence | Operational Excellence |
| Security | Security, Privacy, and Compliance | Security | Security |
| Reliability | Reliability | Reliability | Reliability |
| Performance | Performance Optimization | Performance efficiency | Performance Efficiency |
| Cost | Cost Optimization | Cost optimization | Cost Optimization |
| Sustainability | Sustainability | Sustainability | no pillar (see below) |
| Platform foundations | no separate area | Cloud Foundations (not a pillar) | no separate area |

Real differences:

- **Google merges privacy and compliance into security.** Its security pillar also covers AI
  security, data residency and sovereignty.
- **Azure has five pillars.** Its pillars page lists five, with no sustainability pillar.
  Sustainability is a separate set of workload guidance, written as recommendations under each
  of the five pillars plus a design methodology.
- **AWS (updated 2026-11-16) keeps six pillars** with the same names as before. They now sit
  under "Cloud Workloads". A new area, **Cloud Foundations**, covers decisions taken once per
  organization rather than per workload: account structure, identity, central observability,
  inventory and patching, security and compliance, cost management, and networking. It is
  organized as seven capabilities, not as a pillar. The six pillar whitepapers were merged into
  one document, and each pillar is now organized into "capabilities": 7 operations, 11
  security, 13 reliability, 5 performance, 10 cost and 4 sustainability. The deprecated AWS
  samples skill counts 57 *questions* (11/11/13/5/11/6) from the earlier edition. Reliability
  still lists its own Foundations area (quotas, network topology). The welcome page also says
  the Cloud Foundations custom lens holds the best practices in that Reliability section.
- **"Shared fate" means two different things.** Google uses it for the provider standing
  behind the customer (a partnership model, alongside shared responsibility). The AWS
  resilience framework uses it for correlated failure, where one fault takes down several
  parts. This file calls the second **correlated failure**.

## Operations

1. Define production-readiness criteria (people, process, tooling) before go-live. (G A)
2. Keep all infrastructure, config and pipelines in version control as code; detect drift. (G A Z)
3. Deploy every change through an automated pipeline with quality gates. (G A Z)
4. Ship small, frequent, reversible changes, with progressive exposure and a tested rollback. (A Z)
5. Instrument for observability: metrics trigger actions, logs and traces give context, and
   telemetry is correlated end to end. (G A Z)
6. Alert only on what needs action. Every alert names an owner and a severity. (G Z)
7. Run incidents with defined roles, channels and escalation paths. (G A Z)
8. Hold blameless post-incident reviews and track their action items. (G A Z)
9. Automate repetitive manual work, with guardrails such as rate limits, error thresholds and
   approvals. (A Z)
10. Rehearse failure scenarios and review procedures on a cadence. (A Z)

Products. G: Cloud Monitoring, Cloud Logging, Cloud Build, Cloud Deploy, Infrastructure
Manager. A: CloudWatch, X-Ray, CodePipeline, CodeDeploy, EventBridge, Systems Manager docs.
Z: Azure Monitor, Application Insights, Log Analytics. Neutral: Git + Terraform or Helm,
GitHub Actions or Argo CD, Prometheus + Grafana, OpenTelemetry, an on-call rota.

## Security

1. Least privilege and separation of duties for people and workloads; prefer short-lived,
   just-in-time access over standing credentials. (G A Z)
2. Centralize identity and authenticate every request explicitly (zero trust). (G A Z)
3. Defense in depth: controls at the edge, network, host, runtime and application, with
   segmented networks and environments to limit blast radius. (G A Z)
4. Classify data, then encrypt at rest and in transit according to its class. (G A Z)
5. Keep people away from data: automate access paths instead of granting manual reads. (A)
6. Shift left: scan code, dependencies and images in CI; deploy only trusted artifacts. (G A Z)
7. Centralize audit and security logs, and alert on them. (G A Z)
8. Keep an incident response plan, automate common responses, and rehearse it. (G A Z)
9. Threat-model, keep an asset inventory, patch on a cadence, and test defenses with pen
   tests or red teams. (G A Z)
10. Know the shared-responsibility line for each managed service you use. (G A)

Products. G: IAM, Identity-Aware Proxy, Cloud KMS, VPC Service Controls, Cloud Armor,
Security Command Center, Binary Authorization, Artifact Analysis. A: IAM, IAM Identity
Center, IAM Access Analyzer, KMS, CloudTrail, GuardDuty, Security Hub, Macie, WAF, VPC Flow
Logs. Z: Azure RBAC, Azure Firewall, Virtual Network. Neutral: an
OIDC identity provider, Kubernetes RBAC + NetworkPolicy, an external secrets store, cert
renewal through ACME, image signing, SBOM and dependency scans in CI.

## Reliability

1. Set targets from user journeys: SLIs, SLOs and error budgets per critical flow, not raw
   uptime. (G Z)
2. Agree recovery targets (RTO and RPO) with the business, and design to meet them. (G A Z)
3. Remove single points of failure with redundancy across failure domains (zones,
   regions). (G A Z)
4. Scale horizontally. Many small instances behind a load balancer beat one large one. (G A Z)
5. Know your quotas and capacity limits, and keep headroom for failover and spikes. (G A Z)
6. Degrade gracefully: timeouts, retries with backoff and jitter, circuit breakers, load
   shedding, and a fallback for non-critical paths. (G A Z)
7. Health checks drive automated failover and self-healing. (G A Z)
8. Back up every stateful component and test restores against RPO and RTO. Keep backups
   immutable, and secure the recovery site as strictly as the primary. (G A Z)
9. Test failure on purpose: fault injection, game days, DR drills. (G A Z)
10. Keep it simple: a lean critical path, only the components the business needs. (Z)

Products. G: managed instance groups, GKE, Cloud Load Balancing, Cloud SQL HA, Backup and DR
Service. A: Auto Scaling groups, ELB, AWS Backup, Fault Injection Service, Resilience Hub,
Application Recovery Controller. Z: AKS, VM Scale Sets (unverified), Load Balancer, Front
Door, Traffic Manager, Azure Backup, Site Recovery, zone-down drills (Azure Resiliency).
Neutral: Kubernetes Deployment + HPA + PodDisruptionBudget, topology spread across nodes and
zones, readiness and liveness probes, Postgres streaming replicas, off-site backups with
restore tests, Chaos Mesh or Litmus.

## Performance

1. Set performance targets per critical flow, with tolerances from ideal to unacceptable. (A Z)
2. Size resources from load tests or history, not estimates. (G A Z)
3. Use elasticity: scale with demand automatically, and validate the scaling rules. (G A Z)
4. Pick storage and data stores to fit the access pattern ("mechanical sympathy"). (G A)
5. Cache at several layers (CDN, in-memory, client) to offload the backend. (G A Z)
6. Decouple components so each scales on its own and a slow part cannot stall the rest. (G A Z)
7. Place workloads close to users when latency matters. (A)
8. Run performance tests in the pipeline as a gate, and alert on regressions. (G A Z)
9. Trace and profile to find code-level bottlenecks. (G Z)
10. Revisit choices as new hardware, versions and features appear. (A Z)

Products. G: managed instance groups, GKE HPA/VPA, Cloud Run, Cloud CDN, Memorystore, Cloud
Trace, Cloud Profiler. A: CloudFront, ElastiCache, DAX, RDS Proxy, Global Accelerator,
Graviton. Z: Front Door, Azure Managed Redis, Application Insights. Neutral: HPA/VPA, a CDN
in front of origin, Redis or Valkey, connection pooling, k6 or Locust load tests in CI,
continuous profiling.

## Cost

1. Make spend visible and attributable: label every resource by team, app and
   environment. (G A Z)
2. Set budgets with alerts on thresholds and anomalies. (G A Z)
3. Keep a cost model and tie cost to a business unit (per user, per transaction). (G A Z)
4. Right-size from measured use, and review on a cadence. (G A Z)
5. Delete idle and orphaned resources: disks, IPs, snapshots, old data. (G A Z)
6. Match the pricing model to usage: commitments for steady load, interruptible capacity for
   fault-tolerant batch, pay-per-use for spiky load. (G A Z)
7. Treat environments differently: non-production smaller, on demand, without HA. (G Z)
8. Plan data transfer: keep traffic regional and serve heavy egress from a cache. (G A)
9. Enforce guardrails that cap what can be provisioned. (G A Z)
10. Count people's time too: automate operations that cost effort. (A Z)

Products. G: Cloud Billing reports, billing export, budgets, Recommender, CUDs, SUDs, Spot
VMs, Storage lifecycle. A: Budgets, Cost Anomaly Detection, Compute Optimizer, Savings Plans,
Spot, S3 lifecycle. Z: Advisor, commitment discounts. Neutral: Kubernetes labels plus a
cost-allocation tool such as OpenCost, resource
requests and limits, quotas per namespace, cheaper interruptible nodes for batch.

## Sustainability

1. Measure impact per unit of work and set goals against it. (G A)
2. Maximize utilization: fewer, busier hosts; scale to zero when idle. (G A)
3. Prefer low-carbon regions when latency and residency allow. (G A)
4. Use the lightest computational approach that meets the need. (G A)
5. Keep only data with a purpose and an owner; tier or expire the rest. (G A)
6. Move compute to the data rather than data to the compute. (A)
7. Shift deferrable batch work to low-carbon times or places. (G)
8. Adopt newer, more efficient hardware and software as they appear. (G A)
9. Keep DR standby cold where RTO allows, and rebuild it from code when needed. (G)

Products. G: Carbon Footprint, Region Picker, Cloud Batch, Spot VMs, TPUs. A: Graviton,
Intelligent-Tiering, Glacier, Lambda, Fargate. Z: sustainability workload guidance (no
pillar). Neutral: your host's published energy mix (provider-dependent), cluster bin-packing,
scale-to-zero (Knative or KEDA), lifecycle rules on object storage.

## Resilience failure-mode walk

AWS's resilience analysis framework sorts failures into five categories. For each user story,
consider preventive mitigations first, then corrective ones that let the system heal or
adapt. Weigh each failure mode's likelihood and impact against the mitigation's cost: some
(cells) mean a redesign.

| Failure category | Property wanted | Neutral mitigations |
|---|---|---|
| Single point of failure | Redundancy, fault tolerance | Redundant instances behind a balancer; depend on a provider's data plane, not its global control plane; degrade gracefully so one loss stays tolerable (static stability) |
| Excessive load | Enough capacity | Rate limits, load shedding and priority, constant-work designs, capped backoff with jitter (or no retry), let the smaller service set the pace, bounded queues, autoscaling, warm caches, circuit breakers; plan capacity against every limit |
| Excessive latency | Timely output | Tuned or adaptive timeouts, backoff with jitter, hedged requests, async and loose coupling, caching, keep work already done |
| Misconfiguration and bugs | Correct output | Static analysis, unit, integration, regression, load and resilience tests; config as code via CI/CD; one-box, canary, blue/green or fractional rollouts aligned to fault boundaries |
| Correlated failure (AWS: "shared fate") | Fault isolation | Separate clusters, accounts, credentials, zones and maybe regions; cells and shuffle sharding; loose coupling; keep the core flow (checkout) safe from extras (promotions) |

Also plan recovery: tools to re-drive stalled workflows or fix data, checkpoints against data
loss, and a stop switch that pauses intake. Assume operators will make mistakes. A root cause
of "human error" means a guardrail was missing.

## Provider-specific: safe to ignore off-cloud

- Discount programs and commitment math (CUDs, SUDs, Savings Plans, reservations). Keep the
  principle: match pricing to the usage pattern.
- Provider advisor and recommender tools, scorecards, and review tooling (Well-Architected
  Tool, Advisor score). Use your own metrics instead.
- Region carbon dashboards and region pickers. Off-cloud, ask your host for its energy mix.
- Provider-specific hardware pushes (Graviton, TPUs, machine families). Keep the principle:
  match hardware to the work and re-evaluate.
- Global-service control plane advice. Off-cloud, the analogue is your own control plane
  (the Kubernetes API, DNS, the CI system).
- Multi-account and landing-zone structure. On one host, the analogue is separate clusters,
  namespaces and credentials per environment.
- Partnership programs (Google's shared fate, risk protection). The shared-responsibility
  split still applies to any managed service you buy.

## Sources

Upstream skills (read locally):

- Google, six `google-cloud-waf-*` skills: https://github.com/google/skills, commit `613a392`,
  Apache-2.0. Vendored unchanged in this repo under `vendor/google/`.
- AWS samples, `aws-well-architected-framework-review` (marked deprecated upstream):
  https://github.com/aws-samples/sample-well-architected-skills-and-steering, commit `e81835b`,
  MIT-0.
- AWS, `aws-well-architected-review` and `resilience-skills`:
  https://github.com/aws/agent-toolkit-for-aws, commit `971cf5a`, Apache-2.0. It finds the
  pillars from the live docs and does not list them itself.
- Microsoft, `azure-well-architected`, `azure-reliability`, `azure-resiliency`:
  https://github.com/MicrosoftDocs/Agent-Skills, commit `9b16b5c`, CC BY 4.0.

Pages fetched 2026-11-20:

- AWS, under https://docs.aws.amazon.com/wellarchitected/latest/framework/: `welcome.html`,
  `release-notes.html`, `workloads.html`, `cloud-foundations.html`, `toc-contents.json`, the
  six pillar pages (`operational-excellence`, `security`, `reliability`,
  `performance-efficiency`, `cost-optimization`, `sustainability`, each `.html`) and the
  design principles pages `{fnd,ops,sec,rel,perf,cost,sus}-design-principles.html`.
  `the-pillars-of-the-framework.html` returned 404.
- AWS resilience analysis framework:
  [mitigation strategies](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/mitigation-strategies.html).
- Azure, under https://learn.microsoft.com/en-us/azure/well-architected/: `pillars`, and
  `{reliability,security,cost-optimization,operational-excellence,performance-efficiency}/principles`.

Product names marked "(unverified)" do not appear in the inputs.

Paraphrased from the Google Cloud, AWS and Microsoft Azure Well-Architected Framework skills
and documentation listed above; Google content Apache-2.0, AWS samples MIT-0, AWS toolkit
Apache-2.0, Microsoft docs CC BY 4.0.
