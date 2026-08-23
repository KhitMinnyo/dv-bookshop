# Local TLS and Mutual TLS Lab

This lab uses Nginx on `127.0.0.1:5443`. It requires a client certificate signed by a local, short-lived test CA. No certificate or private key is committed. The files in `generated/` are created only when an authorized user explicitly runs the generation script.

## Generate Local-Only Material

From this directory, review `scripts/generate-certs.sh`, then run it only for this local lab:

```sh
bash scripts/generate-certs.sh
```

The script creates a test CA, a server certificate for `localhost` and `127.0.0.1`, and a client certificate for the lab. It uses a seven-day validity period and restrictive file permissions. These values are dummy training identities, not credentials for any other service.

## Start and Test

After generation:

```sh
docker compose --profile mtls up
```

The Nginx service binds only to `127.0.0.1:5443` and requires a client certificate. A request without the client certificate should fail TLS verification. With the generated client material, a harmless request is:

```sh
curl --cacert generated/ca.crt \
  --cert generated/client.crt \
  --key generated/client.key \
  https://127.0.0.1:5443/healthz
```

Stop the service with:

```sh
docker compose --profile mtls down --remove-orphans
```

## TLS Is Not Authorization

TLS encrypts the connection and authenticates the server to the client when the client trusts the CA. Mutual TLS additionally authenticates possession of a client private key. It does not decide whether that client may read an order, call an admin route, or perform a particular business action. The application or gateway must map the verified certificate identity to an explicit authorization policy, account, tenant, and audit record.

## Rotation

Certificates and private keys need an owner, a short validity period, an overlap window, revocation or replacement handling, and a tested reload process. Rotate server certificates before expiry and rotate client certificates independently when a client is removed or compromised. Never copy this lab CA or its keys into a production trust store. Run `bash scripts/clean.sh` to remove only generated lab files.

## Reset and Safety

`bash scripts/clean.sh` removes `generated/ca.crt`, `generated/ca.key`, `generated/server.crt`, `generated/server.key`, `generated/server.csr`, `generated/client.crt`, `generated/client.key`, and `generated/client.csr` if present. It does not remove files outside `tls/generated/`.

Use this lab only on systems you own or are authorized to test. Do not expose port `5443`, reuse the CA, or use the generated keys with a real application.
