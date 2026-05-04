#!/usr/bin/env bash
# Load repo-root `.env` into the environment, then exec the remainder.
# Used by Makefile targets so operators keep secrets only in `.env` (never committed).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
exec "$@"
