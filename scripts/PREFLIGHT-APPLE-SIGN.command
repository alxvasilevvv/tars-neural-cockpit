#!/usr/bin/env bash
# PREFLIGHT-APPLE-SIGN.command — W310-af PH4 §3+§4 pre-flight helper.
#
# Implementer follow-up to PR #199 (PH4 Apple `.dmg` v10 dock-down brief).
# Bundles the three §3 local-env checks and the §4 CI-secrets check into
# ONE script so the operator runs ONE command BEFORE invoking
# `RELEASE-v10.0.command` instead of pasting four separate commands and
# eyeballing output at the moment when a missing secret is most expensive
# to discover (post-tag, mid-publish — Gate B rollback).
#
# Per brief §3 the three local checks are:
#
#   3.1 security find-identity -v -p codesigning | grep "Developer ID Application"
#       Pass:  ≥ 1 matching identity line
#       Fail:  zero matches → re-import .p12 per APPLE_SIGNING_SETUP.md
#
#   3.2 xcrun notarytool history --keychain-profile "${APPLE_NOTARY_PROFILE:-tars-notary}"
#       Pass:  "Successfully received submission history" (even if empty)
#       Fail:  "could not be found" or auth error → re-run xcrun notarytool
#              store-credentials per APPLE_SIGNING_SETUP.md
#
#   3.3 test -f .env && grep -c "^APPLE_" .env
#       Pass:  count ≥ 3 (TEAM_ID + DEVELOPER_ID_APPLICATION + NOTARY_PROFILE)
#       Fail:  .env absent or < 3 APPLE_* keys → re-provision .env from
#              .env.example per APPLE_SIGNING_SETUP.md
#
# Per brief §4 the CI-side check is:
#
#   4   gh secret list -R "${GH_REPO:-alxvasilevvv/tars-neural-cockpit}"
#       Pass:  all 6 secrets present (APPLE_CERTIFICATE,
#              APPLE_CERTIFICATE_PASSWORD, APPLE_SIGNING_IDENTITY,
#              APPLE_TEAM_ID, APPLE_ID, APPLE_PASSWORD)
#       Fail:  any missing → push via the GitHub UI per APPLE_SIGNING_FOR_CURSOR.md
#              steps 4–6, THEN re-run this script.
#       Also: prints the workflow-dispatch URL the operator clicks
#              ("manual dispatch dry-run" in brief §4) to confirm CI sees
#              all 6 secrets BEFORE the tag cut. Does NOT trigger the
#              dispatch itself (that would consume a build minute on every
#              pre-flight; operator owns the click).
#
# Exit codes:
#   0  all four gates green — operator may proceed with `.p12` export +
#      RELEASE-v10.0.command + post-release `VERIFY-APPLE-SIGNATURE.command`
#   1  one or more gates red — block tag cut; follow brief §3/§4 remediation
#   2  prerequisite missing (not on macOS, missing `gh`/`security`/`xcrun`)
#
# Environment overrides (for tests + cron + non-default repos):
#   APPLE_NOTARY_PROFILE          — notary keychain profile (default: tars-notary)
#   GH_REPO                       — GH repo for secret list (default:
#                                    alxvasilevvv/tars-neural-cockpit)
#   PREFLIGHT_APPLE_REPO          — absolute repo path for §3.3 .env check
#                                    (default: dirname of this script's parent)
#   PREFLIGHT_APPLE_DRY_RUN=1     — print commands without executing
#   PREFLIGHT_APPLE_SKIP_CI=1     — skip §4 gh secret check (offline mode)
#   PREFLIGHT_APPLE_SKIP_LOCAL=1  — skip §3 local checks (CI-only mode,
#                                    e.g. when run from GH Actions on a
#                                    non-Mac runner)
#
# Out of scope (operator owns):
#   - Actually exporting the .p12 from Keychain Access (manual UI step)
#   - Actually pushing the 6 secrets (GitHub UI, owner-only)
#   - Actually clicking "Run workflow" for the manual-dispatch dry-run
#   - Actually invoking `RELEASE-v10.0.command` (separate script, fires
#     `git tag v10.0.0 && git push origin v10.0.0` — destructive)
#
# This script is READ-ONLY by design — same as VERIFY-APPLE-SIGNATURE.

set -u

# ── prereqs ─────────────────────────────────────────────────────────────────

