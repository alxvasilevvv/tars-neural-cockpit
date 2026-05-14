#!/usr/bin/env bash
# W207 — backend-watchdog.command
#
# Polls 127.0.0.1:8765/api/health every 30s. If the backend goes down,
# restarts it via scripts/backend_tars_up.sh. Run from Finder; it
# survives across logout when invoked from a LaunchAgent (see
# scripts/install-tars-backend-launchd.sh).
#
# Logs to ~/.tars/backend-watchdog.log. Stop with:
#   kill $(cat ~/.tars/backend-watchdog.pid)

cd "$(dirname "${BASH_SOURCE[0]}")/.."
HOME_TARS="$HOME/.tars"
mkdir -p "$HOME_TARS"
LOG="$HOME_TARS/backend-watchdog.log"
PIDFILE="$HOME_TARS/backend-watchdog.pid"

# Don't double-run.
if [ -f "$PIDFILE" ]; then
  OLD_PID=$(cat "$PIDFILE" 2>/dev/null)
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "[watchdog] already running (pid $OLD_PID). exit." | tee -a "$LOG"
    exit 0
  fi
fi
echo $$ > "$PIDFILE"

echo "[watchdog] started pid=$$ at $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"

while true; do
  TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  if curl -sS -o /dev/null --connect-timeout 2 --max-time 3 \
      "http://127.0.0.1:8765/api/health" 2>/dev/null; then
    # Healthy — sleep 30s and check again.
    sleep 30
    continue
  fi

  # Backend is down.
  echo "[$TS] backend down → restarting" | tee -a "$LOG"
  bash scripts/backend_tars_up.sh >> "$LOG" 2>&1 || \
    echo "[$TS] restart failed" | tee -a "$LOG"

  # Give uvicorn time to come up before next poll.
  sleep 8
done
