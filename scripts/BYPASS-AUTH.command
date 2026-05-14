#!/usr/bin/env bash
# BYPASS-AUTH.command — write a synthetic local-only meeet token directly,
# skipping the auth screen on next TARS launch. Used when the on-screen
# Skip link is unclickable (Tauri WebView quirk being patched).
#
# Effect: ~/.tars/meeet_token gets {token:"local-only-<ts>", tier:"FREE"}
# next time you launch TARS, /api/auth/meeet/status will return authenticated=true
# and you land straight in the voice cockpit.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.BYPASS-AUTH.txt"

{
  echo "=== BYPASS-AUTH at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""

  mkdir -p "$HOME/.tars"
  TOKEN="local-only-$(date +%s)"

  # Write the token file directly. Backend's GET /api/auth/meeet/status
  # reads this file and returns {authenticated: true} if it exists.
  cat > "$HOME/.tars/meeet_token" <<EOF
{
  "token": "${TOKEN}",
  "tier": "FREE",
  "mode": "local-only",
  "issued_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
  chmod 600 "$HOME/.tars/meeet_token"
  echo "✓ wrote $HOME/.tars/meeet_token"
  echo ""

  # Also POST through backend so it has an in-memory copy too.
  if command -v curl >/dev/null 2>&1; then
    echo "── POST /api/auth/meeet/exchange ──"
    curl -sS -X POST http://127.0.0.1:8765/api/auth/meeet/exchange \
      -H 'Content-Type: application/json' \
      -d "{\"token\":\"${TOKEN}\"}" 2>&1 | head -3
    echo ""
    echo "── GET /api/auth/meeet/status ──"
    curl -sS http://127.0.0.1:8765/api/auth/meeet/status 2>&1 | head -3
    echo ""
  fi

  echo "── restarting TARS.app ──"
  osascript -e 'tell application "TARS" to quit' 2>/dev/null || true
  sleep 1
  open -a "TARS"
  echo "    ✓ TARS launched"

  echo ""
  echo "=== BYPASS DONE — TARS should land directly in voice cockpit ==="
} > "$OUT" 2>&1

sleep 3
osascript -e 'tell application "Терминал" to close (every window whose name contains "BYPASS")' 2>/dev/null || true
osascript -e 'tell application "Terminal" to close (every window whose name contains "BYPASS")' 2>/dev/null || true
