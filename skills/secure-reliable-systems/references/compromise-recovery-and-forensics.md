# Compromise, recovery and forensics

Limiting how far a compromise spreads, keeping the evidence needed to investigate it, and
running a security incident through to a clean rebuild. Restoring data from backups is in
[`data-integrity`](../../data-integrity/SKILL.md); the incident roles, state document and
mitigate-first habits shared with outages are in
[`production-operations` incident-response](../../production-operations/references/incident-response.md);
log record format is in [`structured-logging`](../../structured-logging/SKILL.md). This page
covers what is different when there is an adversary. Anchor sources:
[BSRS ch. 8, Design for Resilience](https://google.github.io/building-secure-and-reliable-systems/raw/ch08.html),
[ch. 9, Design for Recovery](https://google.github.io/building-secure-and-reliable-systems/raw/ch09.html),
[ch. 15, Investigating Systems](https://google.github.io/building-secure-and-reliable-systems/raw/ch15.html),
[ch. 17, Crisis Management](https://google.github.io/building-secure-and-reliable-systems/raw/ch17.html),
[ch. 18, Recovery and Aftermath](https://google.github.io/building-secure-and-reliable-systems/raw/ch18.html).

## What agents typically get wrong

- **Treating a compromise like an outage.** Outage response says mitigate fast and involve many
  people. A watching attacker learns from each visible move: locking one account, deleting a
  file or shutting down one host tells them what you've found, and they change course (BSRS ch.
  17).
- **Debugging steps that destroy evidence:** deleting the unfamiliar file, restarting the odd
  process, "cleaning up" before imaging (BSRS ch. 15).
- **Logging into the compromised host** to look around, with an admin credential the attacker
  may then capture.
- **Coordinating in a channel the attacker can read**: the compromised company chat or email.
- **Cleaning in place** instead of rebuilding from a known-good source. You rarely find every
  piece of what was planted (BSRS ch. 18).
- **Restoring from a tainted source:** the golden image, the repo or the backup that already
  carries the attacker's change (BSRS ch. 18).
- **Logs the attacker can erase.** Audit records on the same host, writable by the same
  credential that did the damage, kept for two weeks when intrusions often go unnoticed for months.
- **One credential that reaches every region, environment and tenant,** so one leak is total.

## Procedure

**Before: contain the blast radius and be ready to investigate**

1. **Separate by role:** one identity per job, so one compromised job doesn't reach the rest
   (BSRS ch. 8).
2. **Separate by location:** credentials and encryption keys scoped to a region, cluster or
   environment, so a local compromise stays local (BSRS ch. 8).
3. **Separate by time:** credentials that expire and rotate, so stolen access decays (see
   [credential-lifecycle-and-rotation](credential-lifecycle-and-rotation.md)).
4. **Test the walls:** run checks that cross-compartment calls fail, and alert when one
   unexpectedly succeeds (BSRS ch. 8).
5. **Ship security logs off the host** to a store the producing workload can append to but not
   modify or delete, with its own access controls and its own audit trail (BSRS ch. 15).
6. **Set retention from dwell time,** not from disk cost: long enough to look back across a
   compromise found months later. Keep summaries longer than full records (BSRS ch. 15).
7. **Know your intended state** (BSRS ch. 9): configuration as code, images by digest,
   provenance on every artifact, so you can rebuild and so you can diff what you find against
   what should be there.
8. **Pre-stage forensic tooling** (remote collection agents) so nobody needs to log into a
   suspect machine (BSRS ch. 17).

**During: a suspected compromise**

1. **Triage:** false positive, contained bug, or attacker? Ask what the system can reach, what
   trusts it, and whether other controls still hold (BSRS ch. 17).
2. **Declare and bring in security early.** Use the [`production-operations`](../../production-operations/SKILL.md) roles, with these
   changes: need-to-know membership, written confidentiality rules each responder acknowledges,
   and a clean out-of-band channel.
3. **Preserve before touching:** snapshot disks and memory, export logs, record hashes. Write
   indicators defanged (`example[.]com`), since chat tools that fetch links can contact the
   attacker's infrastructure (BSRS ch. 17).
4. **Investigate quietly** until you understand the attacker's access: entry point, credentials
   taken, persistence, other affected systems. Act early only when harm is ongoing and the
   decision-maker accepts the tip-off (BSRS ch. 17).
5. **Plan the eviction as one coordinated move** with a separate remediation lead and team
   (BSRS ch. 18): scope every affected system and anything downstream of it, check variants of
   the same flaw elsewhere, confirm the recovery tooling itself is clean, and write a checklist
   with commands, order and rollback steps.
6. **Execute as one coordinated operation** (synthesis on ch. 17 and 18): quarantine, close the
   entry point, rebuild from known-good sources, and rotate what the attacker could reach in a
   planned order (administrators and signing keys first, not everything at once). Piecemeal moves
   over days give the attacker time to adapt.
7. **Verify and watch:** compare rebuilt systems with intended state, and watch for the
   attacker's return through the old routes.

## Techniques

**How a security incident differs** (BSRS ch. 1, 17, 18):

| Aspect | Outage | Security incident |
|---|---|---|
| Who joins | Anyone who can help | Need-to-know; confidentiality rules acknowledged |
| Channel | The usual chat or call | Out-of-band, on infrastructure the attacker can't see |
| First move | Mitigate now | Understand first, unless harm is ongoing |
| Evidence | Nice to keep | Preserve before any change; it may be needed legally |
| Fix | Roll back, restart | Coordinated eviction, then rebuild from known-good |
| Teams | One operations lead | Investigation and remediation in parallel, under one IC |
| Afterwards | Postmortem | Postmortem, plus disclosure and legal duties where they apply |

**Rebuild versus clean** (BSRS ch. 18). Rebuild by default: reinstall from images and sources
whose provenance you trust, then restore data that passed integrity checks. That works only if
builds are reproducible enough and deploys are automated; a team without that has to build it
during recovery. Check source, binaries, images and configuration against known-good digests,
and find when tampering began, which may push the restore point further back.

**Tamper-resistant audit logs** (synthesis on BSRS ch. 15). Layers, cheapest first: ship off the
host immediately; write to an append-only or object-locked store; separate the identity that
writes from the identity that can delete or change retention; audit access to the logs
themselves; chain records by hash and copy the chain's head somewhere else. A hash chain alone is
only tamper-evident if its head is anchored outside the writer's reach; an attacker who controls
the writer can rebuild a consistent chain.

**Debugging access** (BSRS ch. 15). Impersonation tools, raw database access and debug
endpoints are themselves privileged paths: put them behind authorization and audit, and keep
offline emergency credentials for the logging and security systems in case those break.

**Privacy.** Decide what may be logged with privacy and legal input; pseudonymize where a
timeline survives without the identity; never log credentials (BSRS ch. 1, 15).

## Example

A hash-chained audit log whose head is shipped to a separate store. Editing a record breaks the
chain; truncating or rebuilding it is caught only by comparing with the anchored head.

```python
import hashlib, json

def append(log, record):
    prev = log[-1]["hash"] if log else "0" * 64
    body = json.dumps(record, sort_keys=True)
    log.append({"prev": prev, "body": body,
                "hash": hashlib.sha256((prev + body).encode()).hexdigest()})
    return log[-1]["hash"]          # copy this head to a store the writer can't edit

def verify(log, anchored_head):
    prev = "0" * 64
    for i, e in enumerate(log):
        if e["prev"] != prev or hashlib.sha256((prev + e["body"]).encode()).hexdigest() != e["hash"]:
            return f"broken at record {i}"
        prev = e["hash"]
    return "ok" if prev == anchored_head else "head does not match the anchored copy"
```

Run with three records (a drain, an agent restart, a secret read): the intact log verified; an
edited second record gave `broken at record 1`; dropping the last record and a fully rebuilt
two-record chain both verified internally but failed against the anchored head. Without the
anchor, the rebuilt chain passed, which is the point of anchoring.

## Gotchas and contested points

- **OpSec versus the greater good.** Sometimes the right call is a visible shutdown that tips the
  attacker off, because the harm is imminent. That is a decision for the accountable executive,
  advised by the IC (BSRS ch. 17).
- **Waiting has a cost too.** Each hour of quiet investigation is an hour of attacker access.
  The IC decides when new leads have slowed enough to move to eviction (BSRS ch. 17).
- **Compartments cost.** Too few protect little; too many are hard to run. Imperfect walls still
  slow an attacker and buy time (BSRS ch. 8).
- **Logging can cause outages** and costs money: a logging change once exhausted memory under
  production load (BSRS ch. 1). Budget for logs and let collection degrade rather than stop when
  storage fills (BSRS ch. 15).
- **Quarantined hosts left online** are a risk; label them and track them until rebuilt
  (BSRS ch. 18).
- **Shift length.** Security incidents run for days; keep shifts to about 12 hours and plan
  handovers (BSRS ch. 17).

## Review checklist

1. Are credentials and keys scoped by role, location and time, so one leak doesn't reach every
   region, environment or tenant?
2. Do automated checks confirm that cross-compartment access fails, and alert when it succeeds?
3. Do security and audit logs leave the host at once, into a store the actor they record can't
   modify or delete, with access to the logs itself audited?
4. Is log retention set from how long a compromise could go unnoticed?
5. Is intended state (config, image digests, provenance) recorded well enough to rebuild from it
   and to diff a suspect system against it?
6. Is there a written security-incident variant: out-of-band channel, need-to-know list,
   evidence preservation, no logins to suspect hosts?
7. Does the recovery plan rebuild from known-good sources, check those sources for tampering,
   and evict in one coordinated operation with an ordered rotation plan?
8. Is credential rotation after a compromise ordered by what the attacker could reach?

## Related

[admin-access-and-safe-proxies](admin-access-and-safe-proxies.md),
[credential-lifecycle-and-rotation](credential-lifecycle-and-rotation.md),
[`production-operations` incident-response](../../production-operations/references/incident-response.md),
[`data-integrity` disaster-recovery](../../data-integrity/references/disaster-recovery.md),
[`structured-logging`](../../structured-logging/SKILL.md),
[`engineering-practices` reliability](../../engineering-practices/references/reliability.md)
(postmortems).

## Sources

BSRS [ch. 1](https://google.github.io/building-secure-and-reliable-systems/raw/ch01.html),
[ch. 8](https://google.github.io/building-secure-and-reliable-systems/raw/ch08.html),
[ch. 9](https://google.github.io/building-secure-and-reliable-systems/raw/ch09.html),
[ch. 15](https://google.github.io/building-secure-and-reliable-systems/raw/ch15.html),
[ch. 17](https://google.github.io/building-secure-and-reliable-systems/raw/ch17.html),
[ch. 18](https://google.github.io/building-secure-and-reliable-systems/raw/ch18.html), paraphrased.
The outage-versus-security table, the audit-log layers and the hash-chain code are this skill's
synthesis.
