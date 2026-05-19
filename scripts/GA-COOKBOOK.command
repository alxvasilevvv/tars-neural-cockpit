#!/usr/bin/env bash
# GA-COOKBOOK.command — W310-ah single-decision pre-tag wrapper.
#
# FIFTH implementer follow-up on the v10.0.0 GA path. Combines the two
# pre-tag gates from PR #216 (PREFLIGHT-APPLE-SIGN) and PR #217
# (BROTHER-PREFLIGHT) into ONE script that the operator runs to get a
# single PROCEED / BLOCK / PARTIAL decision for "may I tag v10.0.0?".
#
# Why this exists
# ───────────────
# After PRs #214-#217 the GA cookbook reduces to 9 steps, but the
# operator still has to remember:
#
#   - both pre-tag gates exist (Apple + Brother),
#   - they must both run BEFORE RELEASE-v10.0.command,
#   - both must be green to proceed.
#
# This wrapper collapses those three "remembered" facts into one
# command:
#
#     bash scripts/GA-COOKBOOK.command
#
# It runs Gate 1 (Apple pre-flight), then Gate 2 (Brother pre-flight),
# aggregates verdicts, and prints ONE final PROCEED/BLOCK/PARTIAL line
# plus the next-step cookbook. If any sub-gate fails, this wrapper
# fails with the same exit code semantics as the sub-gates.
#
# Per-gate spec contracts are unchanged — this is a thin orchestrator,
# not a re-implementation. The wrapped scripts each ship their own
# spec-pinning tests (test_preflight_apple_sign_script.py +
# test_brother_preflight_script.py); this wrapper has its own
# spec-pinning tests (test_ga_cookbook_script.py) that pin the
# orchestration contract (Gate 1 ALWAYS runs first; Gate 2 ALWAYS
# runs even if Gate 1 failed; aggregate verdict is the worst of the
# two).
#
# Wrapped gates
# ─────────────
#   Gate 1 → scripts/PREFLIGHT-APPLE-SIGN.command  (PR #216, brief #199)
#            Pre-tag Apple .dmg sign + notarize prereq check.
#   Gate 2 → scripts/BROTHER-PREFLIGHT.command     (PR #217, brief #198)
#            Pre-tag brother coord 7-sync convergence check.
#
# Aggregate verdict
# ─────────────────
#   PROCEED:   both gates exit 0 → tag may proceed
#   BLOCK:     either gate exit 1 → DO NOT TAG; remediation in sub-gate logs
#   PARTIAL:   neither BLOCK nor PROCEED (some skips, no hard reds) →
#              operator decides whether to proceed despite incomplete
#              verification (e.g. SKIP_LIVE=1 was set for offline dry-run)
#
# Exit contract:
#   0   PROCEED       — both gates green, tag v10.0.0 is unblocked
#   1   BLOCK         — at least one gate red; sub-gate exit pointed to
#                       brief §<X> remediation
#   2   PARTIAL       — neither all-green nor any-red (skips, prereq
#                       missing on one side); operator judgment required
#
# Env overrides
# ─────────────
#   GA_COOKBOOK_DRY_RUN=1     forwards as PREFLIGHT_APPLE_DRY_RUN=1 and
#                             BROTHER_PREFLIGHT_DRY_RUN=1 to sub-gates
#   GA_COOKBOOK_SKIP_LIVE=1   forwards as BROTHER_PREFLIGHT_SKIP_LIVE=1
#                             (Apple gate has no live-net deps)
#   GA_COOKBOOK_SKIP_APPLE=1  skip Gate 1 entirely (e.g. when running on
#                             Linux without macOS host; falls back to
#                             "Apple gate UNVERIFIED — operator runs on Mac")
#   GA_COOKBOOK_SKIP_BROTHER=1 skip Gate 2 entirely (e.g. when brother
#                              coord is intentionally deferred to a later
#                              sync window)
#   GA_COOKBOOK_REPO=<path>   absolute repo path (default: dirname(script)/..)
#                             forwarded as PREFLIGHT_APPLE_REPO +
#                             BROTHER_PREFLIGHT_REPO
#   GA_COOKBOOK_NO_COLOR=1    disable ANSI color (forwarded to both gates)
#
# All Apple/Brother sub-env-vars (APPLE_NOTARY_PROFILE, GH_REPO,
# BROTHER_RECONCILE_URL, BROTHER_PAIR_TTL_ACK, etc.) pass through
# unchanged because this script invokes the sub-gates as separate bash
# processes that inherit the parent env.
#
# Out of scope (operator owns):
#   - Actually tagging v10.0.0 (RELEASE-v10.0.command; destructive)
#   - Actually running the soak (SOAK-HOURLY.command; 72 h cron)
#   - Actually verifying the .dmg post-download (VERIFY-APPLE-SIGNATURE.command)
#
# This is the FIRST step of the GA cookbook — everything else flows
# from here. If this is green, every other step is mechanical.

