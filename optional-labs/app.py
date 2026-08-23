"""Standalone, localhost-only optional security labs for DV-Bookshop."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import shutil
import sqlite3
import stat
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

import pyotp
import yaml
from flask import Flask, jsonify, request


app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "lab-data"
VULNERABLE_ZIP_DIR = DATA_DIR / "zip-vulnerable"
SAFE_ZIP_DIR = DATA_DIR / "zip-safe"
TENANT_DB = DATA_DIR / "tenant_lab.db"

MAX_ZIP_FILES = 20
MAX_ZIP_ENTRY_BYTES = 512 * 1024
MAX_ZIP_TOTAL_BYTES = 2 * 1024 * 1024
ALLOWED_HOSTS = {"127.0.0.1:5006", "localhost:5006"}
PAYMENT_SECRET = b"optional-lab-only-webhook-secret"

DATA_DIR.mkdir(parents=True, exist_ok=True)
VULNERABLE_ZIP_DIR.mkdir(parents=True, exist_ok=True)
SAFE_ZIP_DIR.mkdir(parents=True, exist_ok=True)


def now() -> int:
    return int(time.time())


def body() -> dict:
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else {}


def error(message: str, status: int = 400):
    return jsonify({"error": message}), status


@app.get("/")
def index():
    return jsonify(
        {
            "name": "DV-Bookshop optional security labs",
            "warning": "Training code only. Use on localhost with dummy data.",
            "port": 5006,
            "labs": {
                "host_header": "/host-header",
                "zip_slip": "/zip-slip",
                "yaml": "/yaml-lab",
                "mfa": "/mfa",
                "multi_tenant": "/tenant",
                "payment": "/payment",
            },
            "reset": "POST /reset",
        }
    )


# ---------------------------------------------------------------------------
# 1. Host header injection
# ---------------------------------------------------------------------------

reset_tokens: dict[str, dict[str, str]] = {}


def make_reset_link(host: str, token: str) -> str:
    return f"http://{host}/host-header/reset/{token}"


@app.post("/host-header/vulnerable/reset")
def vulnerable_reset_link():
    """Builds an absolute link directly from the request Host header."""
    email = str(body().get("email", "demo@example.test"))[:160]
    token = secrets.token_urlsafe(18)
    reset_tokens[token] = {"email": email, "created": str(now())}
    return jsonify(
        {
            "lab": "host-header-injection",
            "mode": "vulnerable",
            "reset_link": make_reset_link(request.host, token),
            "warning": "The absolute URL trusts request.host.",
        }
    )


@app.post("/host-header/safe/reset")
def safe_reset_link():
    """Builds an absolute link only after an exact host allowlist check."""
    if request.host not in ALLOWED_HOSTS:
        return error("Host is not in the exact localhost allowlist.", 400)

    email = str(body().get("email", "demo@example.test"))[:160]
    token = secrets.token_urlsafe(18)
    reset_tokens[token] = {"email": email, "created": str(now())}
    return jsonify(
        {
            "lab": "host-header-injection",
            "mode": "safe",
            "reset_link": make_reset_link(request.host, token),
            "allowed_hosts": sorted(ALLOWED_HOSTS),
        }
    )


@app.get("/host-header/reset/<token>")
def consume_reset_link(token: str):
    record = reset_tokens.get(token)
    if record is None:
        return error("Unknown or already reset token.", 404)
    return jsonify(
        {
            "message": "Dummy reset token accepted for this lab.",
            "email": record["email"],
            "token_is_demo_only": True,
        }
    )


# ---------------------------------------------------------------------------
# 2. Zip Slip and archive extraction
# ---------------------------------------------------------------------------


def save_archive(upload) -> str:
    descriptor, path = tempfile.mkstemp(prefix="archive-", suffix=".zip", dir=DATA_DIR)
    os.close(descriptor)
    upload.save(path)
    return path


def check_archive_limits(infos: list[zipfile.ZipInfo]) -> None:
    if len(infos) > MAX_ZIP_FILES:
        raise ValueError(f"Archive has more than {MAX_ZIP_FILES} entries.")
    total = 0
    for info in infos:
        if info.file_size < 0 or info.file_size > MAX_ZIP_ENTRY_BYTES:
            raise ValueError(f"Entry exceeds the {MAX_ZIP_ENTRY_BYTES}-byte limit.")
        total += info.file_size
    if total > MAX_ZIP_TOTAL_BYTES:
        raise ValueError(f"Archive exceeds the {MAX_ZIP_TOTAL_BYTES}-byte total limit.")


def archive_upload_error():
    return error("Send a ZIP file in the 'archive' form field.", 400)


@app.post("/zip-slip/vulnerable/extract")
def vulnerable_zip_extract():
    upload = request.files.get("archive")
    if upload is None:
        return archive_upload_error()

    archive_path = save_archive(upload)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            check_archive_limits(infos)
            extracted = []
            for info in infos:
                # Deliberately unsafe: an archive filename is joined without
                # checking its real path or rejecting traversal components.
                target = VULNERABLE_ZIP_DIR / info.filename
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                extracted.append(info.filename)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        return error(f"Vulnerable extraction failed: {exc}", 400)
    finally:
        os.unlink(archive_path)

    return jsonify(
        {
            "lab": "zip-slip",
            "mode": "vulnerable",
            "directory": str(VULNERABLE_ZIP_DIR),
            "extracted": extracted,
            "warning": "Entry names were not checked before joining them to the directory.",
        }
    )


def safe_archive_target(root: Path, filename: str, info: zipfile.ZipInfo) -> Path:
    # ZIP names use slash separators, but checking backslashes too makes the
    # policy explicit if the archive is later processed on another platform.
    normalized = filename.replace("\\", "/")
    parts = normalized.split("/")
    if not normalized or normalized.startswith("/") or ".." in parts:
        raise ValueError(f"Unsafe archive entry: {filename!r}")
    mode = (info.external_attr >> 16) & 0xFFFF
    if stat.S_ISLNK(mode):
        raise ValueError(f"Symbolic links are not allowed: {filename!r}")

    root_real = os.path.realpath(root)
    target_real = os.path.realpath(os.path.join(root_real, *parts))
    try:
        inside = os.path.commonpath([root_real, target_real]) == root_real
    except ValueError:
        inside = False
    if not inside:
        raise ValueError(f"Entry leaves the extraction directory: {filename!r}")
    return Path(target_real)


@app.post("/zip-slip/safe/extract")
def safe_zip_extract():
    upload = request.files.get("archive")
    if upload is None:
        return archive_upload_error()

    archive_path = save_archive(upload)
    extraction_dir = SAFE_ZIP_DIR / uuid.uuid4().hex
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            check_archive_limits(infos)
            targets = [(info, safe_archive_target(extraction_dir, info.filename, info)) for info in infos]
            extracted = []
            for info, target in targets:
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with archive.open(info) as source, target.open("xb") as destination:
                    while True:
                        chunk = source.read(64 * 1024)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > MAX_ZIP_ENTRY_BYTES:
                            raise ValueError("Entry exceeded the extraction size limit.")
                        destination.write(chunk)
                extracted.append(info.filename)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        shutil.rmtree(extraction_dir, ignore_errors=True)
        return error(f"Safe extraction rejected the archive: {exc}", 400)
    finally:
        os.unlink(archive_path)

    return jsonify(
        {
            "lab": "zip-slip",
            "mode": "safe",
            "directory": str(extraction_dir),
            "extracted": extracted,
            "safeguards": {
                "realpath_commonpath": True,
                "rejects_parent_and_absolute_names": True,
                "rejects_symlinks": True,
                "max_files": MAX_ZIP_FILES,
                "max_entry_bytes": MAX_ZIP_ENTRY_BYTES,
                "max_total_bytes": MAX_ZIP_TOTAL_BYTES,
            },
        }
    )


# ---------------------------------------------------------------------------
# 3. YAML insecure deserialization
# ---------------------------------------------------------------------------


@app.post("/yaml-lab/vulnerable/parse")
def vulnerable_yaml_parse():
    raw = request.get_data(as_text=True)
    if not raw.strip():
        return error("Send YAML in the request body.")
    try:
        # Deliberately dangerous. Never use yaml.Loader for untrusted input.
        parsed = yaml.load(raw, Loader=yaml.Loader)
    except yaml.YAMLError as exc:
        return error(f"YAML parse error: {exc}", 400)
    return jsonify(
        {
            "lab": "yaml-insecure-deserialization",
            "mode": "vulnerable",
            "parser": "yaml.load(..., Loader=yaml.Loader)",
            "parsed_type": type(parsed).__name__,
            "parsed": repr(parsed),
            "warning": "The vulnerable parser may construct Python objects from untrusted YAML.",
        }
    )


@app.post("/yaml-lab/safe/parse")
def safe_yaml_parse():
    raw = request.get_data(as_text=True)
    if not raw.strip():
        return error("Send YAML in the request body.")
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return error(f"YAML parse error: {exc}", 400)

    if not isinstance(parsed, dict):
        return error("The safe schema requires a YAML mapping.")
    allowed = {"name", "quantity"}
    if set(parsed) - allowed:
        return error("Only the name and quantity fields are allowed.")
    if not isinstance(parsed.get("name"), str) or not parsed["name"].strip():
        return error("name must be a non-empty string.")
    quantity = parsed.get("quantity")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 20:
        return error("quantity must be an integer from 1 through 20.")
    return jsonify(
        {
            "lab": "yaml-insecure-deserialization",
            "mode": "safe",
            "parser": "yaml.safe_load",
            "validated": {"name": parsed["name"][:100], "quantity": quantity},
        }
    )


# ---------------------------------------------------------------------------
# 4. MFA bypass
# ---------------------------------------------------------------------------

MFA_USERS = {
    "alice": {"secret": "JBSWY3DPEHPK3PXP", "role": "member"},
    "bob": {"secret": "KRSXG5DSNFXGOIDN", "role": "admin"},
}
REUSABLE_BACKUP_CODES = {"alice": "ALICE-BACKUP-REUSABLE"}
ONE_TIME_BACKUP_CODES = {"alice": {"ALICE-BACKUP-ONE-TIME"}, "bob": {"BOB-BACKUP-ONE-TIME"}}
mfa_challenges: dict[str, dict] = {}


@app.get("/mfa/demo/<username>")
def mfa_demo(username: str):
    user = MFA_USERS.get(username)
    if user is None:
        return error("Unknown dummy MFA user.", 404)
    return jsonify(
        {
            "username": username,
            "secret": user["secret"],
            "current_totp": pyotp.TOTP(user["secret"]).now(),
            "vulnerable_backup_code": REUSABLE_BACKUP_CODES.get(username),
            "secure_backup_code": sorted(ONE_TIME_BACKUP_CODES[username])[0],
            "warning": "These credentials are dummy values for localhost training only.",
        }
    )


def start_mfa(username: str, secure: bool):
    if username not in MFA_USERS:
        return error("Unknown dummy MFA user.", 404)
    challenge_id = secrets.token_urlsafe(16)
    mfa_challenges[challenge_id] = {
        "username": username,
        "created": now(),
        "attempts": 0,
        "used": False,
        "secure": secure,
    }
    return jsonify({"challenge_id": challenge_id, "expires_in_seconds": 120 if secure else None})


@app.post("/mfa/vulnerable/start")
def vulnerable_mfa_start():
    return start_mfa(str(body().get("username", "")), secure=False)


@app.post("/mfa/vulnerable/verify")
def vulnerable_mfa_verify():
    data = body()
    challenge = mfa_challenges.get(str(data.get("challenge_id", "")))
    if challenge is None or challenge["secure"]:
        return error("Unknown vulnerable MFA challenge.", 404)
    username = challenge["username"]
    code = str(data.get("code", "")).strip()
    valid_totp = pyotp.TOTP(MFA_USERS[username]["secret"]).verify(code, valid_window=1)
    if not valid_totp:
        return error("MFA code was rejected.", 401)
    # Deliberately does not expire or mark the challenge as used.
    return jsonify({"authenticated": True, "mode": "vulnerable", "replayable": True})


@app.post("/mfa/vulnerable/verify-backup")
def vulnerable_backup_verify():
    data = body()
    username = str(data.get("username", ""))
    if username not in REUSABLE_BACKUP_CODES:
        return error("Unknown dummy backup-code user.", 404)
    if str(data.get("backup_code", "")) != REUSABLE_BACKUP_CODES[username]:
        return error("Backup code was rejected.", 401)
    return jsonify(
        {
            "authenticated": True,
            "mode": "vulnerable-backup-code",
            "reusable": True,
        }
    )


@app.post("/mfa/secure/start")
def secure_mfa_start():
    return start_mfa(str(body().get("username", "")), secure=True)


@app.post("/mfa/secure/verify")
def secure_mfa_verify():
    data = body()
    challenge = mfa_challenges.get(str(data.get("challenge_id", "")))
    if challenge is None or not challenge["secure"]:
        return error("Unknown secure MFA challenge.", 404)
    if challenge["used"] or now() - challenge["created"] > 120:
        return error("MFA challenge expired or was already used.", 401)
    if challenge["attempts"] >= 3:
        return error("MFA attempt limit reached.", 429)

    challenge["attempts"] += 1
    username = challenge["username"]
    code = str(data.get("code", "")).strip()
    backup_codes = ONE_TIME_BACKUP_CODES[username]
    valid = pyotp.TOTP(MFA_USERS[username]["secret"]).verify(code, valid_window=0)
    if valid:
        challenge["used"] = True
    elif code in backup_codes:
        backup_codes.remove(code)
        challenge["used"] = True
        valid = True
    if not valid:
        return error("MFA code was rejected.", 401)
    return jsonify(
        {
            "authenticated": True,
            "mode": "secure",
            "one_time_challenge": True,
            "remaining_attempts": 3 - challenge["attempts"],
        }
    )


# ---------------------------------------------------------------------------
# 5. Multi-tenant authorization
# ---------------------------------------------------------------------------


def tenant_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(TENANT_DB)
    connection.row_factory = sqlite3.Row
    return connection


def init_tenant_db() -> None:
    with tenant_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS principals (
                username TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'member'))
            );
            CREATE TABLE IF NOT EXISTS tenant_objects (
                object_id INTEGER PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                owner TEXT NOT NULL,
                label TEXT NOT NULL
            );
            """
        )
        if connection.execute("SELECT COUNT(*) FROM principals").fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO principals(username, tenant_id, role) VALUES (?, ?, ?)",
                [
                    ("alice", "tenant-a", "member"),
                    ("a-admin", "tenant-a", "admin"),
                    ("bob", "tenant-b", "member"),
                    ("b-admin", "tenant-b", "admin"),
                ],
            )
            connection.executemany(
                "INSERT INTO tenant_objects(object_id, tenant_id, owner, label) VALUES (?, ?, ?, ?)",
                [
                    (1, "tenant-a", "alice", "Tenant A private book list"),
                    (2, "tenant-b", "bob", "Tenant B private book list"),
                ],
            )


