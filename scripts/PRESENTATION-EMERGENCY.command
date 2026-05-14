#!/usr/bin/env bash
# PRESENTATION-EMERGENCY.command -- W273 30-second nuke + recover.
#
# Use ONLY if the live demo breaks mid-presentation and DEMO-READY
# pre-flight is too slow. Sequence:
#   1. pkill -9 TARS.app
#   2. pkill stale uvicorn :8765 / :8766
#   3. Re-launch backend  (~5s)
#   4. Re-launch mock meeet :8766 (~3s)
#   5. Re-seed demo data (TARS_DEMO_SEED=1 already in .env from DEMO-READY)
#   6. Re-launch TARS.app
#
# Total time: ~30 seconds.
# Logs to .PRESENTATION-EMERGENCY.txt.
#
# Put this on the macOS dock the morning of the demo so it's one click
# away. Drag scripts/PRESENTATION-EMERGENCY.command into the dock; click
# means recovery, no Terminal navigation needed.

set -u

cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO="$(pwd)"
LOG="${REPO}/.PRESENTATION-EMERGENCY.txt"

exec > >(tee -a "$LOG") 2>&1

if [ -t 1 ]; then
  G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[34m'; X=$'\033[0m'
else
  G=""; R=""; Y=""; B=""; X=""
fi

T0=$(date +%s)

echo ""
echo "${R}========================================================${X}"
echo "${R}  EMERGENCY RECOVERY @ $(date -u +%Y-%m-%dT%H:%M:%SZ)${X}"
echo "${R}========================================================${X}"
echo ""

# ----------------------------------------------------------------------
# Step 1 -- nuke TARS.app
# ----------------------------------------------------------------------
echo "${B}[1/6] killing TARS.app process...${X}"
pkill -9 -f "TARS.app/Contents/MacOS" 2>/dev/null || true
pkill -9 -f "tars-cockpit"            2>/dev/null || true
sleep 1
echo "  ${G}done${X}"

# ----------------------------------------------------------------------
# Step 2 -- nuke uvicorn :8765 + :8766
# ----------------------------------------------------------------------
echo ""
echo "${B}[2/6] killing stale uvicorn on :8765 + :8766...${X}"
for PORT in 8765 8766; do
  if command -v lsof >/dev/null 2>&1; then
    PIDS="$(lsof -tiTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)"
    if [ -n "${PIDS}" ]; then
      echo "  port :${PORT} -> killing ${PIDS}"
      # shellcheck disable=SC2086
      kill -9 ${PIDS} 2>/dev/null || true
    else
      echo "  port :${PORT} -> already free"
    fi
  fi
done
sleep 1

# ----------------------------------------------------------------------
# Step 3 -- relaunch backend
# ----------------------------------------------------------------------
echo ""
echo "${B}[3/6] relaunching backend on :8765 (TARS_DEMO_SEED=1)...${X}"
export TARS_DEMO_SEED=1
( bash "${REPO}/scripts/backend_tars_up.sh" >/tmp/tars-emerg-backend.log 2>&1 ) &
BACKEND_OK=0
for i in $(seq 1 15); do
  if curl -sS -o /dev/null --max-time 1 "http://127.0.0.1:8765/api/health" 2>/dev/null; then
    BACKEND_OK=1
    echo "  ${G}backend up after ${i}s${X}"
    break
  fi
  sleep 1
done
if [ "${BACKEND_OK}" = "0" ]; then
  echo "  ${R}WARN: backend did not respond in 15s -- continuing anyway${X}"
fi

# ----------------------------------------------------------------------
# Step 4 -- relaunch mock meeet
# ----------------------------------------------------------------------
echo ""
echo "${B}[4/6] relaunching mock meeet on :8766...${X}"
if [ -f "${REPO}/scripts/MEEET-MOCK.command" ]; then
  ( nohup bash "${REPO}/scripts/MEEET-MOCK.command" >/tmp/tars-emerg-mock.log 2>&1 < /dev/null ) &
  for i in $(seq 1 10); do
    if curl -sS -o /dev/null --max-time 1 "http://127.0.0.1:8766/health" 2>/dev/null; then
      echo "  ${G}mock up after ${i}s${X}"
      break
    fi
    sleep 1
  done
else
  echo "  scripts/MEEET-MOCK.command missing -- skipping mock"
fi

# ----------------------------------------------------------------------
# Step 5 -- verify seed (lightweight; full seed runs at backend boot)
# ----------------------------------------------------------------------
echo ""
echo "${B}[5/6] verifying demo seed via /api/agents...${X}"
if [ "${BACKEND_OK}" = "1" ]; then
  CNT="$(curl -sS --max-time 3 'http://127.0.0.1:8765/api/agents' 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    if isinstance(d,list): print(len(d))
    elif isinstance(d,dict):
        for v in d.values():
            if isinstance(v,list): print(len(v)); break
        else: print(0)
    else: print(0)
except Exception: print(0)
" 2>/dev/null || echo 0)"
  echo "  /api/agents -> ${CNT} agents"
  if [ "${CNT:-0}" -lt 3 ]; then
    echo "  ${Y}WARN: under 3 agents -- demo data thin but demo still runs${X}"
  fi
fi

# ----------------------------------------------------------------------
# Step 6 -- relaunch TARS.app
# ----------------------------------------------------------------------
echo ""
echo "${B}[6/6] relaunching TARS.app...${X}"
if [ -d "/Applications/TARS.app" ]; then
  open "/Applications/TARS.app" 2>/dev/null || true
  sleep 3
  if pgrep -f "TARS.app/Contents/MacOS" >/dev/null 2>&1; then
    echo "  ${G}TARS.app running${X}"
  else
    echo "  ${R}WARN: TARS.app did not appear in process list${X}"
  fi
else
  echo "  ${R}TARS.app missing at /Applications/TARS.app${X}"
fi

# ----------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------
T1=$(date +%s)
DT=$((T1 - T0))

echo ""
echo "${G}========================================================${X}"
echo "${G}  RECOVERY COMPLETE in ${DT}s${X}"
echo "${G}  go back to the demo. don't apologize. don't explain.${X}"
echo "${G}========================================================${X}"
echo ""
echo "Window closes in 5s..."
sleep 5
osascript -e 'tell application "Терминал" to close (every window whose name contains "PRESENTATION-EMERGENCY")' 2>/dev/null || true
osascript -e 'tell application "Terminal" to close (every window whose name contains "PRESENTATION-EMERGENCY")' 2>/dev/null || true
exit 0
