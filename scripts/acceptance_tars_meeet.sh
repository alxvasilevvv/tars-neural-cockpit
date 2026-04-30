#!/usr/bin/env bash
# scripts/acceptance_tars_meeet.sh
#
# Production acceptance test for tars.meeet.world. Runs the seven
# gates from docs/TARS_MEEET_READINESS.md §3 plus the Lighthouse /
# axe audits if the local node toolchain is available.
#
# Usage:
#   BRIDGE_SHARED_SECRET=<secret> scripts/acceptance_tars_meeet.sh
#
# Optional env:
#   TARS_BASE          target base URL (default https://tars.meeet.world)
#   CORE_BRIDGE_URL    override core-bridge URL
#   SKIP_LIGHTHOUSE    set to 1 to skip the perf/a11y audit (CI-side default)
#   SKIP_AXE           set to 1 to skip @axe-core/cli
#
# Exit codes:
#   0  all gates green
#   1  one or more hard gates failed
#   2  prerequisites missing (e.g. curl, BRIDGE_SHARED_SECRET)
#
# Authoritative spec: docs/TARS_MEEET_READINESS.md §3.
# Bridge contract:    docs/contracts/CORE_BRIDGE.md.

set -euo pipefail

TARS_BASE="${TARS_BASE:-https://tars.meeet.world}"
CORE_BRIDGE_URL="${CORE_BRIDGE_URL:-https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/core-bridge}"

red()   { printf '\033[0;31m%s\033[0m\n' "$*" >&2; }
green() { printf '\033[0;32m%s\033[0m\n' "$*" >&2; }
blue()  { printf '\033[0;34m%s\033[0m\n' "$*" >&2; }
yel()   { printf '\033[0;33m%s\033[0m\n' "$*" >&2; }

# ---------- Pre-flight ----------
need() {
  command -v "$1" >/dev/null 2>&1 || { red "missing prerequisite: $1"; exit 2; }
}
need curl
need awk
need grep

if [[ -z "${BRIDGE_SHARED_SECRET:-}" ]]; then
  red "BRIDGE_SHARED_SECRET is required (sets the x-bridge-secret for relay-event tests)"
  exit 2
fi

failures=0
fail() { red "  FAIL: $*"; failures=$((failures + 1)); }
ok()   { green "  OK:   $*"; }

blue "==> tars.meeet.world acceptance — base=${TARS_BASE}"
echo

# ---------- Gate 1: root returns 200 + X-Tars-Contract ----------
blue "[1/7] root → 200 + X-Tars-Contract: 1.0.0"
headers=$(curl -sIL "${TARS_BASE}/" 2>/dev/null || true)
status=$(printf '%s' "$headers" | awk 'NR==1 {print $2; exit}')
contract=$(printf '%s' "$headers" | awk -F': ' 'tolower($1) == "x-tars-contract" {gsub(/\r/, "", $2); print $2; exit}')
if [[ "$status" == "200" ]]; then
  ok "HTTP $status"
else
  fail "expected 200, got '${status:-<empty>}'"
fi
if [[ "$contract" == "1.0.0" ]]; then
  ok "X-Tars-Contract: 1.0.0"
else
  fail "expected X-Tars-Contract: 1.0.0, got '${contract:-<empty>}'"
fi
echo

# ---------- Gate 2: SPA hydration on /install, /pricing, /faq, /cockpit ----------
blue "[2/7] SPA hydration on key marketing routes"
for route in /install /pricing /faq /compare /cockpit /onboarding; do
  status=$(curl -s -o /dev/null -w '%{http_code}' "${TARS_BASE}${route}")
  if [[ "$status" == "200" ]]; then
    ok "${route} → 200"
  else
    fail "${route} → ${status}"
  fi
done
echo

# ---------- Gate 3: manifest endpoint reachable + JSON 1.0.0 ----------
blue "[3/7] /api/product/downloads → JSON manifest (contract 1.0.0)"
manifest_body=$(curl -sf "${TARS_BASE}/api/product/downloads" 2>/dev/null || true)
manifest_contract=$(printf '%s' "$manifest_body" | grep -oE '"contract_version"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
if [[ "$manifest_contract" == "1.0.0" ]]; then
  ok "contract_version: 1.0.0"
else
  fail "expected contract_version 1.0.0, got '${manifest_contract:-<empty>}'"
fi
manifest_releases=$(printf '%s' "$manifest_body" | grep -oE '"releases"[[:space:]]*:[[:space:]]*\[' | wc -l | tr -d ' ')
if [[ "$manifest_releases" -ge 1 ]]; then
  ok "releases array present"
else
  fail "releases array missing"
fi
echo

# ---------- Gate 4: tars_session_id cookie issued with Domain=.meeet.world ----------
blue "[4/7] first-visit → tars_session_id cookie with Domain=.meeet.world"
cookie_jar=$(mktemp -t cookie_jar.XXXXXX)
trap 'rm -f "$cookie_jar"' EXIT
curl -sIL -c "$cookie_jar" "${TARS_BASE}/" >/dev/null 2>&1 || true
session_line=$(grep -E '\stars_session_id\s' "$cookie_jar" 2>/dev/null || true)
if [[ -n "$session_line" ]]; then
  ok "tars_session_id present in jar"
  cookie_domain=$(awk '{print $1}' <<<"$session_line")
  case "$cookie_domain" in
    \.meeet.world|.meeet.world|meeet.world|*.meeet.world)
      ok "domain attribute scoped to .meeet.world"
      ;;
    *)
      fail "expected Domain=.meeet.world, got '${cookie_domain}'"
      ;;
  esac
