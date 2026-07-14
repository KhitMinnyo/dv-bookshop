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

On reset — `users.db` + `bookshop.db` are rebuilt from the embedded seed, all files in `static/uploads/` are deleted (`default.png` is kept), every difficulty toggle is set back to INSECURE, and rate-limit counters are cleared. Because the DB files are deleted and recreated, even `DROP TABLE` damage is fully recovered.

---

## 🚦 Rate-Limit Demo (E2)

The login page shows a live **failed-attempt counter**. In INSECURE mode it counts but never blocks (brute-force works, visibly). Toggle E2 to **SECURE** to enforce lockout after 5 attempts / 120s.


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
├── users.db                  # Persistent user database (survives reset)
└── bookshop.db               # Shop data (resettable)
```

### Dual Database Design

| Database | Purpose | On Reset |
|---|---|---|
| `users.db` | User accounts, credentials, credit cards | **Preserved** ✅ |
| `bookshop.db` | Books, cart, orders, reviews, coupons, tickets, logs | **Wiped & Re-seeded** 🔄 |

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
| `john_doe` | `password123` | user |
| `jane_smith` | `qwerty` | user |
| `bob_wilson` | `letmein` | user |

> 20 pre-seeded users total. All have fake credit cards and $1,000 balance.

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

Educational use only.

*Built for hackers, by hackers.* ☠️
