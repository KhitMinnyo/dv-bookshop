# WebAuthn and Passkeys Browser Lab

This is a browser-oriented WebAuthn ceremony scaffold. It serves a local page,
creates server-side challenges, and displays the browser's registration and
authentication payloads. It does not implement production attestation or
assertion signature verification. A successful browser call therefore means
only that the ceremony-shaped data reached the local scaffold; it is not proof
of authentication.

## Requirements and Scope

- Use a current browser with WebAuthn support and a platform authenticator or
  security key. A device PIN or biometric may be requested by the browser.
- Use exactly `http://localhost:8000/`. Browsers generally allow WebAuthn on
  localhost as a secure-context exception. Do not change the host, port, or
  origin without also changing the configured RP ID and using HTTPS.
- `curl` cannot complete a WebAuthn ceremony because a browser or authenticator
  must create and sign the credential data. The JavaScript calls
  `navigator.credentials.create` and `navigator.credentials.get`.
- This fixture binds challenges to in-memory pending ceremonies and checks the
  expected origin and challenge shape. It intentionally does not parse CBOR,
  validate an attestation chain, verify a public-key signature, or persist
  credential state.

## Run

```sh
python3 server.py
```

Open `http://localhost:8000/`, choose `Register a passkey`, then choose
`Authenticate`. The server binds to `127.0.0.1` only and stores all state in
memory. Stop it with `Ctrl-C` to reset all challenges and credentials.

## Ceremony Checklist

Registration uses a fresh random challenge, an RP ID of `localhost`, a local RP
name, a user handle, and supported public-key algorithms. Authentication uses
a separate challenge and the RP ID. In a real backend, verify:

- `clientDataJSON.type` is `webauthn.create` or `webauthn.get` as appropriate.
- The decoded challenge equals the server-issued, single-use challenge.
- `clientDataJSON.origin` exactly matches the expected origin.
- The RP ID hash in authenticator data matches the configured RP ID.
- User presence and, when required, user verification flags are set.
- The signature verifies with the stored credential public key over the exact
  authenticator data and client-data hash.
- The credential ID belongs to the account and is not accepted as an account
  identifier by itself.
- The signature counter is tracked. A decrease may indicate a cloned
  authenticator, but counter behavior varies by authenticator and should be
  handled according to the WebAuthn specification.

## Recovery Design Questions

Passkeys are not a complete account-recovery policy. Decide how users recover
when every authenticator is lost, how new authenticators are enrolled, how
recovery is rate-limited and audited, and whether recovery requires a second
independent factor or administrator review. Avoid weakening recovery until it
defeats the assurance provided by the passkey.

## Cleanup

Stop the local Python process. There are no files, cloud resources, browser
accounts, or external identity providers to clean up. Remove any browser test
credential from the browser or authenticator only if it was created for this
local exercise.
