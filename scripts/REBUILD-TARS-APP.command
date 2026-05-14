#!/usr/bin/env bash
# REBUILD-TARS-APP.command — W221 (v2)
#
# Double-click to rebuild TARS.app with the latest auth gate + voice cockpit
# (W219 + W220), copy it into /Applications, clear Gatekeeper quarantine,
# and launch it.
#
# Uses the project's own @tauri-apps/cli (already in desktop/package.json
# devDependencies) so we don't need `cargo install tauri-cli` globally.
#
# Build output is mirrored to terminal (so you can watch progress) AND
# appended to .REBUILD-TARS-APP.txt at the repo root.

set -u

cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO="$(pwd)"
LOG="${REPO}/.REBUILD-TARS-APP.txt"

# Mirror everything below to both terminal and log.
exec > >(tee -a "$LOG") 2>&1

echo "=== REBUILD-TARS-APP at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "repo: $REPO"
echo ""

# ── pick package manager ─────────────────────────────────────────────
PM=""
if command -v pnpm >/dev/null 2>&1; then PM="pnpm"
elif command -v npm  >/dev/null 2>&1; then PM="npm"
else
  echo "✗ neither pnpm nor npm found on PATH."
  echo "  Install Node 20+ (https://nodejs.org) and try again."
  sleep 8
  exit 1
fi
echo "── package manager: $PM ──"

# ── detect target arch ───────────────────────────────────────────────
ARCH="$(uname -m 2>/dev/null || echo unknown)"
case "$ARCH" in
  arm64|aarch64) TARGET="aarch64-apple-darwin" ;;
  x86_64)        TARGET="x86_64-apple-darwin"  ;;
  *)             TARGET="aarch64-apple-darwin" ;;
esac
echo "── target: $TARGET ──"
echo ""

# ── install node deps if missing ─────────────────────────────────────
cd "$REPO/desktop"
if [[ ! -d node_modules ]]; then
  echo "── installing node deps (first run, ~30s) ──"
  if [[ "$PM" == "pnpm" ]]; then
    pnpm install --silent || pnpm install
  else
    npm install --no-audit --no-fund --silent || npm install
  fi
  echo ""
fi

# ── tauri build ──────────────────────────────────────────────────────
echo "── tauri build (this takes 3-5 minutes the first time) ──"
echo "   (Rust compiles a lot. Don't close this window.)"
echo ""

if [[ "$PM" == "pnpm" ]]; then
  pnpm exec tauri build --target "$TARGET"
else
  npx --no-install tauri build --target "$TARGET" \
    || npx tauri build --target "$TARGET"
fi
BUILD_RC=$?
echo ""
if [[ $BUILD_RC -ne 0 ]]; then
  echo "✗ tauri build failed (exit $BUILD_RC). See output above."
  sleep 10
  exit $BUILD_RC
fi

# ── locate artifact ──────────────────────────────────────────────────
APP_SRC="$REPO/desktop/src-tauri/target/${TARGET}/release/bundle/macos/TARS.app"
if [[ ! -d "$APP_SRC" ]]; then
  # Older Tauri sometimes drops bundle under target/release/ directly.
  ALT="$REPO/desktop/src-tauri/target/release/bundle/macos/TARS.app"
  if [[ -d "$ALT" ]]; then APP_SRC="$ALT"; fi
fi
if [[ ! -d "$APP_SRC" ]]; then
  echo "✗ build succeeded but TARS.app not found."
  echo "  Looked at: $APP_SRC"
  echo "  And:       $REPO/desktop/src-tauri/target/release/bundle/macos/TARS.app"
  sleep 10
  exit 2
fi
echo "── artifact: $APP_SRC ──"

# ── kill running TARS so cp -R doesn't hit a busy bundle ─────────────
echo "── kill running TARS ──"
pkill -f "TARS.app/Contents/MacOS/" 2>/dev/null && echo "  ✓ killed" || echo "  (not running)"
sleep 1

# ── install to /Applications ─────────────────────────────────────────
APP_DST="/Applications/TARS.app"
echo "── install → $APP_DST ──"
rm -rf "$APP_DST"
cp -R "$APP_SRC" "$APP_DST"
echo "    ✓ copied"

# ── clear Gatekeeper quarantine (fallback when unsigned) ─────────────
echo "── clear Gatekeeper quarantine ──"
xattr -cr "$APP_DST" 2>/dev/null || true
echo "    ✓ cleared"

# ── auto sign + notarize when Apple creds are configured (W250) ──────
# If .env has APPLE_TEAM_ID, APPLE_DEVELOPER_ID_APPLICATION, and
# APPLE_NOTARY_PROFILE set, run scripts/SIGN-AND-NOTARIZE.command so the
# installed bundle is properly signed + stapled and launches without
# Gatekeeper friction. Without these creds we keep the `xattr -cr`
# workaround above and just open the unsigned app — fine for dev,
# unacceptable for distribution.
APPLE_OK=0
if [[ -f "${REPO}/.env" ]]; then
  if grep -qE '^[[:space:]]*APPLE_TEAM_ID=[^[:space:]]' "${REPO}/.env" \
  && grep -qE '^[[:space:]]*APPLE_DEVELOPER_ID_APPLICATION=[^[:space:]]' "${REPO}/.env" \
  && grep -qE '^[[:space:]]*APPLE_NOTARY_PROFILE=[^[:space:]]' "${REPO}/.env"; then
    APPLE_OK=1
  fi
fi
if [[ $APPLE_OK -eq 1 ]]; then
  echo ""
  echo "── auto sign + notarize (Apple creds detected in .env) ──"
  if bash "${REPO}/scripts/SIGN-AND-NOTARIZE.command"; then
    echo "    ✓ signed + notarized + stapled"
  else
    echo "    ✗ sign/notarize failed — bundle is installed but UNSIGNED."
    echo "      see .SIGN-AND-NOTARIZE.txt and re-run scripts/SIGN-AND-NOTARIZE.command"
  fi
else
  echo ""
  echo "── skip sign + notarize (Apple creds not in .env) ──"
  echo "    Configure codesigning per docs/APPLE_SIGNING_SETUP.md when ready."
fi

# ── launch ───────────────────────────────────────────────────────────
echo "── launching ──"
open "$APP_DST"
echo "    ✓ launched"
echo ""
echo "=== TARS.app rebuilt with v9.2.0-beta2 (W219 auth + W220 voice) ==="
echo ""
echo "On launch you'll see:"
echo "  1. Auth screen → email magic-link / Google / Apple / Skip"
echo "  2. After auth: full-screen voice cockpit (monolith + mic)"
echo "  3. Hamburger (☰, top-left) opens Status/Agents/Chat/… tabs"
echo ""
echo "(Terminal will close automatically in 8s.)"

sleep 8
osascript -e 'tell application "Терминал" to close (every window whose name contains "REBUILD")' 2>/dev/null || true
osascript -e 'tell application "Terminal" to close (every window whose name contains "REBUILD")' 2>/dev/null || true
