# ☠️ Khit's Bookshop — Damn Vulnerable Bookshop

An **intentionally vulnerable** e-commerce web application built with **Python Flask** and **SQLite**. Designed as a comprehensive hands-on lab for learning web application security — from beginner to advanced level.

> ⚠️ **Disclaimer:** This application is for **educational purposes only**. Do not deploy in production. All vulnerabilities are deliberate for safe, legal practice in a controlled environment.

---

## 🔥 Vulnerability Categories

| # | Category | Count |
|---|---|---|
| 1 | SQL Injection | 7 |
| 2 | Cross-Site Scripting (XSS) | 5 |
| 3 | Cross-Site Request Forgery (CSRF) | 5 |
| 4 | Insecure Direct Object Reference (IDOR) | 5 |
| 5 | Account Takeover | 5 |
| 6 | Broken Auth & Access Control | 6 |
| 7 | File Upload | 3 |
| 8 | Command Injection | 2 |
| 9 | SSRF | 1 |
| 10 | Sensitive Data Exposure | 7 |
| 11 | Business Logic Flaws | 5 |
| 12 | Miscellaneous | 6 |
| 13 | JWT / Token Auth | 2 |

---

## 🎚️ Lab Control Panel & Difficulty Toggle

Visit **`/lab`** to switch selected vulnerabilities between **INSECURE** (vulnerable, default) and **SECURE** (patched) mode — no code editing needed. Great for demonstrating before/after in class. State is saved to `lab_config.json` and survives restarts.

Currently toggleable:

| ID | Vulnerability |
|---|---|
| A5 | SQL Injection — Login bypass |
| A7 | SQL Injection — Book search |
| B1 | Reflected XSS — Search page |
| D1 | IDOR — Profile viewing |
| E2 | Login rate-limiting (brute-force) |
| JWT | JWT signature & `alg` verification |

> Extend it by adding a key to `DEFAULT_LAB_CONFIG` and guarding the vulnerable code with `if is_secure('<id>')`.

---

## 🔑 JWT Auth Endpoints (intentionally vulnerable)