if [ "${PREFLIGHT_APPLE_SKIP_LOCAL:-0}" != "1" ]; then
  if [ "$(uname -s)" != "Darwin" ]; then
    echo "PREFLIGHT-APPLE-SIGN: §3 local checks require macOS (uname=$(uname -s))." >&2
    echo "  set PREFLIGHT_APPLE_SKIP_LOCAL=1 to run §4 only." >&2
    exit 2
  fi
fi

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
  if [ "${PREFLIGHT_APPLE_DRY_RUN:-0}" = "1" ]; then
    printf '+ %s\n' "$*"
    return 0
  fi
  "$@"
}

# Repo path for §3.3 .env check: default = parent of this script's directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${PREFLIGHT_APPLE_REPO:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
NOTARY_PROFILE="${APPLE_NOTARY_PROFILE:-tars-notary}"
GH_REPO_DEFAULT="alxvasilevvv/tars-neural-cockpit"
GH_REPO="${GH_REPO:-${GH_REPO_DEFAULT}}"

# Required CI secret names per brief §4.
REQUIRED_SECRETS=(
  APPLE_CERTIFICATE
  APPLE_CERTIFICATE_PASSWORD
  APPLE_SIGNING_IDENTITY
  APPLE_TEAM_ID
  APPLE_ID
  APPLE_PASSWORD
)

# ── tool availability ──────────────────────────────────────────────────────

if [ "${PREFLIGHT_APPLE_SKIP_LOCAL:-0}" != "1" ]; then
  for tool in security xcrun; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
      echo "PREFLIGHT-APPLE-SIGN: missing macOS tool: ${tool}" >&2
      echo "  install Xcode Command Line Tools:  xcode-select --install" >&2
      exit 2
    fi
  done
fi

if [ "${PREFLIGHT_APPLE_SKIP_CI:-0}" != "1" ]; then
  if ! command -v gh >/dev/null 2>&1; then
    echo "PREFLIGHT-APPLE-SIGN: missing tool: gh" >&2
    echo "  install GitHub CLI:  brew install gh   (then: gh auth login)" >&2
    echo "  or set PREFLIGHT_APPLE_SKIP_CI=1 to skip §4." >&2
    exit 2
  fi
fi

# ── gate 3.1 — codesigning identity ────────────────────────────────────────

LOCAL_GATE=0
SKIP_LOCAL="${PREFLIGHT_APPLE_SKIP_LOCAL:-0}"

if [ "${SKIP_LOCAL}" = "1" ]; then
  hdr "§3 local checks  →  SKIPPED (PREFLIGHT_APPLE_SKIP_LOCAL=1)"
else
  hdr "§3.1  security find-identity (codesigning)"
  SECID_OUT="$(run_or_print security find-identity -v -p codesigning 2>&1 || true)"
  # In dry-run we get the command echo only; treat as pass for structure.
  if [ "${PREFLIGHT_APPLE_DRY_RUN:-0}" = "1" ]; then
    note "(dry-run — assume identity present)"
  else
    DEVID_LINES="$(printf '%s\n' "${SECID_OUT}" | grep -c 'Developer ID Application' || true)"
    if [ "${DEVID_LINES}" -ge 1 ]; then
      ok "§3.1: ${DEVID_LINES} 'Developer ID Application' identity present"
      printf '%s\n' "${SECID_OUT}" | grep 'Developer ID Application' | head -3 | sed 's/^/    /'
    else
      bad "§3.1: no 'Developer ID Application' identity in keychain"
      note "remediation: re-import .p12 per docs/APPLE_SIGNING_SETUP.md"
      LOCAL_GATE=1
    fi
  fi

  # ── gate 3.2 — notarytool keychain profile ──────────────────────────────

  hdr "§3.2  xcrun notarytool history (profile: ${NOTARY_PROFILE})"
  NOTARY_OUT="$(run_or_print xcrun notarytool history --keychain-profile "${NOTARY_PROFILE}" 2>&1 || true)"
  if [ "${PREFLIGHT_APPLE_DRY_RUN:-0}" = "1" ]; then
    note "(dry-run — assume profile present)"
  else
    if printf '%s' "${NOTARY_OUT}" | grep -qE 'Successfully received submission history'; then
      ok "§3.2: notary profile '${NOTARY_PROFILE}' accepted by Apple"
    else
      bad "§3.2: notary profile '${NOTARY_PROFILE}' missing or invalid"
      printf '%s\n' "${NOTARY_OUT}" | head -3 | sed 's/^/    /'
      note "remediation: re-run  xcrun notarytool store-credentials '${NOTARY_PROFILE}'"
      note "             per docs/APPLE_SIGNING_SETUP.md"
      LOCAL_GATE=1
    fi
  fi

  # ── gate 3.3 — .env has APPLE_* keys ─────────────────────────────────────

  hdr "§3.3  .env APPLE_* keys (repo: ${REPO_DIR})"
  ENV_FILE="${REPO_DIR}/.env"
  if [ "${PREFLIGHT_APPLE_DRY_RUN:-0}" = "1" ]; then
    note "(dry-run — assume .env present with ≥ 3 APPLE_* keys)"
  elif [ ! -f "${ENV_FILE}" ]; then
    bad "§3.3: .env not found at ${ENV_FILE}"
    note "remediation: cp .env.example .env  (then fill APPLE_* lines)"
    LOCAL_GATE=1
  else
    # grep -c exits 1 with 0 matches AND prints "0", so the || fallback
    # would double-output. Use wc -l on grep's stdout for a guaranteed
    # integer regardless of match count.
    APPLE_COUNT="$(grep -E '^APPLE_' "${ENV_FILE}" 2>/dev/null | wc -l | tr -d ' ')"
    if [ "${APPLE_COUNT}" -ge 3 ]; then
      ok "§3.3: .env has ${APPLE_COUNT} APPLE_* keys (≥ 3 required)"
      grep '^APPLE_' "${ENV_FILE}" | cut -d= -f1 | sed 's/^/    /'
    else
      bad "§3.3: .env has only ${APPLE_COUNT} APPLE_* keys (need ≥ 3: TEAM_ID + DEVELOPER_ID_APPLICATION + NOTARY_PROFILE)"
      note "remediation: see APPLE_SIGNING_SETUP.md §3"
      LOCAL_GATE=1
    fi
  fi
