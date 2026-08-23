#!/usr/bin/env bash
set -eu

umask 077
base_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
out_dir="$base_dir/generated"
openssl_dir="$base_dir/openssl"

mkdir -p "$out_dir"
rm -f "$out_dir"/*

# These keys are generated only for this disposable local lab.
openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 7 \
  -subj '/C=XX/ST=Local/L=Local/O=DV-Bookshop Infrastructure Lab/OU=Local CA/CN=DV-Bookshop Lab CA' \
  -keyout "$out_dir/ca.key" \
  -out "$out_dir/ca.crt"

openssl req -new -newkey rsa:2048 -nodes \
  -config "$openssl_dir/server.cnf" \
  -keyout "$out_dir/server.key" \
  -out "$out_dir/server.csr"

openssl x509 -req -sha256 -days 7 \
  -in "$out_dir/server.csr" \
  -CA "$out_dir/ca.crt" \
  -CAkey "$out_dir/ca.key" \
  -CAcreateserial \
  -extfile "$openssl_dir/server.cnf" \
  -extensions server_ext \
  -out "$out_dir/server.crt"

openssl req -new -newkey rsa:2048 -nodes \
  -config "$openssl_dir/client.cnf" \
  -keyout "$out_dir/client.key" \
  -out "$out_dir/client.csr"

openssl x509 -req -sha256 -days 7 \
  -in "$out_dir/client.csr" \
  -CA "$out_dir/ca.crt" \
  -CAkey "$out_dir/ca.key" \
  -CAcreateserial \
  -extfile "$openssl_dir/client.cnf" \
  -extensions client_ext \
  -out "$out_dir/client.crt"

rm -f "$out_dir/ca.srl"
printf '%s\n' "Created disposable local TLS material in $out_dir"
printf '%s\n' "Run scripts/clean.sh when the lab is no longer needed."
