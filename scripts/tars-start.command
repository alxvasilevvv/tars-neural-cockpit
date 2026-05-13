#!/usr/bin/env bash
# tars-start.command — single double-click to start your TARS.
#
# Brings up:
#   1. FastAPI backend on :8765 (with .env)
#   2. TARS cockpit in Chrome app-mode (chromeless window)
#   3. Background daemon (LaunchAgent, persists across reboots)
#
# Power-user beta v9.2.0-beta1 launcher.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.tars-start.txt"

{
  echo "=== TARS start at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""

  # 1. Backend on :8765
  echo "── [1/3] starting backend ──"
  if curl -sS -o /dev/null --connect-timeout 1 "http://127.0.0.1:8765/api/health" 2>/dev/null \
    || curl -sS -o /dev/null --connect-timeout 1 "http://127.0.0.1:8765/api/entitlements" 2>/dev/null; then
    echo "    backend already alive on :8765 — skip"
  else
    bash scripts/backend_tars_up.sh 2>&1 | tail -5
  fi

  # 2. Daemon (idempotent — re-running is harmless)
  echo ""
  echo "── [2/3] ensuring daemon LaunchAgent ──"
  if launchctl list 2>/dev/null | grep -q "com.tars.background"; then
    echo "    daemon already registered with launchd — skip"
  else
    export PYTHONPATH="$(pwd)"
    ./.venv/bin/python -m backend.core.daemon --install 2>&1 | tail -3
  fi

  # 3. Cockpit (chromeless Chrome app window)
  echo ""
  echo "── [3/3] opening cockpit window ──"
  open -na "Google Chrome" --args \
    --app="http://127.0.0.1:8765/api/doctor/cockpit" \
    --window-size=1280,820 \
    --window-position=80,60 \
    --no-default-browser-check 2>/dev/null
  echo "    cockpit window opened"

  echo ""
  echo "=== TARS READY ==="
  echo ""
  echo "Backend:  http://127.0.0.1:8765"
  echo "Cockpit:  http://127.0.0.1:8765/api/doctor/cockpit"
  echo "Doctor:   http://127.0.0.1:8765/api/doctor/page"
  echo ""
  echo "Stop backend: kill \$(cat /tmp/tars-backend-8765.pid)"
  echo "Daemon logs:  tail -f ~/.tars/daemon.out.log"
} > "$OUT" 2>&1

sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "tars-start")' 2>/dev/null || true
