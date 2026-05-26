#!/usr/bin/env bash
# CURSOR-SOAK-UNTIL-72.command — hourly SOAK-HOURLY until .soak/hourly.log has TARGET lines.
#
# Use when macOS cron returns "Operation not permitted" but an interactive shell
# (Cursor terminal, nohup) can run SOAK-HOURLY. Complements SOAK-CRON-INSTALL.
#
# Env:
#   CURSOR_SOAK_TARGET=72        lines in hourly.log (default 72)
#   CURSOR_OVERNIGHT_INTERVAL=3600  seconds between runs (default 3600)
#   TARS_SOAK_REPO=<path>
#
# Background:
#   nohup bash scripts/CURSOR-SOAK-UNTIL-72.command >> .soak/until-72.log 2>&1 &
#
set -euo pipefail

if [[ -n "${TARS_SOAK_REPO:-}" ]]; then
  cd "${TARS_SOAK_REPO}"
else
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
fi

TARGET="${CURSOR_SOAK_TARGET:-72}"
INTERVAL="${CURSOR_OVERNIGHT_INTERVAL:-3600}"
LOG=".soak/until-72.log"
mkdir -p .soak
touch .soak/hourly.log

echo "[until-72] start $(date -u +%Y-%m-%dT%H:%M:%SZ) target=${TARGET} interval=${INTERVAL}s repo=$(pwd)" | tee -a "$LOG"

while true; do
  n="$(wc -l < .soak/hourly.log 2>/dev/null | tr -d ' ' || echo 0)"
  if [[ "$n" -ge "$TARGET" ]]; then
    echo "[until-72] PROCEED ${n}/${TARGET} samples $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
    exit 0
  fi
  echo "[until-72] sample ${n}/${TARGET} $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
  if bash scripts/SOAK-HOURLY.command >>"$LOG" 2>&1; then
    echo "[until-72] SOAK-HOURLY ok" | tee -a "$LOG"
  else
    rc=$?
    echo "[until-72] SOAK-HOURLY exit=$rc" | tee -a "$LOG"
    if [[ "$rc" -eq 1 ]]; then
      echo "[until-72] BLOCK — 3 consecutive probe failures (PH11 §4.5)" | tee -a "$LOG"
      exit 1
    fi
  fi
  n="$(wc -l < .soak/hourly.log 2>/dev/null | tr -d ' ' || echo 0)"
  if [[ "$n" -ge "$TARGET" ]]; then
    echo "[until-72] PROCEED ${n}/${TARGET} samples $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
    exit 0
  fi
  sleep "$INTERVAL"
done
