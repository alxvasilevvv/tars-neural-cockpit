#!/usr/bin/env bash
# relaunch-cockpit.command — restart backend (picks up new /cockpit route)
# then open chromeless cockpit + doctor tab.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.relaunch-cockpit.txt"

{
  echo "=== relaunch at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo "── restart backend ──"
  bash scripts/backend_tars_up.sh 2>&1 | tail -15
  echo ""
  echo "── open chromeless cockpit ──"
  open -na "Google Chrome" --args \
    --app="http://127.0.0.1:8765/api/doctor/cockpit" \
    --window-size=1280,820 \
    --window-position=80,60 \
    --no-default-browser-check
  echo "(opened chromeless app window)"
  echo ""
  echo "=== DONE ==="
} > "$OUT" 2>&1

sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "relaunch-cockpit")' 2>/dev/null || true
