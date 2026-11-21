---
name: secure-reliable-systems
description: Where security and reliability meet - project-agnostic, after Building Secure and Reliable Systems. Covers controls that cause outages and the reverse; admin access for people, agents and automation via safe proxies, narrow admin APIs, multi-party approval, tested break-glass; credential lifecycle (short-lived tokens, zero-downtime rotation, expiry chains, revocation, rollback protection, lost credentials); blast radius, rebuild after compromise, tamper-resistant audit logs, security crises; understandable identities; DoS defence; security-fix rollouts, deploy provenance; crawler and client fleets as good citizens (identification, robots.txt, opt-outs, abuse reports). Use when designing admin access, credentials, recovery paths or an outbound fleet, or when a security response could cause an outage. Not for app security requirements (see owasp-asvs), secrets, dependencies or threat modeling (see engineering-practices), backups (see data-integrity), or outage response (see production-operations).
---

# Secure and Reliable Systems

Security and reliability fail in the same places: the admin path, the credential that expires,
the recovery plan nobody ran, the control that turns a small fault into a long outage. The
difference is the adversary. Reliability plans for accidents; security assumes someone is
trying to cause the failure and is watching your response (BSRS ch. 1). This skill covers the
system-level decisions where the two meet. It is grounded in Google's
[*Building Secure and Reliable Systems*](https://google.github.io/building-secure-and-reliable-systems/)
(BSRS), paraphrased, with RFC 9309, SLSA, Sigstore and the Kubernetes security docs.

It is deliberately small. Application controls are in [`owasp-asvs`](../owasp-asvs/SKILL.md);
day-to-day secrets, dependencies and threat modeling in
[`engineering-practices` security-practices](../engineering-practices/references/security-practices.md);
deriving a minimal grant in [`core-principles` least-privilege](../core-principles/references/least-privilege.md);
backups and credential recovery copies in [`data-integrity`](../data-integrity/SKILL.md); running
an incident in [`production-operations`](../production-operations/SKILL.md).

## How to use this skill

1. Read **Where security and reliability trade off** below for any design that adds a control
   or a recovery path. It is the core of the skill.
2. Match the task to one row of the catalog and read that reference. Don't load all four.
3. Each reference leads with what agents get wrong and ends with a numbered review checklist;
   in a review, walk the checklist and report the failing items with their concrete cost.

## The catalog

| Topic | Read when | Reference |
|---|---|---|
| Admin access | Designing how people, agents or automation change production; shell access; approvals; break-glass | [admin-access-and-safe-proxies](references/admin-access-and-safe-proxies.md) |
| Credentials | A token, key or certificate is issued, rotated, expires, is revoked or lost; rollback protection | [credential-lifecycle-and-rotation](references/credential-lifecycle-and-rotation.md) |
| Compromise | Limiting blast radius; audit logs an actor can't erase; a suspected intrusion; rebuild versus clean | [compromise-recovery-and-forensics](references/compromise-recovery-and-forensics.md) |
| Abuse and outbound traffic | DoS defence for your services; a crawler, scraper or client fleet hitting other people's sites; robots.txt; an abuse report | [abuse-dos-and-good-citizenship](references/abuse-dos-and-good-citizenship.md) |

## Symptom to reference

| You see | Read |
|---|---|
| Engineers or agents use SSH, `kubectl exec` or a shared admin kubeconfig to fix things | [admin-access](references/admin-access-and-safe-proxies.md) |
| Nobody can say which agent or job ran a command | [admin-access](references/admin-access-and-safe-proxies.md) |
| Break-glass exists but hasn't been used or tested in months, or is used weekly | [admin-access](references/admin-access-and-safe-proxies.md) |
| A token's only copy was on a volume someone deleted | [credentials](references/credential-lifecycle-and-rotation.md) |
| An expired registry, CI or cloud token blocked deploys, rebuilds or node replacement | [credentials](references/credential-lifecycle-and-rotation.md) |
| Rotating a key means a maintenance window | [credentials](references/credential-lifecycle-and-rotation.md) |
| A rollback could reinstall a version with a known vulnerability | [credentials](references/credential-lifecycle-and-rotation.md) |
| One credential works in every region, environment or tenant | [compromise](references/compromise-recovery-and-forensics.md) |
| Audit logs sit on the host they describe, or are kept for days | [compromise](references/compromise-recovery-and-forensics.md) |
| A suspected intrusion and the instinct is to log in and clean up | [compromise](references/compromise-recovery-and-forensics.md) |
| A survey script or crawler fetched pages robots.txt disallows | [abuse-and-outbound](references/abuse-dos-and-good-citizenship.md) |
| A site's CERT reported your crawler to your hosting provider | [abuse-and-outbound](references/abuse-dos-and-good-citizenship.md) |
| A traffic flood, or your own clients' retries, overload a service | [abuse-and-outbound](references/abuse-dos-and-good-citizenship.md) |

## Where security and reliability trade off

Every control is also a new failure mode, and every recovery shortcut is a new way in. Price
both directions before adding either (BSRS ch. 1, 4, 8). Examples in this skill's own layout:

| Control or measure | How it hurts the other side | Mitigation |
|---|---|---|
| Hardware-backed keys, safes, offline secrets | A restart needs a smart card from a safe whose combination is stored in the system that is down; BSRS ch. 1 tells of a drill through a safe | Recovery path with no dependency on the failed system; drill it |
| SSO and MFA in front of every admin action | Identity provider down, nobody can get in to fix it | Break-glass credentials outside SSO, alarmed and tested |
| Fail closed (authz, revocation, deploy policy) | A bug in the policy or its service denies everyone | Dry-run mode first, cached last-known-good policy, loud break-glass |
| Short credential lifetimes | A failed renewal is an outage | Automatic renewal, alerts on renewal failure, overlap |
| Deploy admission that rejects unprovenanced images | A provenance bug blocks the emergency fix | Roll out in audit mode, actionable errors, break-glass with re-check |
| DoS blocking by IP | Blocks offices and mobile carriers behind shared IPs | Challenge instead of block; bypass tokens for solved challenges |
| Logging everything | Log volume exhausts memory or disk; logs leak secrets | Budgets, degrade collection rather than stop, redaction |
| Retry queue for a failing provider | Persists sensitive data to disk, a new target (BSRS ch. 4) | Encrypt or don't persist; short retention |
| Redundant paths and failover providers | More ways in; the attacker needs only one (BSRS ch. 1) | Same controls on every path; test the standby |
| Many responders in an incident | Leaks the response to an attacker who is watching | Need-to-know for security incidents |
| Debug endpoints and impersonation tools | A privileged path around normal authorization | Behind authorization and audit, like any admin operation |

Rules that follow: decide fail-open versus fail-closed per operation, write it down, and give the
closed path a narrow, loud exception. Security-critical operations generally don't fail open
(BSRS ch. 8). Make the emergency path the normal path run faster, so it's exercised every day
(BSRS ch. 9).

## Understandable systems

A system you can't reason about can't be shown to be secure or reliable (BSRS ch. 6).

- **Write the invariants down:** "every write to the store is authorized and audited", "no job
  reads another tenant's keys", "load can't cascade past this tier". Each one should be checked
  by a test, a validator or a type, not by memory.
- **Keep mental models predictive under stress.** Prefer designs that fail in one obvious way
  under overload or attack (BSRS ch. 6's example: no swap, so memory pressure fails fast rather
  than thrashing).
- **Identities** should be readable (role and environment in the name), hard to spoof
  (certificate-backed, not a bearer token in clear text), never reused (a departed admin's name
  handed to a new hire inherits their grants), and cover workloads and agents, not only people.
- **Authorization declared in one framework,** not hand-written per handler, so policy can be
  reviewed and analysed. Authentication and transport security come from the platform.
- **Keep the trusted computing base small.** Split components so a bug in one can't break the
  policy protecting another (separate stores, separate origins).
- **Narrow, typed interfaces** at every boundary; validated types instead of strings, so a
  reviewer checks constructors and sinks, not every path in between.

## Changing safely: security fixes and deploy policy

**Security changes are releases** (BSRS ch. 7): small, behind a flag, tested, staged with
canaries. Rebuild and release often so an emergency patch rides a path that runs daily. Patch
images, not running containers; track image age. For a zero-day, keep an accelerated but still
validated pipeline, find unpatched systems, and assume an embargo can break early. Raising a
requirement across a fleet goes group by group, audit mode before enforcement, with the long tail
tracked.

**Verify artifacts, not just people** (BSRS ch. 14):

1. Every build produces signed provenance: source, dependencies, commands, environment.
   [SLSA v1.0](https://slsa.dev/spec/v1.0/levels) build levels: L1 provenance exists, L2 a hosted
   platform signs it, L3 a hardened platform keeps signing keys away from build steps (the v1.0
   page is now marked retired in favour of a newer version).
2. Signing can be keyless: [Sigstore](https://docs.sigstore.dev/about/overview/) issues a
   short-lived certificate for an OIDC identity and records the signature in a transparency log.
   Verify the signature, the expected identity and the log inclusion, not only that a signature
   exists.
3. One choke point enforces deploy policy (a Kubernetes admission controller, or a proxy in front
   of the deploy API), and nothing deploys around it.
4. Start in dry-run, give rejections that say how to fix them, attach provenance to the artifact
   rather than looking it up, apply exactly one policy per deployment.
5. Keep a break-glass bypass, alarmed and audited, and log enough to re-check deployments later.

Build mechanics belong to `build-systems`, [`container-images`](../container-images/SKILL.md) and
[`github-actions`](../github-actions/SKILL.md); dependency pinning to `engineering-practices`.

## Working rules

1. **Price both directions.** For each control, name the outage it can cause; for each recovery
   path, name who else can use it.
2. **No path into production without an audit record,** for humans, agents and automation alike.
3. **Every emergency path is tested on a schedule.** An untested break-glass or rotation runbook
   counts as missing.
4. **Every credential has an owner, an expiry, a re-issue path and a recovery copy** outside the
   systems it unlocks.
5. **Assume an observer during a security incident.** Preserve, investigate, then evict in one
   coordinated operation, rotating credentials in a planned order (synthesis on BSRS ch. 17-18).
6. **Be identifiable and stoppable** on other people's systems. A block is an answer.

## Related

- [`core-principles`](../core-principles/SKILL.md): least privilege and fail-fast as design heuristics.
- [`engineering-practices`](../engineering-practices/SKILL.md): security-practices (secrets, leaks, dependencies, threat modeling), reliability (retries, postmortems), release-engineering (flags, canaries).
- [`owasp-asvs`](../owasp-asvs/SKILL.md): application security requirements.
- [`data-integrity`](../data-integrity/SKILL.md): backups, disaster recovery, credential recovery copies, safe deletion.
- [`production-operations`](../production-operations/SKILL.md): incident response, expiry alerts, runbooks.
- [`infrastructure-patterns`](../infrastructure-patterns/SKILL.md): rate limiting, load shedding, cells.
- [`data-pipelines`](../data-pipelines/SKILL.md): per-source pacing for crawler fleets.
- [`architecture-review`](../architecture-review/SKILL.md), [`system-design`](../system-design/SKILL.md): reviewing and sizing whole systems.
- [`structured-logging`](../structured-logging/SKILL.md): log record format.

## Sources

BSRS raw chapters, paraphrased:
[1](https://google.github.io/building-secure-and-reliable-systems/raw/ch01.html),
[3](https://google.github.io/building-secure-and-reliable-systems/raw/ch03.html),
[4](https://google.github.io/building-secure-and-reliable-systems/raw/ch04.html),
[5](https://google.github.io/building-secure-and-reliable-systems/raw/ch05.html),
[6](https://google.github.io/building-secure-and-reliable-systems/raw/ch06.html),
[7](https://google.github.io/building-secure-and-reliable-systems/raw/ch07.html),
[8](https://google.github.io/building-secure-and-reliable-systems/raw/ch08.html),
[9](https://google.github.io/building-secure-and-reliable-systems/raw/ch09.html),
[10](https://google.github.io/building-secure-and-reliable-systems/raw/ch10.html),
[14](https://google.github.io/building-secure-and-reliable-systems/raw/ch14.html),
[15](https://google.github.io/building-secure-and-reliable-systems/raw/ch15.html),
[17](https://google.github.io/building-secure-and-reliable-systems/raw/ch17.html),
[18](https://google.github.io/building-secure-and-reliable-systems/raw/ch18.html);
[SLSA v1.0 levels](https://slsa.dev/spec/v1.0/levels);
[Sigstore overview](https://docs.sigstore.dev/about/overview/). Each reference lists its own.
The tradeoff table and the working rules are this skill's synthesis.