def current_principal(connection: sqlite3.Connection):
    username = request.headers.get("X-Lab-User", "alice")
    return connection.execute(
        "SELECT username, tenant_id, role FROM principals WHERE username = ?", (username,)
    ).fetchone()


@app.get("/tenant/demo")
def tenant_demo():
    with tenant_connection() as connection:
        principals = [dict(row) for row in connection.execute("SELECT * FROM principals ORDER BY username")]
        objects = [dict(row) for row in connection.execute("SELECT * FROM tenant_objects ORDER BY object_id")]
    return jsonify({"principals": principals, "objects": objects, "database": str(TENANT_DB)})


@app.get("/tenant/vulnerable/object/<int:object_id>")
def vulnerable_tenant_object(object_id: int):
    with tenant_connection() as connection:
        principal = current_principal(connection)
        if principal is None:
            return error("Unknown X-Lab-User.", 401)
        record = connection.execute(
            "SELECT object_id, tenant_id, owner, label FROM tenant_objects WHERE object_id = ?",
            (object_id,),
        ).fetchone()
    if record is None:
        return error("Object not found.", 404)
    return jsonify(
        {
            "mode": "vulnerable",
            "actor": dict(principal),
            "object": dict(record),
            "warning": "The object lookup does not constrain the result to the actor tenant.",
        }
    )


