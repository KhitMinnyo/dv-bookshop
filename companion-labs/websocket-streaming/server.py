#!/usr/bin/env python3
"""Local WebSocket frame, streaming, and authorization fixture."""

import argparse
import asyncio
import json
from typing import Any

from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol, serve

HOST = "127.0.0.1"
PORT = 8765
DEMO_TOKEN = "lab-demo-token"
MAX_MESSAGE_BYTES = 4096
SAFE_CHANNELS = {"public", "user:demo-user"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("safe", "vulnerable"), default="safe")
    parser.add_argument("--host", default=HOST, help="Use loopback for the lab")
    parser.add_argument("--port", type=int, default=PORT)
    return parser.parse_args()


async def send_json(websocket: WebSocketServerProtocol, value: dict[str, Any], safe: bool) -> None:
    payload = json.dumps(value, separators=(",", ":"))
    if safe:
        # A timeout makes a stalled consumer visible instead of growing work forever.
        await asyncio.wait_for(websocket.send(payload), timeout=1.0)
    else:
        await websocket.send(payload)


async def handler(websocket: WebSocketServerProtocol, mode: str) -> None:
    safe = mode == "safe"
    try:
        first = await websocket.recv()
        if not isinstance(first, str):
            await websocket.close(code=1003, reason="authentication must be JSON text")
            return
        auth = json.loads(first)
        if not isinstance(auth, dict):
            await websocket.close(code=1008, reason="authentication must be an object")
            return
        token = auth.get("token")
        authenticated = token == DEMO_TOKEN if safe else bool(token)
        if not authenticated:
            await send_json(websocket, {"type": "error", "error": "authentication failed"}, safe)
            await websocket.close(code=1008, reason="authentication failed")
            return
        await send_json(websocket, {"type": "auth.ok", "user": "demo-user"}, safe)

        async for message in websocket:
            message_bytes = len(message.encode("utf-8")) if isinstance(message, str) else len(message)
            if safe and message_bytes > MAX_MESSAGE_BYTES:
                await websocket.close(code=1009, reason="message too large")
                return

            if isinstance(message, bytes):
                if safe and len(message) > MAX_MESSAGE_BYTES:
                    await websocket.close(code=1009, reason="binary frame too large")
                    return
                await send_json(websocket, {"type": "binary.received", "bytes": len(message)}, safe)
                if safe:
                    await asyncio.wait_for(websocket.send(b"lab-binary-echo:" + message), timeout=1.0)
                else:
                    await websocket.send(b"lab-binary-echo:" + message)
                continue

            try:
                request = json.loads(message)
            except json.JSONDecodeError:
                await send_json(websocket, {"type": "error", "error": "expected JSON text"}, safe)
                continue

            channel = request.get("channel", "public")
            if safe and channel not in SAFE_CHANNELS:
                await send_json(websocket, {"type": "error", "error": "channel not authorized"}, safe)
                continue

            if request.get("type") == "stream":
                event_count = 5 if safe else 100
                for sequence in range(event_count):
                    await send_json(
                        websocket,
                        {"type": "stream.event", "channel": channel, "sequence": sequence},
                        safe,
                    )
                    await asyncio.sleep(0.05)
                await send_json(websocket, {"type": "stream.complete", "count": event_count}, safe)
            else:
                await send_json(
                    websocket,
                    {"type": "json.received", "channel": channel, "payload": request.get("payload")},
                    safe,
                )
    except (ConnectionClosed, asyncio.TimeoutError, json.JSONDecodeError):
        return


async def main() -> None:
    args = parse_args()
    async with serve(
        lambda websocket: handler(websocket, args.mode),
        args.host,
        args.port,
        max_size=None if args.mode == "vulnerable" else MAX_MESSAGE_BYTES,
        max_queue=None if args.mode == "vulnerable" else 8,
    ):
        print(f"WebSocket lab ({args.mode}) listening on ws://{args.host}:{args.port}")
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
