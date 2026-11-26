# Data ownership

## Problem

Services that share tables are coupled however clean their APIs look. A column rename in one
breaks another, a long lock in one stalls the other, and nobody knows who may change a row's
meaning. Giving each service private data removes that coupling and creates two new problems:
transactions and queries that span services. Those are solved deliberately
([collaboration](collaboration.md)), not by reaching into another service's tables.

## Database per service

Each service's persistent data is private. Other services reach it only through the owner's
API, its published events, or a replica it feeds.

Privacy doesn't require a database server per service. Pick the cheapest level that keeps the
boundary enforced:

| Level | What | Fits | Enforce with |
|---|---|---|---|
| Private tables | Each service's tables in a shared database, prefixed or listed | Small systems, early migration | Per-service database users granted only their own tables |
| Schema per service | A schema (Postgres) or database (MySQL) per service on a shared server | The usual default | Per-service users owning their schema; no grants across schemas |
| Server per service | A dedicated database instance | High throughput, different engine, different backup or compliance needs, noisy neighbours | Network policy and credentials |

Conventions alone don't hold. Without grants, someone writes the one-off join "just for this
report", and the boundary is gone. A shared server is still a shared failure and capacity
domain; see [`infrastructure-patterns` bulkheads](../../infrastructure-patterns/references/bulkheads-and-isolation.md).

Each service can also pick the store that fits: relational for transactional rules, a
document store for aggregates read whole, a search index for a query view.

## Shared database

All services use one database and its ACID transactions directly.

- **Benefits:** familiar transactions across what would be service boundaries; one database to
  operate; queries join anything.
- **Costs:** schema changes need coordination across teams (design-time coupling); one
  service's locks and load hit the others (runtime coupling); one store for every need.

It's acceptable in a monolith and as a stage of a migration. Between independently owned
services it defeats the purpose of splitting. If two services need one transaction, they
probably belong together ([boundaries](boundaries.md)).

## Reporting and analytics

Cross-service reporting is the usual excuse for reaching into other services' databases.
Better options, from simplest:

1. **API composition** for small, fresh reports.
2. **A reporting view** fed by events ([CQRS](../../infrastructure-patterns/references/cqrs-and-materialized-views.md)).
3. **Change data capture into a warehouse or lake,** owned by a data team, treated as a
   read-only downstream with a documented schema contract. The services' internal schemas
   become a published interface here, so expose views or event streams, not raw tables.

## Moving data out of a shared database

When splitting a monolith, data usually separates in stages:

1. **Assign every table an owner.** Tables two modules write are a boundary problem to solve first.
2. **Route access through the owner's code.** Other modules call the owner's module API instead
   of querying its tables. Measure remaining cross-module queries.
3. **Separate schemas and grants** inside the same server.
4. **Replace cross-schema joins** with composition, replicas or views.
5. **Move to a separate server** only if a force requires it.

Keep each step deployable and reversible. Database migration mechanics (expand and contract,
backfills) are in [`engineering-practices` database-migrations](../../engineering-practices/references/database-migrations.md).

## What agents get wrong

- **"Database per service" read as "a server per service".** A schema per service with grants
  is usually enough.
- **Shared read-only access "just for queries".** Readers still couple to the schema; a rename
  breaks them.
- **Foreign keys across service boundaries.** They can't exist across databases; keep the ID,
  drop the constraint, and handle the referenced entity going away.
- **Copying another service's data without an owner.** A replica is fed by the owner's events
  and never written locally.
- **Splitting data before code.** Separate the access paths first, then the storage.

## Review checklist

1. Does every table have exactly one owning service?
2. Are grants set so no service can read or write another's tables?
3. Which cross-service joins exist, and how is each replaced (composition, replica, view)?
4. Are any two services' transactions a sign they belong together?
5. Do reporting or analytics consumers read published views or events, not internal tables?
6. Does a shared database server have per-service limits (connections, statement timeouts)?

## Related

[collaboration](collaboration.md), [migration](migration.md), [boundaries](boundaries.md),
[`data-integrity`](../../data-integrity/SKILL.md) (backups per store),
[`infrastructure-patterns` read-replicas](../../infrastructure-patterns/references/read-replicas.md).

## Sources

microservices.io: [Database per service](https://microservices.io/patterns/data/database-per-service.html),
[Shared database](https://microservices.io/patterns/data/shared-database.html). Sam Newman,
*Monolith to Microservices* (splitting the database). The staged extraction is this skill's
own summary of common practice.
