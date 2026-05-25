#!/usr/bin/env bash
# CURSOR-OVERNIGHT-SOAK.command — run SOAK-HOURLY every hour for N hours (Cursor unattended).
#
# Complements system cron when the operator is away. Does NOT replace the 72h
# GA requirement — use alongside SOAK-CRON-INSTALL or existing crontab.
#
# Env:
#   CURSOR_OVERNIGHT_HOURS=8   iterations (default 8)
#   CURSOR_OVERNIGHT_INTERVAL=3600  seconds between runs (default 3600)
#   TARS_SOAK_REPO=<path>       override repo root
#
# Usage (foreground):
#   bash scripts/CURSOR-OVERNIGHT-SOAK.command
#
# Usage (background while sleeping):
#   nohup bash scripts/CURSOR-OVERNIGHT-SOAK.command >> .soak/overnight-watch.log 2>&1 &
#
set -euo pipefail

if [[ -n "${TARS_SOAK_REPO:-}" ]]; then
  cd "${TARS_SOAK_REPO}"
else
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
fi

HOURS="${CURSOR_OVERNIGHT_HOURS:-8}"
INTERVAL="${CURSOR_OVERNIGHT_INTERVAL:-3600}"
LOG=".soak/overnight-watch.log"
mkdir -p .soak

echo "[overnight] start $(date -u +%Y-%m-%dT%H:%M:%SZ) repo=$(pwd) hours=$HOURS interval=${INTERVAL}s" | tee -a "$LOG"

for ((i = 1; i <= HOURS; i++)); do
  echo "[overnight] run $i/$HOURS $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
  if bash scripts/SOAK-HOURLY.command >>"$LOG" 2>&1; then
    echo "[overnight] SOAK-HOURLY ok" | tee -a "$LOG"
  else
    rc=$?
    echo "[overnight] SOAK-HOURLY exit=$rc (continuing unless 3-consec abort)" | tee -a "$LOG"
    if [[ "$rc" -eq 1 ]]; then
      echo "[overnight] hard abort (3 consecutive probe failures) — stopping" | tee -a "$LOG"
      exit 1
    fi
  fi
  if [[ "$i" -lt "$HOURS" ]]; then
    sleep "$INTERVAL"
  fi
done

echo "[overnight] done $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
samples=$(wc -l < .soak/hourly.log 2>/dev/null | tr -d ' ' || echo 0)
echo "[overnight] hourly.log lines: $samples / 72 target" | tee -a "$LOG"
exit 0
