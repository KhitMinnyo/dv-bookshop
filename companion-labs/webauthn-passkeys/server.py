#!/usr/bin/env python3
"""Loopback-only WebAuthn ceremony scaffold; not a production verifier."""

from __future__ import annotations

import base64
import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ORIGIN = "http://localhost:8000"
RP_ID = "localhost"
PENDING: dict[str, str] = {}
REGISTERED_CREDENTIALS: set[str] = set()


def encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class Handler(BaseHTTPRequestHandler):
    def send_json(self, value: dict[str, object], status: int = 200) -> None:
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        paths = {"/": "index.html", "/webauthn.js": "webauthn.js"}
        filename = paths.get(self.path)
        if filename is None:
            self.send_error(404, "not found")
            return
        body = (ROOT / filename).read_bytes()
        content_type = "text/html; charset=utf-8" if filename.endswith(".html") else "text/javascript; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 1_000_000:
            raise ValueError("invalid request size")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("JSON object required")
        return value

    def do_POST(self) -> None:
        try:
            if self.path == "/options/register":
                challenge = secrets.token_bytes(32)
                challenge_key = encode(challenge)
                PENDING[challenge_key] = "register"
                self.send_json({"publicKey": {
                    "challenge": challenge_key,
                    "rp": {"name": "Local WebAuthn Lab", "id": RP_ID},
                    "user": {"id": encode(b"local-user-001"), "name": "user@localhost", "displayName": "Local Demo User"},
                    "pubKeyCredParams": [{"type": "public-key", "alg": -7}, {"type": "public-key", "alg": -257}],
                    "timeout": 60000,
                    "authenticatorSelection": {"residentKey": "preferred", "userVerification": "preferred"}
                }})
                return
            if self.path == "/options/authenticate":
                challenge = encode(secrets.token_bytes(32))
                PENDING[challenge] = "authenticate"
                self.send_json({"publicKey": {"challenge": challenge, "rpId": RP_ID, "timeout": 60000, "userVerification": "preferred"}})
                return
            payload = self.read_json()
            if self.path == "/verify/register":
                self.verify_register(payload)
                return
            if self.path == "/verify/authenticate":
                self.verify_authenticate(payload)
                return
            self.send_json({"error": "not found"}, 404)
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)

    def validate_client_data(self, payload: dict[str, object], expected_type: str) -> tuple[str, str]:
        response = payload.get("response")
        if not isinstance(response, dict):
            raise ValueError("response object is required")
        encoded = response.get("clientDataJSON")
        if not isinstance(encoded, str):
            raise ValueError("clientDataJSON is required")
        data = json.loads(decode(encoded))
        if data.get("type") != expected_type or data.get("origin") != ORIGIN:
            raise ValueError("client data type or origin mismatch")
        challenge = data.get("challenge")
        expected_purpose = "register" if expected_type == "webauthn.create" else "authenticate"
        if not isinstance(challenge, str) or PENDING.pop(challenge, None) != expected_purpose:
            raise ValueError("challenge is missing, expired, or has the wrong purpose")
        return challenge, payload.get("id", "")

    def verify_register(self, payload: dict[str, object]) -> None:
        _, credential_id = self.validate_client_data(payload, "webauthn.create")
        if not isinstance(credential_id, str) or not credential_id:
            raise ValueError("credential id is required")
        raw_id = payload.get("rawId")
        if not isinstance(raw_id, str) or decode(raw_id) == b"":
            raise ValueError("raw credential id is required")
        REGISTERED_CREDENTIALS.add(credential_id)
        self.send_json({"accepted": True, "credentialId": credential_id, "secureVerificationAvailable": False, "note": "Shape checked only; attestation and signature verification are intentionally omitted."})

    def verify_authenticate(self, payload: dict[str, object]) -> None:
        _, credential_id = self.validate_client_data(payload, "webauthn.get")
        if credential_id not in REGISTERED_CREDENTIALS:
            raise ValueError("credential was not registered in this process")
        response = payload.get("response")
        if not isinstance(response, dict) or not response.get("authenticatorData") or not response.get("signature"):
            raise ValueError("authenticator data and signature are required")
        self.send_json({"accepted": True, "credentialId": credential_id, "secureVerificationAvailable": False, "note": "Shape checked only; RP hash, flags, counter, and public-key signature still require a real verifier."})


if __name__ == "__main__":
    print(f"Local WebAuthn lab: {ORIGIN}/")
    HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
