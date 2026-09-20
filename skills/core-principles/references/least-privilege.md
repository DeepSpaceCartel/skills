# Least Privilege

Give components only the permissions they need. The practical question:
**What happens if this component is compromised?**

Saltzer & Schroeder
([The Protection of Information in Computer Systems, 1975](https://web.mit.edu/Saltzer/www/publications/protection/Basic.html)):
"Every program and every user of the system should operate using the least set
of privileges necessary to complete the job." NIST SP 800-53 AC-6 applies it to
processes acting on behalf of users, not only people. The same paper warns that
its principles "do not represent absolute rules": they serve best as warnings.

## Procedure: derive the minimal set

1. **Ask the blast-radius question:** if this component, or a prompt-injected
   agent, is fully controlled by an attacker, what can it read, write, delete,
   spend or reach?
2. **Enumerate the real needs:** actions, resources, network peers, files,
   secrets.
3. **Start at zero:** `permissions: {}`, deny-all egress, read-only filesystem,
   no tools.
4. **Add the smallest grant that fixes a specific failure.** Read the error and
   add exactly what it names. Never widen to the wildcard.
5. **Generate from observed use** where a tool exists (an access analyzer over
   audit logs) and test before deploying.
6. **Scope everything:** actions *and* resources *and* conditions. `s3:*` on one
   bucket and `s3:GetObject` on `*` are both over-broad.
7. **Make it time-bound:** short-lived credentials (federation, OIDC),
   per-session tokens, expiry dates on exceptions.
8. **One identity per workload,** and separate read and write identities where
   code paths differ.
9. **Review periodically** and remove unused permissions (privilege creep).

## Where to apply it

- **Identities:** IAM roles, DB users (`GRANT SELECT` on named tables, not the
  owner), Kubernetes RBAC and ServiceAccounts
- **Network:** deny-by-default egress, per-service security groups
- **Filesystem and process:** non-root user, read-only root filesystem, dropped
  Linux capabilities, never `--privileged`
- **Tokens:** narrow OAuth scopes; CI `permissions:` (setting any one leaves the
  rest at none)
- **Code:** private-by-default visibility, narrow interfaces, passing a handle
  instead of a global admin client
- **Agents:** an allowlist of tools, granular tools instead of a generic shell or
  URL fetch, credentials kept outside the sandbox

## Detection signals

- `"Action": "*"`, `"Resource": "*"`, `Principal: "*"`, `AdministratorAccess`
- `chmod 777`, `USER root`, `privileged: true`, a mounted `docker.sock`,
  `cap_add: ALL`
- Wildcard RBAC verbs, `cluster-admin` bindings
- Long-lived static keys; one credential shared by several services
- Roles with no recent use; comments like "TODO tighten" or "temporary"

## Example

```json
// before: the "AccessDenied, so I widened it" pattern
{"Effect": "Allow", "Action": "s3:*", "Resource": "*"}

// after: a function that reads uploads
{"Effect": "Allow", "Action": ["s3:GetObject"],
 "Resource": "arn:aws:s3:::uploads-prod/incoming/*"}
```

A compromised function can no longer read other buckets, delete objects or
change bucket policy. The code-level equivalent: hand a report generator a
read-only repository (or a scoped token) instead of the shared admin DB client.

## Gotchas

- **Agents reach for admin, `*`, root, 0777 or `--privileged` to "make it
  work"** and then never narrow. "Temporary" grants become permanent.
- **It applies to services, CI jobs and AI agents,** not just humans.
- **Shrinking permissions doesn't fix a confused deputy:** a program tricked
  into using its own authority on behalf of a caller who lacks it. Pass a
  capability that bundles designation and authority (an open file descriptor, a
  scoped token) rather than a name resolved under ambient authority.
- **Watch escalation paths:** `iam:PassRole`, `iam:*`, and anything that can edit
  its own policy.
- **Instructions are not enforcement.** "The agent is told not to" is a
  probabilistic guardrail; enforce in the system that holds the resource
  (OWASP LLM06 Excessive Agency), and contain at the environment layer.
- **A generic shell, URL-fetch or `run_sql` tool defeats it.**
- **Cost:** per-call micro-policies create sprawl, drift and outages. Prefer a few
  well-named role tiers, scale strictness with blast radius, and roll out with an
  audit or dry-run mode first. Throwaway, network-isolated sandboxes with no real
  credentials can be broad: bound the environment instead.
- **It bounds damage; it doesn't replace authentication and authorization.**
- **Tensions:** `kiss` (sprawl), usability (a painful secure path gets bypassed).

## Review checklist

1. If this component or agent is compromised, is the blast radius one bucket, table or namespace, not the account or cluster?
2. Are all actions and resources named, with no `*`, root or admin (or a justification for each)?
3. Are credentials short-lived and scoped per workload?
4. Did the permissions come from observed need, with an owner and review date for each exception?
5. Is authorization enforced where the resource lives, not in a prompt or the client?
6. Does code pass narrow handles instead of global admin clients, and are agent tools granular?

## Related

- [`owasp-asvs`](../../owasp-asvs/SKILL.md) — authorization and access-control requirements for whole applications.
- [`github-actions`](../../github-actions/SKILL.md) — `permissions:`, tokens and OIDC in CI.
- [`container-images`](../../container-images/SKILL.md) — non-root users and minimal images.
- `defensive-programming` — assume dependencies can fail; least privilege assumes components can be *compromised*.
