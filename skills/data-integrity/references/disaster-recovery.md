# Disaster recovery

Getting a service and its data back after losing a whole store, volume, cluster, account or site.
This covers scenarios and plans, restore drills, the order of recovery, getting back credentials
and keys, and deleting volumes and buckets safely. Anchor sources:
[BSRS ch. 16, Disaster Planning](https://google.github.io/building-secure-and-reliable-systems/raw/ch16.html),
[BSRS ch. 9, Design for Recovery](https://google.github.io/building-secure-and-reliable-systems/raw/ch09.html),
the [SRE book, Data Integrity](https://sre.google/sre-book/data-integrity/), and the AWS
[resilience analysis framework](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/mitigation-strategies.html).
The credential and safe-deletion parts are this skill's own synthesis, built on ch. 9's points
about emergency access and deletion. Neither chapter has a section on recovering credentials.

## What agents typically get wrong

- **A plan never run.** A recovery path that nobody exercises breaks when it is needed most
  (SRE book). A backup that was taken but never restored counts as no backup.
- **Recovery that depends on the thing that's down.** The runbook lives in the wiki that was on
  the lost cluster. The backup key is in the secret store being restored. The restore job needs
  the CI system that ran in the same account.
- **The only copy of a credential on a working volume.** An API token, signing key, kubeconfig
  or decryption key kept on a laptop, a dev workspace or a pod volume is data. When someone
  deletes that volume while cleaning up, the token is lost, and with it access to whatever the
  token unlocked. Encrypted backups are useless without their key.
- **Deleting a volume or bucket because it "looks unused".** Its last writer stopped months ago,
  but it holds the only copy of something. Deleting it is the incident.
- **Restoring in the wrong order.** Bringing apps up before their database is verified, or
  letting writers resume before validators pass, writes new data on top of a bad base.
- **Measuring RTO as "bytes / bandwidth".** Real RTO includes noticing, deciding, finding
  credentials, provisioning, restoring, checking, and switching traffic. The human steps
  usually dominate.
- **Testing only the newest backup on the easy path.** Drills should cover the oldest retained
  copy, a partial restore, and a restore with the primary account or region unavailable.

## Procedure

1. **Risk analysis** (BSRS ch. 16). List the essential systems and what they depend on. List
   likely scenarios for each: a deleted volume, a corrupted database, a lost zone or region, a
   compromised or locked account, a lost credential, ransomware. Rate likelihood and impact, and
   revisit as the system changes.
2. **Write the plan per scenario**: who decides, the order of recovery, where each backup and key
   lives, the commands, and how to check success. Keep copies where they can be reached during
   the outage (printed, in a separate account, or offline), and agree a backup communication
   channel.
3. **Prestage.** Tested restore procedures, capacity to restore into (spare quota, a standby
   cluster, or infrastructure as code that can build one), and emergency access that doesn't
   depend on the failed system (BSRS ch. 9 and 16).
4. **Recover in order:**
   1. Stop the damage: pause writers and intake, revoke compromised credentials.
   2. Restore access: break-glass credentials, the key management service, DNS, the identity
      provider.
   3. Restore stateful stores into a fresh location, never over the only remaining copy.
   4. Verify: integrity checks, invariants, row counts, newest record against the RPO.
   5. Bring up stateless services, read-only first if the platform allows.
   6. Re-enable writes and background jobs. Re-apply deletions that happened after the restore
      point.
   7. Switch traffic. Watch validators and error rates.
5. **Drill.** Run tabletop exercises for the decisions, and real restores for the mechanics. Time
   every step and compare against the RTO. Audit automated systems, backups among them, at least
   once a year (BSRS ch. 16). Restore drills should run far more often (below).
6. **Follow up.** Write a postmortem with owned actions. Update the plan with every step that
   surprised you.

## Techniques

- **Credentials and keys are data.** Keep an inventory of every secret, what it unlocks, where
  the primary copy lives, and where the recovery copy lives. Recovery copies go somewhere with a
  different failure domain and access path: a secret manager in another account, an offline
  vault, sealed envelopes for break-glass. Prefer credentials that can be re-issued (from an
  identity provider or the vendor console) over ones that can only be copied. Back up the keys
  that encrypt backups separately from the backups.
- **Emergency access** stays low-dependency and is used often enough to keep working. BSRS ch. 9
  suggests making emergency procedures close to the normal ones, and practising break-glass on a
  schedule.
- **Record intended state.** Keep the configuration of hosts and services as code, and keep
  standby configuration up to date. During recovery it may become the live one (BSRS ch. 9).
- **Restore without resurrecting.** A restore can bring back data that was deleted after the
  restore point. Keep a deletion log to re-apply (BSRS ch. 9).
- **Re-drive tooling** (AWS). Plan tools to re-run stalled workflows or fix data, checkpoints that
  limit lost work, and a stop switch that pauses intake.
- **Continuous restore tests** (SRE book). Automate end-to-end restores. Emit a heartbeat on
  success and alert when it stops. Check that the restore is not empty, finishes in time, and
  can be watched while it runs.

**Safe deletion of a volume, bucket, database or account:**

| Step | Check |
|---|---|
| 1. Identify | Who created it, which workload mounts or reads it, last write and last read time |
| 2. Look inside | List the top-level contents. Look for databases, keys, tokens, `.env` or config files, exports |
| 3. Find other copies | For each item worth keeping: is there a backup or a source of truth elsewhere, and was it checked? |
| 4. Snapshot first | Take a final snapshot or archive, with a retention date, before deleting |
| 5. Soft-delete | Detach, revoke access, or rename and wait out a quiet period. Deletion protection stays on until then |
| 6. Delete | With a second person for production. Record what was deleted and where the final snapshot is |

For a Kubernetes PV, check the reclaim policy before deleting a PVC. For a VolumeSnapshotClass,
`deletionPolicy: Delete` removes the underlying snapshot along with its VolumeSnapshotContent,
so use `Retain` for any snapshot you mean to keep.

## Example

A restore-drill outline. It restores the newest backup to scratch, checks integrity and
invariants, compares the newest record with the RPO, and times the run against the RTO. It uses
SQLite's online backup API as a stand-in for the real restore command
(`litestream restore`, a base backup restored with WAL replay, or a snapshot clone):

```python
import os, sqlite3, sys, tempfile, time

def restore(backup_path, target):            # stand-in for the real restore command
    src = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
    dst = sqlite3.connect(target)
    src.backup(dst)                          # online backup API: consistent copy
    src.close(); dst.close()

def drill(backup_path, invariants, max_age_s, rto_s):
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory() as d:   # restore to scratch, never over production
        target = os.path.join(d, "restored.db")
        restore(backup_path, target)
        db = sqlite3.connect(target)
        failures = []
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            failures.append("integrity_check failed")
        for name, sql, minimum in invariants:  # the backup is neither empty nor stale
            value = db.execute(sql).fetchone()[0]
            if value is None or value < minimum:
                failures.append(f"{name}={value} < {minimum}")
        newest = db.execute("SELECT max(updated_at) FROM items").fetchone()[0] or 0
        if time.time() - newest > max_age_s:
            failures.append(f"newest row {time.time() - newest:.0f}s old > RPO {max_age_s}s")
        db.close()
    elapsed = time.monotonic() - t0
    if elapsed > rto_s:
        failures.append(f"restore took {elapsed:.1f}s > RTO {rto_s}s")
    print(f"drill elapsed={elapsed:.2f}s failures={failures or 'none'}")
    return not failures                      # caller exports success time as a heartbeat metric

if __name__ == "__main__":
    ok = drill(sys.argv[1], invariants=[("items", "SELECT count(*) FROM items", 1)],
               max_age_s=3600, rto_s=900)
    sys.exit(0 if ok else 1)
```

This was run against three throwaway databases. A fresh 100-row copy passed (exit 0). An empty
copy failed with `items=0 < 1` and a stale newest row (exit 1). A copy whose newest row was 2 h
old failed the 1 h RPO check (exit 1). In real use, schedule it, push the timestamp of the last
success to monitoring, and alert when it is older than the drill interval.

## Gotchas and contested points

- **Drills in production carry risk.** BSRS ch. 16 describes production testing (fault injection,
  real failovers) alongside tabletop exercises. Start with restores into an isolated environment.
  Move to live failovers once those are routine.
- **Offline copies trade speed for safety.** An offline copy survives a compromised production
  account but is the slowest to restore. Most systems need one, but not as the first tier.
- **The plan rots.** Every new store, secret or dependency is a gap until it is in the
  inventory. Review the plan when the architecture changes, not only on a calendar.

## Review checklist

1. Is there a scenario list (deleted volume, corrupted database, lost region, locked account,
   lost credential), each with an owner and a written plan?
2. Can the plan be carried out with the primary cluster, account, wiki and secret store all
   unavailable?
3. Does every credential and key, including backup encryption keys, have a recovery copy in a
   separate failure domain? Is there no secret whose only copy is on a workstation or workload
   volume?
4. Is the recovery order written down, with verification before writes resume?
5. Is there an automated restore drill with a success heartbeat and an alert when it stops?
   Has a real restore been timed against the RTO?
6. Before deleting any volume, bucket, database or account: was it looked inside, its unique
   contents copied or confirmed redundant, and a final snapshot kept?
7. Do snapshot classes and PVs that hold data you keep use `Retain`, or a deletion policy you
   chose deliberately?

## Related

[backup-and-restore](backup-and-restore.md) (RPO/RTO, backup types),
[corruption-and-bad-writes](corruption-and-bad-writes.md) (recovering from a bad write),
[state-and-storage](state-and-storage.md) (where state lives),
[`engineering-practices` security-practices](../../engineering-practices/references/security-practices.md)
(leaked credentials), [`secure-reliable-systems`](../../secure-reliable-systems/SKILL.md) (rollback, revocation, break-glass design),
[`production-operations`](../../production-operations/SKILL.md) (incident response).

## Sources

[BSRS ch. 16, Disaster Planning](https://google.github.io/building-secure-and-reliable-systems/raw/ch16.html);
[BSRS ch. 9, Design for Recovery](https://google.github.io/building-secure-and-reliable-systems/raw/ch09.html);
[SRE book ch. 26, Data Integrity](https://sre.google/sre-book/data-integrity/);
AWS [resilience analysis framework, mitigation strategies](https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/mitigation-strategies.html);
Kubernetes [Volume Snapshots](https://kubernetes.io/docs/concepts/storage/volume-snapshots/);
SQLite [Online Backup API](https://www.sqlite.org/backup.html). The PV reclaim-policy note comes
from general knowledge (unverified against a fetched page).
