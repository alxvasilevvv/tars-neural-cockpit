#!/usr/bin/env bash
# DOWNLOAD-AND-VERIFY-RELEASE.command — W310-ai PH4 post-release helper.
#
# SIXTH implementer follow-up to the W310 planning surface, and the SECOND
# (after #218 GA-COOKBOOK) that composes existing helpers rather than
# wrapping a brief section directly.
#
# Why this exists
# ---------------
# After the operator runs the pre-tag wrapper (`GA-COOKBOOK.command`, #218)
# and then `RELEASE-v10.0.command` (already on `main`), the GH Actions
# workflow signs + notarizes + staples the `.dmg` and attaches it to the
# release. The operator's *next* job in the GA cookbook is:
#
#   1. ssh / walk to a clean Mac
#   2. open https://github.com/<owner>/<repo>/releases/tag/v10.0.0
#   3. click the right `.dmg` for the arch
#   4. wait for download
#   5. drop it somewhere predictable
#   6. open Terminal
#   7. bash scripts/VERIFY-APPLE-SIGNATURE.command ~/Downloads/TARS_10.0.0_*.dmg
#
# That's seven manual context switches between browser + finder + terminal,
# any of which can silently use the wrong arch, the wrong tag, the wrong
# build of the script (older clone), or the wrong .dmg (someone tested a
# detached build into Downloads/ this week).
#
# This wrapper collapses it to ONE command:
#
#   bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command
#
# which:
#
#   1. Detects host arch (aarch64 / x86_64) and the canonical GH-Release
#      tag (default `v10.0.0`, override `RELEASE_TAG=v10.0.1`).
#   2. Resolves owner/repo via `gh repo view --json owner,name` so it
#      Just Works on any clone (override `GH_REPO=owner/name`).
#   3. Confirms the release exists and the matching `.dmg` asset is
#      present (refuses to proceed if release tag is wrong or asset
#      missing — surfaces remediation instead of downloading nothing).
#   4. Downloads the arch-matched `.dmg` into a fresh tmp dir
#      (`/tmp/tars-ga-download-<pid>/`) via `gh release download`.
#   5. Computes + prints the SHA-256 of the downloaded blob so the
#      operator can cross-reference the release-page checksum (which
#      `RELEASE-v10.0.command` records to `.RELEASE-v10.0.txt`).
#   6. Invokes the sibling `scripts/VERIFY-APPLE-SIGNATURE.command`
#      on the downloaded `.dmg` — passes through its own exit code
#      verbatim so the wrapper has the same 0 / 1 / 2 contract as
#      the verifier.
#   7. Cleans up the tmp dir on success (operator can `--keep` to
#      retain the .dmg for manual drag-install).
#
# Exit contract (mirrors VERIFY-APPLE-SIGNATURE for downstream chaining)
# ----------------------------------------------------------------------
#   0  release found + asset downloaded + signature gates green
#      → may proceed to drag-install + soak
#   1  signature verification failed
#      → block release / restart §7 rollback from PR #199
#   2  prerequisite missing (not on macOS, gh not authed, release tag
#      doesn't exist, no matching .dmg asset, sibling verify script
#      missing on disk)
#
# Environment overrides
# ---------------------
#   RELEASE_TAG=v10.0.0        release tag to fetch (default v10.0.0)
#   GH_REPO=owner/name         override gh repo detection
#   RELEASE_ARCH=aarch64       force arch (default auto-detect via uname)
#   DOWNLOAD_VERIFY_KEEP=1     don't clean up tmp dir on success (operator
#                              wants to drag-install the downloaded .dmg)
#   DOWNLOAD_VERIFY_DRY_RUN=1  print commands + skip download + skip verify
#                              (returns exit 0 unless prereqs are red)
#   DOWNLOAD_VERIFY_REPO=<p>   path to repo (default = parent of this script)
#   DOWNLOAD_VERIFY_NO_COLOR=1 strip ANSI color codes from output
#   DOWNLOAD_VERIFY_TMP_DIR=<p>  override the tmp download dir (testing)
#   DOWNLOAD_VERIFY_SKIP_PLATFORM=1
#                              bypass the macOS-only guard (CI smoke only;
#                              real downloads + signature checks STILL
#                              require macOS — this only lets pytest
#                              exercise the script on Linux runners)
#   DOWNLOAD_VERIFY_SKIP_TOOLS=1
#                              bypass the gh + shasum presence check
#                              (combine with DOWNLOAD_VERIFY_DRY_RUN=1
#                              for fully-mocked Linux CI smoke)
#
# Hard dep
# --------
# This script invokes `scripts/VERIFY-APPLE-SIGNATURE.command` (PR #215).
# If that helper hasn't landed on `main` yet, this script exits 2 with a
# remediation pointer naming PR #215. Fails safely, not silently.
#
# Usage
# -----
#   bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command
#   RELEASE_TAG=v10.0.1 bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command
#   DOWNLOAD_VERIFY_KEEP=1 bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command
#   DOWNLOAD_VERIFY_DRY_RUN=1 bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command

set -u

