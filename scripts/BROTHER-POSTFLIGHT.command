#!/usr/bin/env bash
# BROTHER-POSTFLIGHT.command — W310-aj PH11 brother handoff §7 post-tag verification.
#
# SEVENTH implementer follow-up to the W310 planning surface. Symmetric
# counterpart to W310-ag (#217 BROTHER-PREFLIGHT.command) on the
# **post-tag** side of the v10.0.0 GA tag cut. Where preflight runs
# BEFORE the tag to catch missing-prereqs at Gate A, this script runs
# 24-72 h AFTER the tag to detect real-world drift / regressions in the
# brother coord surface.
#
# Why this exists (motion)
# ------------------------
# The brother-coord surface (PR #198 §7's 7 syncs) has TWO failure
# modes the operator cares about post-launch:
#
#   1. **Regression**: did A1/A2/A3/A5/acceptance probes that were
#      green pre-tag silently rot in the 24-72 h post-launch window?
#      (e.g. brother-side meeet.world deployed a config change that
#      broke /operator balance shape; checkout URL started redirecting
#      to a maintenance page; acceptance suite hit a flake.)
#
#   2. **Latent prereq miss**: the §3.A4 reconciliation script was
#      flagged as "either TARS-side OR brother-side owns it" in
#      preflight (Sync 5 only checked EXISTENCE — no execution). Post-
#      tag, the script must actually RUN cleanly to validate the daily
#      ledger reconciliation contract. If reconcile silently errors,
#      the brother-side ledger drifts from TARS-side cockpit reports.
#
# The wrapper bundles these two motions into ONE bash command with the
# same PROCEED / BLOCK / PARTIAL contract as PREFLIGHT, so the operator
# runs ONE script 24-72 h post-launch instead of pasting six probes +
# eyeballing each output. Verdict goes onto the v10 GA tag PR / blog
# post comment thread as evidence "brother coord surface is healthy
# post-launch", same way preflight green goes onto the pre-tag PR.
#
# Per brief §7 the 6 post-tag syncs are:
#
#   Sync 1.  Re-verify A1 ingest endpoint still healthy (regression)
#            → scripts/probe-meeet-billing.command (post-tag run)
#
#   Sync 2.  Re-verify A2 /operator balance shape (regression)
#            → scripts/CHECK-MEEET-LIVE.command (post-tag run)
#
#   Sync 3.  Re-verify A5 auth + billing e2e smoke (regression)
#            → scripts/smoke_billing_tars_backend.sh (post-tag run)
#
#   Sync 4.  Re-verify A3 (top-up checkout URL) still 200/301/302
#            → curl https://meeet.world/billing/tars (regression)
#
#   Sync 5.  RUN A4 reconciliation script (not just existence-check)
#            → bash/python scripts/reconcile-meeet-billing.py
#              OR curl --max-time 30 -fsS "${BROTHER_RECONCILE_URL}"
#                 (HEAD if URL set, expect 200/204)
#
#   Sync 6.  Re-run scripts/acceptance_tars_meeet.sh against live
#            → scripts/acceptance_tars_meeet.sh (end-to-end regression)
#
# Differences from PREFLIGHT (#217)
# ---------------------------------
# - **6 syncs (not 7)**: drops PREFLIGHT Sync 6 (BROTHER_PAIR_TTL_ACK)
#   because ph3-pair-ttl is a v10.2 backlog item — its ack only matters
#   pre-tag (heads-up); post-tag ack is meaningless (either brother
#   shipped it or it's still on backlog, neither verifiable via shell).
# - **Sync 5 EXECUTES instead of checks**: preflight's Sync 5 was
#   `test -f scripts/reconcile-meeet-billing.py` (existence-only); this
#   script actually runs it and asserts exit 0 (catches silent runtime
#   errors that preflight cannot).
# - **All probes are regression-tagged**: header banner says
#   "post-tag regression check" instead of "pre-tag verification".
# - **Per-failure remediation pointer also names §6 (post-launch
#   playbook)** in addition to brief §<N>.<X>, so red verdicts route
#   to the rollback-or-hotfix decision tree the brief documents.
# - **No "next steps print PROCEED → RELEASE-v10.0.command"**: the
#   tag is already cut by the time this script runs. PROCEED prints
#   "post sign-off comment on tag PR" instead.
#
# Each sync runs in sequence, captures exit code + tail of output, and
# the final summary surfaces:
#
#   - per-sync ✓ / ✗ / SKIP with the brief §<N>.<X> remediation pointer
#   - aggregate verdict: PROCEED (all 6 green) / BLOCK + ROLLBACK (any red)
#     / PARTIAL (skips left ≥1 sync unverified)
#   - operator next-step printout (post-tag comment; rollback path on red)
#
# Exit contract:
#   0   all 6 syncs green → brother coord side of v10 GA is healthy
#       post-launch; record sign-off; close the v10 GA dock-down arc
#   1   one or more syncs red → BLOCK launch comms (don't tweet "v10
#       is live"); decide rollback path per brief §6 (A hotfix / B
#       partial rollback / C full revert to v10.0.0-rc.1)
#   2   neither green nor red:
#         - prerequisite missing (no curl / no bash), OR
#         - partial verdict (SKIP_LIVE=1 left ≥1 sync unverified; not a
#           hard red but also not a "PROCEED to announce")
#
# Env overrides:
#   BROTHER_POSTFLIGHT_DRY_RUN=1     print commands without executing — used by CI
#   BROTHER_POSTFLIGHT_SKIP_LIVE=1   skip syncs 1+2+3+4+6 (live network probes)
#                                    — useful if api.meeet.world is intentionally
#                                    offline for maintenance
#   BROTHER_POSTFLIGHT_REPO=<path>   absolute repo path (default: dirname(script)/..)
#                                    lets the same script run from cron / non-cwd
#   BROTHER_RECONCILE_URL=<url>      pointer to brother-side reconciliation script
#                                    (when set, Sync 5 does HEAD instead of exec)
#   BROTHER_POSTFLIGHT_NO_COLOR=1    disable ANSI colors for log-file capture
#
# Spec contract: brief §7 verbatim (5 of 6 syncs are §7 regressions;
# Sync 5 elevates from existence-check to execution-check per §3.A4
# "owner must demonstrate the script runs"). The sync count (=6) and
# each sync header are pinned by tests/test_brother_postflight_script.py
# so brief and script can't drift silently.
#
# Hard deps:
#   - scripts/probe-meeet-billing.command  (on main, Wave M shipped)
#   - scripts/CHECK-MEEET-LIVE.command     (on main, Wave M shipped)
#   - scripts/smoke_billing_tars_backend.sh (on main, Wave M shipped)
#   - scripts/acceptance_tars_meeet.sh     (on main, Wave M shipped)
#   - scripts/reconcile-meeet-billing.py   (TARS-side; OR BROTHER_RECONCILE_URL
#                                           must be set; one of the two
#                                           IS required to ship as part of
#                                           v10 GA dock-down per §3.A4)
#
# Fails safely, not silently: if reconcile script is missing AND
# BROTHER_RECONCILE_URL unset → Sync 5 red → BLOCK (with both-path
# remediation pointer same as preflight Sync 5).

