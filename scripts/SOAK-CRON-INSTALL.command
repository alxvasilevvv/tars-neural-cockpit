#!/usr/bin/env bash
# SOAK-CRON-INSTALL.command — idempotent hourly soak crontab registration (read-only install).
#
# Adds exactly one crontab line for SOAK-HOURLY if not already present.
# Destructively HARMLESS: only mutates user crontab (no tag cut, no release).
#
# Exit: 0 installed or already present; 1 crontab failed; 2 prereq (no crontab).
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LINE="0 * * * * cd ${ROOT} && bash scripts/SOAK-HOURLY.command >> .soak/cron.log 2>&1"

if ! command -v crontab >/dev/null 2>&1; then
  echo "BLOCK: crontab not on PATH"
  exit 2
fi

if crontab -l 2>/dev/null | grep -Fq 'scripts/SOAK-HOURLY.command'; then
  echo "PROCEED: soak cron already installed"
  crontab -l 2>/dev/null | grep 'SOAK-HOURLY' || true
  exit 0
fi

{
  crontab -l 2>/dev/null || true
  echo "$LINE"
} | crontab -

echo "PROCEED: installed hourly soak cron"
echo "$LINE"
exit 0
