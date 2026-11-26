# Service foundations: chassis, template, configuration

## Problem

Every service needs the same plumbing before it does anything useful: build and packaging,
configuration, logging, metrics, tracing, health checks, security, graceful shutdown, and
calls to other services with timeouts and retries. Written by hand each time, it takes days per
service and ends up different in each one. Then operators can't rely on any of it. Shared
foundations make a new service quick to start and keep the fleet consistent.

## Chassis vs template

| | Chassis (shared framework or library) | Service template (copied starter) |
|---|---|---|
| What | A dependency that provides the cross-cutting concerns | A runnable sample service you copy to start a new one |
| Updates | A version bump in each service | Re-applied by hand in each copy; copies drift |
| Fits | Many services on the same stack | A few services, or as the starting point that *uses* a chassis |
| Risk | Becoming a framework that couples every service's releases | Divergence; old copies never get fixes |

Use both: a template for the shape of a new service (layout, pipeline, Dockerfile, sample
endpoint, tests), built on a thin chassis or the platform's own conventions for the concerns.
Keep the chassis technical: it must never contain domain models (see
[anti-patterns](anti-patterns.md), shared domain library). Version it with SemVer and let
services upgrade on their own schedule.

Much of what a chassis once did now belongs to the platform: discovery and load balancing
(Kubernetes Services), mTLS and retries (a mesh), configuration and secrets (the orchestrator).
Don't rebuild in a library what the platform already provides. Decide which layer owns each
mechanism ([`infrastructure-patterns`, reliability at two layers](../../infrastructure-patterns/SKILL.md#reliability-at-two-layers)).

## Externalized configuration

The same build artefact runs in every environment. Everything that differs (endpoints,
credentials, feature flags, limits) comes from outside: environment variables, mounted files,
or a configuration service, read at startup or watched.

- **Validate configuration at startup** and fail fast on missing or invalid values, rather
  than at the first request that needs them.
- **Secrets are configuration with extra rules:** delivered by the platform's secret mechanism,
  never baked into images or committed
  ([`container-images`](../../container-images/SKILL.md),
  [`secure-reliable-systems`](../../secure-reliable-systems/SKILL.md)).
- **Configuration changes are deployments:** versioned, reviewed and rolled out gradually
  ([`production-operations`](../../production-operations/SKILL.md)).

## The baseline every service has

| Concern | Baseline | Where it's specified |
|---|---|---|
| Logs | Structured, with trace and span IDs on every record, sent to one aggregator | [`structured-logging`](../../structured-logging/SKILL.md) |
| Metrics | Request rate, errors and latency per endpoint and per dependency; saturation | [`production-operations` monitoring-and-alerting](../../production-operations/references/monitoring-and-alerting.md) |
| Traces | Context propagated on every inbound and outbound call and message | [`structured-logging` correlation](../../structured-logging/references/correlation.md) |
| Errors | Unhandled exceptions reported to an error tracker (Sentry, GlitchTip or similar) with release, request and trace IDs, grouped so one bug is one issue | This row |
| Health | Liveness, readiness and startup endpoints with the right depth | [`infrastructure-patterns` health-checks-and-probes](../../infrastructure-patterns/references/health-checks-and-probes.md) |
| Outbound calls | Timeouts, bounded retries with jitter, breakers | [`engineering-practices` reliability](../../engineering-practices/references/reliability.md) |
| Shutdown | Drain on SIGTERM, finish in-flight work within the grace period | [`infrastructure-patterns` disruption-budgets-and-safe-rollouts](../../infrastructure-patterns/references/disruption-budgets-and-safe-rollouts.md) |
| Deploy record | Each deploy and config change logged and shown on dashboards | [`production-operations` monitoring-and-alerting](../../production-operations/references/monitoring-and-alerting.md), [config-and-canary-changes](../../production-operations/references/config-and-canary-changes.md) |
| Audit | Security-relevant user actions recorded durably, off the host | [`secure-reliable-systems` compromise-recovery-and-forensics](../../secure-reliable-systems/references/compromise-recovery-and-forensics.md) |
| Packaging | One image per service, non-root, pinned base | [`container-images`](../../container-images/SKILL.md), [`helm-charts`](../../helm-charts/SKILL.md) |
| Tests | Component tests with test doubles; contract tests with each consumer and provider | [`engineering-practices` testing](../../engineering-practices/references/testing.md) |

## What agents get wrong

- **A chassis that carries domain types** or business rules.
- **Re-implementing platform features in code**, such as client-side discovery or retries on top
  of mesh retries.
- **A template copied once and never updated,** so each service is stuck at its birth year's
  practices.
- **Configuration read lazily,** so a typo surfaces in production at 3 a.m.

## Review checklist

1. Can a new service go from zero to deployed with the baseline in a day?
2. Does the chassis contain only technical concerns, and is it versioned?
3. Which baseline concerns does the platform provide, and are they left out of the chassis?
4. Does every service validate its configuration at startup?
5. Does every service meet the baseline table above?

## Related

[anti-patterns](anti-patterns.md), [`kubernetes`](../../kubernetes/SKILL.md),
[`github-actions`](../../github-actions/SKILL.md) (the pipeline in the template).

## Sources

microservices.io: [Microservice chassis](https://microservices.io/patterns/microservice-chassis.html),
[Service template](https://microservices.io/patterns/service-template.html),
[Externalized configuration](https://microservices.io/patterns/externalized-configuration.html),
and the observability patterns ([log aggregation](https://microservices.io/patterns/observability/application-logging.html),
[distributed tracing](https://microservices.io/patterns/observability/distributed-tracing.html),
[health check API](https://microservices.io/patterns/observability/health-check-api.html),
[log deployments and changes](https://microservices.io/patterns/observability/log-deployments-and-changes.html)).
The Twelve-Factor App, [Config](https://12factor.net/config).
