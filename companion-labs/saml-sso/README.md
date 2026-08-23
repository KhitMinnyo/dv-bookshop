# SAML and SSO Companion Lab

This is a local Flask fixture with a mock identity provider and a mock service
provider. It creates a small SAML-like response containing an assertion,
conditions, audience, recipient, destination, `RelayState`, and a local HMAC
signature. It never contacts an external identity provider.

The HMAC is a teaching substitute for XML Digital Signature. It is not a SAML
implementation and must not be used for production authentication. Production
code needs a maintained SAML library, correct XML canonicalization, certificate
validation, replay protection, and provider-specific interoperability tests.

## Exact Scope and Run

Use only the loopback URL printed by the server. The fixed issuer, audience,
recipient, destination, and user values are dummy local values. Do not expose
the listener, replace the values with a real tenant, or paste a real SAML
response into the fixture.

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 saml_lab.py
```

Open `http://127.0.0.1:5005/` in a browser and choose `Start local SSO`. The
mock IdP issues a response and the browser posts it to the local ACS endpoint.
The app keeps pending requests and sessions in memory only.

## Validation Walkthrough

The service provider checks all of the following before creating a session:

- Response destination is exactly the configured ACS URL.
- Response issuer is exactly the configured local issuer.
- `InResponseTo` matches a pending request and is not reused.
- `RelayState` is an allowlisted relative path, not an arbitrary redirect URL.
- Exactly one direct assertion is present. The signed assertion is resolved by
  its expected ID and its signature reference must match that ID.
- The local signature is valid. In production, verify the XML signature against
  a trusted certificate and enforce a safe algorithm policy.
- `NotBefore` and `NotOnOrAfter` are valid with a small clock-skew allowance.
- Audience equals the local service-provider entity ID.
- Subject confirmation `Recipient` equals the local ACS URL and its expiry is
  valid.
- The assertion `NameID` is linked with the exact issuer as a stable identity
  key. Email is an attribute, not an account-linking proof.

## Security Exercises

1. Change the destination, audience, recipient, or issuer in `make_response`
   and observe that the ACS rejects the response.
2. Re-submit the same response and observe the `InResponseTo` replay check.
3. Add a second assertion, or move the signed assertion under an unexpected
   wrapper, then explain why selecting the first descendant would enable an
   XML signature-wrapping risk. The fixture intentionally accepts only one
   direct assertion and verifies the selected node.
4. Change the `RelayState` to an absolute URL and observe the allowlist. A real
   application should use a server-side state handle rather than trusting a
   return URL supplied by a client.
5. Review `identity_key` in the source. Explain why automatically linking an
   IdP email to an existing local account can let an attacker claim an account
   when email ownership or issuer identity is not independently established.
6. Identify where a production implementation must validate certificate trust,
   canonicalization, algorithm restrictions, replay storage, session binding,
   and clock skew.

## Reset and Cleanup

Stop the process with `Ctrl-C` and remove the optional `.venv` directory if it
was created. All pending requests and sessions disappear when the process
stops. No browser or external IdP state is required.
