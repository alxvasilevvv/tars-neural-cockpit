#!/usr/bin/env bash
# BYPASS-AUTH.command v2 — hard restart with pkill, verify status returns
# connected:true BEFORE relaunching TARS, so authBootCheck on next boot
# sees the token and skips the auth screen.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.BYPASS-AUTH.txt"

{
  echo "=== BYPASS-AUTH v2 at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""

  # 1. Make sure backend is alive
  if ! curl -sS --connect-timeout 2 http://127.0.0.1:8765/api/health >/dev/null 2>&1; then
    echo "── backend down, restarting via backend_tars_up.sh ──"
    bash scripts/backend_tars_up.sh 2>&1 | tail -5
    sleep 3
  fi
  echo "✓ backend reachable on :8765"
  echo ""

  # 2. Write token via API (backend persists to ~/.tars/meeet_token)
  TOKEN="local-only-$(date +%s)"
  echo "── POST /api/auth/meeet/exchange ──"
  curl -sS -X POST http://127.0.0.1:8765/api/auth/meeet/exchange \
    -H 'Content-Type: application/json' \
    -d "{\"token\":\"${TOKEN}\"}"
  echo ""
  echo ""

  # 3. Verify status RETURNS connected:true
  echo "── verify /api/auth/meeet/status ──"
  STATUS_JSON="$(curl -sS http://127.0.0.1:8765/api/auth/meeet/status)"
  echo "  raw: $STATUS_JSON"
  if echo "$STATUS_JSON" | grep -q '"connected":true\|"connected": true'; then
    echo "  ✓ status confirms connected=true"
  else
    echo "  ✗ status does NOT show connected=true — abort"
    sleep 8
    exit 1
  fi
  echo ""

  # 4. Hard kill TARS (osascript quit doesn't work for Tauri reliably)
  echo "── hard kill TARS ──"
  pkill -f "TARS.app/Contents/MacOS/" 2>/dev/null && echo "  ✓ killed" || echo "  (not running)"
  sleep 2

  # 5. Re-launch
  echo "── re-launch TARS ──"
  open -a TARS
  echo "  ✓ launched"

  echo ""
  echo "=== BYPASS DONE — TARS should boot straight into voice cockpit ==="
} > "$OUT" 2>&1

sleep 4
osascript -e 'tell application "Терминал" to close (every window whose name contains "BYPASS")' 2>/dev/null || true
osascript -e 'tell application "Terminal" to close (every window whose name contains "BYPASS")' 2>/dev/null || true