Dependency-free JWT implementation. Weak signing secret (`secret`, HS256) + accepts `alg:none`.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/jwt/login` | Get a JWT (`{username, password}` JSON or form) |
| GET | `/api/jwt/me` | Return identity from `Authorization: Bearer <token>` |
| GET | `/api/jwt/admin` | Admin-only; returns the flag if token claims `role=admin` |

**Attack paths:** forge an `alg:none` token with `role=admin`, or brute-force the weak HS256 secret, then hit `/api/jwt/admin`. Turn on the `JWT_verify` toggle to patch both.

---

## ♻️ Full Lab Reset

If the lab breaks while practicing exploitation (SQLi `DROP TABLE`, modified passwords/roles, uploaded files), you can restore it to a pristine state. Two ways —

- **CLI:** `./reset.sh` (best to run while the app is stopped — most reliable)
- **Browser:** `/lab` panel → **Reset Lab to Pristine** button

On reset — `users.db`, `bookshop.db`, and the isolated `race_lab.db` are rebuilt from the embedded seed, all files in `static/uploads/` are deleted (`default.png` is kept), every difficulty toggle is set back to INSECURE, and rate-limit counters are cleared. Because the DB files are deleted and recreated, even `DROP TABLE` damage is fully recovered.

---

## 🚦 Rate-Limit Demo (E2)

The login page shows a live **failed-attempt counter**. In INSECURE mode it counts but never blocks (brute-force works, visibly). Toggle E2 to **SECURE** to enforce lockout after 5 attempts / 120s.

---

## 🏁 Isolated Race-Condition Lab

The existing `/transfer` workflow remains unchanged. For a repeatable race-condition exercise, the app now includes a separate lab database and API under `/api/race-lab/*`.

The race lab uses two disposable accounts:

- `alice_hacker` starts with a balance of `$100.00`.
- `bob_secure` starts with a balance of `$0.00`.

The lab database is `race_lab.db`; it is separate from `users.db` and `bookshop.db`. Resetting the race lab does not change shop orders, carts, coupons, or the main user database.

### Race-Lab Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/race-lab/status` | Show isolated balances and recent transfers |
| POST | `/api/race-lab/transfer/vulnerable` | Demonstrate a check-then-act race |
| POST | `/api/race-lab/transfer/safe` | Compare an atomic transaction-based fix |
| POST | `/api/race-lab/reset` | Reset only `race_lab.db` |

### Step 1: Login and Check the Baseline

Use the port configured by `run.sh` (`5005`):

```bash
curl -s -c race.cookies -L -X POST http://localhost:5005/login \
  -d 'username=alice_hacker&password=password123' \
  -o /dev/null

curl -s -b race.cookies http://localhost:5005/api/race-lab/status | jq
```

### Step 2: Sequential Baseline

Send two `$75` transfers one after another. The first should be accepted and the second should be rejected because the balance is then `$25`.

```bash
curl -s -b race.cookies -X POST http://localhost:5005/api/race-lab/transfer/vulnerable \
  -H 'Content-Type: application/json' \
  -d '{"recipient":"bob_secure","amount":75}' | jq

curl -s -b race.cookies -X POST http://localhost:5005/api/race-lab/transfer/vulnerable \
  -H 'Content-Type: application/json' \
  -d '{"recipient":"bob_secure","amount":75}' | jq
```

Reset the isolated lab before the concurrent test:

```bash
curl -s -b race.cookies -X POST http://localhost:5005/api/race-lab/reset | jq
```

### Step 3: Concurrent Requests

The vulnerable endpoint checks the balance, waits briefly, and then updates it. Two requests can both pass the check before either update is written.

```bash
for i in 1 2; do
  curl -s -b race.cookies -X POST http://localhost:5005/api/race-lab/transfer/vulnerable \
    -H 'Content-Type: application/json' \
    -d '{"recipient":"bob_secure","amount":75}' > /tmp/race-result-$i.json &
done
wait

cat /tmp/race-result-1.json | jq
cat /tmp/race-result-2.json | jq
curl -s -b race.cookies http://localhost:5005/api/race-lab/status | jq
```

On the vulnerable path, both requests may be accepted and Alice's isolated balance may become negative. Exact timing and SQLite behavior can vary, so compare the accepted-transfer count, final balance, and transfer records rather than relying on one number.

### Step 4: Test the Fixed Path

Reset the isolated database, then send the same requests to `/transfer/safe`. The transaction and conditional update allow at most one `$75` transfer from the `$100` balance.

```bash
curl -s -b race.cookies -X POST http://localhost:5005/api/race-lab/reset | jq

for i in 1 2; do
  curl -s -b race.cookies -X POST http://localhost:5005/api/race-lab/transfer/safe \
    -H 'Content-Type: application/json' \
    -d '{"recipient":"bob_secure","amount":75}' > /tmp/safe-result-$i.json &
done
wait

curl -s -b race.cookies http://localhost:5005/api/race-lab/status | jq
```

### What This Lab Teaches

- A sequential test can pass even when concurrent requests are unsafe.
- A check followed by a separate update creates a time-of-check/time-of-use window.
- A database transaction and conditional update can make the balance rule atomic.
- A unique constraint or idempotency key is also needed when an operation must happen only once.
- This local SQLite lab demonstrates the pattern; production systems may need row locks, database isolation, distributed locks, or idempotency keys.

`./reset.sh` now resets `race_lab.db` as well as the existing lab databases. The race-lab endpoints are intentionally local-training endpoints and must not be exposed outside an authorized lab.

---

## 🧪 Optional and Companion Labs

The core Bookshop application remains a small Flask + SQLite lab. Additional topics are isolated so they do not change the existing routes, databases, default port, or original exercises.

### Optional App Labs (`optional-labs/`)

Run these as a separate Flask app on port `5006`:

| Lab | Coverage |
|---|---|
| Host Header | Password-reset link poisoning, exact host allowlists, trusted proxy boundaries |
| Archive | Zip Slip, archive extraction, path jail, symlink and archive-size checks |
| YAML | Unsafe YAML deserialization versus safe parsing and schema validation |
| MFA | TOTP replay, backup-code reuse, expiry, attempt limits, and secure verification |
| Multi-tenant | Tenant isolation, cross-tenant IDOR, role checks, and object ownership |
| Payment mock | Amount trust, webhook replay, HMAC signatures, timestamps, and idempotency |

```bash
cd optional-labs
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

See `optional-labs/README.md` for localhost-only curl examples. Reset only these labs with `optional-labs/reset.sh`.

### Infrastructure Labs (`infra-labs/`)

These labs are optional and require their own tools or containers:

| Directory | Coverage |
|---|---|
| `infra-labs/gateway/` | Nginx gateway, Varnish cache, cache keys, forwarded headers, WAF behavior |
| `infra-labs/tls/` | Local CA, server certificates, client certificates, and mTLS |
| `infra-labs/metadata-mock/` | Local IMDSv1/IMDSv2-style metadata mock with dummy values |
| `infra-labs/hardening/` | Non-root containers, read-only filesystems, network separation, and resource limits |

All infrastructure lab ports are separate from the core app. Do not connect them to real cloud metadata services or production systems.

### Protocol and Identity Companion Labs (`companion-labs/`)

| Directory | Coverage |
|---|---|
| `http-desync/` | Bounded CL.TE/TE.CL parser-difference demonstration |
| `kubernetes/` | Vulnerable/hardened manifests, RBAC, service accounts, NetworkPolicy, and Ingress |
| `cloud-iam-storage/` | Offline S3-like, Azure SAS-like, and GCS signed-URL policy models |
| `saml-sso/` | Local SAML/SSO assertion, audience, recipient, RelayState, replay, and wrapping concepts |
| `webauthn-passkeys/` | Browser-only WebAuthn registration, authentication, challenge, and recovery scaffold |
| `distributed-race/` | Isolated Postgres/Redis race, row locks, distributed locks, and idempotency |
| `advanced-mobile-native-reversing/` | Owner-controlled Android fixture, APK resource inspection, runtime config, and pinning |
| `websocket-streaming/` | JSON/binary frames, streaming events, message limits, and authorization |
| `grpc-streaming/` | Server/client/bidirectional streaming, metadata, TLS, mTLS, and gRPC-Web concepts |
| `prototype-pollution/` | Node.js object pollution, deep merge, path setter, and safe filtering |

Each companion lab has its own README, dependencies, ports, and cleanup instructions. Do not install or run every lab in the core `run.sh` environment.

### Suggested Learning Order

1. Complete the original DV-Bookshop chapters and the isolated race lab.
2. Complete `optional-labs/` in this order: Host Header, Archive, YAML, MFA, Multi-tenant, Payment mock.
3. Study `infra-labs/tls/` and `infra-labs/gateway/` before HTTP desynchronization and cache labs.
4. Study `companion-labs/cloud-iam-storage/`, `kubernetes/`, and `distributed-race/` with disposable local infrastructure.
5. Complete the SAML, WebAuthn, mobile, WebSocket, gRPC, and prototype-pollution labs using their stated toolchains.
6. Record scope, baseline, evidence, cleanup, and remediation for every exercise.

All offensive examples in these directories are for local, owned, or explicitly authorized training targets only.


---

## 🏗️ Architecture

```
bookshop-m/
├── app.py                    # Main Flask application (~40 routes)
├── README.md
├── templates/                # 25 Jinja2 templates
├── static/
│   ├── css/style.css         # Dark theme CSS
│   ├── js/app.js             # Client-side JavaScript
│   └── uploads/              # User avatar uploads
├── users.db                  # User database (resettable)
├── bookshop.db               # Shop data (resettable)
└── race_lab.db               # Isolated race-condition lab data (resettable)
```

### Database Design

| Database | Purpose | On Reset |
|---|---|---|
| `users.db` | User accounts, credentials, credit cards | **Wiped & Re-seeded** 🔄 |
| `bookshop.db` | Books, cart, orders, reviews, coupons, tickets, logs | **Wiped & Re-seeded** 🔄 |
| `race_lab.db` | Isolated race-condition accounts and transfer records | **Wiped & Re-seeded** 🔄 |

---

## 🚀 Setup

```bash
git clone https://github.com/KhitMinnyo/dv-bookshop
cd dv-bookshop
chmod +x install.sh
./install.sh
chmod +x run.sh
./run.sh
```

Access at `http://localhost:5005`

---

## 👤 Default Accounts

| Username | Password | Role |
|---|---|---|
| `alice_hacker` | `password123` | user |
| `bob_secure` | `bob2025secure` | user |
| `charlie_cyber` | `charlie789!` | user |
| `admin` | `SuperSecurePass2025!` | admin |
| `frank_root` | `fr4nk_r00t!` | moderator |

> 20 pre-seeded users total. Credit cards and balances are fake lab data.

---

## 🏁 CTF

**Flag Format:** `CTF{...}`

**Objective:** Extract the admin's flag from `secret_note`.

| Level | Targets |
|---|---|
| 🟢 Easy | Reflected XSS, IDOR, Username enumeration |
| 🟡 Medium | SQL Injection, Stored XSS, CSRF |
| 🔴 Hard | Blind SQLi, Command injection, Race condition |
| ⚫ Expert | Insecure deserialization, Chained exploits |

---

## 📝 License

MIT License. See [LICENSE](LICENSE). The application and all testing examples
are for authorized educational use only; do not deploy this lab in production.

*Built for hackers, by hackers.* ☠️
