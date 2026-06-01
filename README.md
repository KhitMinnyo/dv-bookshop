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
