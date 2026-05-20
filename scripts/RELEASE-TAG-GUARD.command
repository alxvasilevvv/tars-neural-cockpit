#!/usr/bin/env bash
# RELEASE-TAG-GUARD.command — W310-ak EIGHTH implementer follow-up.
#
# Purpose
# -------
# Read-only safety gate sitting between SOAK-REPORT (which always exits
# 0 because the markdown *is* the source of truth) and RELEASE-v10.0
# (which actually cuts + pushes the v10.0.0 GA tag). The operator's
# remaining manual ritual at this point in the cookbook is:
#
#   1. Open docs/qa/SOAK_v10.0.0.md in an editor
#   2. Eyeball the `## 1. Verdict` line for the words "GA tag
#      **authorised**" vs "blocked"
#   3. If authorised, remember to also check that no v10.0.0 tag was
#      already pushed by mistake, that main is clean, that CI is green
#      on HEAD, and finally type `bash scripts/RELEASE-v10.0.command`
#      manually
#
# That's three remembered probes and one remembered command. This
# wrapper compresses it to "did `RELEASE-TAG-GUARD.command` exit 0?".
#
# What this script does
# ---------------------
# Runs 5 gates against the local repo + GitHub state, in order:
#
#   Gate 1 — SOAK-REPORT verdict      Parses the most-recent
#                                     `docs/qa/SOAK_v10.0.0.md` (or
#                                     $TARS_TAG_GUARD_REPORT) for the
#                                     three known verdict signatures
#                                     emitted by SOAK-REPORT.command's
#                                     section "## 1. Verdict":
#                                       a) "GA tag **authorised**"
#                                          (proceed)
#                                       b) "GA tag **blocked** — only
#                                          N/72 hourly samples"
#                                          (BLOCK: incomplete window)
#                                       c) "GA tag **blocked** —
#                                          hard-fail criterion hit"
#                                          (BLOCK: real regression)
#                                       d) "Go / no-go: blocked (no
#                                          data)" (BLOCK: missing log)
#
#   Gate 2 — git HEAD on `main`       Runs `git symbolic-ref --short
#                                     HEAD` and asserts the value is
#                                     exactly `main`. Releasing from a
#                                     branch breaks reproducibility.
#
#   Gate 3 — working tree clean       Runs `git status --porcelain` and
#                                     asserts empty output. Mirrors
#                                     RELEASE-v10.0.command's Step 2
#                                     gate; catches it earlier so the
#                                     operator doesn't waste time
#                                     hitting FINAL-QA-GATE only to be
#                                     bounced one step later.
#
#   Gate 4 — tag does NOT already     Runs `git rev-parse --verify
#            exist                    --quiet refs/tags/v10.0.0` AND
#                                     `git ls-remote --tags origin
#                                     v10.0.0` and asserts both empty.
#                                     If a previous attempt pushed the
#                                     tag (locally or to origin), the
#                                     operator must either reuse it
#                                     deliberately (manual `git tag -f`
#                                     elsewhere) or delete it before
#                                     RELEASE-v10.0 can run cleanly.
#
#   Gate 5 — last CI run on main      Runs `gh run list --branch main
#            HEAD is `success`        --limit 1 --json
#                                     status,conclusion,headSha` and
#                                     asserts: status=completed,
#                                     conclusion=success, headSha
#                                     matches `git rev-parse HEAD`.
#                                     Prevents tagging a SHA whose CI
#                                     never finished / failed.
#
# Verdict aggregation
# -------------------
# Worst-of-five (any gate red → BLOCK):
#   - all 5 green → 0 PROCEED + print exact next command (`bash
#     scripts/RELEASE-v10.0.command`) for operator copy-paste, with the
#     exact env knobs they'd want for a real cut (auto-push=1,
#     dry-run=0)
#   - any gate red → 1 BLOCK + per-gate remediation pointer (verdict
#     re-run guidance, branch-switch guidance, stash/commit guidance,
#     tag-delete guidance, CI-rerun guidance)
#   - prereq missing (no `gh` binary, no `git` binary, no
#     `docs/qa/SOAK_v10.0.0.md`) → 2 PARTIAL with explanation
#
# Hard deps
# ---------
#   - bash >= 4
#   - git on PATH
#   - gh on PATH (for Gate 5; if missing → rc=2 PARTIAL, NOT rc=1)
#   - `docs/qa/SOAK_v10.0.0.md` exists on disk (if missing → rc=1
#     BLOCK with "soak not yet run" pointer; this is a real BLOCK
#     because tagging without a finished soak is a worse failure mode
#     than tagging without `gh`)
#
# Wrapper is destructively HARMLESS — it does NOT push a tag, it does
# NOT modify git state, it does NOT call RELEASE-v10.0. The whole
# point is to *refuse* to let the operator type the tag command until
# all five gates are green.
#
# Env knobs
#   TAG_GUARD_DRY_RUN=1            Skip `gh run list` live call; assume
#                                  green. Smoke-test the runtime path.
#   TAG_GUARD_SKIP_GH=1            Same as dry-run for Gate 5
#                                  specifically; rc downgrades to 2.
#   TAG_GUARD_REPO=<abs path>      Override repo root (test hook +
#                                  worktree usage).
#   TARS_TAG_GUARD_REPORT=<path>   Override the soak-report path (test
#                                  hook + custom-location override).
#   TAG_GUARD_TAG=v10.0.0          Override the expected tag name.
#                                  Default `v10.0.0`. Lets the same
#                                  wrapper be re-used for v10.0.1 etc.
#   TAG_GUARD_BRANCH=main          Override the expected branch.
#                                  Default `main`.
#   TAG_GUARD_NO_COLOR=1           Force ANSI off (CI tail output).
#
# Exit contract
#   0  PROCEED — all 5 gates green; print copy-paste command + log
#   1  BLOCK   — at least one gate red; consult per-gate remediation
#   2  PARTIAL — at least one prereq missing OR live skipped; defer
#
# Author: W310-ak EIGHTH implementer follow-up. Symmetric with #218
# (Gate A pre-tag verify wrapper) and #219 (Gate B post-tag artifact
# verify wrapper) and #220 (Postflight post-launch coord wrapper).
# After this lands, the destructive RELEASE-v10.0.command sits behind a
# single-decision read-only gate; "may I cut the tag now?" reduces to
# "did `RELEASE-TAG-GUARD.command` exit 0?".

