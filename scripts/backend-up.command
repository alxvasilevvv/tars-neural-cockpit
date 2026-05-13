#!/usr/bin/env bash
# backend-up.command — double-click launcher for backend_tars_up.sh
#
# Designed so Claude can trigger the FastAPI backend from Finder
# without needing to type into Terminal (tier=click restriction).
#
# Output is captured to .backend-up.txt so the result can be
# verified from the sandbox via the workspace mount.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.backend-up.txt"

{
  echo "=== backend-up run at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""
  # Default port 8765 — override with PORT=… env if needed.
  bash scripts/backend_tars_up.sh 2>&1
  echo ""
  echo "=== DONE ==="
} > "$OUT" 2>&1

# Auto-close terminal after 2 seconds.
sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "backend-up")' 2>/dev/null || true