# ── Resolve repo root + sibling script paths ──────────────────────────
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${DOWNLOAD_VERIFY_REPO:-$(cd "${SELF_DIR}/.." && pwd)}"
VERIFY_SCRIPT="${REPO}/scripts/VERIFY-APPLE-SIGNATURE.command"

# ── Color setup ──────────────────────────────────────────────────────
if [ -t 1 ] && [ "${DOWNLOAD_VERIFY_NO_COLOR:-0}" != "1" ]; then
  G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[34m'; D=$'\033[2m'; X=$'\033[0m'
else
  G=""; R=""; Y=""; B=""; D=""; X=""
fi

ok()    { printf "${G}✓${X} %s\n" "$1"; }
bad()   { printf "${R}✗${X} %s\n" "$1"; }
warn()  { printf "${Y}!${X} %s\n" "$1"; }
note()  { printf "${D}  %s${X}\n" "$1"; }
hdr()   { printf "\n${B}── [%s] ──${X}\n" "$1"; }

DRY="${DOWNLOAD_VERIFY_DRY_RUN:-0}"
KEEP="${DOWNLOAD_VERIFY_KEEP:-0}"
RELEASE_TAG="${RELEASE_TAG:-v10.0.0}"

hdr "DOWNLOAD-AND-VERIFY-RELEASE — tag ${RELEASE_TAG}"

# ── Platform guard ────────────────────────────────────────────────────
if [ "$(uname -s)" != "Darwin" ] && [ "${DOWNLOAD_VERIFY_SKIP_PLATFORM:-0}" != "1" ]; then
  bad "must run on macOS (uname=$(uname -s))"
  note "the .dmg signature gates rely on codesign + spctl + stapler"
  note "which are Xcode CLT only; cross-platform verification is not"
  note "possible for Apple-signed bundles."
  note "set DOWNLOAD_VERIFY_SKIP_PLATFORM=1 to bypass for CI smoke only"
  exit 2
fi

# ── Sibling script presence ──────────────────────────────────────────
if [ ! -f "${VERIFY_SCRIPT}" ]; then
  bad "sibling helper missing: scripts/VERIFY-APPLE-SIGNATURE.command"
  note "this wrapper composes PR #215's VERIFY-APPLE-SIGNATURE.command;"
  note "if PR #215 hasn't landed on main yet, merge it first or run"
  note "this script from that branch."
  note "REPO=${REPO}"
  exit 2
fi

if [ ! -x "${VERIFY_SCRIPT}" ]; then
  warn "${VERIFY_SCRIPT} is not executable; will invoke via bash"
fi

# ── Tool dependencies ────────────────────────────────────────────────
if [ "${DOWNLOAD_VERIFY_SKIP_TOOLS:-0}" != "1" ]; then
  for tool in gh shasum; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
      bad "missing required tool: ${tool}"
      case "${tool}" in
        gh) note "install GitHub CLI:  brew install gh && gh auth login" ;;
        shasum) note "shasum is part of macOS; check PATH" ;;
      esac
      exit 2
    fi
  done
fi

# Confirm gh is authed (otherwise download silently 404s on private repos).
if [ "${DRY}" != "1" ]; then
  if ! gh auth status >/dev/null 2>&1; then
    bad "gh is not authenticated"
    note "run:  gh auth login"
    exit 2
  fi
fi

# ── Repo resolution ──────────────────────────────────────────────────
if [ -n "${GH_REPO:-}" ]; then
  REPO_SLUG="${GH_REPO}"
elif [ "${DRY}" = "1" ]; then
  REPO_SLUG="${GH_REPO:-owner/repo-dry-run}"
else
  REPO_SLUG="$(gh repo view --json owner,name --jq '.owner.login + "/" + .name' 2>/dev/null || true)"
  if [ -z "${REPO_SLUG}" ]; then
    bad "could not detect owner/repo via gh repo view"
    note "either run this script from inside the TARS clone, or set"
    note "  GH_REPO=alxvasilevvv/tars-neural-cockpit"
    exit 2
  fi
fi

ok "repo: ${REPO_SLUG}"
ok "tag:  ${RELEASE_TAG}"

# ── Arch detection ───────────────────────────────────────────────────
if [ -n "${RELEASE_ARCH:-}" ]; then
  ARCH="${RELEASE_ARCH}"
else
  case "$(uname -m)" in
    arm64|aarch64) ARCH="aarch64" ;;
    x86_64)        ARCH="x86_64" ;;
    *) bad "unsupported host arch: $(uname -m)"; exit 2 ;;
  esac
fi
ok "arch: ${ARCH}"

# ── Release + asset existence check ──────────────────────────────────
hdr "release lookup"

if [ "${DRY}" = "1" ]; then
  note "[dry-run] gh release view ${RELEASE_TAG} -R ${REPO_SLUG} --json assets"
  note "[dry-run] (would verify .dmg asset matching arch ${ARCH} exists)"
  ASSET_PATTERN="*${ARCH}*.dmg"
  ASSET_NAME="TARS_${RELEASE_TAG#v}_${ARCH}.dmg"
  ok "[dry-run] release assumed present"
  ok "[dry-run] asset assumed: ${ASSET_NAME}"
