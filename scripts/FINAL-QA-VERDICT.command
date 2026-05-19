#!/usr/bin/env bash
# FINAL-QA-VERDICT.command — W310-am TENTH implementer follow-up.
#
# Thin wrapper around scripts/FINAL-QA-GATE.command (W267) that normalises
# its 0/1 GO/NO-GO output to the cookbook-uniform 0/1/2 PROCEED/BLOCK/
# PARTIAL contract used by every other GA helper:
#
#   #214 SOAK-HOURLY  / SOAK-REPORT             →  0/1   GA-ready / blocked
#   #215 VERIFY-APPLE-SIGNATURE                  →  0/1/2 PROCEED / BLOCK / PARTIAL
#   #216 PREFLIGHT-APPLE-SIGN                    →  0/1/2 PROCEED / BLOCK / PARTIAL
#   #217 BROTHER-PREFLIGHT                       →  0/1/2 PROCEED / BLOCK / PARTIAL
#   #218 GA-COOKBOOK             (pre-tag Gate A)→  0/1/2 PROCEED / BLOCK / PARTIAL
#   #219 DOWNLOAD-AND-VERIFY-RELEASE (Gate B)    →  0/1/2 PROCEED / BLOCK / PARTIAL
#   #220 BROTHER-POSTFLIGHT      (post-launch)   →  0/1/2 PROCEED / BLOCK / PARTIAL
#   #221 RELEASE-TAG-GUARD       (tag-cut gate)  →  0/1/2 PROCEED / BLOCK / PARTIAL
#   #222 POST-INSTALL-SMOKE      (post-install)  →  0/1/2 PROCEED / BLOCK / PARTIAL
#   #223 FINAL-QA-VERDICT        (final QA gate) →  0/1/2 PROCEED / BLOCK / PARTIAL  ← this script
#
# What FINAL-QA-GATE.command (W267) does today:
#   - Runs 8 mechanical checks (pytest / smoke / perf / codesign /
#     bash -n / doc render / json+yaml / version consistency).
#   - Exits 0 on success and 1 on any failure.
#   - Prints "GO" / "NO-GO" — does NOT distinguish "all 8 green" from
#     "some skipped, none failed" (e.g. codesign skipped because
#     /Applications/TARS.app is not installed yet, which is a SOFT
#     signal that gets lost in the "GO" verdict).
#   - codesign_check returns 0 when /Applications/TARS.app is absent
#     AND simultaneously pushes a record into SKIPPED — so the step
#     ends up in BOTH PASSED and SKIPPED arrays and the operator
#     can read "GO" without actually verifying signing.
#
# What this wrapper adds:
#   - Three-way verdict (PROCEED / BLOCK / PARTIAL) symmetric with
#     #214..#222 so the operator's mental model stays uniform across
#     the GA cookbook ("did the script exit 0?").
#   - Demotes any SKIPPED step to AMBER → PARTIAL (rc=2). So the
#     codesign-skipped-because-TARS-app-not-installed case (and any
#     future skip) surfaces as PARTIAL not PROCEED. v10.0.0 GA tag
#     requires PROCEED (all 8 green); PARTIAL is acceptable for dev
#     builds but the operator owns the call.
#   - Adds per-step remediation pointers for the 8 known steps in the
#     BLOCK verdict block.
#   - Wraps an already-shipped script — does NOT change FINAL-QA-GATE.command
#     itself. RELEASE-v10.0.command keeps calling FINAL-QA-GATE.command
#     unchanged today; a future patch tag can flip the call site to
#     this wrapper without changing the destructive script's behaviour.
#
# Critical invariant: destructively HARMLESS.
#   This script does NOT cut tags, does NOT push code, does NOT modify
#   /Applications/ or any system state. It runs FINAL-QA-GATE.command
#   as a subprocess (which already obeys the same invariant) and just
#   re-renders its verdict in the cookbook-uniform 0/1/2 contract.
#
# Exit contract (cookbook-uniform):
#   0 = PROCEED — all 8 steps green, zero skipped.
#       Next: bash scripts/RELEASE-v10.0.command (after Gate A green).
#   1 = BLOCK   — at least one step failed.
#       Next: read the per-step remediation pointers, fix, re-run.
#   2 = PARTIAL — zero failures but at least one step skipped, OR
#       dry-run, OR sibling FINAL-QA-GATE.command not on PATH.
#       Operator owns the call — v10.0.0 GA requires PROCEED.
#
# Env knobs (all optional):
#   FINAL_QA_VERDICT_DRY_RUN=1       — stub sibling invocation as
#                                      success (no subprocess); useful
#                                      for CI smoke + unit tests.
#   FINAL_QA_VERDICT_REPO=<abs path> — override repo root (resolves
#                                      scripts/ + .FINAL-QA-GATE.txt
#                                      from there). Default = parent
#                                      of this script's dirname.
#   FINAL_QA_VERDICT_GATE_SCRIPT=<path>
#                                    — override sibling resolution.
#                                      Default = ${REPO}/scripts/FINAL-QA-GATE.command.
#   FINAL_QA_VERDICT_LOG=<path>      — override the log file path.
#                                      Default = ${REPO}/.FINAL-QA-GATE.txt
#                                      (matches sibling default so the
#                                      wrapper reads the same file).
#   FINAL_QA_VERDICT_NO_COLOR=1      — strip ANSI escapes from output
#                                      (useful in CI / pipe-to-file).
#
# Usage:
#   bash scripts/FINAL-QA-VERDICT.command
#
# Lands cleanly with or without any of PR #197 / #214 / #218 / #219 /
# #220 / #221 / #222 already merged. FINAL-QA-GATE.command is on main
# since W267 so this wrapper has its hard dep satisfied today.

