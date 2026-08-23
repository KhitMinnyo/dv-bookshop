# Cloud IAM and Object Storage Companion Lab

This lab is an offline policy evaluator and object-storage model. It makes no
cloud calls and contains no cloud credentials. The resource names, signing key,
SAS-like token, and URLs are local demonstration values only.

## Run

Python 3.9 or newer is sufficient:

```sh
python3 policy_lab.py demo
```

The demo evaluates S3-like bucket policies, generates a short-lived
Azure-SAS-like token, and generates a GCS-signed-URL-like value. The evaluator
uses HMAC only to make token expiry and scope visible; it is not a cloud SDK or
a compatible implementation of any provider protocol.

## Concepts Covered

- The vulnerable S3-like policy grants anonymous `GetObject` access to every
  object under `demo-bucket/*`.
- The safe policy denies anonymous access, grants a reader only
  `private/reports/*`, and does not grant list or write access.
- A private object is inaccessible without an identity and an explicit policy
  match. Public access is a deliberate policy decision, not a side effect of
  an object name.
- The SAS-like token binds a method, object resource, and expiry. Verification
  must check all three, not just the signature.
- The GCS-like signed URL binds method, object path, and expiration. A real
  signed URL also includes provider-specific canonicalization and key
  management requirements.
- Presigned access should be short-lived, least-privilege, auditable, and
  issued only after the caller is authorized to delegate that access.

## Exercises

1. Change the vulnerable policy to allow only one public object and compare the
   result with the safe prefix policy.
2. Try `GetObject` and `PutObject` as `anonymous`, `report-reader`, and
   `order-reader`. Explain why a resource prefix is safer than a bucket-wide
   wildcard.
3. Verify a SAS-like token with the wrong object, wrong method, and an expired
   timestamp. Each must fail.
4. Add a maximum expiry policy and explain why a caller should not be able to
   request an arbitrarily long delegation.
5. Design a bucket policy that permits an application to write only to
   `uploads/<tenant-id>/` and cannot read another tenant's prefix.
6. Compare identity-based policy decisions with bearer URL decisions. Record
   how revocation, logging, and accidental disclosure differ.

## Optional Provider Tools

LocalStack or Azurite may be useful for a separate, disposable compatibility
exercise, but neither is required here and this directory does not configure
them. If you use one, bind it to localhost, use a fresh local data directory,
use dummy credentials supplied by that tool, and remove the container and data
afterward. Do not point provider CLIs at a real account or real bucket.

## Reset and Cleanup

The evaluator is in-memory and resets on every invocation. Stop the Python
process when finished. If you create optional LocalStack or Azurite resources,
remove only those local containers and volumes using the tool's documented
cleanup command.
