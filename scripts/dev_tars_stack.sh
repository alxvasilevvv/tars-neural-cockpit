#!/usr/bin/env bash
# Backend (bg + .env) then cockpit dev server (foreground).
# Ctrl+C stops only Vite; API keeps running — stop with:
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
echo "Cockpit → http://127.0.0.1:5174 (default Vite). API → http://127.0.0.1:${PORT}"
echo "Ctrl+C here stops only the UI; backend PID in /tmp/tars-backend-${PORT}.pid"
echo ""

if [[ "${PORT}" != "8765" ]]; then
  export VITE_TARS_API="http://127.0.0.1:${PORT}"
fi

exec pnpm --dir "${ROOT}/experiments/neural-showcase-v3" dev
