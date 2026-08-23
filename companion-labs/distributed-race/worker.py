#!/usr/bin/env python3
"""One local worker for the isolated Postgres and Redis race lab."""

from __future__ import annotations

import argparse
import os
import time
import uuid

import psycopg
import redis


ACCOUNT = "demo-account"


def database() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"])


def status() -> None:
    with database() as connection:
        row = connection.execute("SELECT balance_cents FROM accounts WHERE account_id = %s", (ACCOUNT,)).fetchone()
        keys = connection.execute("SELECT count(*) FROM idempotency_keys").fetchone()
    print(f"balance_cents={row[0]} idempotency_keys={keys[0]}")


def reset() -> None:
    with database() as connection:
        connection.execute("TRUNCATE idempotency_keys")
        connection.execute("UPDATE accounts SET balance_cents = 1000 WHERE account_id = %s", (ACCOUNT,))
    print("reset complete")


def vulnerable(amount: int, pause: float) -> None:
    with database() as connection:
        balance = connection.execute("SELECT balance_cents FROM accounts WHERE account_id = %s", (ACCOUNT,)).fetchone()[0]
        print(f"vulnerable check balance={balance}")
        if balance < amount:
            print("declined")
            return
        time.sleep(pause)
        connection.execute("UPDATE accounts SET balance_cents = balance_cents - %s WHERE account_id = %s", (amount, ACCOUNT))
    print("approved")


def transaction(amount: int, pause: float, request_id: str | None = None) -> None:
    with database() as connection:
        with connection.transaction():
            row = connection.execute("SELECT balance_cents FROM accounts WHERE account_id = %s FOR UPDATE", (ACCOUNT,)).fetchone()
            if row[0] < amount:
                print("insufficient funds")
                return
            if request_id is not None:
                inserted = connection.execute(
                    "INSERT INTO idempotency_keys (request_id, account_id, amount_cents) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (request_id, ACCOUNT, amount),
                ).rowcount
                if inserted == 0:
                    print("duplicate request declined")
                    return
            time.sleep(pause)
            connection.execute("UPDATE accounts SET balance_cents = balance_cents - %s WHERE account_id = %s", (amount, ACCOUNT))
    print("approved")


def release_lock(client: redis.Redis, key: str, token: str) -> None:
    client.eval(
        "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
        1,
        key,
        token,
    )


def distributed_lock(amount: int, pause: float) -> None:
    client = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    key = "companion-race:demo-account"
    token = str(uuid.uuid4())
    deadline = time.monotonic() + 10
    while not client.set(key, token, nx=True, ex=15):
        if time.monotonic() >= deadline:
            raise TimeoutError("could not obtain local Redis lock")
        time.sleep(0.05)
    try:
        transaction(amount, pause)
    finally:
        release_lock(client, key, token)
    print("lock released")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("reset", "status", "vulnerable", "transaction", "lock", "idempotent"), required=True)
    parser.add_argument("--amount", type=int, default=700)
    parser.add_argument("--pause", type=float, default=0.0)
    parser.add_argument("--request-id", default="")
    args = parser.parse_args()
    if args.amount <= 0 or args.pause < 0:
        parser.error("amount must be positive and pause must not be negative")
    if args.mode == "reset":
        reset()
    elif args.mode == "status":
        status()
    elif args.mode == "vulnerable":
        vulnerable(args.amount, args.pause)
    elif args.mode == "transaction":
        transaction(args.amount, args.pause)
    elif args.mode == "lock":
        distributed_lock(args.amount, args.pause)
    else:
        if not args.request_id:
            parser.error("--request-id is required for idempotent mode")
        transaction(args.amount, args.pause, args.request_id)


if __name__ == "__main__":
    main()
