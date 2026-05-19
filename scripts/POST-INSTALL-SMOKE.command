#!/usr/bin/env bash
# POST-INSTALL-SMOKE.command — W310-al NINTH implementer follow-up.
#
# Bridges Step 8a → Step 8b of the v10.0.0 GA cookbook:
#   8a. Operator drag-installs the downloaded .dmg into /Applications/.
#   8b. THIS SCRIPT: machine-checkable "is the installed cockpit alive
#       and serving the expected GA version?" verdict.
#   9.  Post launch comms + GitHub Release publish (only if 8b PROCEED).
#   10. T+24-72h BROTHER-POSTFLIGHT.command (#220).
#
# Today the operator drag-installs and then either:
#   (a) eyeballs Activity Monitor / a browser tab on localhost:8765,
#   (b) double-clicks scripts/SMOKE-TEST.command and reads 50+ endpoint
#       rows looking for ✗ marks — terminal auto-closes after 5 s,
#       results land in .SMOKE-TEST.txt, no aggregate PROCEED/BLOCK,
#   (c) skips smoke entirely and starts SOAK-HOURLY cron, then
#       discovers 3 h later that the cockpit was dead and soak aborted.
#
# This wrapper produces ONE PROCEED / BLOCK / PARTIAL verdict so the
# operator never has to type a curl probe, eyeball Activity Monitor,
# or wait for SOAK-HOURLY to auto-abort on a dead process.
#
# Gates (worst-of-4):
#   Gate 1 — installed-app presence + version
#     /Applications/TARS.app exists AND its CFBundleShortVersionString
#     matches POST_INSTALL_SMOKE_EXPECTED_VERSION (default "10.0.0",
#     override for patch tags). Catches "operator drag-installed the
#     wrong .dmg" + "operator forgot to update Applications/".
#
#   Gate 2 — backend reachable
#     curl http://127.0.0.1:8765/api/health (POST_INSTALL_SMOKE_HOST
#     override). Retries 5× with 2 s sleep — cockpit may still be
#     warming up immediately after the operator clicks "Start" in
#     the desktop app.
#
#   Gate 3 — health payload sanity
#     /api/health JSON must contain "ok": true AND "service": "tars".
#     If POST_INSTALL_SMOKE_REQUIRE_MEEET=1 also asserts
#     "meeet_ingest": true (default 1 — GA expects meeet bridge wired).
#
#   Gate 4 — full smoke probe (optional, default ON)
#     Invokes scripts/SMOKE-TEST.command and parses its tee'd output
#     for "SMOKE TEST PASSED" / "SMOKE TEST FAILED" + the final
#     "N/M endpoints ok" line. Skip via POST_INSTALL_SMOKE_SKIP_FULL=1
#     when LLM creds / meeet token are not on the operator's machine
#     (downgrades verdict to PARTIAL, not BLOCK — refusing to silently
#     let a partial install look like a full green).
#
# Verdict aggregation:
#   any RED → rc=1 BLOCK + uninstall + investigate pointer
#   any AMBER (skip flag / version override / dry-run) + no RED → rc=2 PARTIAL
#   all GREEN → rc=0 PROCEED (safe to start SOAK-HOURLY cron)
#
# CRITICAL INVARIANT: DESTRUCTIVELY HARMLESS.
#   This script does NOT uninstall TARS.app, does NOT kill the backend
#   process, does NOT modify /Applications/, does NOT call
#   RELEASE-v10.0.command or any other destructive sibling. It only
#   READS the install state + probes localhost. The whole point is to
#   refuse to let the operator start the 72 h soak cron until the
#   install + backend + meeet bridge are all confirmed alive.
#
# Composes existing sibling: scripts/SMOKE-TEST.command (W271 endpoint
# smoke). Wrapper degrades gracefully if sibling missing (Gate 4 → AMBER
# instead of BLOCK so operator can still smoke-test on bare bash).
#
# Exit contract:
#   0 = all 4 gates green → PROCEED (safe to start SOAK-HOURLY cron)
#   1 = any gate red      → BLOCK (uninstall, investigate, do NOT soak)
#   2 = AMBER only        → PARTIAL (skip flags or dry-run; operator
#                          decides whether partial confidence is OK)
#
# Env overrides:
#   POST_INSTALL_SMOKE_DRY_RUN=1               stub Gates 2-4 green
#   POST_INSTALL_SMOKE_HOST=127.0.0.1:8765     backend host:port
#   POST_INSTALL_SMOKE_EXPECTED_VERSION=10.0.0 expected .app version
#   POST_INSTALL_SMOKE_SKIP_VERSION=1          dev-build override
#                                              (downgrade Gate 1 to AMBER)
#   POST_INSTALL_SMOKE_SKIP_FULL=1             skip full SMOKE-TEST
#                                              (downgrade Gate 4 to AMBER)
#   POST_INSTALL_SMOKE_REQUIRE_MEEET=1         assert meeet_ingest true
#                                              (default 1; set 0 to skip)
#   POST_INSTALL_SMOKE_HEALTH_RETRIES=5        Gate 2 retry count
#   POST_INSTALL_SMOKE_HEALTH_INTERVAL=2       Gate 2 retry sleep (s)
#   POST_INSTALL_SMOKE_APP_PATH=/Applications/TARS.app    .app location
#                                              override (test hook)
#   POST_INSTALL_SMOKE_REPO=<abs path>         override repo root for
#                                              sibling lookup (test hook)
#   POST_INSTALL_SMOKE_SKIP_PLATFORM=1         bypass Darwin guard for
#                                              CI smoke on Linux
#   POST_INSTALL_SMOKE_NO_COLOR=1              disable ANSI colors
#
# Hard deps:
#   - operator has drag-installed TARS.app into /Applications/ (Gate 1
#     fails otherwise — that IS the point)
#   - cockpit backend is running on the configured host:port (operator
#     clicked "Start" in the desktop app; Gate 2 retries cover warm-up)
#   - bash, curl on PATH
#   - scripts/SMOKE-TEST.command on disk for Gate 4 (graceful AMBER
#     fallback if missing)
#
# Sibling scripts (cookbook order):
#   pre-tag:        scripts/GA-COOKBOOK.command          (PR #218)
#   soak run:       scripts/SOAK-HOURLY.command          (PR #214)
#   soak report:    scripts/SOAK-REPORT.command          (PR #214)
#   tag decision:   scripts/RELEASE-TAG-GUARD.command    (PR #221)
#   release cut:    scripts/RELEASE-v10.0.command        (destructive)
#   download verify:scripts/DOWNLOAD-AND-VERIFY-RELEASE.command (PR #219)
#   ↓ this script slots in here ↓
#   post-install:   scripts/POST-INSTALL-SMOKE.command   (PR #222)
#   post-launch:    scripts/BROTHER-POSTFLIGHT.command   (PR #220)
#
# Closes the ninth ritual gap on the v10.0.0 GA path:
#   "did my drag-installed binary actually wake up + serve traffic +
#    talk to meeet ingest?"
# After this lands, that question reduces to:
#   "did POST-INSTALL-SMOKE.command exit 0?"

