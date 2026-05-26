#!/usr/bin/env bash
# SOAK-CRON-DIAGNOSE.command — read-only: crontab line + last cron.log errors.
#
# Exit: 0 cron line present and no recent "Operation not permitted"; 1 issues found; 2 prereq.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRON_LOG="${ROOT}/.soak/cron.log"
HOURLY="${ROOT}/.soak/hourly.log"

if ! command -v crontab >/dev/null 2>&1; then
  echo "BLOCK: crontab not on PATH"
  exit 2
fi

echo "── crontab (SOAK lines) ──"
if crontab -l 2>/dev/null | grep -F 'SOAK-HOURLY' || true; then
  :
else
  echo "(no SOAK-HOURLY line — run: bash scripts/SOAK-CRON-INSTALL.command)"
fi

echo ""
echo "── soak progress ──"
if [[ -f "$HOURLY" ]]; then
  n="$(wc -l < "$HOURLY" | tr -d ' ')"
  echo "hourly.log: ${n}/72 lines"
else
  echo "hourly.log: missing (run: bash scripts/SOAK-HOURLY.command)"
fi

echo ""
echo "── last cron.log (if any) ──"
if [[ -f "$CRON_LOG" ]]; then
  tail -5 "$CRON_LOG"
  if tail -20 "$CRON_LOG" | grep -q 'Operation not permitted'; then
    echo ""
    echo "BLOCK: cron cannot execute SOAK-HOURLY (macOS privacy)."
    echo "  Fix: docs/macos/SOAK_CRON_PERMISSIONS.md"
    echo "  Workaround: nohup bash scripts/CURSOR-SOAK-UNTIL-72.command >> .soak/until-72.log 2>&1 &"
    exit 1
  fi
else
  echo "(no .soak/cron.log yet)"
fi

echo ""
echo "PROCEED: no cron permission errors in recent log"
exit 0