fi

# ── gate 4 — CI secrets push ───────────────────────────────────────────────

CI_GATE=0
SKIP_CI="${PREFLIGHT_APPLE_SKIP_CI:-0}"

if [ "${SKIP_CI}" = "1" ]; then
  hdr "§4 CI secrets check  →  SKIPPED (PREFLIGHT_APPLE_SKIP_CI=1)"
else
  hdr "§4  gh secret list -R ${GH_REPO}"
  SECRETS_OUT="$(run_or_print gh secret list -R "${GH_REPO}" 2>&1 || true)"
  if [ "${PREFLIGHT_APPLE_DRY_RUN:-0}" = "1" ]; then
    note "(dry-run — assume all 6 present)"
  else
    if printf '%s' "${SECRETS_OUT}" | grep -qiE 'not (logged in|authenticated)|HTTP 401|HTTP 403'; then
      bad "§4: gh not authenticated or no repo access"
      note "remediation:  gh auth login   (then re-run)"
      CI_GATE=1
    else
      MISSING=()
      for s in "${REQUIRED_SECRETS[@]}"; do
        if printf '%s' "${SECRETS_OUT}" | awk '{print $1}' | grep -qFx "${s}"; then
          ok "§4: ${s}"
        else
          bad "§4: MISSING — ${s}"
          MISSING+=("${s}")
          CI_GATE=1
        fi
      done
      if [ "${#MISSING[@]}" -gt 0 ]; then
        note "remediation: push missing secret(s) at"
        note "  https://github.com/${GH_REPO}/settings/secrets/actions"
        note "per APPLE_SIGNING_FOR_CURSOR.md steps 4-6"
      else
        note "operator step: trigger manual dispatch dry-run BEFORE tag-cut at"
        note "  https://github.com/${GH_REPO}/actions/workflows/release-desktop.yml"
        note "(brief §4: catches typos pre-tag → avoids doomed tag cut)"
      fi
    fi
  fi
fi

# ── summary ────────────────────────────────────────────────────────────────

hdr "summary"
TOTAL=$((LOCAL_GATE + CI_GATE))
if [ "${TOTAL}" -eq 0 ]; then
  ok "all pre-flight gates green — operator may proceed"
  ok "next steps (brief §5 + §6):"
  ok "  1. bash scripts/RELEASE-v10.0.command            # tag-cut + CI publish"
  ok "  2. download .dmg from GH Release on clean Mac"
  ok "  3. bash scripts/VERIFY-APPLE-SIGNATURE.command <path>.dmg"
  exit 0
else
  bad "${TOTAL} gate group(s) failed — block tag cut"
  note "fix listed remediations above, then re-run this script"
  exit 1
fi