set -u

# ── color knobs ────────────────────────────────────────────────────────────
if [ -t 1 ] && [ -z "${POST_INSTALL_SMOKE_NO_COLOR:-}" ]; then
  G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; D=$'\033[2m'; B=$'\033[1m'; X=$'\033[0m'
else
  G=""; R=""; Y=""; D=""; B=""; X=""
fi

hdr() { printf "${B}── %s ──${X}\n" "$*"; }

# ── env defaults ───────────────────────────────────────────────────────────
DRY="${POST_INSTALL_SMOKE_DRY_RUN:-0}"
HOST="${POST_INSTALL_SMOKE_HOST:-127.0.0.1:8765}"
EXPECTED_VERSION="${POST_INSTALL_SMOKE_EXPECTED_VERSION:-10.0.0}"
SKIP_VERSION="${POST_INSTALL_SMOKE_SKIP_VERSION:-0}"
SKIP_FULL="${POST_INSTALL_SMOKE_SKIP_FULL:-0}"
REQUIRE_MEEET="${POST_INSTALL_SMOKE_REQUIRE_MEEET:-1}"
RETRIES="${POST_INSTALL_SMOKE_HEALTH_RETRIES:-5}"
INTERVAL="${POST_INSTALL_SMOKE_HEALTH_INTERVAL:-2}"
APP_PATH="${POST_INSTALL_SMOKE_APP_PATH:-/Applications/TARS.app}"
REPO_ROOT="${POST_INSTALL_SMOKE_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SKIP_PLATFORM="${POST_INSTALL_SMOKE_SKIP_PLATFORM:-0}"

# ── banner ─────────────────────────────────────────────────────────────────
printf "${B}=== POST-INSTALL-SMOKE — W310-al NINTH implementer follow-up ===${X}\n"
printf "${D}cookbook step 8b — installed-binary health verdict${X}\n"
printf "${D}host: ${HOST}  expected version: ${EXPECTED_VERSION}  app: ${APP_PATH}${X}\n"
[ "${DRY}" = "1" ] && printf "${Y}[dry-run] Gates 2-4 stubbed green${X}\n"
echo

