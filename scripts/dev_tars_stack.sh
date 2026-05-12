#!/usr/bin/env bash
# Backend (bg + .env) only. The React/marketing cockpit was removed from the repo;
# use API clients, `make desktop-dev` (bundled static shell), or your own UI.
# Ctrl+C stops this script; API keeps running — stop with:
#   kill $(cat /tmp/tars-backend-<PORT>.pid)
#
#   bash scripts/dev_tars_stack.sh
#   PORT=8766 bash scripts/dev_tars_stack.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PORT="${PORT:-8765}"

bash scripts/backend_tars_up.sh

echo ""
echo "API → http://127.0.0.1:${PORT}"
echo "Marketing/showcase SPA removed — start desktop with: make desktop-dev"
echo "Backend PID in /tmp/tars-backend-${PORT}.pid"
