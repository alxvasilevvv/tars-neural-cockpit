#!/usr/bin/env bash
# SIGN-AND-NOTARIZE.command — W250
#
# Double-clickable end-to-end workflow:
#   1. Reads .env for Apple Developer credentials
#   2. Codesigns TARS.app with hardened runtime + entitlements
#   3. Submits to Apple notary service via notarytool
#   4. Staples ticket so the app launches offline without Gatekeeper bounce
#   5. Validates via `spctl --assess`
#
# Pre-requisite: one-time keychain setup per docs/APPLE_SIGNING_SETUP.md.
# This script does not perform any setup — it only runs the pipeline.
#
# Once this script returns "accepted", the .app can be distributed without
# users needing `xattr -cr` workarounds.

set -u

cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO="$(pwd)"
LOG="${REPO}/.SIGN-AND-NOTARIZE.txt"

# Mirror everything below to terminal AND append to log.
exec > >(tee -a "$LOG") 2>&1

if [ -t 1 ]; then
  G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[34m'; D=$'\033[2m'; X=$'\033[0m'
else
  G=""; R=""; Y=""; B=""; D=""; X=""
fi

step() { printf "\n${B}── [%s/%s] %s ──${X}\n" "$1" "$2" "$3"; }
ok()   { printf "${G}✓${X} %s\n" "$1"; }
warn() { printf "${Y}⚠${X} %s\n" "$1"; }
fail() {
  printf "${R}✗ %s${X}\n" "$1"
  if [ -n "${2:-}" ]; then
    printf "${R}  hint: %s${X}\n" "$2"
  fi
  printf "\n${R}=== ABORTED ===${X}\n"
  sleep 12
  exit 1
}

echo "=== SIGN-AND-NOTARIZE at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "repo: $REPO"

# ── 1. Load .env credentials ─────────────────────────────────────────
step 1 8 "load Apple Developer credentials from .env"

ENV_FILE="${REPO}/.env"
if [ ! -f "$ENV_FILE" ]; then
  fail "no .env file at $ENV_FILE" \
       "copy .env.example → .env and fill the APPLE_* lines per docs/APPLE_SIGNING_SETUP.md"
fi

# Source .env without exporting noise — only the keys we care about.
# Using grep so `set -u` doesn't trip on the operator-supplied file.
APPLE_TEAM_ID="$(grep -E '^[[:space:]]*APPLE_TEAM_ID=' "$ENV_FILE" | tail -1 | cut -d= -f2- | sed 's/^"\(.*\)"$/\1/; s/^[[:space:]]*//; s/[[:space:]]*$//')"
APPLE_DEVELOPER_ID_APPLICATION="$(grep -E '^[[:space:]]*APPLE_DEVELOPER_ID_APPLICATION=' "$ENV_FILE" | tail -1 | cut -d= -f2- | sed 's/^"\(.*\)"$/\1/; s/^[[:space:]]*//; s/[[:space:]]*$//')"
APPLE_NOTARY_PROFILE="$(grep -E '^[[:space:]]*APPLE_NOTARY_PROFILE=' "$ENV_FILE" | tail -1 | cut -d= -f2- | sed 's/^"\(.*\)"$/\1/; s/^[[:space:]]*//; s/[[:space:]]*$//')"

MISSING=()
[ -z "$APPLE_TEAM_ID" ]                 && MISSING+=("APPLE_TEAM_ID")
[ -z "$APPLE_DEVELOPER_ID_APPLICATION" ] && MISSING+=("APPLE_DEVELOPER_ID_APPLICATION")
[ -z "$APPLE_NOTARY_PROFILE" ]          && MISSING+=("APPLE_NOTARY_PROFILE")

if [ ${#MISSING[@]} -gt 0 ]; then
  printf "${R}✗ missing in .env:${X} %s\n" "${MISSING[*]}"
  echo ""
  echo "  Setup instructions: ${REPO}/docs/APPLE_SIGNING_SETUP.md"
  echo ""
  echo "  Quick recap of what each value is:"
  echo "    APPLE_TEAM_ID                  — your 10-char team ID (e.g. ZGR2C33ZLZ)"
  echo "    APPLE_DEVELOPER_ID_APPLICATION — exact cert name as it appears in Keychain"
  echo "                                     (e.g. 'Developer ID Application: Your Name (XXXXX)')"
  echo "    APPLE_NOTARY_PROFILE           — name you gave 'xcrun notarytool store-credentials'"
  echo ""
  fail "Apple credentials not configured" \
       "follow docs/APPLE_SIGNING_SETUP.md (one-time, ~15 minutes)"
fi

ok "APPLE_TEAM_ID                  = $APPLE_TEAM_ID"
ok "APPLE_DEVELOPER_ID_APPLICATION = $APPLE_DEVELOPER_ID_APPLICATION"
ok "APPLE_NOTARY_PROFILE           = $APPLE_NOTARY_PROFILE"

# ── 2. Locate TARS.app ───────────────────────────────────────────────
step 2 8 "locate TARS.app bundle"

APP_PATH=""
CANDIDATES=(
  "/Applications/TARS.app"
  "${REPO}/desktop/src-tauri/target/aarch64-apple-darwin/release/bundle/macos/TARS.app"
  "${REPO}/desktop/src-tauri/target/x86_64-apple-darwin/release/bundle/macos/TARS.app"
  "${REPO}/desktop/src-tauri/target/release/bundle/macos/TARS.app"
)
for c in "${CANDIDATES[@]}"; do
  if [ -d "$c" ]; then
    APP_PATH="$c"
    break
  fi
done

if [ -z "$APP_PATH" ]; then
  echo "  Looked at:"
  for c in "${CANDIDATES[@]}"; do echo "    - $c"; done
  fail "TARS.app not found" \
       "build it first via scripts/REBUILD-TARS-APP.command"
fi
ok "APP_PATH = $APP_PATH"

# ── 3. Verify entitlements + cert ────────────────────────────────────
step 3 8 "verify entitlements + signing cert available"

ENT_PLIST="${REPO}/desktop/src-tauri/entitlements.plist"
if [ ! -f "$ENT_PLIST" ]; then
  fail "entitlements file missing: $ENT_PLIST" \
       "expected the W250 commit to ship this file"
fi
if ! plutil -lint "$ENT_PLIST" >/dev/null 2>&1; then
  fail "entitlements.plist failed plutil -lint" \
       "fix XML syntax errors in $ENT_PLIST"
fi
ok "entitlements OK ($(basename "$ENT_PLIST"))"

if ! security find-identity -v -p codesigning 2>/dev/null | grep -q "$APPLE_DEVELOPER_ID_APPLICATION"; then
  warn "cert '$APPLE_DEVELOPER_ID_APPLICATION' not found in default keychain"
  warn "  available codesigning identities:"
  security find-identity -v -p codesigning 2>/dev/null | sed 's/^/    /'
  fail "Developer ID Application cert not in keychain" \
       "import the .p12 from your Apple Developer account into Keychain Access (see docs/APPLE_SIGNING_SETUP.md §3)"
fi
ok "signing cert found in keychain"

# ── 4. Codesign (deep, hardened runtime, timestamped) ────────────────
step 4 8 "codesign with hardened runtime + entitlements"

# `--deep` recurses into frameworks + helper binaries (incl. the sidecar).
# `--options runtime` enables hardened runtime (required for notarization).
# `--timestamp` embeds a secure RFC3161 timestamp — required by notary.
# `--force` re-signs even if already signed (we re-sign on every release).
if ! codesign \
    --deep \
    --force \
    --options runtime \
    --timestamp \
    --entitlements "$ENT_PLIST" \
    --sign "$APPLE_DEVELOPER_ID_APPLICATION" \
    "$APP_PATH"; then
  fail "codesign failed" \
       "common cause: cert mismatch — re-check APPLE_DEVELOPER_ID_APPLICATION exact string"
fi
ok "codesigned successfully"

# ── 5. Verify signature ──────────────────────────────────────────────
step 5 8 "verify signature is valid + deep"

if ! codesign --verify --deep --strict --verbose=2 "$APP_PATH" 2>&1 | tee /tmp/tars-codesign-verify.txt; then
  fail "codesign --verify failed" \
       "see /tmp/tars-codesign-verify.txt — usually a nested bundle that didn't get re-signed"
fi
ok "signature is valid"

# ── 6. Zip for notarization ──────────────────────────────────────────
step 6 8 "zip bundle for notary submission"

NOTARY_ZIP="/tmp/tars-notary.zip"
rm -f "$NOTARY_ZIP"
if ! ditto -c -k --keepParent "$APP_PATH" "$NOTARY_ZIP"; then
  fail "ditto failed to produce $NOTARY_ZIP" \
       "check that $APP_PATH is readable and /tmp has space"
fi
ZIP_SIZE_MB=$(du -m "$NOTARY_ZIP" | awk '{print $1}')
ok "zip ready ($NOTARY_ZIP, ${ZIP_SIZE_MB} MB)"

# ── 7. Submit to Apple notary ────────────────────────────────────────
step 7 8 "submit to Apple notary service (--wait, typically 1-5 min)"

# `--wait` blocks until Apple returns Accepted/Invalid/Rejected.
# Typical turnaround: 1-5 minutes for a ~100 MB .app. Can spike to 30+ min
# when Apple is busy (post-WWDC, late-night batch processing, etc.).
echo "  $(date +%H:%M:%S) — submission started, blocking until Apple responds..."
if ! xcrun notarytool submit "$NOTARY_ZIP" \
       --keychain-profile "$APPLE_NOTARY_PROFILE" \
       --wait 2>&1 | tee /tmp/tars-notary-submit.txt; then
  # notarytool returns nonzero on Invalid/Rejected (the wait succeeded, the
  # verdict was no). Show the developer log for fast diagnosis.
  SUBMISSION_ID=$(grep -E "^[[:space:]]*id:" /tmp/tars-notary-submit.txt | head -1 | awk '{print $2}')
  if [ -n "$SUBMISSION_ID" ]; then
    echo ""
    echo "  fetching developer log for submission $SUBMISSION_ID..."
    xcrun notarytool log "$SUBMISSION_ID" \
      --keychain-profile "$APPLE_NOTARY_PROFILE" 2>&1 | sed 's/^/    /' || true
  fi
  fail "notarization failed" \
       "see developer log above (most common: bad entitlements or unsigned nested binary)"
fi
ok "notarization accepted"

# ── 8. Staple + spctl assess ─────────────────────────────────────────
step 8 8 "staple ticket + spctl assess"

if ! xcrun stapler staple "$APP_PATH"; then
  fail "stapler failed" \
       "notarization succeeded but the ticket couldn't be embedded — try `xcrun stapler staple -v $APP_PATH`"
fi
ok "ticket stapled (app now launches offline without Gatekeeper round-trip)"

if ! spctl --assess --type execute --verbose "$APP_PATH" 2>&1 | tee /tmp/tars-spctl.txt | grep -q "accepted"; then
  fail "spctl --assess did NOT report 'accepted'" \
       "see /tmp/tars-spctl.txt — bundle is signed+notarized but Gatekeeper still rejects it"
fi
ok "spctl assessment: accepted"

# ── done ─────────────────────────────────────────────────────────────
echo ""
echo "${G}=== DONE — TARS.app is signed, notarized, stapled ===${X}"
echo ""
echo "  Bundle: $APP_PATH"
echo "  Users can now download + launch with zero Gatekeeper friction."
echo ""
echo "  Next: build the .dmg (already happens in REBUILD-TARS-APP.command)"
echo "  and re-run this script against the .dmg if you want it stapled too:"
echo ""
echo "    xcrun stapler staple <path-to-dmg>"
echo ""
echo "  Terminal will auto-close in 8 seconds…"

sleep 8
osascript -e 'tell application "Terminal" to close (every window whose name contains "SIGN-AND-NOTARIZE")' >/dev/null 2>&1 || true
exit 0