# ── platform guard ─────────────────────────────────────────────────────────
if [ "${SKIP_PLATFORM}" != "1" ]; then
  if [ "$(uname -s)" != "Darwin" ]; then
    printf "${R}✗ this script is macOS-only (uname=$(uname -s))${X}\n"
    printf "  set POST_INSTALL_SMOKE_SKIP_PLATFORM=1 for CI smoke on Linux\n\n"
    printf "${R}=== BLOCK (rc=2) — wrong platform ===${X}\n"
    exit 2
  fi
fi

# Aggregation flags. RED beats AMBER beats GREEN.
RC_BAD=0     # any gate red → rc=1
RC_PARTIAL=0 # any gate amber → rc=2 if no red

# ── Gate 1 — installed-app presence + version ─────────────────────────────
hdr "Gate 1 — installed-app presence + version"
if [ "${DRY}" = "1" ]; then
  printf "  ${Y}⊘${X} dry-run: stubbing TARS.app version=${EXPECTED_VERSION}\n"
  RC_PARTIAL=1
elif [ ! -d "${APP_PATH}" ]; then
  printf "  ${R}✗${X} ${APP_PATH} not found\n"
  printf "    → drag the verified .dmg from DOWNLOAD-AND-VERIFY-RELEASE (#219)\n"
  printf "      into /Applications/, then re-run this script\n"
  RC_BAD=1
else
  if INSTALLED_VERSION=$(defaults read "${APP_PATH}/Contents/Info" CFBundleShortVersionString 2>/dev/null); then
    if [ "${SKIP_VERSION}" = "1" ]; then
      printf "  ${Y}⊘${X} version check skipped (installed=${INSTALLED_VERSION}, expected=${EXPECTED_VERSION})\n"
      RC_PARTIAL=1
    elif [ "${INSTALLED_VERSION}" = "${EXPECTED_VERSION}" ]; then
      printf "  ${G}✓${X} TARS.app installed (version ${INSTALLED_VERSION})\n"
    else
      printf "  ${R}✗${X} version mismatch: installed=${INSTALLED_VERSION} expected=${EXPECTED_VERSION}\n"
      printf "    → operator drag-installed wrong .dmg, or POST_INSTALL_SMOKE_EXPECTED_VERSION stale\n"
      printf "    → re-run scripts/DOWNLOAD-AND-VERIFY-RELEASE.command with correct RELEASE_TAG\n"
      RC_BAD=1
    fi
  else
    printf "  ${R}✗${X} cannot read CFBundleShortVersionString from ${APP_PATH}\n"
    printf "    → .app bundle structure may be corrupted; re-download via #219\n"
    RC_BAD=1
  fi
fi
echo

# ── Gate 2 — backend reachable ────────────────────────────────────────────
hdr "Gate 2 — backend reachable (${RETRIES} retries × ${INTERVAL}s)"
HEALTH_JSON=""
if [ "${DRY}" = "1" ]; then
  printf "  ${Y}⊘${X} dry-run: stubbing health payload\n"
  HEALTH_JSON='{"ok":true,"service":"tars","meeet_ingest":true,"uptime_s":42.0,"trace_id":"dry-run"}'
  RC_PARTIAL=1
else
  if ! command -v curl >/dev/null 2>&1; then
    printf "  ${R}✗${X} curl not on PATH\n"
    printf "    → brew install curl (macOS ships one; if missing, system is borked)\n"
    RC_BAD=1
  else
    REACHED=0
    for attempt in $(seq 1 "${RETRIES}"); do
      if HEALTH_JSON=$(curl -sS --connect-timeout 3 --max-time 5 "http://${HOST}/api/health" 2>/dev/null); then
        if [ -n "${HEALTH_JSON}" ]; then
          REACHED=1
          printf "  ${G}✓${X} backend reachable on attempt ${attempt}/${RETRIES}\n"
          break
        fi
      fi
      [ "${attempt}" -lt "${RETRIES}" ] && sleep "${INTERVAL}"
    done
    if [ "${REACHED}" = "0" ]; then
      printf "  ${R}✗${X} backend not reachable at http://${HOST}/api/health after ${RETRIES} attempts\n"
      printf "    → click 'Start' in TARS.app menubar, OR run: bash scripts/backend_tars_up.sh\n"
      printf "    → if backend dies on launch, see docs/handoff/PH11_QA_SWEEP_BRIEF.md §4 (soak hard-fail criteria)\n"
      RC_BAD=1
    fi
  fi
fi
echo

