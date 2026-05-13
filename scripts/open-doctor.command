#!/usr/bin/env bash
# open-doctor.command — launch the TARS cockpit + doctor in Chrome.
#
# Two surfaces:
#   1. tars-cockpit.html → opens in Chrome --app mode (chromeless window)
#   2. /api/doctor/page → opens in a regular Chrome tab
#
# This replaces the broken bundled Tauri cockpit (known v9.1.0-preview
# render bug). The HTML shell talks live to the local FastAPI backend.

COCKPIT_URL="http://127.0.0.1:8765/api/doctor/cockpit"
DOCTOR_URL="http://127.0.0.1:8765/api/doctor/page"

# Open the cockpit as a chromeless app window (same-origin so fetches work).
open -na "Google Chrome" --args \
  --app="${COCKPIT_URL}" \
  --window-size=1280,820 \
  --window-position=80,60 \
  --no-default-browser-check 2>/dev/null || open "${COCKPIT_URL}"

# Also keep the regular doctor tab open.
sleep 0.5
open -a "Google Chrome" "${DOCTOR_URL}" 2>/dev/null || open "${DOCTOR_URL}"

sleep 1
osascript -e 'tell application "Терминал" to close (every window whose name contains "open-doctor")' 2>/dev/null || true