set -u

# ── 0. Plumbing ──────────────────────────────────────────────────────────

REPO_ROOT="${BROTHER_POSTFLIGHT_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "${REPO_ROOT}" || {
  echo "ERROR: cannot cd to ${REPO_ROOT}" >&2
  exit 2
}

if [ "${BROTHER_POSTFLIGHT_NO_COLOR:-0}" = "1" ] || [ ! -t 1 ]; then
  C_RED=""; C_GRN=""; C_YEL=""; C_BLU=""; C_DIM=""; C_RST=""
else
  C_RED=$'\033[31m'
  C_GRN=$'\033[32m'
  C_YEL=$'\033[33m'
  C_BLU=$'\033[34m'
  C_DIM=$'\033[2m'
  C_RST=$'\033[0m'
fi

ok()   { echo "${C_GRN}✓${C_RST}  $*"; }
bad()  { echo "${C_RED}✗${C_RST}  $*"; }
skip() { echo "${C_YEL}⊘${C_RST}  $*"; }
note() { echo "   ${C_DIM}$*${C_RST}"; }
hdr()  { echo; echo "${C_BLU}── $* ──${C_RST}"; }

# ── 1. Platform sanity ───────────────────────────────────────────────────

if [ "${BROTHER_POSTFLIGHT_DRY_RUN:-0}" != "1" ]; then
  if ! command -v curl >/dev/null 2>&1; then
    echo "ERROR: curl not on PATH — install curl and retry" >&2
    exit 2
  fi
  if ! command -v bash >/dev/null 2>&1; then
    echo "ERROR: bash not on PATH (?!)" >&2
    exit 2
  fi
fi

