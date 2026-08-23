# WebSocket Binary Frames and Streaming Lab

This lab is a local-only Python fixture. It demonstrates protocol handling concerns without touching DV-Bookshop. The service listens on `127.0.0.1:8765` only after the learner starts it.

## Definitions

- A WebSocket text frame carries UTF-8 text, commonly JSON.
- A WebSocket binary frame carries opaque bytes and should be validated independently from JSON.
- Server streaming is an application pattern where one request causes multiple server-to-client events; WebSocket keeps the connection open for those events.
- Backpressure is the process of limiting or slowing producers when a consumer cannot accept data fast enough.
- Authentication identifies a caller. Authorization checks whether that caller may access the requested channel or operation.

## Setup

Python 3.10 or newer is recommended. The dependency is intentionally optional and is not installed by this repository.

```sh
cd websocket-streaming
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

## Start and Exercise

The default is safe mode. Use a second terminal for the client.

```sh
python server.py --mode safe
python client.py --mode safe
```

The client sends an authentication message, a JSON message, a binary frame, and a streaming request. Expected output includes a JSON acknowledgment, binary-frame metadata, a binary echo, and five ordered `stream.event` messages.

To compare the intentionally unsafe behavior:

```sh
python server.py --mode vulnerable
python client.py --mode vulnerable --channel private:other-user
```

Vulnerable mode accepts any non-empty token, permits arbitrary channel names, accepts a larger frame, and does not use the bounded event policy. Safe mode requires the demo token, allows only `public` or `user:demo-user`, rejects oversized frames, and bounds the streamed event count. Both modes are examples, not production authentication.

The client uses only `ws://127.0.0.1:8765`. It makes no external calls. The demo token is not a secret.

## Inspect the Controls

Read `server.py` while exercising these cases:

1. Send a text JSON message with a normal payload.
2. Send a binary frame and observe that the server does not parse it as JSON.
3. Request `stream` and observe multiple server events on one connection.
4. Change the channel to `private:other-user`; safe mode should return an authorization error.
5. Change the client to send more than `MAX_MESSAGE_BYTES`; safe mode should close the connection with a size error.

The safe server sets a small `max_size` and `max_queue`, validates message types, uses a bounded stream count, and applies a send timeout. In a production service, also use per-user quotas, cancellation propagation, application-level rate limits, observability, and a deliberate binary format.

## Remediation

Authenticate during the handshake or first message, then derive identity from verified credentials rather than trusting a client-supplied user or channel. Enforce authorization for every subscription and command. Apply limits before deserialization, use bounded queues, honor cancellation, and close idle or malformed connections with a documented policy.

## Reset and Cleanup

Stop the server and client with `Ctrl-C`, then remove only this lab's local environment and caches:

```sh
./cleanup.sh
```

The script does not remove Python installations or global packages. If the script is not executable on the current filesystem, run `sh cleanup.sh`.
