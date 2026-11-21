# Backup and restore

Turning "we have backups" into a recovery you can count on. That means picking RPO and RTO as
numbers, choosing backup types that meet them, setting retention, protecting the copies, and
proving restores work by running them. Anchor sources: Google's
[SRE book, Data Integrity](https://sre.google/sre-book/data-integrity/), the PostgreSQL
chapters on [backup](https://www.postgresql.org/docs/current/backup.html),
[file-system backup](https://www.postgresql.org/docs/current/backup-file.html) and
[continuous archiving](https://www.postgresql.org/docs/current/continuous-archiving.html), the
SQLite [backup API](https://www.sqlite.org/backup.html) and [WAL](https://www.sqlite.org/wal.html)
pages, and [Litestream](https://litestream.io/how-it-works/).

## What agents typically get wrong

- **Designing backups instead of restores.** A job that "succeeds" every night proves only that
  bytes moved. The value is in the restore, not the copy (SRE book). Start from how
  you will get data back, how fast, and to what point.
- **No numbers.** "Daily backups" isn't a target. RPO (how much recent data you may lose) and
  RTO (how long until the service works again) are numbers someone agreed to. The schedule and
  method come from those numbers.
- **Copying a live database file.** `cp` of a live SQLite file, or `tar` of a running Postgres
  data directory, can produce a copy that won't open. Postgres says half-measures such as
  blocking connections don't make a file copy safe. SQLite warns that a crash mid-copy can leave
  a corrupt backup.
- **Leaving the WAL behind.** SQLite's `-wal` file holds committed transactions. A Postgres
  snapshot without `pg_wal` won't recover. Both docs say to keep the WAL with the data.
- **Treating a replica as a backup.** Replication copies deletes and corruption to every copy at
  once. It protects against losing a disk, not against a bad write.
- **Backups stored next to the data.** Same volume, same account, same credentials: one mistake
  or one compromised key takes both.
- **Retention chosen by default.** Low-grade corruption is often found weeks later, so a 7-day
  window may hold only bad copies by the time anyone looks.
- **Incremental chains nobody tracks.** A restore needs the full backup and every later
  increment. PostgreSQL says outright that it does not track those dependencies for you.
- **No alert when the backup stops.** A dead cron job looks just like a quiet night.

## Procedure

1. **Inventory the state.** List every store that holds data you can't rebuild: databases,
   volumes, object buckets, queues with unconsumed messages, config, secrets and keys. Mark what
   can be regenerated (caches, derived tables) and how long that takes.
2. **Agree RPO and RTO per store**, with the people who bear the loss. Write them down. Very
   different numbers for different stores are normal.
3. **Pick the mechanism from the numbers** (table below). RPO measured in minutes or seconds
   means continuous log shipping. RPO measured in hours can be met with snapshots or dumps.
4. **Pick a consistent capture method**: the database's own backup tool, an atomic snapshot of
   every volume the database uses (data and WAL together), or a stopped service. Never a plain
   file copy of a live store.
5. **Store copies apart from the original**: another failure domain (zone, region, provider or
   site), and credentials that the production workload can't use to delete them.
6. **Set retention** at least as long as it can take to notice silent corruption. Add a longer
   tier if you need to reach further back.
7. **Monitor freshness**: alert when the newest good backup, or the archive lag, is older than
   the RPO.
8. **Restore on a schedule.** Restore into a scratch environment, run integrity checks and
   invariants, time the run, and record the result. See the drill in
   [disaster-recovery](disaster-recovery.md).

## Techniques

| Mechanism | Typical RPO | Restore cost | Granularity | Notes |
|---|---|---|---|---|
| Logical dump (`pg_dump`, SQLite `.dump`, `VACUUM INTO`) | Interval between dumps | Reload and reindex: slowest for big stores | Per table or database | Portable across versions; good second copy; can't do PITR |
| Volume or filesystem snapshot | Interval between snapshots | Clone or attach: fast | Whole volume | Crash-consistent only if atomic across all volumes; database replays its log on start |
| Physical base backup (`pg_basebackup`) | Interval between backups | Copy back: fast | Whole cluster | With `-X` it is standalone but not usable for PITR |
| Base backup + continuous WAL archive | About `archive_timeout`, or near zero for streaming | Base copy plus WAL replay | Any point after the base | PITR; archive must have no gaps back to the base's start |
| SQLite WAL streaming (Litestream-style) | Sync interval (about 1 s by default) | Snapshot plus replay of later files | Any file boundary | Async: a crash loses the last interval |
| Incremental (block or page deltas) | As the base type | Full plus every increment | As the base | Chains raise restore risk; track dependencies yourself |

- **Tiers.** The SRE book's layering trades restore speed for reach. A copy on the same storage
  comes back in minutes but is costly to keep and shares that storage's fate, so it covers days;
  cheaper copies elsewhere cover weeks; only offline or offsite media survives losing the site.
  A common shorthand is "3-2-1": three copies, two kinds of media, one offsite (a folk rule,
  unverified against a primary source here).
- **Postgres WAL archiving.** Set `wal_level=replica`, `archive_mode=on`, and `archive_command`
  or `archive_library`. The command must exit 0 only when the file is safely stored, and it must
  refuse to overwrite a different file of the same name. A forced segment is still 16 MB, so a
  very short `archive_timeout` bloats the archive; the docs suggest about a minute. Set up and
  test archiving before the first base backup. Archive the `.history` timeline files too.
- **Postgres incrementals.** `pg_basebackup --incremental=<manifest>` needs WAL summaries.
  Restore with `pg_combinebackup`. Never delete a backup that a later increment depends on.
- **SQLite.** Use the online backup API (in steps, so writers aren't blocked), `VACUUM INTO`, or
  `sqlite3_rsync`. A finished backup-API copy is consistent as of when it started. Heavy writes
  from other connections can make it restart without end.
- **Litestream.** A separate process holds a read transaction and takes over checkpointing. It
  ships WAL pages as LTX files to object storage. Defaults: a snapshot every 24 h, kept for 24 h.
  A restore replays every file since the last snapshot, so lower `snapshot.interval` when restore
  time matters. Two writers replicating to the same path can make restores impossible.
- **Protecting copies.** Integrity-protect backups as strictly as primary data and check them
  when you restore (BSRS ch. 9). Use write-once or object-lock storage where the platform offers
  it. Give backup deletion its own credentials.
- **Freshness alerts.** Export "newest restorable point" and "last successful restore drill" as
  timestamps. Alert when either is older than its target. For Postgres, watch archive failures:
  unarchived WAL piles up in `pg_wal` and never clears on its own.

## Example

RPO/RTO for a 20 GiB database (SQLite or Postgres). The targets are RPO 15 min and RTO 1 h.
Restore throughput is an assumption here (100 MiB/s from object storage, 20 MiB/s WAL replay).
Replace both with what your own drill measures.

| | A: volume snapshot every 6 h | B: daily base + continuous WAL |
|---|---|---|
| Worst-case loss | 6 h + snapshot duration (mean 3 h) | Sync or archive interval: about 1 s (Litestream), about 60 s (`archive_timeout=60`) |
| Data copy on restore | 20 GiB / 100 MiB/s = 205 s | Same 205 s for the base |
| Log replay | None (the database replays its own WAL on start) | Up to 24 h of WAL; at 2 GiB/day, 2048 / 20 = 102 s |
| Detection + decision + DNS/app cut-over | Measured in drills; say 20 min | Same 20 min |
| Estimated RTO | About 23 min | About 25 min |
| Meets RPO 15 min? | **No** | Yes, if archive lag is monitored |
| What it loses | Up to 6 h of writes; can't reach a point between snapshots | Last interval only; can stop just before a bad write |

Option A fails the RPO however fast it restores. Option B meets both targets, but only if the
archive has no gaps and the replay rate holds. A drill is the only way to know. Both RTOs are
dominated by the human steps, not by bytes. The arithmetic was checked with a one-liner
(20 x 1024 / 100 = 204.8 s; 2 x 1024 / 20 = 102.4 s; 205 s + 20 min = 23.4 min; 205 + 102 s + 20 min = 25.1 min).

## Gotchas and contested points

- **Snapshots are not automatically consistent.** Postgres treats a frozen snapshot as a crash
  and replays WAL. That is fine only if all its volumes were captured at the same instant. If
  they can't be, use a base backup with archiving instead.
- **`pg_dump` output can't be combined with WAL** for point-in-time recovery; it is logical.
- **Managed backups still need checking.** A provider's automated backups still need an RPO
  check, a restore drill, and a copy outside the account they protect (general practice).
- **Old backups may not load.** Schema and code move on, so an old copy can need old code to read
  it (SRE book). Restore drills should cover the oldest copy you keep, not only the newest.
- **Restores must not bring back data that was meant to be deleted** (BSRS ch. 9). Re-apply
  deletions after a restore. Crypto-shredding works only if keys are scoped to match.
- **Longer retention costs money and privacy.** Data kept for recovery is still data you hold.
  Set it consciously, not "forever".

## Review checklist

1. Does each store have a written RPO and RTO, agreed with the people who lose if it's missed?
2. Is every backup taken with a consistent method (the database's tool, an atomic snapshot that
   includes the WAL, or a stopped service) rather than a copy of live files?
3. Is at least one copy in a different failure domain, under credentials the workload can't use
   to delete it?
4. Does retention cover the time it can take to notice silent corruption?
5. For continuous archiving: does the archive command fail loudly, refuse to overwrite, and is
   archive lag alerted against the RPO?
6. Are incremental chains and their base backups tracked so nothing a restore needs is pruned?
7. Is there an alert when the newest restorable point is older than the RPO?
8. Has a backup been restored, checked and timed in the last period? Is "a backup was taken but
   never restored" treated as having no backup?

## Related

[disaster-recovery](disaster-recovery.md) (drills, order of recovery),
[state-and-storage](state-and-storage.md) (WAL growth, where the data lives),
[corruption-and-bad-writes](corruption-and-bad-writes.md) (why retention must outlast detection),
[`architecture-review`](../../architecture-review/references/provider-crosswalk.md) (provider
backup services).

## Sources

[SRE book ch. 26, Data Integrity](https://sre.google/sre-book/data-integrity/);
[BSRS ch. 9, Design for Recovery](https://google.github.io/building-secure-and-reliable-systems/raw/ch09.html);
PostgreSQL [Backup and Restore](https://www.postgresql.org/docs/current/backup.html),
[File System Level Backup](https://www.postgresql.org/docs/current/backup-file.html),
[Continuous Archiving and PITR](https://www.postgresql.org/docs/current/continuous-archiving.html);
SQLite [Online Backup API](https://www.sqlite.org/backup.html), [WAL](https://www.sqlite.org/wal.html);
Litestream [How it works](https://litestream.io/how-it-works/), [Tips](https://litestream.io/tips/).
The 3-2-1 rule is stated from common practice, not a fetched source.
