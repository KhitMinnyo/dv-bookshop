#!/usr/bin/env python3
"""Small client for the local WebSocket fixture."""

import argparse
import asyncio
import json

from websockets.legacy.client import connect

URI = "ws://127.0.0.1:8765"


async def run(channel: str, token: str) -> None:
    async with connect(URI, max_size=4096) as websocket:
        await websocket.send(json.dumps({"type": "auth", "token": token}))
        print("server:", await websocket.recv())
        await websocket.send(json.dumps({"type": "message", "channel": channel, "payload": {"hello": "world"}}))
        print("server:", await websocket.recv())
        await websocket.send(b"bytes-from-client")
        print("server:", await websocket.recv())
        print("server binary:", await websocket.recv())
        await websocket.send(json.dumps({"type": "stream", "channel": channel}))
        while True:
            response = json.loads(await websocket.recv())
            print("server:", response)
            if response.get("type") == "stream.complete":
                break


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("safe", "vulnerable"), default="safe", help="Documentation label")
    parser.add_argument("--channel", default="public")
    parser.add_argument("--token", default="lab-demo-token")
    args = parser.parse_args()
    print(f"Client mode label: {args.mode}")
    asyncio.run(run(args.channel, args.token))


if __name__ == "__main__":
    main()
