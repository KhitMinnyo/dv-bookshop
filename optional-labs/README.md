# DV-Bookshop Optional Security Labs

This is a self-contained, English-only lab suite. It is not part of the main DV-Bookshop application and does not import or modify its `app.py`, database, templates, static files, or uploads.

## Safety and Scope

- The server binds to `127.0.0.1:5006` only. Do not expose it to a network.
- Every identity, token, secret, payment provider, and order is dummy data.
- Runtime state is kept in `optional-labs/lab-data/`. The tenant database is `tenant_lab.db` in that directory.
- The archive labs never use the existing `static/uploads` directory.
- The intentionally vulnerable routes are included for code-reading and controlled local demonstrations. Use harmless inputs only.
- No route calls a real payment service or uses real credentials.
- The reset endpoint and `reset.sh` affect only this optional suite's runtime data.

## Start

From this directory:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
bash run.sh
```

The app is available at `http://127.0.0.1:5006`. The existing DV-Bookshop app is not started by these commands.

Reset only this suite with either command:

```sh
curl -X POST http://127.0.0.1:5006/reset
bash reset.sh
```

The reset script removes only `optional-labs/lab-data`; the app recreates it when it starts.

## 1. Host Header Injection

The vulnerable route uses `request.host` to create an absolute password-reset URL. A client controls the HTTP `Host` header unless the application or its front proxy validates it. A trusted proxy can also rewrite the host-related forwarding headers, so proxy trust must be limited to known proxies and the forwarded host must be validated at the application boundary.

The safe route requires an exact match against `localhost:5006` or `127.0.0.1:5006`. A production application should use a configured canonical origin and should not put sensitive reset tokens in links generated from arbitrary request metadata.

Harmless local examples:

```sh
curl -s -X POST http://127.0.0.1:5006/host-header/vulnerable/reset \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.test"}'

curl -s -X POST http://127.0.0.1:5006/host-header/safe/reset \
  -H 'Host: 127.0.0.1:5006' \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.test"}'
```

The returned reset URL points only to a dummy in-memory token endpoint. Do not send hostile `Host` values outside a controlled local experiment.

## 2. Zip Slip and Archive Extraction

Both routes accept a multipart field named `archive`. The vulnerable route demonstrates an unsafe `base / archive_entry_name` join. The safe route resolves each entry with `realpath` and `commonpath`, rejects absolute names, parent-directory components, and symbolic links, and extracts into a unique directory under `lab-data/zip-safe`.

Both routes enforce a maximum of 20 entries, a 512 KiB per-entry limit, and a 2 MiB total uncompressed limit. These limits reduce archive-bomb risk but do not replace resource controls outside the application. Use a harmless ZIP containing a normal file such as `notes.txt`; do not create traversal entries or point an archive at existing project files.

```sh
curl -s -X POST http://127.0.0.1:5006/zip-slip/vulnerable/extract \
  -F 'archive=@./sample.zip'

curl -s -X POST http://127.0.0.1:5006/zip-slip/safe/extract \
  -F 'archive=@./sample.zip'
```

`sample.zip` is expected to be a local, harmless test archive. Extraction is isolated from the existing bookshop files and from `static/uploads`.

## 3. YAML Insecure Deserialization

The vulnerable route is deliberately labeled and calls `yaml.load(..., Loader=yaml.Loader)`. That parser can construct Python objects from untrusted YAML and must not be used for request data. Both YAML routes reject request bodies larger than 64 KiB before parsing. The safe route uses a `SafeLoader` subclass limited to 200 parsed nodes, 20 nesting levels, and 20 aliases, then applies a small schema: a mapping with only a non-empty string `name` and an integer `quantity` from 1 through 20. These are local fixture limits, not a replacement for deployment-level request and resource controls.

Use only ordinary scalar YAML in the vulnerable example. Do not submit object-construction or code-execution payloads.

```sh
curl -s -X POST http://127.0.0.1:5006/yaml-lab/vulnerable/parse \
  -H 'Content-Type: text/plain' \
  --data-binary $'name: notebook\nquantity: 1\n'

curl -s -X POST http://127.0.0.1:5006/yaml-lab/safe/parse \
  -H 'Content-Type: text/plain' \
  --data-binary $'name: notebook\nquantity: 1\n'
```

