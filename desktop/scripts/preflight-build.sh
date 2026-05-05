#!/usr/bin/env bash
# Pre-flight gate before `pnpm tauri build`.
#
# Reasons this script exists (Wave 59-3):
#   1. silent blank window — if src-tauri/web/ is empty or missing
#      index.html, Tauri will happily build a .dmg / .msi that opens
#      to a blank window. Easy to ship by accident; impossible to
#      diagnose from the bundle.
#   2. missing icons — the bundle config references icons/icon.icns
#      and icons/icon.ico; Tauri build crashes with a confusing
#      "stat failed" error if either is absent. We surface this
#      *before* the slow Rust compile.
#   3. updater pubkey placeholder — if `tauri.conf.json` still has
#      `TODO_PUBLIC_KEY` and `--release` is implied, signed installers
#      will publish but never auto-update. Hard-fail in release mode.
#
# Usage:
#   bash desktop/scripts/preflight-build.sh           # dev / fast check
#   bash desktop/scripts/preflight-build.sh --release # full release-mode gate
#
# Exits non-zero on any blocker; prints a single-line cause so it's
# easy to grep in CI logs.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB="$ROOT/src-tauri/web"
ICONS="$ROOT/src-tauri/icons"
CONF="$ROOT/src-tauri/tauri.conf.json"

mode="dev"
if [[ "${1:-}" == "--release" ]]; then
  mode="release"
fi

fail() {
  echo "[preflight] FAIL ($mode): $1" >&2
  echo "[preflight] hint: $2" >&2
  exit 1
}

# 1. Cockpit web/ directory populated?
if [[ ! -d "$WEB" ]]; then
  fail "src-tauri/web/ does not exist" \
       "run \`pnpm cockpit:build && pnpm cockpit:package\` from desktop/"
fi
if [[ ! -f "$WEB/index.html" ]]; then
  fail "src-tauri/web/index.html missing — Tauri would build a blank-window installer" \
       "run \`bash desktop/scripts/package-cockpit.sh\` (after \`pnpm build\` in the v3 cockpit)"
fi
# Sanity: there should be SOME built JS chunks in the assets dir.
asset_count=0
if [[ -d "$WEB/assets" ]]; then
  # shellcheck disable=SC2012
  asset_count=$(ls -1 "$WEB/assets" 2>/dev/null | wc -l | tr -d ' ')
fi
if [[ "$asset_count" -lt 5 ]]; then
  fail "src-tauri/web/assets has only $asset_count files — looks like a stale or partial build" \
       "rebuild the cockpit and re-run package-cockpit.sh"
fi

# 2. Icon set present.
for ic in icon.icns icon.ico 32x32.png 128x128.png 128x128@2x.png; do
  if [[ ! -f "$ICONS/$ic" ]]; then
    fail "missing icon: src-tauri/icons/$ic" \
         "run \`python3 desktop/scripts/build_icon_set.py\`"
  fi
done

# 3. Updater pubkey check — only enforced in --release mode.
if [[ "$mode" == "release" ]]; then
  if grep -Fq 'TODO_PUBLIC_KEY' "$CONF"; then
    fail "updater pubkey is still TODO_PUBLIC_KEY" \
         "run \`bash desktop/scripts/generate-release-keys.sh --patch-tauri-conf\` and add private key to CI secrets"
  fi
fi

echo "[preflight] OK ($mode) — web=$asset_count assets · icons present · pubkey=${mode}-acceptable"
