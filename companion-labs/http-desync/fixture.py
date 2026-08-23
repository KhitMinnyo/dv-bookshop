#!/usr/bin/env python3
"""Bounded, offline demonstration of two HTTP body framing decisions."""

from __future__ import annotations

import argparse
from dataclasses import dataclass


MAX_INPUT = 4096
SAMPLE = (
    b"POST /local-demo HTTP/1.1\r\n"
    b"Host: localhost\r\n"
    b"Content-Length: 4\r\n"
    b"Transfer-Encoding: chunked\r\n"
    b"\r\n"
    b"4\r\nWXYZ\r\n0\r\n\r\n"
)


@dataclass
class ParseResult:
    framing: str
    body: bytes
    consumed: int
    error: str | None = None


def split_headers(raw: bytes) -> tuple[dict[str, str], int]:
    header_end = raw.find(b"\r\n\r\n")
    if header_end < 0:
        raise ValueError("header terminator is missing")
    header_block = raw[:header_end].decode("ascii")
    lines = header_block.split("\r\n")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, colon, value = line.partition(":")
        if not colon or not name or name.lower() in headers:
            raise ValueError("duplicate or malformed header")
        headers[name.lower()] = value.strip()
    return headers, header_end + 4


def parse_body(raw: bytes, framing: str) -> ParseResult:
    headers, body_start = split_headers(raw)
    body = raw[body_start:]
    if framing == "cl":
        try:
            length = int(headers["content-length"])
        except (KeyError, ValueError):
            return ParseResult(framing, b"", body_start, "invalid Content-Length")
        if length < 0 or length > MAX_INPUT:
            return ParseResult(framing, b"", body_start, "Content-Length exceeds bound")
        if len(body) < length:
            return ParseResult(framing, body, len(raw), "body is incomplete")
        return ParseResult(framing, body[:length], body_start + length)

    if framing != "te":
        raise ValueError("framing must be cl or te")
    if headers.get("transfer-encoding", "").lower() != "chunked":
        return ParseResult(framing, b"", body_start, "fixture only accepts chunked encoding")
    position = 0
    decoded = bytearray()
    while True:
        line_end = body.find(b"\r\n", position)
        if line_end < 0:
            return ParseResult(framing, bytes(decoded), body_start + len(body), "chunk size is incomplete")
        size_text = body[position:line_end].decode("ascii", errors="replace")
        if ";" in size_text:
            size_text = size_text.split(";", 1)[0]
        try:
            size = int(size_text, 16)
        except ValueError:
            return ParseResult(framing, bytes(decoded), body_start + position, "invalid chunk size")
        if size < 0 or len(decoded) + size > MAX_INPUT:
            return ParseResult(framing, bytes(decoded), body_start + position, "chunked body exceeds bound")
        position = line_end + 2
        if len(body) < position + size + 2:
            return ParseResult(framing, bytes(decoded), len(raw), "chunk data is incomplete")
        decoded.extend(body[position : position + size])
        position += size
        if body[position : position + 2] != b"\r\n":
            return ParseResult(framing, bytes(decoded), body_start + position, "chunk terminator is missing")
        position += 2
        if size == 0:
            return ParseResult(framing, bytes(decoded), body_start + position)

    raise AssertionError("unreachable")


def show(label: str, result: ParseResult) -> None:
    print(f"{label}: framing={result.framing}")
    print(f"  body={result.body!r}")
    print(f"  consumed={result.consumed} of {len(SAMPLE)} bytes")
    print(f"  unread={SAMPLE[result.consumed:]!r}")
    if result.error:
        print(f"  error={result.error}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("cl-te", "te-cl"), required=True)
    args = parser.parse_args()
    if len(SAMPLE) > MAX_INPUT:
        raise RuntimeError("built-in sample exceeds safety bound")
    first, second = (("cl", "te") if args.scenario == "cl-te" else ("te", "cl"))
    print("Offline fixture only; no network I/O is performed.")
    print(f"scenario={args.scenario}")
    show("first parser", parse_body(SAMPLE, first))
    show("second parser", parse_body(SAMPLE, second))


if __name__ == "__main__":
    main()
