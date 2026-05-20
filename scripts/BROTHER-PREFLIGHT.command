#!/usr/bin/env bash
# BROTHER-PREFLIGHT.command — W310-ag PH11 brother handoff §7 helper.
#
# Implementer follow-up to PR #198 (PH11 v10.0.0 brother handoff brief).
# Aggregates the existing probe primitives into ONE script the operator
# runs to verify the 7 §7 syncs in a single pass. Same motion as
# PREFLIGHT-APPLE-SIGN: bundle existing primitives into one command so
# the "remembered ritual" (paste five separate probe invocations and
# eyeball each one) collapses into "one bash command, colored verdict".
#
# Per brief §7 the 7 syncs are:
#
#   Sync 1.  Confirm A1 endpoint path + auth scheme
#            → scripts/probe-meeet-billing.command (idempotent usage event)
#
#   Sync 2.  Confirm A2 endpoint path + balance value parity
#            → scripts/CHECK-MEEET-LIVE.command (GET /operator shape)
#
#   Sync 3.  Re-run A5 auth e2e smoke
#            → scripts/smoke_billing_tars_backend.sh (combined billing + auth)
#
#   Sync 4.  Confirm A3 (top-up via checkout URL) lives at /billing/tars
#            → curl https://meeet.world/billing/tars (expect HTTP 200)
#
#   Sync 5.  Confirm A4 reconciliation script ownership
#            → existence check: scripts/reconcile-meeet-billing.py
#              OR brother-side equivalent URL (recorded in .env as
#              BROTHER_RECONCILE_URL — see §5 of this header).
#
#   Sync 6.  Acknowledge ph3-pair-ttl ownership for v10.2
#            → manual sign-off via BROTHER_PAIR_TTL_ACK=yes env var
#              (operator records brother's verbal confirmation here).
#
#   Sync 7.  Run scripts/acceptance_tars_meeet.sh against live
#            → scripts/acceptance_tars_meeet.sh
#
# Each sync runs in sequence, captures exit code + tail of output, and
# the final summary surfaces:
#
#   - per-sync ✓ / ✗ / SKIP with the brief §<N>.<X> remediation pointer
#   - aggregate verdict: PROCEED (all 7 green) / BLOCK GA TAG (any red)
#   - operator next-step printout (e.g. "post sign-off comment on #tars-coord")
#
# Exit contract:
#   0   all 7 syncs green → brother coord side of v10 GA dock-down is clear
#   1   one or more syncs red → block GA tag cut; remediation per brief §<N>.<X>
#   2   neither green nor red:
#         - prerequisite missing (no curl / no bash), OR
#         - partial verdict (SKIP_LIVE=1 left ≥1 sync unverified; not a hard red
#           but also not a "PROCEED to tag")
#
# Env overrides:
#   BROTHER_PREFLIGHT_DRY_RUN=1     print commands without executing — used by CI
#   BROTHER_PREFLIGHT_SKIP_LIVE=1   skip syncs 1+2+3+7 (live network probes) — useful
#                                   if api.meeet.world is intentionally offline
#   BROTHER_PREFLIGHT_REPO=<path>   absolute repo path (default: dirname(script)/..)
#                                   lets the same script run from cron / non-cwd
#   BROTHER_RECONCILE_URL=<url>     pointer to brother-side reconciliation script
#                                   (when set, Sync 5 passes without TARS-side file)
#   BROTHER_PAIR_TTL_ACK=yes        operator records §6 verbal sign-off (default unset
#                                   → Sync 6 reports SKIP-PENDING, not a hard red)
#   BROTHER_PREFLIGHT_NO_COLOR=1    disable ANSI colors for log-file capture
#
# Spec contract: brief §7 verbatim. Each sync number in §7 maps to the
# SYNC_N=... block below. Brief and script can't drift silently because
# tests/test_brother_preflight_script.py pins both the sync count (=7)
# and the headers verbatim.

set -u

