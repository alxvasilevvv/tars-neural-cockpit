#!/usr/bin/env bash
# VERIFY-APPLE-SIGNATURE.command — W310-ae PH4 §6.2 verification helper.
#
# Implementer follow-up to PR #199 (PH4 Apple `.dmg` v10 dock-down brief).
# Automates the three "clean-machine" verification commands in §6.2 so the
# operator runs ONE script after downloading the GH-Release `.dmg`/`.app`
# instead of pasting three separate commands and eyeballing output.
#
# Per brief §6.2 the three checks are:
#
#   1. codesign --verify --deep --strict --verbose=2 <path>
#      Pass:  output contains "valid on disk" + "satisfies its Designated Requirement"
#      Fail:  any other state ("invalid", "modified", missing identity)
#
#   2. spctl --assess --type execute --verbose <path>
#      Pass:  "accepted" + "source=Notarized Developer ID"
#      Fail:  "rejected" → block GA cut + rollback per brief §7 Gate B
#
#   3. stapler validate <path>
#      Pass:  "The validate action worked!"
#      Fail:  staple ticket missing → spctl will reject when offline; rollback
#
# Designed to be the second-to-last gate before declaring v10.0.0 launched:
# operator runs `RELEASE-v10.0.command` → GH workflow signs + notarizes →
# operator downloads on a clean Mac → `VERIFY-APPLE-SIGNATURE.command` →
# manual drag-install + first-launch.
#
# Usage:
#   bash scripts/VERIFY-APPLE-SIGNATURE.command /Volumes/TARS/TARS.app
#   bash scripts/VERIFY-APPLE-SIGNATURE.command ~/Downloads/TARS_10.0.0_aarch64.dmg
#
# A `.dmg` target is auto-mounted (read-only), verified, then detached.
# A `.app` target is verified in place.
#
# Exit codes:
#   0  all three gates green — GA tag verification passed
#   1  one or more gates red — block release / restart §7 rollback
#   2  prerequisite missing (path absent, tool not found, not running on macOS)
#
# Environment overrides (mostly for tests):
#   VERIFY_APPLE_EXPECTED_IDENTITY  — substring expected in codesign output
#       (default: "Developer ID Application")
#   VERIFY_APPLE_DRY_RUN=1          — print commands without executing
#   VERIFY_APPLE_NO_DMG_MOUNT=1     — skip the .dmg auto-mount path (treat
#                                      target as already-extracted .app)

set -u

if [ "$(uname -s)" != "Darwin" ]; then
  echo "VERIFY-APPLE-SIGNATURE: must run on macOS (uname=$(uname -s))." >&2
  exit 2
fi

TARGET="${1:-}"
if [ -z "${TARGET}" ]; then
  cat <<'EOF' >&2
VERIFY-APPLE-SIGNATURE: missing argument.

Usage:
  bash scripts/VERIFY-APPLE-SIGNATURE.command <path-to-.app-or-.dmg>

Examples:
  bash scripts/VERIFY-APPLE-SIGNATURE.command /Volumes/TARS/TARS.app
  bash scripts/VERIFY-APPLE-SIGNATURE.command ~/Downloads/TARS_10.0.0_aarch64.dmg
EOF
  exit 2
fi

if [ ! -e "${TARGET}" ]; then
  echo "VERIFY-APPLE-SIGNATURE: target not found: ${TARGET}" >&2
  exit 2
fi

EXPECTED_IDENTITY="${VERIFY_APPLE_EXPECTED_IDENTITY:-Developer ID Application}"

# Resolve required tools — all three are part of Xcode CLT.
for tool in codesign spctl stapler hdiutil; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "VERIFY-APPLE-SIGNATURE: missing required macOS tool: ${tool}" >&2
    echo "  install Xcode Command Line Tools:  xcode-select --install" >&2
    exit 2
  fi
done

