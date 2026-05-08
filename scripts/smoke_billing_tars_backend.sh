#!/usr/bin/env bash
# Load `.env` then run stdlib billing snapshot (no uvicorn).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"

# Guard so a fresh-machine operator gets a useful error instead of
# bash's terse "exec: ./.venv/bin/python: not found".
if [[ ! -x ./.venv/bin/python ]]; then
  cat >&2 <<'EOF'
[smoke-billing-tars] missing: ./.venv/bin/python — virtualenv not bootstrapped.

Quick fix (matches README setup):

    python3.12 -m venv .venv
    ./.venv/bin/pip install --upgrade pip
    ./.venv/bin/pip install -r requirements.txt

Then re-run `make smoke-billing-tars`.
EOF
  exit 2
fi

exec bash scripts/with_repo_env.sh ./.venv/bin/python scripts/smoke_billing_tars_backend.py
