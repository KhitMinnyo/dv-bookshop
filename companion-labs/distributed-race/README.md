# Distributed Race Condition Companion Lab

This optional lab uses a dedicated Postgres database and Redis instance to
compare a check-then-act double-spend with transaction, row-lock, distributed
lock, and idempotency-key controls. It never reads or writes DV-Bookshop
databases. The Compose ports are non-default localhost ports to make accidental
connection to another local service less likely.

## Exact Scope

Run only with Docker Compose resources declared in this directory. The
database is named `race_lab`, contains a single demo account, and is disposable.
Do not change `DATABASE_URL`, host names, or ports to point at a real or shared
database. The worker has no HTTP listener and makes no cloud calls.

## Start the Isolated Services

```sh
docker compose up -d db redis
docker compose run --rm worker --mode reset
docker compose run --rm worker --mode status
```

These commands are documentation only and have not been run here. The worker
image is built from the local `Dockerfile` and installs only the pinned local
database and Redis clients.

## Compare the Modes

Use two terminals for the vulnerable mode. Each command tries to spend 700
cents from the same 1000-cent balance with the same isolated database:

```sh
docker compose run --rm worker --mode vulnerable --amount 700 --pause 1
docker compose run --rm worker --mode vulnerable --amount 700 --pause 1
```

The vulnerable code reads the balance, pauses, and then updates it without a
transaction. Depending on scheduling, both workers may approve the check.
Reset before each comparison:

```sh
docker compose run --rm worker --mode reset
```

Then compare these controls using the same two-terminal pattern:

```sh
docker compose run --rm worker --mode transaction --amount 700 --pause 1
docker compose run --rm worker --mode lock --amount 700 --pause 1
docker compose run --rm worker --mode idempotent --amount 700 --request-id order-001 --pause 1
```

Run `transaction` or `lock` concurrently to observe row serialization and a
single accepted spend. Run `idempotent` concurrently with the same
`--request-id` to see the duplicate request rejected before another debit.
An idempotency key is not a substitute for a transaction; the worker uses both.

## What to Inspect

- `vulnerable` performs separate read and update statements with no protection.
- `transaction` uses a Postgres transaction and `SELECT ... FOR UPDATE` on the
  account row.
- `lock` uses a short-lived Redis `SET NX EX` lock plus the database row lock.
  The database remains the source of truth; the lock is coordination, not a
  replacement for database constraints.
- `idempotent` claims a unique request key inside the same transaction before
  debiting the row.
- A production design should also use integer minor units, database
  constraints, bounded lock leases, fencing or ownership checks where needed,
  retry rules, and durable audit records.

## Reset and Cleanup

```sh
docker compose run --rm worker --mode reset
docker compose down -v
```

`down -v` removes only this Compose project's Postgres and Redis volumes. Do
not use it against a project that was not started from this directory.
