#!/usr/bin/env bash
# tars-cockpit.command — launch the local TARS cockpit as a chromeless app.
#
# Workaround while the bundled Tauri cockpit has a known v9.1.0-preview
# render bug ("operation is insecure" on /cockpit). The HTML shell here
# talks live to the local FastAPI backend on :8765 — doctor checks,
# entitlements, fix actions, test-notify.

set -e
COCKPIT_URL="file:///Users/alien/Documents/Claude/Projects/Jarvis/tars-cockpit.html"

# Ensure backend is up first.
if ! curl -sS -o /dev/null --connect-timeout 1 "http://127.0.0.1:8765/api/health" 2>/dev/null \
  && ! curl -sS -o /dev/null --connect-timeout 1 "http://127.0.0.1:8765/api/entitlements" 2>/dev/null; then
  bash "$(dirname "${BASH_SOURCE[0]}")/backend_tars_up.sh" >/dev/null 2>&1 &
  for _ in $(seq 1 30); do
    sleep 0.5
    curl -sS -o /dev/null --connect-timeout 1 "http://127.0.0.1:8765/api/entitlements" 2>/dev/null && break
  done
fi

# Open in Chrome app-mode for a chromeless window.
open -na "Google Chrome" --args \
  --app="${COCKPIT_URL}" \
  --window-size=1280,820 \
  --window-position=120,80 \
  --no-default-browser-check

sleep 1
osascript -e 'tell application "Терминал" to close (every window whose name contains "tars-cockpit")' 2>/dev/null || true
