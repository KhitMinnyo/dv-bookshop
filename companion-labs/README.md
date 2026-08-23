# DV-Bookshop Companion Labs

These optional labs are isolated teaching fixtures. They do not modify or call the DV-Bookshop application. Every runnable service binds to `127.0.0.1` and uses its own port.

## Lab Map

- `advanced-mobile-native-reversing/`: owner-controlled Android source fixture for static and dynamic reversing practice.
- `websocket-streaming/`: Python WebSocket JSON/binary frame and streaming fixture on port `8765`.
- `grpc-streaming/`: Python gRPC streaming fixture on port `50051`, with optional grpc-web notes.
- `prototype-pollution/`: Node.js/Express deep-merge and path-setter fixture on port `3003`.

## Safety Boundary

Use these labs only on a local machine, local emulator, and systems you own or are explicitly authorized to test. The secrets in the Android fixture are deliberately fake and must not be reused. No APK, generated certificate, generated protobuf module, package cache, virtual environment, `node_modules`, or runtime data is committed here.

Each lab README includes definitions, setup, expected behavior, vulnerable and safe modes, remediation, reset steps, and environment-dependent notes.

## Cleanup Overview

Stop any foreground process with `Ctrl-C`, then follow the lab-specific cleanup instructions. The cleanup scripts remove only artifacts inside their own lab directory; review them before execution in a shared workspace.
