# DV-Bookshop Infrastructure Labs

These labs are optional, isolated training material. They do not modify the DV-Bookshop application, its databases, `run.sh`, or `install.sh`.

## Authorization and Local-Only Scope

- Run these labs only on a machine and application that you own or are explicitly authorized to test.
- Keep every service bound to loopback. Do not publish these examples to a LAN, the Internet, a cloud network, or a shared Docker host.
- Use only the dummy values in these files. Never place production certificates, private keys, cloud credentials, customer data, or real API tokens in this directory.
- The metadata mock is not a cloud metadata service and makes no cloud requests.
- The gateway examples are defensive configuration examples. Use harmless paths and headers only; do not use them as a target against an external service.

## Labs

| Directory | Purpose | Local entry point |
|---|---|---|
| `gateway/` | Nginx gateway, Varnish cache, and dummy backend | `http://127.0.0.1:8088` |
| `tls/` | Nginx TLS and mutual TLS with a local test CA | `https://127.0.0.1:5443` |
| `metadata-mock/` | AWS IMDSv1 and IMDSv2-style local metadata mock | `http://127.0.0.1:5160` |
| `hardening/` | Non-root, read-only, limited-resource container example | `http://127.0.0.1:8090` |

The ports above are intentionally different from the main DV-Bookshop port `5005`.

## Reset and Cleanup

Stop each Compose lab from its own directory with `docker compose down --remove-orphans`. Add `--volumes` only when you also want to remove that lab's named volumes. The gateway and hardening examples do not persist application data.

Stop the metadata mock with `Ctrl-C`; it keeps no state. Remove its Python bytecode cache if one was created by a local run:

```sh
rm -rf metadata-mock/__pycache__
```

For the TLS lab, run `bash scripts/clean.sh` from `tls/` after stopping its Compose service. That removes only locally generated TLS files under `tls/generated/`. The cleanup script does not touch any root project files.

Do not use the root `reset.sh` to manage these labs. It is outside this directory and has a different scope.

## Static Checks

The following checks do not start a server, run Docker, call a cloud service, or generate certificates:

```sh
python3 -c "from pathlib import Path; compile(Path('metadata-mock/mock_metadata.py').read_text(), 'metadata-mock/mock_metadata.py', 'exec')"
python3 -c "from pathlib import Path; compile(Path('hardening/example_app.py').read_text(), 'hardening/example_app.py', 'exec')"
```

Review Compose and Nginx/Varnish files before any optional local run. Docker and OpenSSL are deliberately not invoked by this documentation.
