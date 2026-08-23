#!/usr/bin/env python3
"""Offline IAM and object-storage policy examples with local bearer tokens."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


LOCAL_SIGNING_KEY = b"companion-lab-only-key-do-not-use"


@dataclass(frozen=True)
class Policy:
    principal: str
    action: str
    resource_prefix: str

    def allows(self, principal: str, action: str, resource: str) -> bool:
        return (
            self.principal in (principal, "*")
            and self.action in (action, "*")
            and resource.startswith(self.resource_prefix)
        )


class LocalObjectStore:
    def __init__(self, policies: list[Policy]) -> None:
        self.policies = policies
        self.objects = {
            "public/readme.txt": b"This is a public demo object.\n",
            "private/orders/1001.json": b'{"order":"local-only"}\n',
            "private/reports/monthly.csv": b"month,total\nlocal,0\n",
        }

    def resource(self, key: str) -> str:
        return f"arn:local:s3:::demo-bucket/{key}"

    def authorized(self, principal: str, action: str, key: str) -> bool:
        return any(policy.allows(principal, action, self.resource(key)) for policy in self.policies)

    def get(self, principal: str, key: str) -> bytes:
        if not self.authorized(principal, "s3:GetObject", key):
            raise PermissionError("policy denied s3:GetObject")
        return self.objects[key]


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def signed_payload(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(LOCAL_SIGNING_KEY, encoded, hashlib.sha256).digest()
    return f"{b64(encoded)}.{b64(signature)}"


def verify_payload(token: str) -> dict[str, object]:
    encoded, supplied_signature = token.split(".", 1)
    raw = unb64(encoded)
    expected = hmac.new(LOCAL_SIGNING_KEY, raw, hashlib.sha256).digest()
    if not hmac.compare_digest(unb64(supplied_signature), expected):
        raise PermissionError("invalid local signature")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise PermissionError("invalid local token payload")
    return value


def make_sas_like(key: str, expires: int) -> str:
    return signed_payload({"sp": "r", "sr": f"/demo-bucket/{key}", "se": expires})


def verify_sas_like(token: str, key: str, method: str, now: int) -> bool:
    payload = verify_payload(token)
    return (
        method == "GET"
        and payload.get("sp") == "r"
        and payload.get("sr") == f"/demo-bucket/{key}"
        and isinstance(payload.get("se"), int)
        and now < payload["se"]
    )


def make_gcs_like(key: str, expires: int) -> str:
    token = signed_payload({"method": "GET", "object": f"demo-bucket/{key}", "expires": expires})
    return f"http://storage.local/demo-bucket/{key}?X-Goog-Expires={expires}&X-Local-Signature={token}"


def verify_gcs_like(url: str, key: str, now: int) -> bool:
    marker = "X-Local-Signature="
    if marker not in url:
        return False
    try:
        payload = verify_payload(url.split(marker, 1)[1])
    except (ValueError, PermissionError, json.JSONDecodeError):
        return False
    return (
        payload.get("method") == "GET"
        and payload.get("object") == f"demo-bucket/{key}"
        and isinstance(payload.get("expires"), int)
        and now < payload["expires"]
    )


def check(store: LocalObjectStore, principal: str, action: str, key: str) -> str:
    return "ALLOW" if store.authorized(principal, action, key) else "DENY"


def demo() -> None:
    now = int(time.time())
    vulnerable = LocalObjectStore(
        [Policy("*", "s3:GetObject", "arn:local:s3:::demo-bucket/")]
    )
    safe = LocalObjectStore(
        [Policy("report-reader", "s3:GetObject", "arn:local:s3:::demo-bucket/private/reports/")]
    )
    print("Offline evaluator; no cloud or network I/O is performed.")
    print("vulnerable anonymous private object:", check(vulnerable, "anonymous", "s3:GetObject", "private/orders/1001.json"))
    print("safe anonymous private object:", check(safe, "anonymous", "s3:GetObject", "private/orders/1001.json"))
    print("safe report reader report:", check(safe, "report-reader", "s3:GetObject", "private/reports/monthly.csv"))
    print("safe report reader write:", check(safe, "report-reader", "s3:PutObject", "private/reports/monthly.csv"))
    sas = make_sas_like("private/reports/monthly.csv", now + 60)
    print("SAS-like valid:", verify_sas_like(sas, "private/reports/monthly.csv", "GET", now))
    print("SAS-like wrong object:", verify_sas_like(sas, "private/orders/1001.json", "GET", now))
    print("SAS-like expired:", verify_sas_like(sas, "private/reports/monthly.csv", "GET", now + 61))
    gcs_url = make_gcs_like("private/reports/monthly.csv", now + 60)
    print("GCS-like valid:", verify_gcs_like(gcs_url, "private/reports/monthly.csv", now))
    print("GCS-like expired:", verify_gcs_like(gcs_url, "private/reports/monthly.csv", now + 61))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo",))
    args = parser.parse_args()
    if args.command == "demo":
        demo()


if __name__ == "__main__":
    main()
