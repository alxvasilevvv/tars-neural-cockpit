#!/usr/bin/env bash
# auto-push.command — non-interactive git push, output to .auto-push.txt
# Designed to be triggered via Spotlight by Claude without user dialog.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.auto-push.txt"

{
  echo "=== auto-push run at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""
  ahead=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "?")
  echo "Commits ahead of origin/main: $ahead"
  if [ "$ahead" = "0" ]; then
    echo "Nothing to push."
  else
    echo ""
    echo "── commits being pushed ──"
    git log --oneline origin/main..HEAD
    echo ""
    echo "── push ──"
    git push origin main 2>&1
  fi
  echo ""
  echo "=== DONE ==="
} > "$OUT" 2>&1

# Auto-close terminal after 2 seconds.
sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "auto-push")' 2>/dev/null || true