# --- 0. Plumbing -----------------------------------------------------------

REPO_ROOT="${BROTHER_PREFLIGHT_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "${REPO_ROOT}" || {
  echo "ERROR: cannot cd to ${REPO_ROOT}" >&2
  exit 2
}

if [ "${BROTHER_PREFLIGHT_NO_COLOR:-0}" = "1" ] || [ ! -t 1 ]; then
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

# --- 1. Platform sanity ---------------------------------------------------

if [ "${BROTHER_PREFLIGHT_DRY_RUN:-0}" != "1" ]; then
  if ! command -v curl >/dev/null 2>&1; then
    echo "ERROR: curl not on PATH — install curl and retry" >&2
    exit 2
  fi
  if ! command -v bash >/dev/null 2>&1; then
    echo "ERROR: bash not on PATH (?!)" >&2
    exit 2
  fi
fi

# --- 2. Header ------------------------------------------------------------

echo "${C_BLU}╔══════════════════════════════════════════════════════════════════╗${C_RST}"
echo "${C_BLU}║   BROTHER-PREFLIGHT.command — v10 GA brother coord verification  ║${C_RST}"
echo "${C_BLU}║   Per PR #198 (PH11 brother handoff brief) §7 — 7 syncs total    ║${C_RST}"
echo "${C_BLU}╚══════════════════════════════════════════════════════════════════╝${C_RST}"

if [ "${BROTHER_PREFLIGHT_DRY_RUN:-0}" = "1" ]; then
  note "(BROTHER_PREFLIGHT_DRY_RUN=1 — printing commands, not executing them)"
fi

# Track verdict
FAILED=0
SKIPPED=0
PASSED=0
RESULTS=""

# Append a one-line result row to RESULTS for the final summary
record() {
  local mark="$1"; local label="$2"
  RESULTS+="${mark} ${label}"$'\n'
}