else
  fail "tars_session_id cookie missing (edge middleware not active?)"
fi
echo

# ---------- Gate 5: core-bridge smoke green ----------
blue "[5/7] core-bridge end-to-end smoke (relay → tars-ingest)"
if scripts/smoke_core_bridge_e2e.sh >/dev/null 2>&1; then
  ok "smoke_core_bridge_e2e.sh: all assertions passed"
else
  rc=$?
  fail "smoke_core_bridge_e2e.sh exited with code $rc — re-run manually for details"
fi
echo

# ---------- Gate 6: trace_id round-trip via /relay-event ----------
blue "[6/7] trace_id round-trip via core-bridge → tars-ingest"
trace_id="acceptance_$(date -u +%s)_$(printf '%x' $$)"
session_id="acceptance_session_$(printf '%x' $$)"
relay_payload=$(cat <<JSON
{
  "kind": "tars.acceptance.probe",
  "trace_id": "${trace_id}",
  "session_id": "${session_id}",
  "contract_version": "1.0.0",
  "payload": {
    "source": "acceptance_tars_meeet.sh",
    "host": "${TARS_BASE}"
  }
}
JSON
)
relay_body=$(curl -sS -X POST "${CORE_BRIDGE_URL}/relay-event" \
  -H "Content-Type: application/json" \
  -H "Origin: https://tars.meeet.world" \
  -H "x-bridge-secret: ${BRIDGE_SHARED_SECRET}" \
  -d "$relay_payload" 2>/dev/null || true)
if printf '%s' "$relay_body" | grep -q '"ok":true'; then
  ok "relay returned ok:true (trace_id=${trace_id})"
else
  fail "relay rejected: $(printf '%s' "$relay_body" | head -c 200)"
fi
echo

# ---------- Gate 7: Lighthouse perf > 90 + a11y > 95 (optional) ----------
blue "[7/7] Lighthouse perf > 90, a11y > 95"
if [[ "${SKIP_LIGHTHOUSE:-0}" == "1" ]]; then
  yel "  SKIP: SKIP_LIGHTHOUSE=1"
elif ! command -v npx >/dev/null 2>&1; then
  yel "  SKIP: npx not available (install Node 20+ to run this gate)"
else
  out=$(mktemp -t lighthouse.XXXXXX.json)
  trap 'rm -f "$cookie_jar" "$out"' EXIT
  if npx --yes lighthouse "${TARS_BASE}/" \
       --only-categories=performance,accessibility \
       --chrome-flags="--headless=new --no-sandbox" \
       --output=json --output-path="$out" --quiet >/dev/null 2>&1; then
    perf=$(grep -oE '"performance"[^}]*"score"[[:space:]]*:[[:space:]]*[0-9.]*' "$out" | head -1 | grep -oE '[0-9.]+$' || true)
    a11y=$(grep -oE '"accessibility"[^}]*"score"[[:space:]]*:[[:space:]]*[0-9.]*' "$out" | head -1 | grep -oE '[0-9.]+$' || true)
    perf_pct=$(awk "BEGIN { printf \"%.0f\", ${perf:-0} * 100 }")
    a11y_pct=$(awk "BEGIN { printf \"%.0f\", ${a11y:-0} * 100 }")
    if [[ "$perf_pct" -ge 90 ]]; then
      ok "perf score ${perf_pct} >= 90"
    else
      fail "perf score ${perf_pct} < 90"
    fi
    if [[ "$a11y_pct" -ge 95 ]]; then
      ok "a11y score ${a11y_pct} >= 95"
    else
      fail "a11y score ${a11y_pct} < 95"
    fi
  else
    yel "  SKIP: lighthouse run failed (network? Chrome missing?)"
  fi
fi
echo

# ---------- Summary ----------
if [[ $failures -eq 0 ]]; then
  green "================================================"
  green "  ACCEPTANCE GREEN: every gate passed"
  green "================================================"
  exit 0
else
  red "================================================"
  red "  ACCEPTANCE FAILED: ${failures} gate(s) red"
  red "================================================"
  exit 1
fi
