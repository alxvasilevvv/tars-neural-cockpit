#!/usr/bin/env bash
# build-tars-app.command — rebuild + sign TARS.app with new bundled cockpit.
#
# W201: after the user pivot (cockpit lives only in TARS.app), the bundled
# desktop/src-tauri/web/index.html now contains the full control center.
# This script rebuilds the .app so end-users get the working UI.
#
# Requirements (one-time setup):
#   - pnpm (`npm install -g pnpm` or `brew install pnpm`)
#   - Rust toolchain (`curl https://sh.rustup.rs -sSf | sh`)
#   - Tauri CLI bundled via pnpm devDependencies (auto-installed)
#   - Apple Developer ID (for signing — set APPLE_SIGNING_IDENTITY env)
#
# Result:
#   - desktop/src-tauri/target/release/bundle/dmg/TARS_*.dmg
#   - desktop/src-tauri/target/release/bundle/macos/TARS.app
#   - Optionally drag .app to /Applications/

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.build-tars-app.txt"

{
  echo "=== build-tars-app at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""
  echo "── env check ──"
  echo "pnpm: $(command -v pnpm || echo MISSING)"
  echo "cargo: $(command -v cargo || echo MISSING)"
  echo "node: $(command -v node || echo MISSING)"
  echo "APPLE_SIGNING_IDENTITY: ${APPLE_SIGNING_IDENTITY:-(unset)}"
  echo ""

  if ! command -v pnpm >/dev/null 2>&1; then
    echo "ERROR: pnpm not found. Install:"
    echo "  brew install pnpm"
    echo "  # or"
    echo "  npm install -g pnpm"
    exit 1
  fi

  if ! command -v cargo >/dev/null 2>&1; then
    echo "ERROR: cargo not found. Install Rust:"
    echo "  curl https://sh.rustup.rs -sSf | sh"
    exit 1
  fi

  echo "── pnpm install ──"
  cd desktop && pnpm install 2>&1 | tail -10
  echo ""

  echo "── preflight ──"
  pnpm preflight 2>&1 | tail -5
  echo ""

  echo "── tauri build (this takes 5-15 minutes) ──"
  pnpm tauri:build 2>&1 | tail -30
  echo ""

  echo "── artifacts ──"
  find src-tauri/target/release/bundle -name "*.dmg" -o -name "*.app" 2>/dev/null | head -5
  echo ""

  echo "── next steps ──"
  echo "1. Drag desktop/src-tauri/target/release/bundle/macos/TARS.app to /Applications/"
  echo "2. Verify: open -a TARS (should show the new control center)"
  echo "3. Upload .dmg to GitHub Release for distribution"
  echo ""
  echo "=== DONE ==="
} > "$OUT" 2>&1

sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "build-tars-app")' 2>/dev/null || true
