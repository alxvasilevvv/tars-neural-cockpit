#!/usr/bin/env bash
# Load `.env` then run stdlib billing snapshot (no uvicorn).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
exec bash scripts/with_repo_env.sh ./.venv/bin/python scripts/smoke_billing_tars_backend.py