set -u

# ── plumbing ───────────────────────────────────────────────────────────────

REPO_ROOT="${GA_COOKBOOK_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "${REPO_ROOT}" || {
  echo "ERROR: cannot cd to ${REPO_ROOT}" >&2
  exit 2
}

if [ "${GA_COOKBOOK_NO_COLOR:-0}" = "1" ] || [ ! -t 1 ]; then
  C_RED=""; C_GRN=""; C_YEL=""; C_BLU=""; C_DIM=""; C_BLD=""; C_RST=""
else
  C_RED=$'\033[31m'
  C_GRN=$'\033[32m'
  C_YEL=$'\033[33m'
  C_BLU=$'\033[34m'
  C_DIM=$'\033[2m'
  C_BLD=$'\033[1m'
  C_RST=$'\033[0m'
fi

ok()   { echo "${C_GRN}✓${C_RST}  $*"; }
bad()  { echo "${C_RED}✗${C_RST}  $*"; }
skip() { echo "${C_YEL}⊘${C_RST}  $*"; }
note() { echo "   ${C_DIM}$*${C_RST}"; }

# ── env forwarding plan ────────────────────────────────────────────────────

# Build the env arg arrays once so the orchestration is testable.
APPLE_ENV=()
BROTHER_ENV=()

if [ "${GA_COOKBOOK_DRY_RUN:-0}" = "1" ]; then
  APPLE_ENV+=("PREFLIGHT_APPLE_DRY_RUN=1")
  BROTHER_ENV+=("BROTHER_PREFLIGHT_DRY_RUN=1")
fi

if [ "${GA_COOKBOOK_SKIP_LIVE:-0}" = "1" ]; then
  BROTHER_ENV+=("BROTHER_PREFLIGHT_SKIP_LIVE=1")
fi

if [ "${GA_COOKBOOK_NO_COLOR:-0}" = "1" ]; then
  APPLE_ENV+=("PREFLIGHT_APPLE_NO_COLOR=1")
  BROTHER_ENV+=("BROTHER_PREFLIGHT_NO_COLOR=1")
fi

# Forward repo path so sub-gates see the same root we did.
APPLE_ENV+=("PREFLIGHT_APPLE_REPO=${REPO_ROOT}")
BROTHER_ENV+=("BROTHER_PREFLIGHT_REPO=${REPO_ROOT}")

# ── header ─────────────────────────────────────────────────────────────────

echo "${C_BLU}╔══════════════════════════════════════════════════════════════════╗${C_RST}"
echo "${C_BLU}║        GA-COOKBOOK.command — single pre-tag decision wrapper     ║${C_RST}"
echo "${C_BLU}║    Per PRs #216 (Apple) + #217 (Brother) — two gates, one verdict║${C_RST}"
echo "${C_BLU}╚══════════════════════════════════════════════════════════════════╝${C_RST}"
echo
echo "Repo:  ${REPO_ROOT}"

