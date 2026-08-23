#!/bin/sh
set -eu
rm -rf .venv __pycache__ bookshop_pb2.py bookshop_pb2_grpc.py grpc_web/__pycache__
printf '%s\n' 'Removed the gRPC lab virtual environment, generated stubs, and Python caches.'