## 4. MFA Bypass

The MFA lab uses `pyotp` and fixed dummy users. `alice` is a member and `bob` is an admin in this lab's separate identity data. The demo endpoint shows the current TOTP value and dummy backup codes so no real account is involved.

The vulnerable TOTP flow does not expire or consume a challenge. The separate vulnerable backup-code route accepts the same backup code repeatedly. The secure flow has a 120-second challenge lifetime, a three-attempt limit, exact-current-period TOTP verification, one-time challenge use, and one-time backup-code consumption.

Start and inspect a dummy flow:

```sh
curl -s http://127.0.0.1:5006/mfa/demo/alice

curl -s -X POST http://127.0.0.1:5006/mfa/vulnerable/start \
  -H 'Content-Type: application/json' -d '{"username":"alice"}'

curl -s -X POST http://127.0.0.1:5006/mfa/secure/start \
  -H 'Content-Type: application/json' -d '{"username":"alice"}'
```

Use the returned `challenge_id` and the current `current_totp` value in a local verification request. For the secure backup path, use `ALICE-BACKUP-ONE-TIME`; for the intentionally weak backup path, use `ALICE-BACKUP-REUSABLE`. Never use these patterns or values for a real account.

## 5. Multi-Tenant Authorization

The lab creates a separate SQLite database at `lab-data/tenant_lab.db` with two tenants:

- `tenant-a`: `alice` as member and `a-admin` as admin
- `tenant-b`: `bob` as member and `b-admin` as admin

Object 1 belongs to Alice in tenant A. Object 2 belongs to Bob in tenant B. The vulnerable route checks that the dummy principal exists but does not constrain the object query to that principal's tenant. The secure route requires the same tenant plus ownership, or the admin role within that same tenant. `X-Lab-User` is a training-only identity selector, not production authentication.

```sh
curl -s http://127.0.0.1:5006/tenant/demo

curl -s http://127.0.0.1:5006/tenant/vulnerable/object/2 \
  -H 'X-Lab-User: alice'

curl -s http://127.0.0.1:5006/tenant/secure/object/1 \
  -H 'X-Lab-User: alice'

curl -s http://127.0.0.1:5006/tenant/secure/object/1 \
  -H 'X-Lab-User: a-admin'
```

The first object request is a harmless read of dummy data. The secure route returns `403` when a user is outside the tenant or lacks ownership/admin scope.

## 6. Local Payment Mock

The payment lab is an in-process fake provider. It stores payments in memory and signs demo webhooks with the fixed lab-only key `optional-lab-only-webhook-secret`. It never contacts a real provider.

The vulnerable shop endpoint accepts a client-supplied amount rather than calculating the amount from the server-side order table. Its webhook uses ordinary signature equality and does not enforce a timestamp, event uniqueness, or idempotency. The secure shop endpoint uses the server-side order amount. Its webhook uses `hmac.compare_digest`, a five-minute timestamp window, exact order and amount comparison, and event-id idempotency.

Amounts are integer USD cents. The known dummy orders are `order-100` for 1999 cents and `order-200` for 4999 cents.

Create local payments:

```sh
curl -s -X POST http://127.0.0.1:5006/payment/vulnerable/create \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"order-100","amount":1999}'

curl -s -X POST http://127.0.0.1:5006/payment/secure/create \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"order-100"}'
```

Copy a returned `payment_id`, then obtain one ordinary signed dummy webhook fixture:

```sh
curl -s http://127.0.0.1:5006/payment/demo/webhook-fixture/PAYMENT_ID
```

The fixture response contains an `event` object and its `signature`. Submit those values once to either webhook route with the signature in `X-Provider-Signature`. The secure route treats a repeated event ID as an idempotent duplicate; the vulnerable route has no replay protection. Keep all testing to the dummy payment records created by this app.

## Verification

This suite is intentionally separate from the existing application. A basic static check, without starting a server, is:

```sh
python3 -m py_compile app.py
```

The optional dependencies in `requirements.txt` are required to run the app. The static check does not execute the lab routes or exploit behavior.
