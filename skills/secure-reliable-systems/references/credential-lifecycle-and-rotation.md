# Credential lifecycle and rotation

Keeping credentials, keys and certificates working and trustworthy over time: preferring
short-lived ones, rotating without downtime, knowing what depends on each one, revoking at
scale, guarding rollbacks, and getting back in after a credential is lost. Day-to-day secret
handling and leak response are in
[`engineering-practices` security-practices](../../engineering-practices/references/security-practices.md);
expiry alert thresholds and the deadline inventory's metrics are in
[`production-operations` monitoring-and-alerting](../../production-operations/references/monitoring-and-alerting.md);
where recovery copies live is in
[`data-integrity` disaster-recovery](../../data-integrity/references/disaster-recovery.md).
Anchor sources: [BSRS ch. 7](https://google.github.io/building-secure-and-reliable-systems/raw/ch07.html),
[ch. 8](https://google.github.io/building-secure-and-reliable-systems/raw/ch08.html) and
[ch. 9](https://google.github.io/building-secure-and-reliable-systems/raw/ch09.html), and the
Kubernetes pages on [service accounts](https://kubernetes.io/docs/concepts/security/service-accounts/),
[projected volumes](https://kubernetes.io/docs/concepts/storage/projected-volumes/) and
[secrets good practices](https://kubernetes.io/docs/concepts/security/secrets-good-practices/).

## What agents typically get wrong

- **The only copy of a credential on a working volume.** A coordinator's API token lives in a
  workspace or pod volume. A cleanup deletes the volume. There is no re-issue path, no recovery
  copy and no runbook, so the service it unlocked is out of reach.
- **A credential nobody knew was on the critical path.** A registry pull or push token expires
  quietly. Image pushes fail, and so does everything that builds or replaces a machine: node
  replacement, workspace teardown and rebuild, disaster recovery. The expiry blocks the very
  steps you'd use to fix it.
- **Rotation as a one-step swap.** The new key replaces the old one everywhere at once. Tokens
  signed with the old key are rejected, and verifiers that haven't reloaded reject the new ones.
- **Rotation never practised.** The first rotation happens during a compromise, under pressure.
  BSRS ch. 7's Heartbleed lessons: rotate regularly so the emergency swap is routine.
- **Static, long-lived tokens where short-lived ones exist.** Legacy Kubernetes Secret-based
  service account tokens don't expire or rotate; projected tokens do.
- **Disabling certificate or expiry checks to get past a clock or expiry problem** (BSRS ch. 9
  warns against it).
- **A revocation check that fails open** when the revocation service is down. An attacker who
  can cause that outage gets their revoked credential back (BSRS ch. 9).
- **Rollback to any old version,** which brings back known vulnerabilities and old trust.

## Procedure

1. **Inventory every credential** (synthesis): what it is, what it unlocks, who issued it, its
   expiry, its owner, where the primary and recovery copies live, how it's re-issued, and **what
   depends on it** (deploys, builds, node bootstrap, backups, DR). Feed the expiry dates into the
   deadline alerts in [`production-operations`](../../production-operations/SKILL.md).
2. **Trace the dependency chain** for each one: if it expired now, what stops, and does
   anything you'd need to fix it stop too? A credential that blocks its own renewal path (the
   registry token the rebuild needs, the SSO the vault login needs) gets a break-glass copy and
   an earlier alert.
3. **Prefer short-lived and re-issuable** over copied: workload identity, OIDC federation,
   Kubernetes projected tokens, certificates from an automated issuer. Something an identity
   provider can mint again can't be lost the way a one-off token can.
4. **Rotate in overlapping phases** (below), and automate it so it runs on a schedule.
5. **Practise emergency rotation** of the important keys at least once, timed, and keep the
   runbook beside the inventory.
6. **Design revocation** before you need it (techniques below).
7. **Guard rollback** with a security version floor, not a free-for-all (techniques below).
8. **After a loss:** re-issue from the source of truth (the provider console, the identity
   system), revoke the lost copy, update every consumer, then write the missing recovery copy and
   runbook so it can't happen the same way twice.

## Techniques

**Overlapping rotation** (synthesis; BSRS ch. 9 recommends gradual signing-key rotation with
overlapping keys, ch. 7 gives no zero-downtime method):

| Phase | Signers | Verifiers | Move on when |
|---|---|---|---|
| 1. Distribute | old key | old + new | every verifier reports the new key loaded |
| 2. Switch | new key | old + new | the longest-lived credential signed by the old key has expired |
| 3. Retire | new key | new | the old key is deleted and its revocation recorded |

For a shared secret (an API key, a database password) the same shape applies: create the second
credential, roll consumers to it, confirm the old one has had no use for a full cycle, then delete
it. Systems that allow only one active credential at a time can't rotate without downtime; prefer
ones that allow two.

**Short-lived Kubernetes credentials.** Since v1.22 pods get a token from the TokenRequest API,
mounted as a projected volume, that expires and is rotated by the kubelet. Its `expirationSeconds`
defaults to one hour with a ten-minute minimum. It is bound to the pod: deleting the pod
invalidates it at once for TokenReview, while OIDC validators accept it until it expires. Set
`automountServiceAccountToken: false` where a pod doesn't call the API. A container mounting the
token with `subPath` doesn't get updates. Re-read the token file instead of caching it
(unverified against the fetched pages, but implied by rotation).

**Secrets in Kubernetes** (secrets good practices): encrypt Secrets at rest in etcd; `list` and
`watch` on Secrets effectively reveal their contents; anyone who can create a pod that mounts a
Secret can read it; base64 in a manifest is plaintext. Those are the reasons a narrow RBAC rule
on Secrets is not the whole story.

**Expiry depends on time; recovery shouldn't** (BSRS ch. 9). A recovery that replays signed data
can fail because certificates expired in the meantime. Where possible, base validity on version
or epoch numbers and validity lists rather than wall-clock time, with rate limits as a backstop.

**Revocation at scale** (BSRS ch. 9):

- Distribute revocation lists that each node caches, rather than asking a central service on every
  check and failing open when it is down.
- Shard the lists, and have nodes refuse an update that revokes their own credentials, so one bad
  push can't lock out the fleet.
- No emergency-only bypass list or special unrevocable account: it becomes the target.

**Rollback protection** (BSRS ch. 9). A deny list of bad versions works only if it lives outside
the component and can't be walked around by installing an even older version. A **minimum
acceptable security version number** is a floor that only rises: ordinary rollbacks to safe
versions still work, downgrades below the floor don't. Rotating the signing key cuts trust in
everything signed before. The hazard runs both ways: raise the floor too early and you can't
roll back a broken release.

## Example

Overlapping rotation of an HMAC signing key. Verifiers accept every key in the ring; signers use
one. A key can be promoted to signing only after verifiers have it, and the signing key can't be
retired.

```python
import hmac, hashlib, os

class KeyRing:
    def __init__(self):
        self.keys, self.verify, self.signing = {}, set(), None
    def add(self, kid):            # phase 1: distribute, verify-only
        self.keys[kid] = os.urandom(32); self.verify.add(kid)
    def promote(self, kid):        # phase 2: sign with it
        assert kid in self.verify, "promote only a key verifiers already accept"
        self.signing = kid
    def retire(self, kid):         # phase 3: after old tokens have expired
        assert kid != self.signing, "never retire the signing key"
        self.verify.discard(kid); del self.keys[kid]
    def sign(self, msg):
        return self.signing, hmac.new(self.keys[self.signing], msg, hashlib.sha256).hexdigest()
    def check(self, msg, kid, mac):
        if kid not in self.verify:
            return False
        good = hmac.new(self.keys[kid], msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(good, mac)

ring = KeyRing(); ring.add("k1"); ring.promote("k1")
old = ring.sign(b"job-42")
ring.add("k2")
ring.promote("k2"); new = ring.sign(b"job-43")
print(ring.check(b"job-42", *old), ring.check(b"job-43", *new))   # True True
ring.retire("k1")
print(ring.check(b"job-42", *old))                               # False
```

Run: the old token verified during the overlap and after the switch; the new token, signed with
`k2`, verified; after retiring `k1` the old token was rejected; a separate call promoting a key
never distributed (`ring.promote("k3")`) raised the assertion. In a fleet, "verifiers already accept" is a fleet-wide fact from
telemetry, not one object's set.

## Gotchas and contested points

- **Shorter isn't free.** Expiry forces an attacker to keep re-acquiring access, but every
  expiry is also a chance for an outage if renewal fails (BSRS ch. 8). Short lifetimes need
  automatic renewal and an alert on renewal failure, not just on expiry.
- **Emergency credential lifetimes.** A break-glass credential that expires during a long outage
  locks responders out; one that never expires is a standing risk. BSRS ch. 9 says to balance
  lifetime against outage length; pick a lifetime longer than your longest plausible outage and
  rotate it on a schedule.
- **Rotating everything at once** after a compromise is disruptive (BSRS ch. 18). Order it by
  what the attacker could reach, administrators and signing keys first.
- **Fail closed on revocation** can itself be an outage. Cached lists with a known age bound the
  risk on both sides.

## Review checklist

1. Is every credential in an inventory with owner, expiry, re-issue path, recovery copy and the
   systems that depend on it, and does each expiry feed an alert?
2. Is any credential's only copy on a workstation, workspace or workload volume?
3. If this credential expired now, would its own renewal or the rebuild path still work? If not,
   is there a break-glass copy and an earlier alert?
4. Are workloads on short-lived, re-issuable credentials (projected tokens, federation) instead
   of static tokens, and is automounting off where unused?
5. Is there a written re-issue and rotation runbook per credential, does rotation overlap
   (distribute, switch, retire) and run automatically, and was emergency rotation timed in a drill?
6. Does any check get disabled, or fail open, when a clock, expiry or revocation service is
   wrong or down?
7. Is revocation distributed and cached, with no bypass list?
8. Is there a security version floor, so rollback can't reinstall a known-vulnerable version?

## Related

[admin-access-and-safe-proxies](admin-access-and-safe-proxies.md) (break-glass),
[compromise-recovery-and-forensics](compromise-recovery-and-forensics.md) (rotation after a
compromise), [`engineering-practices` security-practices](../../engineering-practices/references/security-practices.md)
(leaks), [`production-operations` monitoring-and-alerting](../../production-operations/references/monitoring-and-alerting.md)
(expiry alerts), [`data-integrity` disaster-recovery](../../data-integrity/references/disaster-recovery.md)
(recovery copies).

## Sources

BSRS [ch. 7](https://google.github.io/building-secure-and-reliable-systems/raw/ch07.html),
[ch. 8](https://google.github.io/building-secure-and-reliable-systems/raw/ch08.html),
[ch. 9](https://google.github.io/building-secure-and-reliable-systems/raw/ch09.html),
[ch. 18](https://google.github.io/building-secure-and-reliable-systems/raw/ch18.html), paraphrased;
Kubernetes [Service Accounts](https://kubernetes.io/docs/concepts/security/service-accounts/),
[Projected Volumes](https://kubernetes.io/docs/concepts/storage/projected-volumes/),
[Good practices for Kubernetes Secrets](https://kubernetes.io/docs/concepts/security/secrets-good-practices/).
The inventory fields, the dependency-chain check and the phase table are this skill's synthesis.
The kubelet's refresh threshold was not confirmed, so it is not given.
