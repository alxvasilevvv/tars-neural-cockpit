#!/usr/bin/env bash
# MEEET-MOCK.command — W265
#
# Double-clickable launcher for the local meeet.world mock server.
# Runs on 127.0.0.1:8766; logs to .MEEET-MOCK.txt.
#
# Use case: brother hasn't shipped api.meeet.world yet, but you want to
# test TARS in MEEET_MODE=live end-to-end. Start this, point TARS at
# http://127.0.0.1:8766, and TARS will believe it's talking to the real
# thing.
#
# Stop with: lsof -i :8766 → kill <PID>     (or just close the terminal)

set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$(pwd)"
OUT="${ROOT}/.MEEET-MOCK.txt"
PORT="${MEEET_MOCK_PORT:-8766}"

# Prefer the project's local venv so we use the same Python TARS uses.
PY="${ROOT}/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3 || true)"
fi
if [ -z "${PY:-}" ] || [ ! -x "$PY" ]; then
  echo "FATAL: no python found (.venv/bin/python missing, no python3 on PATH)" | tee "$OUT"
  exit 1
fi

# Quick port-busy check (without lsof we shouldn't crash silently)
if command -v lsof >/dev/null 2>&1; then
  if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "WARN: port $PORT already in use. Stop it first: lsof -i :$PORT → kill <PID>" | tee "$OUT"
    sleep 5 || true
    exit 2
  fi
fi

{
  echo "=== meeet.world MOCK (W265) ==="
  echo "started:   $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "root:      $ROOT"
  echo "python:    $PY"
  echo "port:      $PORT"
  echo "URL:       http://127.0.0.1:$PORT"
  echo "health:    http://127.0.0.1:$PORT/health"
  echo "DB:        ~/.tars/meeet_mock.sqlite"
  echo ""
  echo "To stop: lsof -i :$PORT  →  kill <PID>   (or just Ctrl+C / close window)"
  echo "==============================="
  echo ""
} | tee "$OUT"

export PYTHONPATH="$ROOT"
# Run uvicorn with the module path so reload works.
exec "$PY" -m uvicorn scripts.meeet_mock.server:app \
  --host 127.0.0.1 \
  --port "$PORT" \
  --reload 2>&1 | tee -a "$OUT" &

UVICORN_PID=$!

# Give it a moment to start, then auto-close 5s after the user has read
# the URL. The actual server keeps running until the user kills it.
sleep 5
echo ""
echo "Mock is running in the background (PID $UVICORN_PID)."
echo "This terminal closes in 5s — server keeps running."
echo "Stop later with: lsof -i :$PORT  →  kill <PID>"
sleep 5
# Don't kill the server; let it keep listening. Just close terminal.
osascript -e 'tell application "Terminal" to close (every window whose name contains "MEEET-MOCK")' 2>/dev/null || true
exit 0