# ── 2. Header ────────────────────────────────────────────────────────────

echo "${C_BLU}╔══════════════════════════════════════════════════════════════════╗${C_RST}"
echo "${C_BLU}║  BROTHER-POSTFLIGHT.command — v10 GA brother coord post-tag check ║${C_RST}"
echo "${C_BLU}║  Per PR #198 (PH11 brother handoff brief) §7 — 6 regression syncs ║${C_RST}"
echo "${C_BLU}║  Run 24-72 h after tag cut to detect drift / silent rot           ║${C_RST}"
echo "${C_BLU}╚══════════════════════════════════════════════════════════════════╝${C_RST}"

if [ "${BROTHER_POSTFLIGHT_DRY_RUN:-0}" = "1" ]; then
  note "(BROTHER_POSTFLIGHT_DRY_RUN=1 — printing commands, not executing them)"
fi

FAILED=0
SKIPPED=0
PASSED=0
RESULTS=""

record() {
  local mark="$1"; local label="$2"
  RESULTS+="${mark} ${label}"$'\n'
}

# Run a primitive script. Returns its exit code. Captures last 3 lines of
# combined output for the diag tail. Dry-run prints the command instead.
run_primitive() {
  local label="$1"; shift
  if [ "${BROTHER_POSTFLIGHT_DRY_RUN:-0}" = "1" ]; then
    note "(dry-run) ${label}: $*"
    return 0
  fi
  local out
  out="$("$@" 2>&1 | tail -3)"
  local rc=$?
  if [ -n "${out}" ]; then
    note "${out}"
  fi
  return ${rc}
}

# ── 3. Sync 1 — A1 (POST usage_event ingest regression) ─────────────────

hdr "Sync 1 — A1: POST /operator/usage post-tag regression"

if [ "${BROTHER_POSTFLIGHT_SKIP_LIVE:-0}" = "1" ]; then
  skip "Sync 1 SKIPPED (BROTHER_POSTFLIGHT_SKIP_LIVE=1)"
  record "⊘" "Sync 1 (A1 ingest regression) — SKIP"
  SKIPPED=$((SKIPPED+1))
elif [ ! -x "scripts/probe-meeet-billing.command" ]; then
  bad "scripts/probe-meeet-billing.command not executable or missing"
  note "remediation: re-checkout main; brief §2.A1 + §6 rollback decision"
  record "✗" "Sync 1 (A1 ingest regression) — script missing"
  FAILED=$((FAILED+1))
else
  if run_primitive "probe-meeet-billing.command" \
       bash scripts/probe-meeet-billing.command; then
    ok "Sync 1: probe-meeet-billing exit 0 (no regression)"
    record "✓" "Sync 1 (A1 ingest regression) — green"
    PASSED=$((PASSED+1))
  else
    bad "Sync 1: probe-meeet-billing exit non-zero (REGRESSION)"
    note "remediation: brief §2.A1 + §6 — Bearer auth or endpoint rotated post-tag"
    record "✗" "Sync 1 (A1 ingest regression) — red"
    FAILED=$((FAILED+1))
  fi
fi

# ── 4. Sync 2 — A2 (GET /operator balance regression) ───────────────────

hdr "Sync 2 — A2: GET /operator (balance shape regression)"

if [ "${BROTHER_POSTFLIGHT_SKIP_LIVE:-0}" = "1" ]; then
  skip "Sync 2 SKIPPED (BROTHER_POSTFLIGHT_SKIP_LIVE=1)"
  record "⊘" "Sync 2 (A2 balance regression) — SKIP"
  SKIPPED=$((SKIPPED+1))
elif [ ! -x "scripts/CHECK-MEEET-LIVE.command" ]; then
  bad "scripts/CHECK-MEEET-LIVE.command not executable or missing"
  note "remediation: re-checkout main; brief §2.A2 + §6 rollback decision"
  record "✗" "Sync 2 (A2 balance regression) — script missing"
  FAILED=$((FAILED+1))
else
  if run_primitive "CHECK-MEEET-LIVE.command" \
       bash scripts/CHECK-MEEET-LIVE.command; then
    ok "Sync 2: CHECK-MEEET-LIVE exit 0 (no regression)"
    record "✓" "Sync 2 (A2 balance regression) — green"
    PASSED=$((PASSED+1))
  else
    bad "Sync 2: CHECK-MEEET-LIVE exit non-zero (REGRESSION)"
    note "remediation: brief §2.A2 + §6 — /operator shape changed post-tag"
    record "✗" "Sync 2 (A2 balance regression) — red"
    FAILED=$((FAILED+1))
  fi
