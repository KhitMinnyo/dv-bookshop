# gRPC Streaming and gRPC-Web Lab

This is a separate, local-only Python gRPC fixture. It listens on `127.0.0.1:50051` and does not call DV-Bookshop or any external service. Generated protobuf Python files are intentionally not committed; the commands below create them locally.

## Definitions

- Server-streaming sends one response for a request and then yields multiple responses.
- Client-streaming accepts multiple client messages and returns one summary.
- Bidirectional streaming lets both sides yield messages independently on one RPC.
- Metadata is a request header channel commonly used for authorization context.
- TLS authenticates and encrypts a connection. Mutual TLS (mTLS) also authenticates the client with a client certificate.
- gRPC-Web is a browser-compatible protocol/transport usually terminated by a proxy that forwards to a gRPC server.

## Setup and Code Generation

Python 3.10 or newer is recommended. The dependencies are optional and are not installed by this repository.

```sh
cd grpc-streaming
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m grpc_tools.protoc \
  -I. \
  --python_out=. \
  --grpc_python_out=. \
  bookshop.proto
```

The last command should create `bookshop_pb2.py` and `bookshop_pb2_grpc.py` beside the `.proto`. They are generated local artifacts, ignored by the lab-local `.gitignore`, and removed by `cleanup.sh`.

## Run the Fixture

Start the server in one terminal, then choose a client operation in another.

```sh
python grpc_server.py --mode safe
python grpc_client.py watch --owner demo-user
python grpc_client.py upload
python grpc_client.py chat
```

Expected behavior:

- `watch` prints four ordered `BookEvent` messages from one request.
- `upload` sends three `BookUpload` messages and receives one summary.
- `chat` sends two messages and receives two replies on a bidirectional stream.

The client sends `authorization: Bearer lab-reader` metadata. This token is a training value only. Safe mode requires that token, permits only `demo-user`, and checks the owner on every Chat message. Vulnerable mode accepts any non-empty bearer token and trusts the requested owner, illustrating why authentication alone is not authorization.

To compare authorization behavior, run the server with `--mode vulnerable`, then request another owner:

```sh
python grpc_server.py --mode vulnerable
python grpc_client.py watch --owner another-user --token arbitrary-demo-token
```

These commands are local documentation. Do not run them against an external endpoint.

## TLS, mTLS, and gRPC-Web Notes

The fixture uses an insecure loopback channel so no certificates are generated or committed. For a real deployment, terminate TLS with a certificate whose hostname matches the service, validate the client certificate for mTLS, rotate credentials, and avoid silently falling back to plaintext. `grpc_server.py` contains the insertion point for `grpc.ssl_server_credentials`.

`grpc-web/envoy.yaml` is an optional configuration sketch. It binds an Envoy listener to `127.0.0.1:8080`, enables the grpc_web and cors filters, and forwards to the local gRPC port. It is not required for the Python client, and it does not provide certificates. grpc-web browser clients must still receive server-side authorization decisions; a proxy is not an authorization boundary by itself.

## Remediation

Validate metadata with a real identity provider, authorize the resource owner on every RPC, use deadlines and cancellation, cap message sizes, and apply quotas to streaming calls. Never derive permissions from a client-supplied owner string. Keep error details non-sensitive and log stream termination reasons without logging bearer tokens.

## Reset and Cleanup

Stop foreground processes with `Ctrl-C`, then run:

```sh
./cleanup.sh
```

This removes the virtual environment, generated protobuf Python files, and Python cache only within this lab. No certificates are removed because none are generated here.
