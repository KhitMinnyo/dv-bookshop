#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
rm -rf "$SCRIPT_DIR/lab-data"
printf '%s\n' "Optional lab data reset. The directory will be recreated on the next start."