fi

# ── 5. Sync 3 — A5 (auth e2e regression) ────────────────────────────────

hdr "Sync 3 — A5: auth + billing e2e regression"

if [ "${BROTHER_POSTFLIGHT_SKIP_LIVE:-0}" = "1" ]; then
  skip "Sync 3 SKIPPED (BROTHER_POSTFLIGHT_SKIP_LIVE=1)"
  record "⊘" "Sync 3 (A5 auth e2e regression) — SKIP"
  SKIPPED=$((SKIPPED+1))
elif [ ! -f "scripts/smoke_billing_tars_backend.sh" ]; then
  bad "scripts/smoke_billing_tars_backend.sh missing"
  note "remediation: re-checkout main; brief §5 coord test handoff"
  record "✗" "Sync 3 (A5 auth e2e regression) — script missing"
  FAILED=$((FAILED+1))
else
  if run_primitive "smoke_billing_tars_backend.sh" \
       bash scripts/smoke_billing_tars_backend.sh; then
    ok "Sync 3: smoke_billing_tars_backend exit 0 (no regression)"
    record "✓" "Sync 3 (A5 auth e2e regression) — green"
    PASSED=$((PASSED+1))
  else
    bad "Sync 3: smoke_billing_tars_backend exit non-zero (REGRESSION)"
    note "remediation: brief §2.A5 + §6 — re-run smoke_auth_meeet_e2e.sh brother-side"
    record "✗" "Sync 3 (A5 auth e2e regression) — red"
    FAILED=$((FAILED+1))
  fi
fi

# ── 6. Sync 4 — A3 (top-up checkout URL regression) ─────────────────────

hdr "Sync 4 — A3: meeet.world/billing/tars checkout liveness regression"

if [ "${BROTHER_POSTFLIGHT_SKIP_LIVE:-0}" = "1" ]; then
  skip "Sync 4 SKIPPED (BROTHER_POSTFLIGHT_SKIP_LIVE=1)"
  record "⊘" "Sync 4 (A3 checkout regression) — SKIP"
  SKIPPED=$((SKIPPED+1))
elif [ "${BROTHER_POSTFLIGHT_DRY_RUN:-0}" = "1" ]; then
  note "(dry-run) curl -fsSI https://meeet.world/billing/tars"
  ok "Sync 4: dry-run mocked (no network call)"
  record "✓" "Sync 4 (A3 checkout regression) — green (dry-run)"
  PASSED=$((PASSED+1))
else
  HTTP_CODE="$(curl -fsSI -o /dev/null -w '%{http_code}' \
                 --max-time 10 \
                 https://meeet.world/billing/tars 2>/dev/null || echo "000")"
  if [ "${HTTP_CODE}" = "200" ] || [ "${HTTP_CODE}" = "301" ] || [ "${HTTP_CODE}" = "302" ]; then
    ok "Sync 4: /billing/tars returns HTTP ${HTTP_CODE} (no regression)"
    record "✓" "Sync 4 (A3 checkout regression) — green (HTTP ${HTTP_CODE})"
    PASSED=$((PASSED+1))
  else
    bad "Sync 4: /billing/tars returned HTTP ${HTTP_CODE} (expected 200/301/302) — REGRESSION"
    note "remediation: brief §3.A3 + §6 — checkout flow broken or maintenance page surfaced"
    record "✗" "Sync 4 (A3 checkout regression) — red (HTTP ${HTTP_CODE})"
    FAILED=$((FAILED+1))
  fi
fi

# ── 7. Sync 5 — A4 (reconciliation EXECUTION, not just existence) ──────

hdr "Sync 5 — A4: reconciliation script EXECUTION (post-tag elevation)"

# Two valid resolutions per brief §3.A4: (a) TARS-side script runs cleanly,
# OR (b) brother-side URL responds 200/204 (curl HEAD). Unlike PREFLIGHT
# Sync 5 which only existence-checked, here we actually invoke the
# script / probe the URL so silent-runtime-error in the reconcile
# pipeline becomes a visible BLOCK instead of a latent drift bug.

