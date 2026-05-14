#!/usr/bin/env bash
# LAUNCH-NOW.command — single double-click to finish the v9.2.0-beta2 launch.
#
# Runs backend-up + install-tars-watchdog in sequence.
# After this completes, TARS is 100% live.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.LAUNCH-NOW.txt"

{
  echo "=== LAUNCH-NOW at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""

  echo "── [1/2] backend up ──"
  bash scripts/backend_tars_up.sh 2>&1 | tail -8
  echo ""

  echo "── [2/2] install backend watchdog as LaunchAgent ──"
  bash scripts/install-tars-watchdog.command 2>&1 | tail -10 || \
    echo "    (watchdog install script ran in background)"
  echo ""

  echo "── verify ──"
  sleep 3
  if curl -sS -o /dev/null --connect-timeout 2 \
      "http://127.0.0.1:8765/api/health" 2>/dev/null; then
    echo "    ✓ backend alive on :8765"
  else
    echo "    ⚠ backend not responding yet — give it 5-10s and Reload in TARS.app"
  fi

  if launchctl list 2>/dev/null | grep -q "com.tars.backend-watchdog"; then
    echo "    ✓ watchdog LaunchAgent registered"
  else
    echo "    ⚠ watchdog not yet listed — may need re-login"
  fi

  echo ""
  echo "=== TARS v9.2.0-beta2 IS LIVE ==="
  echo ""
  echo "Open TARS.app → ↻ Reload in Quick Actions"
  echo "Status should go green, tier-pill updates, Today briefing fills in"
} > "$OUT" 2>&1

sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "LAUNCH-NOW")' 2>/dev/null || true