if [ -t 1 ]; then
  G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[34m'; D=$'\033[2m'; X=$'\033[0m'
else
  G=""; R=""; Y=""; B=""; D=""; X=""
fi

ok()   { printf "${G}✓${X} %s\n" "$1"; }
bad()  { printf "${R}✗${X} %s\n" "$1"; }
note() { printf "${D}  %s${X}\n" "$1"; }
hdr()  { printf "\n${B}── [%s] ──${X}\n" "$1"; }

run_or_print() {
  if [ "${VERIFY_APPLE_DRY_RUN:-0}" = "1" ]; then
    printf '+ %s\n' "$*"
    return 0
  fi
  "$@"
}

# ── auto-mount .dmg if needed ───────────────────────────────────────────────

MOUNTED_DEV=""
APP_PATH="${TARGET}"

cleanup() {
  if [ -n "${MOUNTED_DEV}" ]; then
    hdr "cleanup"
    note "detaching ${MOUNTED_DEV}"
    hdiutil detach "${MOUNTED_DEV}" -quiet >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

case "${TARGET}" in
  *.dmg)
    if [ "${VERIFY_APPLE_NO_DMG_MOUNT:-0}" = "1" ]; then
      bad ".dmg mount disabled via VERIFY_APPLE_NO_DMG_MOUNT but target is .dmg"
      exit 2
    fi
    hdr "mount ${TARGET}"
    MOUNT_OUT="$(hdiutil attach -nobrowse -readonly -plist "${TARGET}" 2>&1)"
    if [ $? -ne 0 ]; then
      bad "hdiutil attach failed"
      printf '%s\n' "${MOUNT_OUT}" >&2
      exit 1
    fi
    MOUNT_POINT="$(printf '%s' "${MOUNT_OUT}" | grep -A1 '<key>mount-point</key>' | tail -1 | sed -E 's/.*<string>(.+)<\/string>.*/\1/')"
    MOUNTED_DEV="$(printf '%s' "${MOUNT_OUT}" | grep -E '<string>/dev/disk[0-9]+s?[0-9]*' | head -1 | sed -E 's/.*<string>(.+)<\/string>.*/\1/')"
    if [ -z "${MOUNT_POINT}" ]; then
      bad "could not parse mount-point from hdiutil"
      printf '%s\n' "${MOUNT_OUT}" >&2
      exit 1
    fi
    APP_PATH="$(find "${MOUNT_POINT}" -maxdepth 2 -name '*.app' -print -quit 2>/dev/null)"
    if [ -z "${APP_PATH}" ] || [ ! -d "${APP_PATH}" ]; then
      bad "no .app found inside ${MOUNT_POINT}"
      exit 1
    fi
    ok "mounted ${MOUNT_POINT} → ${APP_PATH}"
    ;;
  *.app)
    if [ ! -d "${TARGET}" ]; then
      bad ".app target is not a directory: ${TARGET}"
      exit 2
    fi
    ;;
  *)
    bad "unrecognized target — expected .app or .dmg, got: ${TARGET}"
    exit 2
    ;;
esac

# ── gate 1 — codesign ───────────────────────────────────────────────────────

hdr "1/3  codesign --verify"
CODESIGN_OUT="$(run_or_print codesign --verify --deep --strict --verbose=2 "${APP_PATH}" 2>&1 || true)"
printf '%s\n' "${CODESIGN_OUT}"

CS_GATE=0
if printf '%s' "${CODESIGN_OUT}" | grep -qE 'valid on disk'; then
  ok "codesign: signature valid on disk"
else
  bad "codesign: signature missing or invalid"
  CS_GATE=1
fi
if printf '%s' "${CODESIGN_OUT}" | grep -qE 'satisfies its Designated Requirement'; then
  ok "codesign: satisfies Designated Requirement"
else
  bad "codesign: does NOT satisfy Designated Requirement"
  CS_GATE=1
fi

# Display the resolved signing identity for human eyeballing.
IDENTITY="$(codesign -dvv "${APP_PATH}" 2>&1 | grep -E '^Authority=' | head -1 | sed -E 's/^Authority=//')"
if [ -n "${IDENTITY}" ]; then
  note "identity: ${IDENTITY}"
  if printf '%s' "${IDENTITY}" | grep -qE "${EXPECTED_IDENTITY}"; then
    ok "identity matches expected substring: '${EXPECTED_IDENTITY}'"
  else
    bad "identity does NOT match expected substring: '${EXPECTED_IDENTITY}'"
    CS_GATE=1
  fi
fi

# ── gate 2 — spctl ──────────────────────────────────────────────────────────

hdr "2/3  spctl --assess"
SPCTL_OUT="$(run_or_print spctl --assess --type execute --verbose "${APP_PATH}" 2>&1 || true)"
printf '%s\n' "${SPCTL_OUT}"

SP_GATE=0
if printf '%s' "${SPCTL_OUT}" | grep -qE '^.*: accepted$'; then
  ok "spctl: accepted"
else
  bad "spctl: NOT accepted (Gatekeeper would block on download)"
  SP_GATE=1
fi
if printf '%s' "${SPCTL_OUT}" | grep -qE 'source=Notarized Developer ID'; then
  ok "spctl: source = Notarized Developer ID"
else
  bad "spctl: source is NOT 'Notarized Developer ID' — staple may be missing"
  SP_GATE=1
fi

# ── gate 3 — stapler ────────────────────────────────────────────────────────

hdr "3/3  stapler validate"
STAPLE_OUT="$(run_or_print stapler validate "${APP_PATH}" 2>&1 || true)"
printf '%s\n' "${STAPLE_OUT}"

ST_GATE=0
if printf '%s' "${STAPLE_OUT}" | grep -qE 'The validate action worked'; then
  ok "stapler: notary ticket attached and valid"
else
  bad "stapler: validate failed (offline launch would re-trigger Gatekeeper)"
  ST_GATE=1
fi

# ── summary ─────────────────────────────────────────────────────────────────

hdr "summary"
TOTAL=$((CS_GATE + SP_GATE + ST_GATE))
if [ "${TOTAL}" -eq 0 ]; then
  ok "all 3 gates green — Apple signature verification PASSED"
  ok "next step: drag-install /Applications, first-launch smoke per brief §6.3"
  exit 0
else
  bad "${TOTAL} of 3 gates failed — block GA cut"
  note "follow rollback per PH4_APPLE_SIGN_V10_BRIEF.md §7 (Gate A/B/C)"
  exit 1
fi