@app.get("/tenant/secure/object/<int:object_id>")
def secure_tenant_object(object_id: int):
    with tenant_connection() as connection:
        principal = current_principal(connection)
        if principal is None:
            return error("Unknown X-Lab-User.", 401)
        record = connection.execute(
            "SELECT object_id, tenant_id, owner, label FROM tenant_objects WHERE object_id = ?",
            (object_id,),
        ).fetchone()
    if record is None:
        return error("Object not found.", 404)
    same_tenant = record["tenant_id"] == principal["tenant_id"]
    owns_object = record["owner"] == principal["username"]
    is_admin = principal["role"] == "admin"
    if not same_tenant or not (owns_object or is_admin):
        return error("Object is outside the actor tenant or ownership scope.", 403)
    return jsonify({"mode": "secure", "actor": dict(principal), "object": dict(record)})


# ---------------------------------------------------------------------------
# 6. Local payment mock
# ---------------------------------------------------------------------------

ORDER_TOTALS = {"order-100": 1999, "order-200": 4999}
payments: dict[str, dict] = {}
processed_webhook_events: set[str] = set()


def provider_create_payment(order_id: str, amount: int) -> dict:
    payment_id = f"pay_{secrets.token_hex(8)}"
    payment = {
        "payment_id": payment_id,
        "order_id": order_id,
        "amount": amount,
        "status": "pending",
        "created_at": now(),
    }
    payments[payment_id] = payment
    return payment.copy()


