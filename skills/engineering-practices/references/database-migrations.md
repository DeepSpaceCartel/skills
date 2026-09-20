# Database migrations

Changing a live database's schema and data without downtime or data loss: lock
behavior of DDL, index builds, constraints, backfills, renames and drops, the window
where old and new application versions run against one schema, and rollback vs
roll-forward. Anchor sources: Fowler and Sadalage's
[Evolutionary Database Design](https://martinfowler.com/articles/evodb.html),
Fowler's [Parallel Change](https://martinfowler.com/bliki/ParallelChange.html),
Stripe's [Online migrations at scale](https://stripe.com/blog/online-migrations), the
[`strong_migrations` catalogue of unsafe migrations](https://github.com/ankane/strong_migrations),
the PostgreSQL and MySQL manuals, and GitLab's
[migration style guide](https://docs.gitlab.com/ee/development/migration_style_guide.html).
SQL below is PostgreSQL and was run on PostgreSQL 16.

## What agents typically get wrong

- **`RENAME COLUMN` or `DROP COLUMN` in one deploy.** Instances still running the
  old code break the moment it lands. Use expand and contract.
- **Over- and under-warning about defaults.** On PostgreSQL 11+, adding a column
  with a *constant* default does not rewrite the table. A *volatile* default
  (`random()`, `gen_random_uuid()`, `clock_timestamp()`), an identity column or a
  stored generated column does. Agents often flag the first and miss the second.
- **`SET NOT NULL` or `ADD CONSTRAINT ... CHECK` on a big table,** which scans the
  whole table under an `ACCESS EXCLUSIVE` lock.
- **Plain `CREATE INDEX`,** which blocks writes. `CONCURRENTLY` cannot run in a
  transaction, and the migration tool's default wrapper transaction makes it fail.
- **A failed `CONCURRENTLY` build leaves an INVALID index** that still slows
  writes. Check for it, then drop and retry.
- **Backfilling inside the schema migration:** one giant `UPDATE` holds locks for
  the whole run and causes bloat and replication lag.
- **Ignoring the lock queue** (below).
- **Editing an already-applied migration.** Migrations are numbered, versioned
  history; add a new one.
- **Assuming `down` restores the previous state.** Dropped data is gone. On MySQL,
  DDL implicitly commits, so a failed migration can be half applied.
- **Forgetting the deploy overlap.** The schema has to work with both the old and
  the new code, and with `SELECT *`, cached ORM columns and `INSERT` without a
  column list.
- **`ALTER COLUMN TYPE` treated as cheap.** It usually rewrites the table and its
  indexes.
- **Adding a foreign key without `NOT VALID`,** which takes a strong lock on both
  tables.
- **Mixing a data backfill and a schema change in one migration file.**

## Procedure

1. **Classify the change.**
   - Usually safe: create table, add a nullable column, add a column with a constant
     default (PostgreSQL 11+), `CREATE INDEX CONCURRENTLY`, `VALIDATE CONSTRAINT`.
   - Unsafe: rename, drop, type change, volatile default, `SET NOT NULL`, plain
     index, adding a foreign key or CHECK without `NOT VALID`.
2. **Check table size and traffic.** A small, idle table can take the simple path.
   Otherwise assume the multi-step path.
3. **Expand.** Add the new structure, nullable and without constraints. Deploy code
   that tolerates both shapes and *dual-writes*.
4. **Migrate.** Run a batched, throttled, resumable, idempotent backfill outside
   the schema migration, then verify counts and equality. Move reads over (ideally
   comparing old and new paths first, as Stripe did). Then stop writing the old
   structure.
5. **Contract.** Only after no deployed code, old instance or job uses the old
   structure, drop it in a *later* deploy.
6. **Session settings.** Set a short `lock_timeout` (a couple of seconds) and retry on
   failure; run DDL off-peak and check for long-running transactions first.
7. **Verify.** No INVALID indexes, constraints validated. Rehearse on a
   production-sized copy and time it.
8. **Plan the reversal.** Expand steps are safe to abandon. Contract steps are
   one-way, so take a backup or keep the data first. Prefer roll-forward, and say in
   the PR which steps are irreversible.

## Techniques

- **Expand/contract (parallel change).** For any breaking change on a live table.
  Skip it for a table that isn't live yet or for a change made in a maintenance
  window.
- **Dual writes.** Write old and new, switch reads, stop writing old, remove old.
  For renames, type changes and table splits. Costs code and consistency risk.
- **Batched backfill.** Small batches (10,000 rows is a common example) with a short
  sleep between them, committing per batch, resumable. Run it outside the schema
  migration. Dual-writes must already be live, or rows created during the backfill
  will be missed.
- **`NOT VALID` then `VALIDATE` (PostgreSQL).** For foreign keys and CHECK
  constraints. `VALIDATE` takes a weaker lock, so writes continue during the scan.
  For `SET NOT NULL`, add a `CHECK (col IS NOT NULL) NOT VALID`, validate it, then
  `SET NOT NULL`, which skips the scan because the valid CHECK proves no NULLs; then
  drop the CHECK. (Newer PostgreSQL releases add `NOT VALID` for NOT NULL directly;
  check your version.)
- **`CREATE INDEX CONCURRENTLY`.** Any live table. Takes two scans, waits on older
  transactions, must run outside a transaction block.
- **Online schema change tools (MySQL).** gh-ost reads the binlog to feed a shadow
  table and avoids triggers; pt-online-schema-change uses triggers. Use them when
  the change needs `ALGORITHM=COPY`; skip them when MySQL can do it `INSTANT` or
  `INPLACE` (much of MySQL 8.4's column and secondary-index work).
- **Feature flags around schema changes** let you flip reads and writes without a
  deploy. They don't replace the expand/contract sequencing.

## Example

Rename `users.name` to `full_name` on a large table, one step per deploy. Run on
PostgreSQL 16 against 200,000 rows.

```sql
-- Deploy 1 (expand): the app now writes both columns and still reads `name`
SET lock_timeout = '2s';
ALTER TABLE users ADD COLUMN full_name text;

-- Backfill: a separate job, NOT inside the migration tool's transaction
DO $$
DECLARE n bigint;
BEGIN
  LOOP
    UPDATE users SET full_name = name
    WHERE id IN (SELECT id FROM users WHERE full_name IS NULL LIMIT 10000);
    GET DIAGNOSTICS n = ROW_COUNT;
    EXIT WHEN n = 0;
    COMMIT;                          -- release locks between batches (PostgreSQL 11+)
    PERFORM pg_sleep(0.01);
  END LOOP;
END $$;

-- Deploy 2 (migrate): add the constraint without a long lock; reads move to full_name
ALTER TABLE users ADD CONSTRAINT users_full_name_nn CHECK (full_name IS NOT NULL) NOT VALID;
ALTER TABLE users VALIDATE CONSTRAINT users_full_name_nn;

-- Deploy 3 (contract): only after no code or job uses `name`
ALTER TABLE users DROP COLUMN name;
```

Checked on PostgreSQL 16:

- A constant default (`DEFAULT 'active'`) left the table's file untouched, while
  `DEFAULT random()` rewrote it.
- `CREATE INDEX CONCURRENTLY` inside `BEGIN ... COMMIT` fails with "cannot run inside
  a transaction block".
- After `VALIDATE`, `SET NOT NULL` logged that existing constraints are sufficient to
  prove there are no NULLs, so it skipped the scan.
- Lock queue: while a long transaction held a read lock, a plain `SELECT` returned in
  about 0.2 s. With an `ALTER TABLE` queued behind that transaction, the same
  `SELECT` waited about 3 s, until the ALTER's `lock_timeout` fired. A short
  `lock_timeout` plus a retry keeps a waiting DDL from stalling every query on the
  table.

## Gotchas and contested points

- **Transactional DDL differs by database.** PostgreSQL DDL is transactional, so a
  failed migration rolls back. MySQL DDL implicitly commits.
- **Lock strength differs.** MySQL 8.4 does many changes `INSTANT` or `INPLACE`;
  PostgreSQL takes `ACCESS EXCLUSIVE` unless documented otherwise.
- **Dropping a PostgreSQL column is fast** but doesn't reclaim disk space
  immediately.
- **Reversibility is contested.** Fowler: automated down migrations aren't
  cost-effective, so make access code work with both versions. GitLab requires
  every migration to have a `down` or a comment explaining why not. In practice:
  `down` is for local development, and production relies on roll-forward.
- **Rolling deploys mean old code sees the new schema.** ORM column caching, `SELECT
  *` and `INSERT` without a column list all break when columns change.
- **Some ORMs need a step first** (for example Rails `ignored_columns` before a drop).
- **GitLab's variant:** add a NOT NULL column with a default first, remove the default
  in a later post-deployment migration, to survive cached schemas during a rolling
  deploy.
- **Data and schema migrations in one file** can fail with "pending trigger events"
  on PostgreSQL. Split them.

## Review checklist

1. Does every deployed app version, including old instances and background jobs, work against both the before and after schema?
2. Is any rename, drop or type change split across separate deploys?
3. Is `lock_timeout` set, with a retry for lock failures?
4. Are indexes built concurrently, with the tool's DDL transaction disabled?
5. Are constraints added as `NOT VALID` and then validated?
6. Is the backfill batched, resumable, idempotent and outside the schema migration?
7. Am I adding a new migration rather than editing an applied one?
8. Are irreversible steps labeled, with a roll-forward or backup plan?

## Related

`api-evolution` (the same expand/contract idea for interfaces), `release-engineering`
(shipping the code side in separate deploys), `refactoring` (Parallel Change),
`reliability` (lock timeouts and retries).

## Sources

Fowler and Sadalage, [Evolutionary Database Design](https://martinfowler.com/articles/evodb.html);
Fowler, [Parallel Change](https://martinfowler.com/bliki/ParallelChange.html);
Stripe, [Online migrations at scale](https://stripe.com/blog/online-migrations);
[strong_migrations](https://github.com/ankane/strong_migrations);
PostgreSQL manual, [ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html),
[CREATE INDEX](https://www.postgresql.org/docs/current/sql-createindex.html) and
[explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html);
MySQL 8.4 [online DDL](https://dev.mysql.com/doc/refman/8.4/en/innodb-online-ddl-operations.html);
[gh-ost](https://github.com/github/gh-ost/blob/master/doc/why-triggerless.md);
GitLab [migration style guide](https://docs.gitlab.com/ee/development/migration_style_guide.html);
Xata, [migrations and exclusive locks](https://xata.io/blog/migrations-and-exclusive-locks).
Sadalage and Ambler's *Refactoring Databases* and Kleppmann's *Designing
Data-Intensive Applications* ch. 4 could not be read directly.