# ── Gate 3 — health payload sanity ────────────────────────────────────────
hdr "Gate 3 — health payload sanity (ok + service + meeet_ingest)"
if [ -z "${HEALTH_JSON}" ]; then
  printf "  ${Y}⊘${X} skipped (Gate 2 did not capture payload)\n"
  RC_PARTIAL=1
else
  PAYLOAD_OK=1
  if printf '%s' "${HEALTH_JSON}" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
    printf "  ${G}✓${X} payload contains \"ok\": true\n"
  else
    printf "  ${R}✗${X} payload missing \"ok\": true\n"
    printf "    → backend booted but rejected health check; inspect cockpit logs\n"
    PAYLOAD_OK=0
  fi
  if printf '%s' "${HEALTH_JSON}" | grep -q '"service"[[:space:]]*:[[:space:]]*"tars"'; then
    printf "  ${G}✓${X} payload contains \"service\": \"tars\"\n"
  else
    printf "  ${R}✗${X} payload missing \"service\": \"tars\" (wrong process listening on port?)\n"
    printf "    → another app is bound to ${HOST}; check with: lsof -i :${HOST##*:}\n"
    PAYLOAD_OK=0
  fi
  if [ "${REQUIRE_MEEET}" = "1" ]; then
    if printf '%s' "${HEALTH_JSON}" | grep -q '"meeet_ingest"[[:space:]]*:[[:space:]]*true'; then
      printf "  ${G}✓${X} payload contains \"meeet_ingest\": true\n"
    else
      printf "  ${R}✗${X} payload missing \"meeet_ingest\": true (MEEET_INGEST_URL not set in env)\n"
      printf "    → export MEEET_INGEST_URL, MEEET_API_KEY, MEEET_SOURCE before app launch\n"
      printf "    → OR set POST_INSTALL_SMOKE_REQUIRE_MEEET=0 if intentionally offline-only\n"
      PAYLOAD_OK=0
    fi
  else
    printf "  ${Y}⊘${X} meeet_ingest check skipped (REQUIRE_MEEET=0)\n"
    RC_PARTIAL=1
  fi
  [ "${PAYLOAD_OK}" = "0" ] && RC_BAD=1
fi
echo

# ── Gate 4 — full SMOKE-TEST probe ────────────────────────────────────────
hdr "Gate 4 — full SMOKE-TEST probe (sibling: scripts/SMOKE-TEST.command)"
SMOKE_SIBLING="${REPO_ROOT}/scripts/SMOKE-TEST.command"
if [ "${SKIP_FULL}" = "1" ]; then
  printf "  ${Y}⊘${X} full smoke skipped (POST_INSTALL_SMOKE_SKIP_FULL=1)\n"
  printf "    → 4 baseline routes from Gate 3 covered; LLM/meeet-token routes deferred\n"
  RC_PARTIAL=1
elif [ "${DRY}" = "1" ]; then
  printf "  ${Y}⊘${X} dry-run: stubbing SMOKE-TEST green (no sibling invocation)\n"
  RC_PARTIAL=1
elif [ ! -f "${SMOKE_SIBLING}" ]; then
  printf "  ${Y}⊘${X} sibling not found at ${SMOKE_SIBLING}\n"
  printf "    → graceful AMBER: Gates 1-3 still verified core install\n"
  printf "    → for full ~50-endpoint coverage, ensure scripts/SMOKE-TEST.command on PATH\n"
  RC_PARTIAL=1
elif [ ! -x "${SMOKE_SIBLING}" ]; then
  printf "  ${R}✗${X} sibling exists but not executable: ${SMOKE_SIBLING}\n"
  printf "    → chmod +x ${SMOKE_SIBLING}\n"
  RC_BAD=1
