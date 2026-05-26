#!/usr/bin/env bash
# CURSOR-GA-STATUS.command — one-screen combat-readiness dashboard (read-only).
#
# Aggregates what blocks v10.0.0 GA without running destructive steps.
# Safe to run anytime; intended for Cursor takeover when Claude Cloud is down.
#
# Exit codes (worst-of):
#   0  all automatable gates green (operator may still need soak wall-clock)
#   1  at least one hard blocker (Apple secrets, tests, brother, etc.)
#   2  partial / skipped checks (gh missing, dry-run only, backend down)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RED=$'\033[0;31m'
GRN=$'\033[0;32m'
AMB=$'\033[0;33m'
RST=$'\033[0m'

rc=0
partial=0

hdr() { printf '\n── %s ──\n' "$1"; }
ok()  { printf '%b✓%b %s\n' "$GRN" "$RST" "$*"; }
warn(){ printf '%b~%b %s\n' "$AMB" "$RST" "$*"; partial=1; }
bad() { printf '%b✗%b %s\n' "$RED" "$RST" "$*"; rc=1; }

printf '===========================================================\n'
printf 'TARS combat readiness — %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'repo: %s\n' "$ROOT"
printf '===========================================================\n'

hdr "Code health"
if [[ -x ./.venv/bin/python ]]; then
  if PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_cockpit_runtime_contract.py -q --tb=no >/dev/null 2>&1; then
    ok "cockpit runtime contract tests (quick slice)"
  else
    bad "cockpit runtime contract tests failed — run: make test"
  fi
else
  warn "no .venv — run: make bootstrap && make test"
fi

if [[ -d apps/cockpit/node_modules ]]; then
  if (cd apps/cockpit && pnpm run test:e2e --reporter=line >/dev/null 2>&1); then
    ok "cockpit Playwright e2e (7 scenarios)"
  else
    bad "cockpit e2e failed — run: make ci-cockpit"
  fi
else
  warn "cockpit node_modules missing — run: pnpm install (apps/cockpit)"
fi

hdr "Backend liveness (127.0.0.1:8765)"
if curl -fsS --connect-timeout 2 --max-time 4 http://127.0.0.1:8765/api/health >/dev/null 2>&1; then
  ok "GET /api/health"
else
  warn "backend not reachable — run: make dev-tars-stack or make backend-tars-up"
fi

hdr "72h soak"
SOAK_LOG="${ROOT}/.soak/hourly.log"
if [[ -f "$SOAK_LOG" ]]; then
  n="$(wc -l < "$SOAK_LOG" | tr -d ' ')"
  last="$(tail -1 "$SOAK_LOG" 2>/dev/null || true)"
  if echo "$last" | grep -q '"any_fail":0'; then
    ok "hourly samples: ${n}/72 (latest hour any_fail=0)"
  else
    bad "latest soak hour has any_fail≠0 — inspect .soak/hourly.log"
  fi
  if [[ "$n" -lt 72 ]]; then
    warn "need ${n}→72 samples — cron or: nohup bash scripts/CURSOR-SOAK-UNTIL-72.command"
  fi
  if [[ -f "${ROOT}/.soak/cron.log" ]] && tail -30 "${ROOT}/.soak/cron.log" 2>/dev/null | grep -q 'Operation not permitted'; then
    bad "cron cannot run SOAK-HOURLY — see docs/macos/SOAK_CRON_PERMISSIONS.md"
  fi
else
  warn "no .soak/hourly.log — run: bash scripts/SOAK-HOURLY.command or CURSOR-SOAK-UNTIL-72"
fi

if [[ -f docs/qa/SOAK_v10.0.0.md ]]; then
  ok "SOAK-REPORT markdown present"
else
  warn "docs/qa/SOAK_v10.0.0.md missing — run SOAK-REPORT after 72h"
fi

hdr "Brother coord (live)"
if bash scripts/BROTHER-PREFLIGHT.command >/tmp/tars-brother-pf.txt 2>&1; then
  ok "BROTHER-PREFLIGHT PROCEED"
else
  b_rc=$?
  if grep -q PROCEED /tmp/tars-brother-pf.txt 2>/dev/null; then
    ok "BROTHER-PREFLIGHT PROCEED (rc=$b_rc ignored)"
  else
    bad "BROTHER-PREFLIGHT BLOCK — see docs/handoff/PH11_BROTHER_HANDOFF_BRIEF.md"
    tail -8 /tmp/tars-brother-pf.txt >&2 || true
  fi
