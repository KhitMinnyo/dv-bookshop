#!/usr/bin/env python3
"""Local gRPC server-streaming, client-streaming, and bidi fixture."""

import argparse
import asyncio
from collections.abc import AsyncIterator

import grpc

import bookshop_pb2
import bookshop_pb2_grpc

HOST = "127.0.0.1"
PORT = 50051
DEMO_TOKEN = "lab-reader"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("safe", "vulnerable"), default="safe")
    parser.add_argument("--host", default=HOST, help="Use loopback for the lab")
    parser.add_argument("--port", type=int, default=PORT)
    return parser.parse_args()


async def authorize(context: grpc.aio.ServicerContext, owner: str, safe: bool) -> None:
    metadata = dict(context.invocation_metadata())
    authorization = metadata.get("authorization", "")
    token = authorization.removeprefix("Bearer ").strip()
    authenticated = token == DEMO_TOKEN if safe else bool(token)
    if not authenticated:
        await context.abort(grpc.StatusCode.UNAUTHENTICATED, "invalid lab credentials")
    if safe and owner != "demo-user":
        await context.abort(grpc.StatusCode.PERMISSION_DENIED, "owner is not authorized")


class BookStream(bookshop_pb2_grpc.BookStreamServicer):
    def __init__(self, mode: str) -> None:
        self.safe = mode == "safe"

    async def WatchBooks(
        self, request: bookshop_pb2.WatchRequest, context: grpc.aio.ServicerContext
    ) -> AsyncIterator[bookshop_pb2.BookEvent]:
        await authorize(context, request.owner, self.safe)
        for sequence in range(4):
            yield bookshop_pb2.BookEvent(
                owner=request.owner,
                sequence=sequence,
                title=f"local-stream-book-{sequence}",
            )
            await asyncio.sleep(0.05)

    async def UploadBooks(
        self,
        request_iterator: AsyncIterator[bookshop_pb2.BookUpload],
        context: grpc.aio.ServicerContext,
    ) -> bookshop_pb2.UploadSummary:
        accepted = 0
        owner = ""
        async for request in request_iterator:
            if not owner:
                owner = request.owner
                await authorize(context, owner, self.safe)
            if self.safe and request.owner != owner:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "owner changed in stream")
            if self.safe and len(request.title.encode("utf-8")) > 256:
                await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "title is too large")
            accepted += 1
            if self.safe and accepted >= 100:
                await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "stream item limit reached")
        return bookshop_pb2.UploadSummary(owner=owner, accepted=accepted)

    async def Chat(
        self,
        request_iterator: AsyncIterator[bookshop_pb2.ChatMessage],
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[bookshop_pb2.ChatMessage]:
        first = True
        count = 0
        async for request in request_iterator:
            if first:
                await authorize(context, request.owner, self.safe)
                first = False
            if self.safe and len(request.text.encode("utf-8")) > 512:
                await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "chat message is too large")
            count += 1
            yield bookshop_pb2.ChatMessage(
                owner=request.owner,
                sequence=count,
                text=f"server reply: {request.text}",
            )
            if self.safe and count >= 20:
                await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "chat message limit reached")


async def main() -> None:
    args = parse_args()
    server = grpc.aio.server(options=[("grpc.max_receive_message_length", 64 * 1024)])
    bookshop_pb2_grpc.add_BookStreamServicer_to_server(BookStream(args.mode), server)
    server.add_insecure_port(f"{args.host}:{args.port}")
    await server.start()
    print(f"gRPC lab ({args.mode}) listening on {args.host}:{args.port}")
    try:
        await server.wait_for_termination()
    finally:
        await server.stop(grace=1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
