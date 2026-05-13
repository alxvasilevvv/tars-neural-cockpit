#!/usr/bin/env bash
# tars-start.command — single double-click to start TARS for end-users.
#
# W201 pivot: cockpit lives ONLY in TARS.app (Tauri desktop). No more
# Chrome --app windows, no more FastAPI-served HTML cockpits.
#
# Brings up:
#   1. FastAPI backend on :8765 (data plane — JSON API only)
#   2. Background daemon LaunchAgent (persistent across reboots)
#   3. TARS.app desktop client (loads bundled cockpit + connects to :8765)

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.tars-start.txt"

{
  echo "=== TARS start at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""

  # 1. Backend on :8765 (JSON API only — no HTML)
  echo "── [1/3] backend ──"
  if curl -sS -o /dev/null --connect-timeout 1 "http://127.0.0.1:8765/api/health" 2>/dev/null \
    || curl -sS -o /dev/null --connect-timeout 1 "http://127.0.0.1:8765/api/entitlements" 2>/dev/null; then
    echo "    backend already alive on :8765 — skip"
  else
    bash scripts/backend_tars_up.sh 2>&1 | tail -5
  fi

  # 2. Daemon (idempotent)
  echo ""
  echo "── [2/3] daemon LaunchAgent ──"
  if launchctl list 2>/dev/null | grep -q "com.tars.background"; then
    echo "    daemon already registered — skip"
  else
    export PYTHONPATH="$(pwd)"
    ./.venv/bin/python -m backend.core.daemon --install 2>&1 | tail -3
  fi

  # 3. Launch TARS.app desktop client
  echo ""
  echo "── [3/3] TARS.app ──"
  if open -a "TARS" 2>/dev/null; then
    echo "    TARS.app opened"
  else
    echo "    ⚠ TARS.app not found. Build it first:"
    echo "       cd desktop && pnpm install && pnpm tauri:build"
    echo "    Or use scripts/build-tars-app.command (if available)."
  fi

  echo ""
  echo "=== TARS READY ==="
  echo ""
  echo "Backend API:  http://127.0.0.1:8765 (JSON only)"
  echo "Doctor:       /api/doctor (JSON) — was HTML, removed in W201"
  echo "Desktop UI:   TARS.app (Tauri) — loads bundled control center"
  echo ""
  echo "Stop backend: kill \$(cat /tmp/tars-backend-8765.pid)"
  echo "Daemon logs:  tail -f ~/.tars/daemon.out.log"
} > "$OUT" 2>&1

sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "tars-start")' 2>/dev/null || true
