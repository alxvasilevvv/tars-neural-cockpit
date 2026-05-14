#!/usr/bin/env bash
cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.CHECK-STATUS.txt"
{
  echo "=== CHECK-STATUS at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo "── ~/.tars/meeet_token ──"
  ls -la ~/.tars/meeet_token 2>&1
  echo ""
  echo "── /api/health ──"
  curl -sS http://127.0.0.1:8765/api/health
  echo ""
  echo "── /api/auth/meeet/status ──"
  curl -sS http://127.0.0.1:8765/api/auth/meeet/status
  echo ""
  echo "── TARS process ──"
  ps aux | grep -i "TARS.app/Contents/MacOS" | grep -v grep || echo "(not running)"
} > "$OUT" 2>&1
sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "CHECK")' 2>/dev/null || true
osascript -e 'tell application "Terminal" to close (every window whose name contains "CHECK")' 2>/dev/null || true
