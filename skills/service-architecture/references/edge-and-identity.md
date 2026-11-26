# The edge: gateways, BFFs, identity, discovery, UI composition

## Problem

Clients shouldn't know how the system is split into services. If they call services directly,
every split, merge or move breaks them. Mobile clients on slow networks pay for each extra round
trip. Each service would also repeat authentication, rate limiting and protocol translation. The
edge is where those concerns are handled once.

## API gateway

A single entry point for external clients. It routes some requests to one service, fans others
out and aggregates the results ([API composition](collaboration.md)), and handles the edge
concerns: TLS termination, authentication, rate limits, request size limits, protocol
translation (for example, HTTP/JSON outside and gRPC inside).

- **Benefits:** clients are insulated from service boundaries and locations; fewer round trips;
  edge concerns live in one place.
- **Costs:** one more component to build, run and keep highly available; one more hop; a risk
  of becoming a shared bottleneck that every team must change.
- **Keep business logic out.** A gateway that grows rules becomes a monolith every team must
  edit. Routing, aggregation and edge policy only.

Timeouts and retries at the gateway must agree with the services behind it; see
[`infrastructure-patterns` timeouts-and-retries-infra](../../infrastructure-patterns/references/timeouts-and-retries-infra.md).

## Backends for frontends (BFF)

A separate gateway per *user experience*, owned by the team that builds that UI.

- **When:** different clients need different shapes, amounts of data or release cadences
  (mobile vs web vs partner API); one general-purpose API keeps being bent for one client at
  the others' expense.
- **Granularity:** one experience, one BFF. iOS and Android may share one when their screens
  match; a partner API usually gets its own.
- **Ownership:** the UI team owns its BFF and changes it in the same release as the UI. That's
  the point; a BFF owned by a central team is just a second gateway.
- **Duplication** between BFFs is acceptable. Extract shared logic only when it repeats a third
  time, and preferably into a downstream service rather than a shared library.
- **Partial failure:** a BFF aggregates, so design for one source failing. Return what you have
  with the missing part marked, and make the client render partial responses.
- **Skip it** for a single web UI that needs little server-side aggregation. For mobile or
  third-party consumers, plan for one from the start.

## Identity propagation

Inner services must know who the caller is, without each one re-authenticating the user.

1. The gateway or BFF **authenticates** the request (session, OAuth 2.0 / OIDC).
2. It passes a **token** to inner services: a short-lived, signed access token (JWT or similar)
   carrying the subject and the claims needed for authorisation.
3. Each service **validates the token itself** (signature, issuer, audience, expiry) and makes
   its own authorisation decision. The gateway authenticates; services authorise.
4. When a service calls another on the user's behalf, it forwards the token or exchanges it
   (OAuth 2.0 token exchange) for one scoped to the next service. Service-to-service calls
   without a user use the service's own identity (mTLS, workload identity).

Never pass identity in a plain header like `X-User-Id` that inner services trust because "only
the gateway can reach them". One misrouted request or one compromised pod and it's spoofable.
Token content and validation rules are in [`owasp-asvs`](../../owasp-asvs/SKILL.md) (V9
self-contained tokens); credential lifetimes and rotation in
[`secure-reliable-systems`](../../secure-reliable-systems/SKILL.md).

## Service discovery

Clients of a service need its instances' current addresses. Two approaches:

| | Server-side (platform) | Client-side (library) |
|---|---|---|
| How | Call a stable name; a load balancer or proxy resolves instances | The client queries a registry and picks an instance |
| Examples | Kubernetes Services and DNS, cloud load balancers, a service mesh | Consul or etcd clients, older Eureka/Ribbon setups |
| Trade-off | Simple clients, one extra hop, platform-provided | No extra hop; a discovery library per language |

On Kubernetes or a managed platform, use the platform's discovery and don't add a registry.
Registration happens automatically (the platform registers instances: third-party
registration) instead of each instance registering itself. See
[`kubernetes`](../../kubernetes/SKILL.md) and
[`infrastructure-patterns` load-balancing](../../infrastructure-patterns/references/load-balancing.md).

## UI composition

When teams own capabilities end to end, a page can show regions owned by different teams:

- **Server-side fragment composition:** each team's web app renders an HTML fragment; a page
  template assembles them (edge or server includes).
- **Client-side composition** (micro-frontends): each team ships a UI component; a shell
  composes them in the browser.

Both are worth their cost only when several teams must release parts of the same screen
independently. Otherwise one UI team calling a BFF is simpler. If you do compose: one design
system, one shared shell, no runtime dependencies between fragments, and a budget for total
page weight.

## What agents get wrong

- **A gateway full of business rules,** or one central team that owns every route.
- **One BFF per device model** (or one BFF shared by every client). The unit is the user
  experience.
- **Trusting an identity header.** Validate a signed token in every service.
- **Adding a service registry on Kubernetes.** The platform already does discovery.
- **Micro-frontends for a single team.** They add the costs of distribution to the UI.

## Review checklist

1. Do clients depend on service boundaries or locations anywhere?
2. Is the gateway limited to routing, aggregation and edge policy?
3. Is each BFF owned by the team that owns its UI, and does it handle partial failure?
4. Does every service validate the caller's token itself, and are tokens short-lived and scoped?
5. Are gateway timeouts and retries consistent with the services behind it?
6. Is discovery the platform's, with no hand-rolled registry?
7. If the UI is composed, which teams release parts of the same page independently, and is that
   worth the cost?

## Related

[collaboration](collaboration.md), [`openapi`](../../openapi/SKILL.md) and
[`jsonapi`](../../jsonapi/SKILL.md) (the external API's contract),
[`rfc9457`](../../rfc9457/SKILL.md) (error responses at the edge),
[`infrastructure-patterns` rate-limiting-and-throttling](../../infrastructure-patterns/references/rate-limiting-and-throttling.md).

## Sources

microservices.io: [API gateway / Backends for frontends](https://microservices.io/patterns/apigateway.html),
[Access token](https://microservices.io/patterns/security/access-token.html),
[Client-side discovery](https://microservices.io/patterns/client-side-discovery.html),
[Server-side discovery](https://microservices.io/patterns/server-side-discovery.html),
[Server-side page fragment composition](https://microservices.io/patterns/ui/server-side-page-fragment-composition.html),
[Client-side UI composition](https://microservices.io/patterns/ui/client-side-ui-composition.html).
Sam Newman, [Backends For Frontends](https://samnewman.io/patterns/architectural/bff/). OAuth 2.0
Token Exchange, [RFC 8693](https://www.rfc-editor.org/rfc/rfc8693).