set -u

# ── env knob normalisation ──────────────────────────────────────────────────

DRY_RUN="${TAG_GUARD_DRY_RUN:-0}"
SKIP_GH="${TAG_GUARD_SKIP_GH:-0}"
TAG_NAME="${TAG_GUARD_TAG:-v10.0.0}"
BRANCH_NAME="${TAG_GUARD_BRANCH:-main}"
NO_COLOR="${TAG_GUARD_NO_COLOR:-0}"

if [ -n "${TAG_GUARD_REPO:-}" ]; then
  cd "${TAG_GUARD_REPO}" || {
    echo "FATAL: TAG_GUARD_REPO=${TAG_GUARD_REPO} not a directory" >&2
    exit 2
  }
else
  cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 2
fi
REPO="$(pwd)"

REPORT_PATH="${TARS_TAG_GUARD_REPORT:-${REPO}/docs/qa/SOAK_v10.0.0.md}"

# ── color helpers (skip when no tty + no_color knob) ────────────────────────

if [ -t 1 ] && [ "${NO_COLOR}" != "1" ]; then
  G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[34m'; D=$'\033[2m'; X=$'\033[0m'
else
  G=""; R=""; Y=""; B=""; D=""; X=""
fi

hdr()  { printf "\n${B}── %s ──${X}\n" "$1"; }
ok()   { printf "${G}✓${X} %s\n" "$1"; }
warn() { printf "${Y}⚠${X} %s\n" "$1"; }
bad()  { printf "${R}✗${X} %s\n" "$1"; }

# Accumulators.
RC_BAD=0      # any gate set this → rc=1 BLOCK
RC_PARTIAL=0  # any gate set this → rc=2 PARTIAL (unless RC_BAD wins)
GATE_RESULTS=()  # "Gate N — Name|RESULT|hint"

record() {
  GATE_RESULTS+=("$1|$2|$3")
}

# ── prereq probes ──────────────────────────────────────────────────────────

hdr "Pre-flight prereqs"

if ! command -v git >/dev/null 2>&1; then
  bad "git not on PATH — cannot run any gate"
  echo
  echo "Install git and re-run. Exit 2 PARTIAL."
  exit 2
fi
ok "git on PATH ($(git --version 2>/dev/null | head -1))"

GH_AVAILABLE=1
if [ "${SKIP_GH}" = "1" ]; then
  warn "TAG_GUARD_SKIP_GH=1 — Gate 5 will be downgraded to PARTIAL"
  GH_AVAILABLE=0
  RC_PARTIAL=1
elif ! command -v gh >/dev/null 2>&1; then
  warn "gh not on PATH — Gate 5 will be downgraded to PARTIAL"
  GH_AVAILABLE=0
  RC_PARTIAL=1
else
  ok "gh on PATH ($(gh --version 2>/dev/null | head -1))"
fi

if [ "${DRY_RUN}" = "1" ]; then
  warn "TAG_GUARD_DRY_RUN=1 — Gate 5 live call will be stubbed green"
fi

echo "repo:   ${REPO}"
echo "report: ${REPORT_PATH}"
echo "tag:    ${TAG_NAME}"
echo "branch: ${BRANCH_NAME}"

# ── Gate 1 — SOAK-REPORT verdict ───────────────────────────────────────────

hdr "Gate 1 — SOAK-REPORT verdict (${REPORT_PATH})"

if [ ! -f "${REPORT_PATH}" ]; then
  if [ "${DRY_RUN}" = "1" ]; then
    warn "soak report not found at ${REPORT_PATH}"
    echo "  (TAG_GUARD_DRY_RUN=1 — Gate 1 recorded AMBER for W310-ap rehearsal;"
    echo "   real tag cut still requires a rendered SOAK_v10.0.0.md verdict.)"
    record "Gate 1 — SOAK-REPORT verdict" "AMBER" "report missing (dry-run rehearsal)"
  else
    bad "soak report not found at ${REPORT_PATH}"
    echo "  remediation: run \`bash scripts/SOAK-REPORT.command >"
    echo "               docs/qa/SOAK_v10.0.0.md\` after \`bash"
    echo "               scripts/SOAK-HOURLY.command\` has populated"
    echo "               .soak/hourly.log for at least 72 hours."
    echo "               OR set TARS_TAG_GUARD_REPORT=<path> if the"
    echo "               report lives elsewhere."
    record "Gate 1 — SOAK-REPORT verdict" "RED" "report missing — run SOAK-REPORT first"
    RC_BAD=1
  fi
else
  # SOAK-REPORT writes ONE of these four canonical signatures in
  # section "## 1. Verdict" (or the no-data fallback at the top of the
  # file). We grep-match each known string verbatim.
  VERDICT_LINE=""
  if grep -q 'GA tag \*\*authorised\*\*' "${REPORT_PATH}"; then
    VERDICT_LINE="GA tag **authorised**"
    ok "soak verdict = AUTHORISED"
    record "Gate 1 — SOAK-REPORT verdict" "GREEN" "authorised"
  elif grep -q 'GA tag \*\*blocked\*\* — only' "${REPORT_PATH}"; then
    VERDICT_LINE="$(grep 'GA tag \*\*blocked\*\* — only' "${REPORT_PATH}" | head -1)"
    bad "soak verdict = INCOMPLETE WINDOW (less than 72/72)"
    echo "  detail: ${VERDICT_LINE}"
    echo "  remediation: continue running \`bash scripts/SOAK-HOURLY.command\`"
    echo "               on cron until 72 samples accumulate, then"
    echo "               re-render the report and re-run this gate."
    record "Gate 1 — SOAK-REPORT verdict" "RED" "soak window incomplete — wait for full 72h"
    RC_BAD=1
  elif grep -q 'GA tag \*\*blocked\*\* — hard-fail' "${REPORT_PATH}"; then
    VERDICT_LINE="$(grep 'GA tag \*\*blocked\*\* — hard-fail' "${REPORT_PATH}" | head -1)"
    bad "soak verdict = HARD-FAIL CRITERION HIT"
    echo "  detail: ${VERDICT_LINE}"
    echo "  remediation: see SOAK_v10.0.0.md §2 (thresholds table) for"
    echo "               which signal exceeded; file cursor/soak-v10-fix-NN"
    echo "               PRs; after fixes land, \`rm -rf .soak/\` and"
    echo "               restart soak from T-0 per PH11 brief §4.5."
    record "Gate 1 — SOAK-REPORT verdict" "RED" "soak hard-fail — fix + restart from T-0"
    RC_BAD=1
  elif grep -q 'Go / no-go: blocked (no data)' "${REPORT_PATH}"; then
    bad "soak verdict = NO DATA (.soak/hourly.log is empty or missing)"
    echo "  remediation: kick off \`bash scripts/SOAK-HOURLY.command\` on"
    echo "               cron per PH11 brief §4.4 to start the 72h window."
    record "Gate 1 — SOAK-REPORT verdict" "RED" "soak never started — kick off SOAK-HOURLY cron"
    RC_BAD=1
  else
    bad "soak verdict = UNRECOGNISED (report does not match any of the"
    echo "                4 known SOAK-REPORT signatures)"
    echo "  remediation: open ${REPORT_PATH} and confirm it was produced"
    echo "               by \`scripts/SOAK-REPORT.command\` and not"
    echo "               hand-edited; re-render via \`bash"
    echo "               scripts/SOAK-REPORT.command > ${REPORT_PATH}\`."
    record "Gate 1 — SOAK-REPORT verdict" "RED" "report unrecognised — re-render via SOAK-REPORT"
    RC_BAD=1
  fi
fi

# ── Gate 2 — git HEAD on main ──────────────────────────────────────────────

hdr "Gate 2 — git HEAD on ${BRANCH_NAME}"

CURRENT_BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || echo "DETACHED")"
if [ "${CURRENT_BRANCH}" = "${BRANCH_NAME}" ]; then
  ok "HEAD is on ${BRANCH_NAME}"
  record "Gate 2 — git HEAD branch" "GREEN" "on ${BRANCH_NAME}"
else
  bad "HEAD is on '${CURRENT_BRANCH}', expected '${BRANCH_NAME}'"
  echo "  remediation: \`git checkout ${BRANCH_NAME}\` (and merge any"
  echo "               pending PRs first), then re-run this gate."
  record "Gate 2 — git HEAD branch" "RED" "wrong branch — checkout ${BRANCH_NAME}"
  RC_BAD=1
fi

# ── Gate 3 — working tree clean ────────────────────────────────────────────

hdr "Gate 3 — working tree clean"

DIRTY="$(git status --porcelain 2>/dev/null || true)"
if [ -z "${DIRTY}" ]; then
  ok "working tree clean — no uncommitted changes"
  record "Gate 3 — working tree clean" "GREEN" "clean"
else
  bad "uncommitted changes in working tree:"
  printf '%s\n' "${DIRTY}" | sed 's/^/    /'
  echo "  remediation: \`git stash\` (if WIP unrelated to release) or"
  echo "               \`git commit\` (if release-related), then re-run."
  record "Gate 3 — working tree clean" "RED" "dirty tree — stash or commit"
  RC_BAD=1
fi

# ── Gate 4 — tag does NOT already exist (local + remote) ───────────────────

hdr "Gate 4 — ${TAG_NAME} does NOT already exist"

TAG_EXISTS_LOCAL=0
TAG_EXISTS_REMOTE=0

if git rev-parse --verify --quiet "refs/tags/${TAG_NAME}" >/dev/null 2>&1; then
  TAG_EXISTS_LOCAL=1
fi
if [ "${DRY_RUN}" != "1" ] && git ls-remote --tags origin "refs/tags/${TAG_NAME}" 2>/dev/null | grep -q .; then
  TAG_EXISTS_REMOTE=1
fi

if [ "${TAG_EXISTS_LOCAL}" = "0" ] && [ "${TAG_EXISTS_REMOTE}" = "0" ]; then
  ok "${TAG_NAME} does not exist locally or on origin"
  record "Gate 4 — tag fresh" "GREEN" "tag fresh"
else
  bad "${TAG_NAME} already exists (local=${TAG_EXISTS_LOCAL} remote=${TAG_EXISTS_REMOTE})"
  if [ "${TAG_EXISTS_LOCAL}" = "1" ]; then
    echo "  local:  delete via \`git tag -d ${TAG_NAME}\` if mistaken"
  fi
  if [ "${TAG_EXISTS_REMOTE}" = "1" ]; then
    echo "  remote: delete via \`git push --delete origin ${TAG_NAME}\` if mistaken"
    echo "          BUT: deleting an already-published GA tag is a"
    echo "          big-deal operation; consult PH11 brief §7"
    echo "          (rollback A/B/C) before proceeding."
  fi
  record "Gate 4 — tag fresh" "RED" "tag already exists — see remediation"
  RC_BAD=1
fi

# ── Gate 5 — last CI run on main HEAD is success ───────────────────────────

hdr "Gate 5 — last CI run on ${BRANCH_NAME} HEAD is success"

HEAD_SHA="$(git rev-parse HEAD 2>/dev/null || echo "")"
HEAD_SHA_SHORT="${HEAD_SHA:0:12}"

if [ "${GH_AVAILABLE}" = "0" ]; then
  warn "Gate 5 SKIPPED (gh missing or TAG_GUARD_SKIP_GH=1) — recording PARTIAL"
  record "Gate 5 — CI green on HEAD" "AMBER" "gh unavailable — re-run with gh installed"
elif [ "${DRY_RUN}" = "1" ]; then
  warn "Gate 5 SKIPPED (TAG_GUARD_DRY_RUN=1) — recording PARTIAL"
  record "Gate 5 — CI green on HEAD" "AMBER" "dry-run mode — stubbed green"
  RC_PARTIAL=1
else
  # gh run list returns the most recent run for the branch; we want
  # status=completed AND conclusion=success AND headSha matches local
  # HEAD. Anything else is RED.
  if RUN_JSON="$(gh run list --branch "${BRANCH_NAME}" --limit 1 --json status,conclusion,headSha 2>/dev/null)"; then
    if [ -z "${RUN_JSON}" ] || [ "${RUN_JSON}" = "[]" ]; then
      bad "no CI runs found for branch ${BRANCH_NAME}"
      echo "  remediation: push a commit / re-trigger CI on ${BRANCH_NAME}"
      echo "               and wait for it to complete before re-running."
      record "Gate 5 — CI green on HEAD" "RED" "no CI runs on ${BRANCH_NAME}"
      RC_BAD=1
    else
      # Parse the three fields with a tiny awk dance (no jq dep).
      RUN_STATUS="$(printf '%s' "${RUN_JSON}" | tr ',' '\n' | grep '"status"' | head -1 | sed 's/.*"status":"\([^"]*\)".*/\1/')"
      RUN_CONCL="$(printf '%s' "${RUN_JSON}" | tr ',' '\n' | grep '"conclusion"' | head -1 | sed 's/.*"conclusion":"\([^"]*\)".*/\1/')"
      RUN_SHA="$(printf '%s' "${RUN_JSON}" | tr ',' '\n' | grep '"headSha"' | head -1 | sed 's/.*"headSha":"\([^"]*\)".*/\1/')"
      RUN_SHA_SHORT="${RUN_SHA:0:12}"

      if [ "${RUN_STATUS}" = "completed" ] && [ "${RUN_CONCL}" = "success" ] && [ "${RUN_SHA}" = "${HEAD_SHA}" ]; then
        ok "CI green on ${BRANCH_NAME} HEAD (${HEAD_SHA_SHORT})"
        record "Gate 5 — CI green on HEAD" "GREEN" "ci green"
      else
        bad "CI not green on ${BRANCH_NAME} HEAD"
        echo "  HEAD SHA: ${HEAD_SHA_SHORT}"
        echo "  CI SHA:   ${RUN_SHA_SHORT}"
        echo "  status:   ${RUN_STATUS}"
        echo "  concl:    ${RUN_CONCL}"
        if [ "${RUN_SHA}" != "${HEAD_SHA}" ]; then
          echo "  remediation: last CI run was on a different SHA. Wait"
          echo "               for the run on ${HEAD_SHA_SHORT} to complete,"
          echo "               or trigger one via \`gh workflow run\`."
        elif [ "${RUN_STATUS}" != "completed" ]; then
          echo "  remediation: CI still running (status=${RUN_STATUS}). Wait."
        elif [ "${RUN_CONCL}" != "success" ]; then
          echo "  remediation: CI conclusion=${RUN_CONCL}. Investigate via"
          echo "               \`gh run view <id> --log-failed\` and fix"
          echo "               before tagging."
        fi
        record "Gate 5 — CI green on HEAD" "RED" "ci not green — see remediation"
        RC_BAD=1
      fi
    fi
  else
    bad "\`gh run list\` failed — cannot verify CI state"
    echo "  remediation: run \`gh auth status\` to confirm auth + scope;"
    echo "               retry once auth works."
    record "Gate 5 — CI green on HEAD" "RED" "gh failed — auth or transient issue"
    RC_BAD=1
  fi
fi

# ── verdict summary ────────────────────────────────────────────────────────

hdr "VERDICT"

GREEN=0; AMBER=0; RED=0
for entry in "${GATE_RESULTS[@]}"; do
  res="$(printf '%s' "${entry}" | awk -F'|' '{print $2}')"
  case "${res}" in
    GREEN) GREEN=$((GREEN+1)) ;;
    AMBER) AMBER=$((AMBER+1)) ;;
    RED)   RED=$((RED+1)) ;;
  esac
done
TOTAL=${#GATE_RESULTS[@]}

echo "  gates: ${GREEN}/${TOTAL} green   ${AMBER}/${TOTAL} amber   ${RED}/${TOTAL} red"
echo

for entry in "${GATE_RESULTS[@]}"; do
  name="$(printf '%s' "${entry}" | awk -F'|' '{print $1}')"
  res="$(printf '%s'  "${entry}" | awk -F'|' '{print $2}')"
  hint="$(printf '%s' "${entry}" | awk -F'|' '{print $3}')"
  case "${res}" in
    GREEN) printf "  ${G}✓${X} %-40s  ${D}%s${X}\n" "${name}" "${hint}" ;;
    AMBER) printf "  ${Y}~${X} %-40s  ${D}%s${X}\n" "${name}" "${hint}" ;;
    RED)   printf "  ${R}✗${X} %-40s  ${D}%s${X}\n" "${name}" "${hint}" ;;
  esac
done

echo

if [ "${RC_BAD}" = "1" ]; then
  printf "${R}=== BLOCK (rc=1) — do NOT run RELEASE-v10.0.command yet ===${X}\n\n"
  echo "Next steps:"
  echo "  1. Fix the failing gate(s) per the remediation pointers above."
  echo "  2. Re-run \`bash scripts/RELEASE-TAG-GUARD.command\`."
  echo "  3. Only when this script exits 0 PROCEED, type:"
  echo "       bash scripts/RELEASE-v10.0.command"
  echo
  exit 1
fi

if [ "${RC_PARTIAL}" = "1" ]; then
  printf "${Y}=== PARTIAL (rc=2) — some gates skipped ===${X}\n\n"
  echo "At least one gate could not be verified (gh missing, dry-run,"
  echo "or live skip). Treat as YELLOW: do NOT auto-run RELEASE-v10.0."
  echo "Re-run with the live dependencies present before tagging."
  echo
  exit 2
fi

# All 5 gates green.
printf "${G}=== PROCEED (rc=0) — safe to tag ${TAG_NAME} ===${X}\n\n"
echo "All 5 gates green. The exact next command is:"
echo
echo "    bash scripts/RELEASE-v10.0.command"
echo
echo "  (env defaults: RELEASE_v10_AUTO_PUSH=1, RELEASE_v10_DRY_RUN=0,"
echo "   RELEASE_v10_SKIP_VSCE=0 — override if needed)"
echo
echo "After RELEASE-v10.0 completes, the remaining cookbook steps are:"
echo "  1. Watch CI sign+notarize complete (auto)"
echo "  2. bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command   (Gate B)"
echo "  3. (operator) drag-install on clean Mac"
echo "  4. (operator) post launch comms"
echo "  5. At T+24h (optionally T+72h cron):"
echo "       bash scripts/BROTHER-POSTFLIGHT.command            (Postflight)"
echo
exit 0