# Run a primitive script. Returns its exit code. Captures last 3 lines of
# combined output for the diag tail. Dry-run prints the command instead.
run_primitive() {
  local label="$1"; shift
  if [ "${BROTHER_PREFLIGHT_DRY_RUN:-0}" = "1" ]; then
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

# --- 3. Sync 1 — A1 (POST usage_event idempotency) ------------------------

hdr "Sync 1 — A1: POST /operator/usage (idempotent ingest)"

if [ "${BROTHER_PREFLIGHT_SKIP_LIVE:-0}" = "1" ]; then
  skip "Sync 1 SKIPPED (BROTHER_PREFLIGHT_SKIP_LIVE=1)"
  record "⊘" "Sync 1 (A1 ingest) — SKIP"
  SKIPPED=$((SKIPPED+1))
elif [ ! -x "scripts/probe-meeet-billing.command" ]; then
  bad "scripts/probe-meeet-billing.command not executable or missing"
  note "remediation: re-checkout main; brief §2.A1 smoke probe block"
  record "✗" "Sync 1 (A1 ingest) — script missing"
  FAILED=$((FAILED+1))
else
  if run_primitive "probe-meeet-billing.command" \
       bash scripts/probe-meeet-billing.command; then
    ok "Sync 1: probe-meeet-billing exit 0"
    record "✓" "Sync 1 (A1 ingest) — green"
    PASSED=$((PASSED+1))
  else
    bad "Sync 1: probe-meeet-billing exit non-zero"
    note "remediation: brief §2.A1 — confirm endpoint path + Bearer auth + idempotency"
    record "✗" "Sync 1 (A1 ingest) — red"
    FAILED=$((FAILED+1))
  fi
fi

# --- 4. Sync 2 — A2 (GET /operator balance shape) -------------------------

hdr "Sync 2 — A2: GET /operator (balance parity)"

if [ "${BROTHER_PREFLIGHT_SKIP_LIVE:-0}" = "1" ]; then
  skip "Sync 2 SKIPPED (BROTHER_PREFLIGHT_SKIP_LIVE=1)"
  record "⊘" "Sync 2 (A2 balance) — SKIP"
  SKIPPED=$((SKIPPED+1))
elif [ ! -x "scripts/CHECK-MEEET-LIVE.command" ]; then
  bad "scripts/CHECK-MEEET-LIVE.command not executable or missing"
  note "remediation: re-checkout main; brief §2.A2 smoke probe block"
  record "✗" "Sync 2 (A2 balance) — script missing"
  FAILED=$((FAILED+1))
else
  if run_primitive "CHECK-MEEET-LIVE.command" \
       bash scripts/CHECK-MEEET-LIVE.command; then
    ok "Sync 2: CHECK-MEEET-LIVE exit 0"
    record "✓" "Sync 2 (A2 balance) — green"
    PASSED=$((PASSED+1))
  else
    bad "Sync 2: CHECK-MEEET-LIVE exit non-zero"
    note "remediation: brief §2.A2 — confirm /operator shape + remaining_usd parity"
    record "✗" "Sync 2 (A2 balance) — red"
    FAILED=$((FAILED+1))
  fi
fi

# --- 5. Sync 3 — A5 (auth e2e smoke) --------------------------------------

hdr "Sync 3 — A5: auth + billing e2e smoke"

if [ "${BROTHER_PREFLIGHT_SKIP_LIVE:-0}" = "1" ]; then
  skip "Sync 3 SKIPPED (BROTHER_PREFLIGHT_SKIP_LIVE=1)"
  record "⊘" "Sync 3 (A5 auth e2e) — SKIP"
  SKIPPED=$((SKIPPED+1))
elif [ ! -f "scripts/smoke_billing_tars_backend.sh" ]; then
  bad "scripts/smoke_billing_tars_backend.sh missing"
  note "remediation: re-checkout main; brief §5 coord test handoff"
  record "✗" "Sync 3 (A5 auth e2e) — script missing"
  FAILED=$((FAILED+1))
else
  if run_primitive "smoke_billing_tars_backend.sh" \
       bash scripts/smoke_billing_tars_backend.sh; then
    ok "Sync 3: smoke_billing_tars_backend exit 0"
    record "✓" "Sync 3 (A5 auth e2e) — green"
    PASSED=$((PASSED+1))
  else
    bad "Sync 3: smoke_billing_tars_backend exit non-zero"
    note "remediation: brief §2.A5 — re-run scripts/smoke_auth_meeet_e2e.sh on brother side"
    record "✗" "Sync 3 (A5 auth e2e) — red"
    FAILED=$((FAILED+1))
  fi
fi

# --- 6. Sync 4 — A3 (top-up checkout URL liveness) ------------------------

hdr "Sync 4 — A3: meeet.world/billing/tars checkout liveness"

if [ "${BROTHER_PREFLIGHT_SKIP_LIVE:-0}" = "1" ]; then
  skip "Sync 4 SKIPPED (BROTHER_PREFLIGHT_SKIP_LIVE=1)"
  record "⊘" "Sync 4 (A3 checkout) — SKIP"
  SKIPPED=$((SKIPPED+1))
elif [ "${BROTHER_PREFLIGHT_DRY_RUN:-0}" = "1" ]; then
  note "(dry-run) curl -fsSI https://meeet.world/billing/tars"
  ok "Sync 4: dry-run mocked (no network call)"
  record "✓" "Sync 4 (A3 checkout) — green (dry-run)"
  PASSED=$((PASSED+1))
else
  HTTP_CODE="$(curl -fsSI -o /dev/null -w '%{http_code}' \
                 --max-time 10 \
                 https://meeet.world/billing/tars 2>/dev/null || echo "000")"
  if [ "${HTTP_CODE}" = "200" ] || [ "${HTTP_CODE}" = "301" ] || [ "${HTTP_CODE}" = "302" ]; then
    ok "Sync 4: /billing/tars returns HTTP ${HTTP_CODE}"
    record "✓" "Sync 4 (A3 checkout) — green (HTTP ${HTTP_CODE})"
    PASSED=$((PASSED+1))
  else
    bad "Sync 4: /billing/tars returned HTTP ${HTTP_CODE} (expected 200/301/302)"
    note "remediation: brief §3.A3 — confirm SOL + card flow on /billing/tars is live"
    record "✗" "Sync 4 (A3 checkout) — red (HTTP ${HTTP_CODE})"
    FAILED=$((FAILED+1))
  fi
fi

# --- 7. Sync 5 — A4 (reconciliation ownership) ----------------------------

hdr "Sync 5 — A4: reconciliation script ownership"

# Two valid resolutions per brief §3.A4: (a) TARS ships the script, OR
# (b) brother points to their version via BROTHER_RECONCILE_URL.

if [ -n "${BROTHER_RECONCILE_URL:-}" ]; then
  ok "Sync 5: brother-side reconcile pointer = ${BROTHER_RECONCILE_URL}"
  record "✓" "Sync 5 (A4 reconcile) — green (brother owns)"
  PASSED=$((PASSED+1))
elif [ -f "scripts/reconcile-meeet-billing.py" ]; then
  ok "Sync 5: TARS-side scripts/reconcile-meeet-billing.py exists"
  record "✓" "Sync 5 (A4 reconcile) — green (TARS owns)"
  PASSED=$((PASSED+1))
else
  bad "Sync 5: no TARS-side scripts/reconcile-meeet-billing.py AND BROTHER_RECONCILE_URL unset"
  note "remediation: brief §3.A4 — either"
  note "  (a) ship scripts/reconcile-meeet-billing.py TARS-side (~3 h scaffolded on audit_billing.py), OR"
  note "  (b) export BROTHER_RECONCILE_URL=https://… pointing to brother-side script"
  record "✗" "Sync 5 (A4 reconcile) — red (no owner)"
  FAILED=$((FAILED+1))
fi

# --- 8. Sync 6 — ph3-pair-ttl ownership ack -------------------------------

hdr "Sync 6 — ph3-pair-ttl ownership ack (v10.2 — heads-up only)"

# This is the only sync that is NOT a hard GA blocker. It's an
# acknowledgement that brother has the v10.2 TODO on their backlog.
# Operator records the verbal ack via env var. Default unset = SKIP-PENDING,
# not a hard red, because brief §3.ph3-pair-ttl says "NOT v10 GA — heads-up only".

if [ "${BROTHER_PAIR_TTL_ACK:-}" = "yes" ]; then
  ok "Sync 6: brother acknowledged ph3-pair-ttl ownership (v10.2 backlog)"
  record "✓" "Sync 6 (ph3-pair-ttl) — green (ack recorded)"
  PASSED=$((PASSED+1))
else
  skip "Sync 6: BROTHER_PAIR_TTL_ACK unset — heads-up only, NOT a v10 GA blocker"
  note "to record brother's verbal sign-off: export BROTHER_PAIR_TTL_ACK=yes"
  note "brief §3.ph3-pair-ttl framing: 'NOT v10 GA — heads-up only'"
  record "⊘" "Sync 6 (ph3-pair-ttl) — SKIP-PENDING (not a blocker)"
  SKIPPED=$((SKIPPED+1))
fi

# --- 9. Sync 7 — acceptance_tars_meeet.sh end-to-end -----------------------

hdr "Sync 7 — acceptance: scripts/acceptance_tars_meeet.sh against live"

if [ "${BROTHER_PREFLIGHT_SKIP_LIVE:-0}" = "1" ]; then
  skip "Sync 7 SKIPPED (BROTHER_PREFLIGHT_SKIP_LIVE=1)"
  record "⊘" "Sync 7 (acceptance) — SKIP"
  SKIPPED=$((SKIPPED+1))
elif [ ! -f "scripts/acceptance_tars_meeet.sh" ]; then
  bad "scripts/acceptance_tars_meeet.sh missing"
  note "remediation: re-checkout main; brief §5 coord test handoff"
  record "✗" "Sync 7 (acceptance) — script missing"
  FAILED=$((FAILED+1))
else
  if run_primitive "acceptance_tars_meeet.sh" \
       bash scripts/acceptance_tars_meeet.sh; then
    ok "Sync 7: acceptance_tars_meeet exit 0"
    record "✓" "Sync 7 (acceptance) — green"
    PASSED=$((PASSED+1))
  else
    bad "Sync 7: acceptance_tars_meeet exit non-zero"
    note "remediation: brief §9 acceptance criteria — investigate failing stage in log"
    record "✗" "Sync 7 (acceptance) — red"
    FAILED=$((FAILED+1))
  fi
fi

# --- 10. Verdict summary --------------------------------------------------

echo
echo "${C_BLU}╔══════════════════════════════════════════════════════════════════╗${C_RST}"
echo "${C_BLU}║                     BROTHER PREFLIGHT VERDICT                    ║${C_RST}"
echo "${C_BLU}╚══════════════════════════════════════════════════════════════════╝${C_RST}"
echo
echo "${RESULTS}"
echo "Passed:   ${C_GRN}${PASSED}${C_RST} / 7"
echo "Failed:   ${C_RED}${FAILED}${C_RST} / 7"
echo "Skipped:  ${C_YEL}${SKIPPED}${C_RST} / 7"
echo

if [ "${FAILED}" -gt 0 ]; then
  echo "${C_RED}✗  BLOCK v10.0.0 GA TAG${C_RST} — ${FAILED} sync(s) red"
  echo
  echo "Next steps:"
  echo "  1. Address red sync(s) per the inline remediation pointers above"
  echo "  2. Re-run: bash scripts/BROTHER-PREFLIGHT.command"
  echo "  3. Only proceed to tag cut when verdict is PROCEED"
  exit 1
fi

# Partial verdict = "neither green nor red". Sync 6 alone skipped (no ack)
# is the only "clean" partial — it's documented as not a v10 GA blocker.
# Any additional skip means live probes were intentionally bypassed.
ALLOWED_SKIPS=0
if [ "${BROTHER_PAIR_TTL_ACK:-}" != "yes" ]; then
  ALLOWED_SKIPS=1  # Sync 6 SKIP-PENDING is the only acceptable skip
fi
if [ "${SKIPPED}" -gt "${ALLOWED_SKIPS}" ]; then
  echo "${C_YEL}⚠  PARTIAL VERDICT${C_RST} — ${SKIPPED} sync(s) skipped"
  echo
  echo "Next steps:"
  echo "  - If BROTHER_PREFLIGHT_SKIP_LIVE=1 was set deliberately, run without"
  echo "    that env var when api.meeet.world is up to get a real verdict"
  echo "  - Set BROTHER_PAIR_TTL_ACK=yes once brother confirms v10.2 ownership"
  echo "    (this sync is not a v10 GA hard blocker; safe to defer)"
  exit 2
fi

echo "${C_GRN}✓  PROCEED${C_RST} — brother coord side of v10.0.0 GA clear"
echo
echo "Next steps:"
echo "  1. Run: bash scripts/PREFLIGHT-APPLE-SIGN.command (Apple side, #216)"
echo "  2. If both green: bash scripts/RELEASE-v10.0.command"
echo "  3. After CI signs+notarizes: bash scripts/VERIFY-APPLE-SIGNATURE.command <dmg>"
echo "  4. Start soak: bash scripts/SOAK-HOURLY.command (cron, 72 h)"
echo "  5. After 72 h: bash scripts/SOAK-REPORT.command"
echo "  6. If soak verdict green: tag v10.0.0"
echo
echo "Brief sign-off:"
echo "  - Post '✓ brother preflight green' comment on v10 GA tag PR"
echo "  - Flip V10_GA_CHECKLIST.md A1/A2/A5 to [x] (per brief §9)"

exit 0