fi

hdr "Apple sign (live)"
if bash scripts/PREFLIGHT-APPLE-SIGN.command >/tmp/tars-apple-pf.txt 2>&1; then
  ok "PREFLIGHT-APPLE-SIGN PROCEED"
else
  bad "PREFLIGHT-APPLE-SIGN BLOCK (expected until .p12 + GH secrets)"
  grep -E '✗|MISSING|remediation' /tmp/tars-apple-pf.txt 2>/dev/null | head -12 >&2 || true
  printf '\n  Fix playbook: docs/APPLE_SIGNING_SETUP.md + docs/APPLE_SIGNING_FOR_CURSOR.md\n' >&2
fi

hdr "GA cookbook aggregate"
if bash scripts/GA-COOKBOOK.command >/tmp/tars-ga-cookbook.txt 2>&1; then
  ok "GA-COOKBOOK PROCEED (both gates)"
else
  if grep -q 'Gate 2 (Brother).*PROCEED' /tmp/tars-ga-cookbook.txt && \
     grep -q 'Gate 1 (Apple).*BLOCK' /tmp/tars-ga-cookbook.txt; then
    warn "GA-COOKBOOK: Brother green, Apple red — tag blocked on signing only"
  else
    bad "GA-COOKBOOK BLOCK — see /tmp/tars-ga-cookbook.txt"
  fi
fi

hdr "Mechanical QA wrapper"
if [[ -f .FINAL-QA-GATE.txt ]]; then
  if FINAL_QA_VERDICT_DRY_RUN=0 bash scripts/FINAL-QA-VERDICT.command >/tmp/tars-fqa.txt 2>&1; then
    ok "FINAL-QA-VERDICT PROCEED"
  else
    f_rc=$?
    if grep -q 'VERDICT: PARTIAL' /tmp/tars-fqa.txt; then
      warn "FINAL-QA-VERDICT PARTIAL (often codesign skip without TARS.app) — rc=$f_rc"
    else
      bad "FINAL-QA-VERDICT BLOCK — run bash scripts/FINAL-QA-GATE.command"
    fi
  fi
else
  warn "no .FINAL-QA-GATE.txt — run: bash scripts/FINAL-QA-GATE.command"
fi

hdr "Tag-cut guard (dry-run)"
if TAG_GUARD_DRY_RUN=1 bash scripts/RELEASE-TAG-GUARD.command >/tmp/tars-tag-guard.txt 2>&1; then
  ok "RELEASE-TAG-GUARD dry-run PROCEED"
else
  tg_rc=$?
  if grep -q 'PARTIAL' /tmp/tars-tag-guard.txt; then
    warn "RELEASE-TAG-GUARD dry-run PARTIAL (soak report / CI stub) — rc=$tg_rc"
  else
    bad "RELEASE-TAG-GUARD dry-run BLOCK"
  fi
fi

printf '\n===========================================================\n'
printf 'Next operator commands (W310-ao cookbook):\n'
printf '  1. docs/APPLE_SIGNING_SETUP.md          # unblock Apple (B1–B5)\n'
printf '  2. bash scripts/FINAL-QA-VERDICT.command\n'
printf '  3. bash scripts/GA-COOKBOOK.command      # must exit 0\n'
printf '  4. crontab SOAK-HOURLY × 72h\n'
printf '  5. bash scripts/SOAK-REPORT.command\n'
printf '  6. bash scripts/RELEASE-TAG-GUARD.command\n'
printf '  7. bash scripts/RELEASE-v10.0.command    # destructive\n'
printf 'RU checklist: docs/OPERATOR_GA_RU.md\n'
printf 'Wake report:  docs/CURSOR_WAKEUP_2026-05-26.md\n'
printf 'Full chain: docs/W310_WAVE_SUMMARY.md (TLDR at top)\n'
printf '===========================================================\n'

if [[ "$rc" -ne 0 ]]; then
  printf '\n%bVERDICT: BLOCK%b — fix red items above\n' "$RED" "$RST"
  exit 1
fi
if [[ "$partial" -ne 0 ]]; then
  printf '\n%bVERDICT: PARTIAL%b — code ready; operator soak/signing remain\n' "$AMB" "$RST"
  exit 2
fi
printf '\n%bVERDICT: PROCEED%b — automatable gates green; run soak + tag when ready\n' "$GRN" "$RST"
exit 0