else
  # Capture sibling output; tolerate non-zero exit (we make our own verdict).
  SMOKE_OUT=$(bash "${SMOKE_SIBLING}" 2>&1 || true)
  if printf '%s\n' "${SMOKE_OUT}" | grep -q 'SMOKE TEST PASSED'; then
    SUMMARY_LINE=$(printf '%s\n' "${SMOKE_OUT}" | grep -E '^[[:space:]]+[0-9]+/[0-9]+ endpoints ok' | head -n1 | sed 's/^[[:space:]]*//')
    printf "  ${G}✓${X} SMOKE-TEST.command reported PASSED\n"
    [ -n "${SUMMARY_LINE}" ] && printf "    ${D}${SUMMARY_LINE}${X}\n"
  elif printf '%s\n' "${SMOKE_OUT}" | grep -q 'SMOKE TEST FAILED'; then
    SUMMARY_LINE=$(printf '%s\n' "${SMOKE_OUT}" | grep -E '^[[:space:]]+[0-9]+/[0-9]+ endpoints ok' | head -n1 | sed 's/^[[:space:]]*//')
    printf "  ${R}✗${X} SMOKE-TEST.command reported FAILED\n"
    [ -n "${SUMMARY_LINE}" ] && printf "    ${D}${SUMMARY_LINE}${X}\n"
    printf "    → see .SMOKE-TEST.txt for per-endpoint detail\n"
    printf "    → if only optional routes (vision OCR, magic-link) failed,\n"
    printf "      re-run with POST_INSTALL_SMOKE_SKIP_FULL=1 to downgrade to PARTIAL\n"
    RC_BAD=1
  elif printf '%s\n' "${SMOKE_OUT}" | grep -q 'ABORTED (backend down)'; then
    printf "  ${R}✗${X} SMOKE-TEST.command aborted — backend died between Gate 2 and Gate 4\n"
    printf "    → cockpit process exited; inspect ~/.tars/logs/ or syslog\n"
    RC_BAD=1
  else
    printf "  ${Y}⊘${X} SMOKE-TEST.command output had no recognised verdict (treating as AMBER)\n"
    printf "    → sibling may have been updated; review ${SMOKE_SIBLING}\n"
    RC_PARTIAL=1
  fi
fi
echo

# ── verdict summary ───────────────────────────────────────────────────────
hdr "verdict"
if [ "${RC_BAD}" = "1" ]; then
  printf "${R}=== BLOCK (rc=1) — do NOT start SOAK-HOURLY cron yet ===${X}\n\n"
  echo "Remediation:"
  echo "  1. Read the per-gate ✗ explanations above."
  echo "  2. If install is corrupted, uninstall TARS.app and re-download via:"
  echo "       bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command"
  echo "  3. If backend is dead, click 'Start' in TARS.app or run:"
  echo "       bash scripts/backend_tars_up.sh"
  echo "  4. If meeet bridge missing, export MEEET_INGEST_URL + MEEET_API_KEY"
  echo "     + MEEET_SOURCE before re-launching."
  echo "  5. Re-run this script. Soak cron must NOT start until rc=0."
  echo
  echo "Rollback decision tree if install repeatedly fails:"
  echo "  docs/handoff/PH4_APPLE_SIGN_V10_BRIEF.md §7 (A/B/C)"
  echo "  docs/handoff/PH11_QA_SWEEP_BRIEF.md §6 (post-launch playbook)"
  exit 1
fi

if [ "${RC_PARTIAL}" = "1" ]; then
  printf "${Y}=== PARTIAL (rc=2) — some gates skipped or dry-run ===${X}\n\n"
  echo "Cause (one of):"
  echo "  - POST_INSTALL_SMOKE_DRY_RUN=1 stubbed live gates"
  echo "  - POST_INSTALL_SMOKE_SKIP_VERSION=1 bypassed version check"
  echo "  - POST_INSTALL_SMOKE_SKIP_FULL=1 bypassed full SMOKE-TEST"
  echo "  - POST_INSTALL_SMOKE_REQUIRE_MEEET=0 bypassed meeet bridge check"
  echo "  - scripts/SMOKE-TEST.command missing (graceful AMBER fallback)"
  echo
  echo "Operator decision:"
  echo "  - For dev / offline-mode installs: PARTIAL is acceptable;"
  echo "    proceed to SOAK-HOURLY cron at your discretion."
  echo "  - For v10.0.0 GA tag: re-run WITHOUT skip flags. Soak should"
  echo "    only start when all 4 gates are GREEN (rc=0)."
  exit 2
fi

# All 4 gates green.
printf "${G}=== PROCEED (rc=0) — installed cockpit healthy at ${HOST} ===${X}\n\n"
echo "Next step: start the 72 h soak cron"
echo
echo "    bash scripts/SOAK-HOURLY.command   # one-shot (manual)"
echo
echo "Or schedule hourly via cron:"
echo
echo "    (crontab -l 2>/dev/null; \\"
echo "     echo \"0 * * * * cd $(cd "${REPO_ROOT}" && pwd) && bash scripts/SOAK-HOURLY.command >> .soak/cron.log 2>&1\") \\"
echo "       | crontab -"
echo
echo "After 72 h:"
echo "  1. bash scripts/SOAK-REPORT.command            # render verdict"
echo "  2. bash scripts/RELEASE-TAG-GUARD.command      # tag-cut decision (#221)"
echo "  3. if PROCEED: post launch comms + tag GitHub Release"
echo "  4. at T+24h: bash scripts/BROTHER-POSTFLIGHT.command   # coord health (#220)"
exit 0