else
  ASSETS_JSON="$(gh release view "${RELEASE_TAG}" -R "${REPO_SLUG}" --json assets 2>&1 || true)"
  if echo "${ASSETS_JSON}" | grep -qi 'release not found\|no release'; then
    bad "release ${RELEASE_TAG} does not exist on ${REPO_SLUG}"
    note "either the tag hasn't been cut yet (run RELEASE-v10.0.command"
    note "first) or you're targeting the wrong RELEASE_TAG. Available:"
    gh release list -R "${REPO_SLUG}" -L 5 2>/dev/null | sed 's/^/    /' >&2 || true
    exit 2
  fi

  # Find the matching .dmg by arch substring.
  ASSET_NAME="$(echo "${ASSETS_JSON}" | grep -oE '"name":"[^"]*\.dmg"' | sed 's/"name":"//;s/"$//' | grep -i "${ARCH}" | head -1 || true)"
  if [ -z "${ASSET_NAME}" ]; then
    bad "no .dmg asset matching arch '${ARCH}' on ${RELEASE_TAG}"
    note "available .dmg assets:"
    echo "${ASSETS_JSON}" | grep -oE '"name":"[^"]*\.dmg"' | sed 's/"name":"/    /;s/"$//' >&2 || true
    note "tip: override with RELEASE_ARCH=<arch> to match"
    exit 2
  fi

  ok "asset: ${ASSET_NAME}"
fi

# ── Tmp dir ──────────────────────────────────────────────────────────
DEFAULT_TMP="/tmp/tars-ga-download-$$"
TMP_DIR="${DOWNLOAD_VERIFY_TMP_DIR:-${DEFAULT_TMP}}"

cleanup() {
  if [ "${KEEP}" = "1" ]; then
    note "(--keep) leaving ${TMP_DIR} for drag-install"
    return
  fi
  if [ -d "${TMP_DIR}" ] && [ "${TMP_DIR}" != "/" ] && [ -n "${TMP_DIR}" ]; then
    rm -rf "${TMP_DIR}"
  fi
}

if [ "${DRY}" != "1" ]; then
  mkdir -p "${TMP_DIR}"
  trap cleanup EXIT
fi

# ── Download ────────────────────────────────────────────────────────
hdr "download"

DMG_PATH="${TMP_DIR}/${ASSET_NAME}"

if [ "${DRY}" = "1" ]; then
  note "[dry-run] gh release download ${RELEASE_TAG} -R ${REPO_SLUG} -p '${ASSET_NAME}' -D ${TMP_DIR}"
  ok "[dry-run] download skipped"
  ok "[dry-run] sha256: <skipped>"
  ok "[dry-run] would invoke: bash ${VERIFY_SCRIPT} <dmg>"
  printf "\n${Y}PARTIAL${X}  (dry-run; no real download or verify performed)\n\n"
  exit 2
fi

if ! gh release download "${RELEASE_TAG}" -R "${REPO_SLUG}" -p "${ASSET_NAME}" -D "${TMP_DIR}" 2>&1; then
  bad "gh release download failed"
  note "tag=${RELEASE_TAG} asset=${ASSET_NAME} repo=${REPO_SLUG}"
  exit 2
fi

if [ ! -f "${DMG_PATH}" ]; then
  bad "downloaded but file missing at ${DMG_PATH}"
  note "tmp dir contents:"
  ls -la "${TMP_DIR}" >&2 || true
  exit 2
fi

SIZE="$(stat -f '%z' "${DMG_PATH}" 2>/dev/null || echo "?")"
ok "downloaded: ${DMG_PATH}  (${SIZE} bytes)"

SHA="$(shasum -a 256 "${DMG_PATH}" | awk '{print $1}')"
ok "sha256: ${SHA}"
note "cross-reference against .RELEASE-v10.0.txt log on the build machine"

# ── Verify ───────────────────────────────────────────────────────────
hdr "signature verification (delegates to VERIFY-APPLE-SIGNATURE.command)"

set +e
bash "${VERIFY_SCRIPT}" "${DMG_PATH}"
VERIFY_RC=$?
set -e || true  # honour the same set -u (no -e) discipline as the rest

case "${VERIFY_RC}" in
  0)
    printf "\n${G}PROCEED${X}  signature gates green — may drag-install + start soak\n\n"
    if [ "${KEEP}" = "1" ]; then
      note "downloaded .dmg retained at: ${DMG_PATH}"
      note "drag it from Finder onto /Applications/ to install"
    fi
    exit 0
    ;;
  1)
    printf "\n${R}BLOCK${X}    signature gate red — DO NOT publish; rollback per PR #199 §7\n\n"
    note "downloaded .dmg retained for forensics: ${DMG_PATH}"
    KEEP=1   # force-keep for forensics on red
    exit 1
    ;;
  *)
    printf "\n${Y}PARTIAL${X}  verifier exited ${VERIFY_RC} (prereq missing); see output above\n\n"
    note "downloaded .dmg retained for retry: ${DMG_PATH}"
    KEEP=1
    exit 2
    ;;
esac
