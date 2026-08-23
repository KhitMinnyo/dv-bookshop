#!/usr/bin/env python3
"""Client for the local gRPC streaming fixture."""

import argparse
import asyncio
from collections.abc import AsyncIterator

import grpc

import bookshop_pb2
import bookshop_pb2_grpc

TARGET = "127.0.0.1:50051"


def metadata(token: str) -> tuple[tuple[str, str], ...]:
    return (("authorization", f"Bearer {token}"),)


async def upload_requests() -> AsyncIterator[bookshop_pb2.BookUpload]:
    for title in ("stream-one", "stream-two", "stream-three"):
        yield bookshop_pb2.BookUpload(owner="demo-user", title=title)


async def chat_requests() -> AsyncIterator[bookshop_pb2.ChatMessage]:
    for sequence, text in enumerate(("first", "second"), start=1):
        yield bookshop_pb2.ChatMessage(owner="demo-user", sequence=sequence, text=text)


async def run(args: argparse.Namespace) -> None:
    async with grpc.aio.insecure_channel(TARGET) as channel:
        stub = bookshop_pb2_grpc.BookStreamStub(channel)
        call_metadata = metadata(args.token)
        if args.operation == "watch":
            events = stub.WatchBooks(bookshop_pb2.WatchRequest(owner=args.owner), metadata=call_metadata)
            async for event in events:
                print(event)
        elif args.operation == "upload":
            summary = await stub.UploadBooks(upload_requests(), metadata=call_metadata)
            print(summary)
        else:
            replies = stub.Chat(chat_requests(), metadata=call_metadata)
            async for reply in replies:
                print(reply)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("watch", "upload", "chat"))
    parser.add_argument("--owner", default="demo-user")
    parser.add_argument("--token", default="lab-reader")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
