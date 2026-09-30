#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

mode=${1:-vulnerable}
case "$mode" in
  vulnerable) set -- -f docker-compose.yml ;;
  hardened) set -- -f docker-compose.yml -f docker-compose.hardened.yml ;;
  *) printf 'Usage: bash start.sh [vulnerable|hardened]\n' >&2; exit 2 ;;
esac

docker compose "$@" up --build -d --wait --wait-timeout 120