if [ "${GA_COOKBOOK_DRY_RUN:-0}" = "1" ]; then
  note "(GA_COOKBOOK_DRY_RUN=1 — forwarded to both sub-gates)"
fi
if [ "${GA_COOKBOOK_SKIP_LIVE:-0}" = "1" ]; then
  note "(GA_COOKBOOK_SKIP_LIVE=1 — Brother gate will skip live probes)"
fi

# ── Gate 1: PREFLIGHT-APPLE-SIGN ──────────────────────────────────────────

APPLE_RC=0

echo
echo "${C_BLD}── Gate 1: PREFLIGHT-APPLE-SIGN.command (PR #216) ──${C_RST}"

if [ "${GA_COOKBOOK_SKIP_APPLE:-0}" = "1" ]; then
  skip "Gate 1 skipped via GA_COOKBOOK_SKIP_APPLE=1"
  note "Apple sign side will remain UNVERIFIED — operator must run #216 separately on a Mac"
  APPLE_RC=2  # treat skip as partial, not pass
elif [ ! -x "scripts/PREFLIGHT-APPLE-SIGN.command" ]; then
  bad "Gate 1 script missing or non-executable: scripts/PREFLIGHT-APPLE-SIGN.command"
  note "remediation: re-checkout main (PR #216 should be on it)"
  APPLE_RC=1
else
  # env -i would strip *too much* (we want $HOME, $PATH); instead use env -S to
  # forward our additions without losing the inherited PATH/HOME.
  if env "${APPLE_ENV[@]}" bash scripts/PREFLIGHT-APPLE-SIGN.command; then
    APPLE_RC=0
  else
    APPLE_RC=$?
  fi
fi

# ── Gate 2: BROTHER-PREFLIGHT ─────────────────────────────────────────────

BROTHER_RC=0

echo
echo "${C_BLD}── Gate 2: BROTHER-PREFLIGHT.command (PR #217) ──${C_RST}"

if [ "${GA_COOKBOOK_SKIP_BROTHER:-0}" = "1" ]; then
  skip "Gate 2 skipped via GA_COOKBOOK_SKIP_BROTHER=1"
  note "Brother coord side will remain UNVERIFIED — operator must run #217 separately"
  BROTHER_RC=2  # treat skip as partial, not pass
elif [ ! -x "scripts/BROTHER-PREFLIGHT.command" ]; then
  bad "Gate 2 script missing or non-executable: scripts/BROTHER-PREFLIGHT.command"
  note "remediation: re-checkout main (PR #217 should be on it)"
  BROTHER_RC=1
else
  if env "${BROTHER_ENV[@]}" bash scripts/BROTHER-PREFLIGHT.command; then
    BROTHER_RC=0
  else
    BROTHER_RC=$?
  fi
fi

# ── aggregate verdict ──────────────────────────────────────────────────────

# Aggregate rule: worst-of-two. Any 1 → 1 (BLOCK). Any 2 (and no 1) → 2
# (PARTIAL). Both 0 → 0 (PROCEED).
if [ "${APPLE_RC}" -eq 1 ] || [ "${BROTHER_RC}" -eq 1 ]; then
  AGG_RC=1
elif [ "${APPLE_RC}" -eq 2 ] || [ "${BROTHER_RC}" -eq 2 ]; then
  AGG_RC=2
else
  AGG_RC=0
fi

echo
echo "${C_BLU}╔══════════════════════════════════════════════════════════════════╗${C_RST}"
echo "${C_BLU}║                   GA-COOKBOOK AGGREGATE VERDICT                  ║${C_RST}"
echo "${C_BLU}╚══════════════════════════════════════════════════════════════════╝${C_RST}"
echo