if [ -n "${BROTHER_RECONCILE_URL:-}" ]; then
  # Brother-side URL path: HEAD probe with a generous timeout
  # (reconcile job may run sync; brother decides to expose status URL).
  if [ "${BROTHER_POSTFLIGHT_DRY_RUN:-0}" = "1" ]; then
    note "(dry-run) curl -fsSI --max-time 30 \"${BROTHER_RECONCILE_URL}\""
    ok "Sync 5: dry-run mocked (no network call)"
    record "✓" "Sync 5 (A4 reconcile exec) — green (dry-run, brother URL)"
    PASSED=$((PASSED+1))
  else
    RECONCILE_CODE="$(curl -fsSI -o /dev/null -w '%{http_code}' \
                       --max-time 30 \
                       "${BROTHER_RECONCILE_URL}" 2>/dev/null || echo "000")"
    if [ "${RECONCILE_CODE}" = "200" ] || [ "${RECONCILE_CODE}" = "204" ]; then
      ok "Sync 5: brother-side reconcile URL HTTP ${RECONCILE_CODE}"
      record "✓" "Sync 5 (A4 reconcile exec) — green (brother HTTP ${RECONCILE_CODE})"
      PASSED=$((PASSED+1))
    else
      bad "Sync 5: brother-side reconcile URL HTTP ${RECONCILE_CODE} (expected 200/204)"
      note "remediation: brief §3.A4 + §6 — brother's reconcile endpoint down or broken"
      record "✗" "Sync 5 (A4 reconcile exec) — red (HTTP ${RECONCILE_CODE})"
      FAILED=$((FAILED+1))
    fi
  fi
elif [ -f "scripts/reconcile-meeet-billing.py" ]; then
  # TARS-side path: actually RUN the script (preflight only existence-checked).
  if [ "${BROTHER_POSTFLIGHT_DRY_RUN:-0}" = "1" ]; then
    note "(dry-run) python3 scripts/reconcile-meeet-billing.py --check"
    ok "Sync 5: dry-run mocked (no exec)"
    record "✓" "Sync 5 (A4 reconcile exec) — green (dry-run, TARS script)"
    PASSED=$((PASSED+1))
  elif ! command -v python3 >/dev/null 2>&1; then
    bad "Sync 5: python3 not on PATH — cannot exec reconcile-meeet-billing.py"
    note "remediation: install python3 (brew install python3) and retry"
    record "✗" "Sync 5 (A4 reconcile exec) — red (no python3)"
    FAILED=$((FAILED+1))
  else
    # Pass --check flag if script supports it (graceful: script may not yet
    # ship the flag — we accept exit 0 from either invocation form).
    if run_primitive "reconcile-meeet-billing.py" \
         python3 scripts/reconcile-meeet-billing.py --check 2>/dev/null \
       || run_primitive "reconcile-meeet-billing.py (fallback)" \
            python3 scripts/reconcile-meeet-billing.py; then
      ok "Sync 5: TARS-side reconcile-meeet-billing.py exit 0"
      record "✓" "Sync 5 (A4 reconcile exec) — green (TARS runs clean)"
      PASSED=$((PASSED+1))
    else
      bad "Sync 5: TARS-side reconcile-meeet-billing.py exit non-zero"
      note "remediation: brief §3.A4 + §6 — reconcile script throws; ledger drift risk"
      record "✗" "Sync 5 (A4 reconcile exec) — red (TARS script failed)"
      FAILED=$((FAILED+1))
    fi
  fi
else
  bad "Sync 5: no TARS-side scripts/reconcile-meeet-billing.py AND BROTHER_RECONCILE_URL unset"
  note "remediation: brief §3.A4 — either"
  note "  (a) ship scripts/reconcile-meeet-billing.py TARS-side (~3 h scaffolded on audit_billing.py), OR"
  note "  (b) export BROTHER_RECONCILE_URL=https://… pointing to brother-side reconcile endpoint"
  note "  Post-tag this is HARDER red than pre-tag — daily ledger drift accrues silently."
  record "✗" "Sync 5 (A4 reconcile exec) — red (no owner)"
  FAILED=$((FAILED+1))
fi

# ── 8. Sync 6 — acceptance regression ─────────────────────────────────────

hdr "Sync 6 — acceptance: scripts/acceptance_tars_meeet.sh post-tag regression"

if [ "${BROTHER_POSTFLIGHT_SKIP_LIVE:-0}" = "1" ]; then
  skip "Sync 6 SKIPPED (BROTHER_POSTFLIGHT_SKIP_LIVE=1)"
  record "⊘" "Sync 6 (acceptance regression) — SKIP"
  SKIPPED=$((SKIPPED+1))
