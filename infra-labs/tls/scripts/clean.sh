#!/usr/bin/env bash
set -eu

base_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
out_dir="$base_dir/generated"

rm -f "$out_dir/ca.crt" "$out_dir/ca.key" "$out_dir/ca.srl" \
  "$out_dir/server.crt" "$out_dir/server.key" "$out_dir/server.csr" \
  "$out_dir/client.crt" "$out_dir/client.key" "$out_dir/client.csr"

printf '%s\n' "Removed generated TLS files from $out_dir"
