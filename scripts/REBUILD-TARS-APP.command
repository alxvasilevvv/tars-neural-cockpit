#!/usr/bin/env bash
# REBUILD-TARS-APP.command — W221
#
# Double-click this to rebuild TARS.app with the latest auth gate + voice
# cockpit (W219 + W220), copy it into /Applications, clear Gatekeeper
# quarantine, and launch it.
#
# Log lands at .REBUILD-TARS-APP.txt at the repo root (same pattern as
# scripts/LAUNCH-NOW.command). The Terminal window auto-closes ~5s
# after the build finishes.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.REBUILD-TARS-APP.txt"

{
  echo "=== REBUILD-TARS-APP at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""
  echo "Building TARS.app (this takes ~3-5 minutes the first time)..."
  echo ""

  # Detect arch — default to aarch64-apple-darwin (Apple Silicon).
  TARGET="aarch64-apple-darwin"
  if [[ "$(arch 2>/dev/null)" == "i386" || "$(uname -m 2>/dev/null)" == "x86_64" ]]; then
    TARGET="x86_64-apple-darwin"
  fi
  echo "── target: ${TARGET} ──"
  echo ""

  echo "── tauri build ──"
  (cd desktop && cargo tauri build --target "${TARGET}" 2>&1 | tail -30)
  echo ""

  APP_SRC="desktop/src-tauri/target/${TARGET}/release/bundle/macos/TARS.app"
  APP_DST="/Applications/TARS.app"

  if [[ ! -d "${APP_SRC}" ]]; then
    echo "✗ build artifact not found at ${APP_SRC}"
    echo "  Check the cargo tauri build output above."
    exit 1
  fi

  echo "── install to ${APP_DST} ──"
  rm -rf "${APP_DST}"
  cp -R "${APP_SRC}" "${APP_DST}"
  echo "    ✓ copied"

  echo "── clear Gatekeeper quarantine ──"
  xattr -cr "${APP_DST}" 2>&1 | tail -5 || true
  echo "    ✓ cleared"

  echo "── launching ──"
  open "${APP_DST}"
  echo "    ✓ launched"

  echo ""
  echo "=== TARS.app rebuilt with v9.2.0-beta2 (W219+W220) ==="
  echo ""
  echo "On launch you'll see:"
  echo "  1. Auth screen → email magic link / Google / Apple / Skip"
  echo "  2. After auth: full-screen voice cockpit (monolith + mic)"
  echo "  3. Hamburger (☰, top-left) opens Status/Agents/Chat/… tabs"
} > "$OUT" 2>&1

sleep 5
osascript -e 'tell application "Терминал" to close (every window whose name contains "REBUILD")' 2>/dev/null || true
osascript -e 'tell application "Terminal" to close (every window whose name contains "REBUILD")' 2>/dev/null || true