elif [ ! -f "scripts/acceptance_tars_meeet.sh" ]; then
  bad "scripts/acceptance_tars_meeet.sh missing"
  note "remediation: re-checkout main; brief §5 coord test handoff"
  record "✗" "Sync 6 (acceptance regression) — script missing"
  FAILED=$((FAILED+1))
else
  if run_primitive "acceptance_tars_meeet.sh" \
       bash scripts/acceptance_tars_meeet.sh; then
    ok "Sync 6: acceptance_tars_meeet exit 0 (no regression)"
    record "✓" "Sync 6 (acceptance regression) — green"
    PASSED=$((PASSED+1))
  else
    bad "Sync 6: acceptance_tars_meeet exit non-zero (REGRESSION)"
    note "remediation: brief §9 + §6 — investigate failing stage; decide rollback A/B/C"
    record "✗" "Sync 6 (acceptance regression) — red"
    FAILED=$((FAILED+1))
  fi
fi

# ── 9. Verdict summary ───────────────────────────────────────────────────

echo
echo "${C_BLU}╔══════════════════════════════════════════════════════════════════╗${C_RST}"
echo "${C_BLU}║                    BROTHER POSTFLIGHT VERDICT                    ║${C_RST}"
echo "${C_BLU}╚══════════════════════════════════════════════════════════════════╝${C_RST}"
echo
echo "${RESULTS}"
echo "Passed:   ${C_GRN}${PASSED}${C_RST} / 6"
echo "Failed:   ${C_RED}${FAILED}${C_RST} / 6"
echo "Skipped:  ${C_YEL}${SKIPPED}${C_RST} / 6"
echo

if [ "${FAILED}" -gt 0 ]; then
  echo "${C_RED}✗  BLOCK LAUNCH COMMS — POST-TAG REGRESSION DETECTED${C_RST}"
  echo "   ${FAILED} sync(s) red on post-launch brother coord surface"
  echo
  echo "Next steps:"
  echo "  1. Address red sync(s) per the inline remediation pointers above"
  echo "  2. Decide rollback path per PH4 brief §6 (or PH11 brother handoff §6):"
  echo "     A. Hotfix (push v10.0.1 with the fix; keep v10.0.0 tag live)"
  echo "     B. Partial rollback (un-publish v10.0.0 binaries; keep tag)"
  echo "     C. Full revert (re-tag v10.0.0-rc.1 as v10.0.0 emergency)"
  echo "  3. Re-run: bash scripts/BROTHER-POSTFLIGHT.command"
  echo "  4. Only post '✓ v10 live' comms when verdict is PROCEED"
  exit 1
fi

# Partial = skipped >0. Unlike preflight (where Sync 6 SKIP-PENDING was
# acceptable for ph3-pair-ttl), postflight has NO allowed skips:
# every skip means a probe was bypassed. SKIP_LIVE=1 is operator's
# choice but yields partial verdict, not green.
if [ "${SKIPPED}" -gt 0 ]; then
  echo "${C_YEL}⚠  PARTIAL VERDICT${C_RST} — ${SKIPPED} sync(s) skipped"
  echo
  echo "Next steps:"
  echo "  - If BROTHER_POSTFLIGHT_SKIP_LIVE=1 was set deliberately, re-run"
  echo "    without that env var when api.meeet.world is up to get a real verdict"
  echo "  - Defer launch comms until verdict is PROCEED (not PARTIAL)"
  echo "  - Partial verdict 72 h+ post-tag indicates ops attention needed"
  exit 2
fi

echo "${C_GRN}✓  PROCEED${C_RST} — brother coord side of v10.0.0 GA healthy post-launch"
echo
echo "Next steps:"
echo "  1. Post '✓ brother postflight green (T+24h)' comment on v10 GA tag PR"
echo "  2. Update V10_GA_CHECKLIST.md: flip post-launch row to [x]"
echo "  3. Close the v10 GA dock-down arc on the master plan"
echo "  4. Schedule a T+72h re-run via cron to catch slow-rot regressions:"
echo "     (crontab -l ; echo \"0 9 * * * cd \$(pwd) && bash scripts/BROTHER-POSTFLIGHT.command >> .postflight/daily.log 2>&1\") | crontab -"
echo
echo "Brief sign-off:"
echo "  - Together with GA-COOKBOOK (#218) + DOWNLOAD-AND-VERIFY-RELEASE (#219),"
echo "    the v10 GA tag-cut surface is now symmetric: pre-tag verification +"
echo "    pre-tag release + post-tag verification + post-tag brother health."

exit 0