case "${APPLE_RC}" in
  0) ok   "Gate 1 (Apple)   — PROCEED (rc=0)" ;;
  1) bad  "Gate 1 (Apple)   — BLOCK   (rc=1)" ;;
  2) skip "Gate 1 (Apple)   — PARTIAL (rc=2)" ;;
  *) bad  "Gate 1 (Apple)   — UNKNOWN (rc=${APPLE_RC})" ;;
esac

case "${BROTHER_RC}" in
  0) ok   "Gate 2 (Brother) — PROCEED (rc=0)" ;;
  1) bad  "Gate 2 (Brother) — BLOCK   (rc=1)" ;;
  2) skip "Gate 2 (Brother) — PARTIAL (rc=2)" ;;
  *) bad  "Gate 2 (Brother) — UNKNOWN (rc=${BROTHER_RC})" ;;
esac

echo

case "${AGG_RC}" in
  0)
    echo "${C_GRN}${C_BLD}✓  PROCEED${C_RST} — both pre-tag gates green; tag v10.0.0 is unblocked"
    echo
    echo "Next steps (per cookbook):"
    echo "  3. bash scripts/RELEASE-v10.0.command          # tag + push v10.0.0"
    echo "  4. CI signs + notarizes (~5-7 min)"
    echo "  5. download .dmg on clean Mac"
    echo "  6. bash scripts/VERIFY-APPLE-SIGNATURE.command <dmg-path>"
    echo "  7. drag-install + smoke (PH11 §3 ritual)"
    echo "  8. nohup bash scripts/SOAK-HOURLY.command &  # cron, 72 h"
    echo "  9. 72 h later: bash scripts/SOAK-REPORT.command"
    echo " 10. if soak verdict green: post '✓ v10.0.0 SOAK GREEN' in #tars-release"
    ;;
  1)
    echo "${C_RED}${C_BLD}✗  BLOCK${C_RST} — at least one pre-tag gate is RED; DO NOT TAG"
    echo
    echo "Next steps:"
    if [ "${APPLE_RC}" -eq 1 ]; then
      echo "  - Address Gate 1 (Apple) failures per remediation pointers above"
      echo "    or in docs/APPLE_SIGNING_SETUP.md / APPLE_SIGNING_FOR_CURSOR.md"
    fi
    if [ "${BROTHER_RC}" -eq 1 ]; then
      echo "  - Address Gate 2 (Brother) failures per remediation pointers above"
      echo "    or in docs/handoff/PH11_BROTHER_HANDOFF_BRIEF.md §<N>.<X>"
    fi
    echo "  - Re-run: bash scripts/GA-COOKBOOK.command"
    ;;
  2)
    echo "${C_YEL}${C_BLD}⚠  PARTIAL${C_RST} — no hard reds, but verification incomplete"
    echo
    echo "Causes:"
    [ "${APPLE_RC}" -eq 2 ] && echo "  - Apple gate exited 2 (not on macOS, or SKIP_LOCAL=1 / SKIP_CI=1)"
    [ "${BROTHER_RC}" -eq 2 ] && echo "  - Brother gate exited 2 (SKIP_LIVE=1 or missing ph3-pair-ttl ack)"
    [ "${APPLE_RC}" -ne 0 ] && [ "${APPLE_RC}" -ne 1 ] && [ "${APPLE_RC}" -ne 2 ] && echo "  - Apple gate exited ${APPLE_RC} (unexpected — investigate)"
    [ "${BROTHER_RC}" -ne 0 ] && [ "${BROTHER_RC}" -ne 1 ] && [ "${BROTHER_RC}" -ne 2 ] && echo "  - Brother gate exited ${BROTHER_RC} (unexpected — investigate)"
    echo
    echo "Next steps:"
    echo "  - Re-run from a macOS host with network access to get a real verdict"
    echo "  - If the partial is intentional (offline dry-run, deferred coord),"
    echo "    operator judgment required before tagging — this script will not"
    echo "    decide for you."
    ;;
  *)
    bad "AGG_RC=${AGG_RC} unexpected — investigate"
    ;;
esac

echo

exit "${AGG_RC}"