set -u

# ── Resolve repo + sibling + log ─────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DEFAULT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO="${FINAL_QA_VERDICT_REPO:-${REPO_DEFAULT}}"
GATE_SCRIPT="${FINAL_QA_VERDICT_GATE_SCRIPT:-${REPO}/scripts/FINAL-QA-GATE.command}"
LOG="${FINAL_QA_VERDICT_LOG:-${REPO}/.FINAL-QA-GATE.txt}"

# ── Colour helpers ───────────────────────────────────────────────────
if [ -z "${FINAL_QA_VERDICT_NO_COLOR:-}" ] && [ -t 1 ]; then
  G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[34m'; D=$'\033[2m'; X=$'\033[0m'
else
  G=""; R=""; Y=""; B=""; D=""; X=""
fi

hdr() { printf "\n%s── %s ──%s\n" "${B}" "$1" "${X}"; }
ok()  { printf "%s✓%s %s\n" "${G}" "${X}" "$1"; }
bad() { printf "%s✗%s %s\n" "${R}" "${X}" "$1"; }
amb() { printf "%s⚠%s %s\n" "${Y}" "${X}" "$1"; }
info(){ printf "%s%s%s\n" "${D}" "$1" "${X}"; }

echo "==========================================================="
echo "${B}FINAL-QA-VERDICT.command${X} — W310-am cookbook-uniform wrapper"
echo "         (around scripts/FINAL-QA-GATE.command W267)"
echo "==========================================================="
echo "repo:         ${REPO}"
echo "gate script:  ${GATE_SCRIPT}"
echo "log:          ${LOG}"
echo "ran at:       $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# ── Aggregate verdict bookkeeping ────────────────────────────────────
RC_BAD=0    # any failed step → BLOCK
RC_PARTIAL=0 # any skipped / dry-run / sibling-missing → PARTIAL

# Track per-step counts parsed out of the sibling log.
PASSED_COUNT=0
SKIPPED_COUNT=0
FAILED_COUNT=0
SKIPPED_NAMES=""
FAILED_NAMES=""

# ── Run sibling ──────────────────────────────────────────────────────
hdr "Step — run scripts/FINAL-QA-GATE.command"

GATE_RC=0
GATE_INVOKED=0

if [ -n "${FINAL_QA_VERDICT_DRY_RUN:-}" ]; then
  info "[dry-run] would invoke: bash ${GATE_SCRIPT}"
  info "[dry-run] would parse:  ${LOG}"
  amb "dry-run mode → AMBER (sibling not invoked)"
  RC_PARTIAL=1
elif [ ! -f "${GATE_SCRIPT}" ]; then
  bad "sibling not found: ${GATE_SCRIPT}"
  bad "→ land W267 scripts/FINAL-QA-GATE.command (already on main since W267)"
  bad "→ or set FINAL_QA_VERDICT_GATE_SCRIPT to point at a custom location"
  # Missing sibling is BLOCK not AMBER — we cannot make a GA decision
  # without the gate having run. (This differs from #222's graceful AMBER
  # fallback for SMOKE-TEST.command, because there the wrapped script
  # is one of 4 gates; here it IS the gate.)
  RC_BAD=1
else
  echo "Invoking ${GATE_SCRIPT}..."
  echo ""
  GATE_INVOKED=1
  # Run the sibling; do NOT short-circuit on failure (operator wants
  # the full sibling output streamed to stdout AND captured in the log
  # file the sibling already writes via its own `exec > >(tee -a ...)`).
  if bash "${GATE_SCRIPT}"; then
    GATE_RC=0
  else
    GATE_RC=$?
  fi
  echo ""
  info "FINAL-QA-GATE.command exited with rc=${GATE_RC}"
fi

# ── Parse counts out of the sibling's log file ──────────────────────
# FINAL-QA-GATE.command writes a "Passed:  N / Skipped: N / Failed: N"
# block + per-step bullets at the bottom of .FINAL-QA-GATE.txt. We
# parse those directly so this wrapper doesn't have to re-implement
# the sibling's counting logic.
if [ "${GATE_INVOKED}" = 1 ] && [ -f "${LOG}" ]; then
  # Tail to the last "go/no-go report" block (sibling appends to log
  # across runs, so we want only the most-recent run's counters).
  LAST_BLOCK="$(awk '/FINAL-QA-GATE — go\/no-go report/{found=NR} END{print found}' "${LOG}")"
  if [ -n "${LAST_BLOCK}" ] && [ "${LAST_BLOCK}" != "0" ]; then
    # Strip ANSI escape sequences so grep/sed don't trip on colour codes.
    BLOCK_TEXT="$(sed -n "${LAST_BLOCK},\$p" "${LOG}" \
                  | sed $'s/\x1b\\[[0-9;]*[mK]//g')"

    PASSED_COUNT="$(printf "%s\n" "${BLOCK_TEXT}" | awk '/^Passed:[ ]+[0-9]+/{print $2; exit}')"
    SKIPPED_COUNT="$(printf "%s\n" "${BLOCK_TEXT}" | awk '/^Skipped:[ ]+[0-9]+/{print $2; exit}')"
    FAILED_COUNT="$(printf "%s\n" "${BLOCK_TEXT}" | awk '/^Failed:[ ]+[0-9]+/{print $2; exit}')"

    # Collect the SKIPPED + FAILED bullet names so the verdict block
    # can name them in remediation pointers. Sibling formats them as
    # "  ⚠ 4/8 codesign (TARS.app not installed)" / "  ✗ 1/8 pytest".
    SKIPPED_NAMES="$(printf "%s\n" "${BLOCK_TEXT}" \
                     | awk '/^[ ]+⚠/{sub(/^[ ]+⚠[ ]+/,""); print}')"
    FAILED_NAMES="$(printf "%s\n" "${BLOCK_TEXT}" \
                    | awk '/^[ ]+✗/{sub(/^[ ]+✗[ ]+/,""); print}')"
  else
    amb "sibling log present but no go/no-go block found — treating as PARTIAL"
    RC_PARTIAL=1
  fi
elif [ "${GATE_INVOKED}" = 1 ]; then
  amb "sibling log not written: ${LOG} — treating as PARTIAL"
  RC_PARTIAL=1
fi

# Normalise empty parses to 0.
PASSED_COUNT="${PASSED_COUNT:-0}"
SKIPPED_COUNT="${SKIPPED_COUNT:-0}"
FAILED_COUNT="${FAILED_COUNT:-0}"

# ── Map counts to RC ────────────────────────────────────────────────
if [ "${GATE_INVOKED}" = 1 ]; then
  if [ "${FAILED_COUNT}" != "0" ] || [ "${GATE_RC}" != "0" ]; then
    # Either parsed count says failures, or sibling exited non-zero
    # (defensive: covers the case where the log wasn't written but
    # the sibling still returned 1).
    RC_BAD=1
  fi
  if [ "${SKIPPED_COUNT}" != "0" ]; then
    # Skipped steps = AMBER → PARTIAL (unless there are also reds,
    # in which case RC_BAD wins per worst-of rule).
    RC_PARTIAL=1
  fi
fi

# ── Verdict ──────────────────────────────────────────────────────────
echo ""
echo "==========================================================="
echo "${B}FINAL-QA-VERDICT — go/no-go (cookbook-uniform)${X}"
echo "==========================================================="
echo "passed:  ${PASSED_COUNT}"
echo "skipped: ${SKIPPED_COUNT}"
echo "failed:  ${FAILED_COUNT}"

if [ "${RC_BAD}" = 1 ]; then
  echo ""
  printf "%sVERDICT: BLOCK%s — at least one QA step failed.\n" "${R}" "${X}"
  echo ""
  if [ -n "${FAILED_NAMES}" ]; then
    echo "Failed steps:"
    printf "%s\n" "${FAILED_NAMES}" | while IFS= read -r name; do
      [ -z "${name}" ] && continue
      bad "${name}"
    done
    echo ""
  fi
  echo "Remediation pointers (per step from FINAL-QA-GATE.command W267 header):"
  echo "  1/8 pytest             → re-run with 'python3 -m pytest tests/ -x -v' to surface first fail"
  echo "  2/8 smoke              → bring backend up (bash scripts/backend_tars_up.sh) + re-run"
  echo "  3/8 perf               → check perf SLO regressions in tests/perf/conftest.py thresholds"
  echo "  4/8 codesign           → if rejected: bash scripts/SIGN-AND-NOTARIZE.command"
  echo "                         → if not installed: drag /Applications/TARS.app, re-run #222 POST-INSTALL-SMOKE"
  echo "  5/8 .command bash -n   → bash -n the offending file; fix syntax bug; re-run"
  echo "  6/8 doc render         → grep the broken link path; fix or relocate target md"
  echo "  7/8 json/yaml          → cat the offending file; fix parse error; re-run"
  echo "  8/8 version consistency→ check RELEASE-v10.0.command bumps lockstep across 10 files"
  echo ""
  echo "${R}Do NOT run RELEASE-v10.0.command yet.${X}"
  echo "Full log: ${LOG}"
  echo "Sibling brief: scripts/FINAL-QA-GATE.command header (lines 8-17)"
  exit 1
fi

if [ "${RC_PARTIAL}" = 1 ]; then
  echo ""
  printf "%sVERDICT: PARTIAL%s — zero failures but at least one step skipped.\n" "${Y}" "${X}"
  echo ""
  if [ -n "${SKIPPED_NAMES}" ]; then
    echo "Skipped steps:"
    printf "%s\n" "${SKIPPED_NAMES}" | while IFS= read -r name; do
      [ -z "${name}" ] && continue
      amb "${name}"
    done
    echo ""
  fi
  echo "Operator owns the call. PARTIAL causes:"
  echo "  • dry-run mode (FINAL_QA_VERDICT_DRY_RUN=1) — re-run without flag for real verdict"
  echo "  • TARS.app not installed → step 4/8 codesign was skipped"
  echo "    → drag the verified .dmg into /Applications/ (after PR #219 Gate B),"
  echo "      then re-run this script + #222 POST-INSTALL-SMOKE.command"
  echo "  • spctl unavailable (non-macOS host) → run on a Mac before tagging"
  echo "  • non-macOS host → run on a Mac before tagging v10.0.0"
  echo "  • sibling log missing/unparseable → set FINAL_QA_VERDICT_LOG explicitly"
  echo ""
  printf "%sv10.0.0 GA requires PROCEED (rc=0) — PARTIAL is acceptable for dev builds only.%s\n" "${Y}" "${X}"
  printf "%sDo NOT auto-run RELEASE-v10.0.command on a PARTIAL verdict.%s\n" "${Y}" "${X}"
  echo "Full log: ${LOG}"
  exit 2
fi

# ── PROCEED ─────────────────────────────────────────────────────────
echo ""
printf "%sVERDICT: PROCEED%s — all %s QA steps green, zero skipped.\n" \
  "${G}" "${X}" "${PASSED_COUNT}"
echo ""
echo "Cookbook next steps (per GA tag-cut ritual):"
echo "  1) Confirm Gate A: bash scripts/GA-COOKBOOK.command (#218)"
echo "  2) Confirm tag-cut: bash scripts/RELEASE-TAG-GUARD.command (#221)"
echo "  3) Cut tag: bash scripts/RELEASE-v10.0.command"
echo "  4) After CI sign+notarize: bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command (#219)"
echo "  5) Drag-install + post-install: bash scripts/POST-INSTALL-SMOKE.command (#222)"
echo "  6) Start 72h soak: see #214 SOAK-HOURLY cron one-liner from #222 PROCEED block"
echo "  7) After soak: bash scripts/SOAK-REPORT.command (#214)"
echo "  8) Post-launch: bash scripts/BROTHER-POSTFLIGHT.command (#220) at T+24h"
echo ""
echo "Full log: ${LOG}"
exit 0
