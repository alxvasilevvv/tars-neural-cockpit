#!/usr/bin/env bash
# RUN-HARNESS-AND-LOG.command — W290
#
# Wrapper around scripts/qa_w290_cockpit.sh that captures the full
# harness output to .qa_w290_cockpit_output.txt for the cowork agent
# to read after the run.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO="$(pwd)"
LOG="${REPO}/.qa_w290_cockpit_output.txt"
{
  echo "=== qa_w290_cockpit.sh @ $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo "TARS_HOST=${TARS_HOST:-http://127.0.0.1:8765}"
  echo ""
  bash scripts/qa_w290_cockpit.sh
  echo ""
  echo "EXIT=$?"
} > "$LOG" 2>&1
echo "wrote: $LOG"
sleep 6
osascript -e 'tell application "Терминал" to close (every window whose name contains "RUN-HARNESS")' 2>/dev/null || true
osascript -e 'tell application "Terminal" to close (every window whose name contains "RUN-HARNESS")' 2>/dev/null || true