def canonical_event(event: dict) -> bytes:
    return json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_event(event: dict) -> str:
    digest = hmac.new(PAYMENT_SECRET, canonical_event(event), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@app.get("/payment/demo/orders")
def payment_demo_orders():
    return jsonify({"orders": ORDER_TOTALS, "currency": "USD cents", "provider": "local in-process mock"})


@app.post("/payment/provider/create")
def payment_provider_create():
    data = body()
    try:
        order_id = str(data["order_id"])
        amount = int(data["amount"])
        if amount <= 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return error("order_id and a positive integer amount are required.")
    return jsonify({"provider": "local-mock", "payment": provider_create_payment(order_id, amount)})


@app.post("/payment/vulnerable/create")
def vulnerable_payment_create():
    data = body()
    try:
        order_id = str(data["order_id"])
        client_amount = int(data["amount"])
        if client_amount <= 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return error("order_id and a positive integer amount are required.")
    payment = provider_create_payment(order_id, client_amount)
    return jsonify(
        {
            "mode": "vulnerable",
            "payment": payment,
            "warning": "The shop trusted the client-supplied amount instead of its order total.",
        }
    )


@app.post("/payment/secure/create")
def secure_payment_create():
    data = body()
    order_id = str(data.get("order_id", ""))
    if order_id not in ORDER_TOTALS:
        return error("Unknown order.", 404)
    payment = provider_create_payment(order_id, ORDER_TOTALS[order_id])
    return jsonify(
        {
            "mode": "secure",
            "payment": payment,
            "amount_source": "server-side order total",
        }
    )


def payment_fixture(payment_id: str):
    payment = payments.get(payment_id)
    if payment is None:
        return None
    event = {
        "event_id": f"evt_{secrets.token_hex(8)}",
        "payment_id": payment_id,
        "order_id": payment["order_id"],
        "amount": payment["amount"],
        "status": "succeeded",
        "timestamp": now(),
    }
    return {"event": event, "signature": sign_event(event)}


@app.get("/payment/demo/webhook-fixture/<payment_id>")
def payment_webhook_fixture(payment_id: str):
    fixture = payment_fixture(payment_id)
    if fixture is None:
        return error("Unknown payment. Create one through a payment route first.", 404)
    return jsonify(fixture)


@app.post("/payment/vulnerable/webhook")
def vulnerable_payment_webhook():
    event = body()
    payment = payments.get(str(event.get("payment_id", "")))
    if payment is None:
        return error("Unknown payment.", 404)
    expected = sign_event(event)
    # Deliberately uses ordinary equality and has no timestamp, event-id, or
    # idempotency check. A valid old event can be accepted repeatedly.
    if request.headers.get("X-Provider-Signature", "") != expected:
        return error("Invalid webhook signature.", 401)
    payment["status"] = str(event.get("status", "unknown"))
    return jsonify({"mode": "vulnerable", "accepted": True, "payment": payment})


@app.post("/payment/secure/webhook")
def secure_payment_webhook():
    event = body()
    payment = payments.get(str(event.get("payment_id", "")))
    if payment is None:
        return error("Unknown payment.", 404)
    signature = request.headers.get("X-Provider-Signature", "")
    expected = sign_event(event)
    if not hmac.compare_digest(signature, expected):
        return error("Invalid webhook signature.", 401)
    try:
        event_time = int(event["timestamp"])
        amount = int(event["amount"])
        event_id = str(event["event_id"])
        order_id = str(event["order_id"])
    except (KeyError, TypeError, ValueError):
        return error("Webhook is missing required fields.", 400)
    if abs(now() - event_time) > 300:
        return error("Webhook timestamp is outside the five-minute window.", 401)
    if event_id in processed_webhook_events:
        return jsonify({"mode": "secure", "accepted": True, "duplicate": True, "payment": payment})
    expected_amount = ORDER_TOTALS.get(order_id)
    if order_id != payment["order_id"] or expected_amount is None or amount != expected_amount:
        return error("Webhook order or amount does not match server state.", 400)
    if event.get("status") != "succeeded":
        return error("Only succeeded events are handled by this demo.", 400)
    processed_webhook_events.add(event_id)
    payment["status"] = "succeeded"
    return jsonify({"mode": "secure", "accepted": True, "duplicate": False, "payment": payment})


# ---------------------------------------------------------------------------
# Optional-suite reset and startup
# ---------------------------------------------------------------------------


@app.post("/reset")
def reset_optional_suite():
    reset_tokens.clear()
    mfa_challenges.clear()
    processed_webhook_events.clear()
    payments.clear()
    for backup_codes in ONE_TIME_BACKUP_CODES.values():
        # Restore the fixed dummy code after a lab reset.
        backup_codes.clear()
    ONE_TIME_BACKUP_CODES["alice"].add("ALICE-BACKUP-ONE-TIME")
    ONE_TIME_BACKUP_CODES["bob"].add("BOB-BACKUP-ONE-TIME")
    shutil.rmtree(DATA_DIR, ignore_errors=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VULNERABLE_ZIP_DIR.mkdir(parents=True, exist_ok=True)
    SAFE_ZIP_DIR.mkdir(parents=True, exist_ok=True)
    init_tenant_db()
    return jsonify({"reset": True, "scope": "optional-labs only"})


init_tenant_db()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5006, debug=False)
