# Docker Hardening Example

This lab packages a tiny DV-Bookshop-style HTTP placeholder as an example of container controls. It is not a replacement for the deliberately vulnerable root application and does not copy the root `run.sh` or `install.sh`. The placeholder exposes only `/` and `/healthz`, stores no data, and contains no credentials.

## Controls Demonstrated

- The image runs as the non-root `bookshop` user.
- The container filesystem is read-only and only `/tmp` is a writable in-memory filesystem.
- The public proxy and app use separate `edge` and internal `app_net` networks. The app has no host port.
- The proxy is the only loopback-published service, on `127.0.0.1:8090`.
- Both services drop Linux capabilities and enable `no-new-privileges`.
- Health checks test the local proxy and app.
- CPU, memory, process, and file-descriptor limits are explicit examples.
- No secret is passed through the Dockerfile, copied into the image, or placed in an environment variable.

## Start and Stop

From this directory:

```sh
docker compose --profile hardened up --build
curl -i http://127.0.0.1:8090/healthz
curl -i http://127.0.0.1:8090/
docker compose --profile hardened down --remove-orphans
```

This is an optional local build. The build context is the repository root only so the Dockerfile can be selected without changing any root files; the Dockerfile copies only `infra-labs/hardening/example_app.py`.

## Adapting a Real Application

An application that writes SQLite files or uploaded files beneath its source directory cannot be made read-only by changing one Compose flag. Move runtime state to a deliberate writable volume or external service, use a non-root-compatible directory, and make the application path configurable. Keep databases, uploads, logs, and caches out of the image. Supply production secrets through an approved runtime secret manager rather than `ARG`, `ENV`, source files, or image layers.

Add a real reverse proxy only after defining trusted proxy addresses and health semantics. Restrict outbound network access where practical, pin and scan image versions, set a suitable seccomp or AppArmor policy, and review the resource limits for the workload.

## Reset and Safety

The example has no persistent volume. `docker compose --profile hardened down --remove-orphans` removes its containers and networks. Add `--volumes` if you later add disposable volumes. Run only on a host you control and do not publish the proxy beyond loopback.
