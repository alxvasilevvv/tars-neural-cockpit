#!/usr/bin/env bash
# One-shot: free PORT, start TARS FastAPI with repo `.env`, probe /api/entitlements.
# Uvicorn runs in the background so this script can print billing + exit.
#
#   bash scripts/backend_tars_up.sh
#   PORT=8766 bash scripts/backend_tars_up.sh
#
# Stop later: kill "$(cat /tmp/tars-backend-<PORT>.pid)"

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"

PORT="${PORT:-8765}"
LOG="/tmp/tars-backend-${PORT}.log"
PIDFILE="/tmp/tars-backend-${PORT}.pid"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1" >&2; exit 2; }; }
need curl
if ! command -v jq >/dev/null 2>&1; then
  echo "missing: jq (brew install jq)" >&2
  exit 2
fi
if [[ ! -x ./.venv/bin/python ]]; then
  echo "missing: ./.venv/bin/python — create venv first" >&2
  exit 2
fi

kill_port() {
  local pids
  pids="$(lsof -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "${pids}" ]]; then
    echo "Stopping listener(s) on :${PORT}: ${pids}"
    # shellcheck disable=SC2086
    kill ${pids} 2>/dev/null || true
    sleep 0.6
    pids="$(lsof -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "${pids}" ]]; then
      # shellcheck disable=SC2086
      kill -9 ${pids} 2>/dev/null || true
      sleep 0.3
    fi
  fi
}

kill_port
rm -f "$LOG" "$PIDFILE"

echo "Starting uvicorn on 127.0.0.1:${PORT} (log: ${LOG}) …"
nohup bash scripts/with_repo_env.sh ./.venv/bin/python -m uvicorn web_extras.app:app \
  --host 127.0.0.1 --port "$PORT" >"$LOG" 2>&1 &
echo $! >"$PIDFILE"

for _ in $(seq 1 60); do
  if curl -sS -o /dev/null --connect-timeout 1 "http://127.0.0.1:${PORT}/api/entitlements" 2>/dev/null; then
    break
  fi
  sleep 0.25
done

if ! curl -sS -o /dev/null --connect-timeout 2 "http://127.0.0.1:${PORT}/api/entitlements" 2>/dev/null; then
  echo "Backend did not become ready on :${PORT}. Last log lines:" >&2
  tail -30 "$LOG" >&2 || true
  exit 1
fi

echo ""
echo "--- GET /api/entitlements (billing) ---"
curl -sS "http://127.0.0.1:${PORT}/api/entitlements" \
  | jq '{tier, billing_authority: .billing.authority, billing_source: .billing.source, remote_ok: .billing.remote_ok}'

echo ""
echo "Uvicorn PID $(cat "$PIDFILE") still running. Log: $LOG"
echo "Stop: kill \$(cat $PIDFILE)"
