#!/usr/bin/env bash
# diagnose-launch.command — single double-click diagnostic.
#
# Writes everything to .diagnose-launch.txt next to itself so Claude
# can read it back without screenshotting.
#
# Double-click in Finder → macOS opens Terminal and runs this.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.diagnose-launch.txt"

{
  echo "=== diagnose-launch.command run at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""

  echo "[1] /api/product/version"
  curl -s --max-time 8 https://tars.meeet.world/api/product/version || echo "<curl failed>"
  echo ""
  echo ""

  echo "[2] /dl/TARS_9.1.0_aarch64.dmg — full response body"
  curl -s --max-time 8 https://tars.meeet.world/dl/TARS_9.1.0_aarch64.dmg
  echo ""
  echo "---HEADERS---"
  curl -sI --max-time 8 https://tars.meeet.world/dl/TARS_9.1.0_aarch64.dmg
  echo ""

  echo "[3] GitHub Release for v9.1.0 — does it exist + has assets?"
  if command -v gh >/dev/null 2>&1; then
    gh release view v9.1.0 --repo alxvasilevvv/tars-neural-cockpit --json tagName,name,publishedAt,assets 2>&1 | head -80 || echo "<gh release view failed>"
  else
    echo "<gh CLI not installed — falling back to raw API>"
    curl -s --max-time 8 https://api.github.com/repos/alxvasilevvv/tars-neural-cockpit/releases/tags/v9.1.0 | head -100
  fi
  echo ""

  echo "[4] Latest release-desktop-tagged workflow run status"
  if command -v gh >/dev/null 2>&1; then
    gh run list --repo alxvasilevvv/tars-neural-cockpit --workflow release-desktop-tagged.yml --limit 3 2>&1 || echo "<gh run list failed>"
  else
    echo "<gh CLI not installed — skipping>"
  fi
  echo ""

  echo "=== DONE ==="
} 2>&1 | tee "$OUT"

echo ""
echo "Output written to: $OUT"
echo "Closing in 3 seconds..."
sleep 3
