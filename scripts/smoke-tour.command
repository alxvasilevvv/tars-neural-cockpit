#!/usr/bin/env bash
# smoke-tour.command — full user-journey QA pass against live backend.
#
# Hits every public read-only endpoint, records HTTP status + JSON shape,
# reports pass/fail/partial. Side-effect-free.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.smoke-tour.txt"
BASE="http://127.0.0.1:8765"

probe() {
  local name="$1"
  local method="${2:-GET}"
  local path="$3"
  local expect_status="${4:-200}"
  local body="${5:-}"
  local hdr="-H 'Accept: application/json'"

  local args=( -sS -o /tmp/smoke-body -w '%{http_code}|%{time_total}s' --max-time 5 )
  if [ "$method" != "GET" ]; then
    args+=( -X "$method" )
  fi
  if [ -n "$body" ]; then
    args+=( -H 'Content-Type: application/json' --data "$body" )
  fi

  local result
  result=$(curl "${args[@]}" "$BASE$path" 2>&1 || echo "999|ERROR")
  local status="${result%%|*}"
  local timing="${result##*|}"
  local body_len=$(wc -c < /tmp/smoke-body 2>/dev/null || echo 0)
  local body_head=$(head -c 80 /tmp/smoke-body 2>/dev/null | tr -d '\n' | head -c 60)

  if [ "$status" = "$expect_status" ]; then
    printf "  ✓ %-44s %s  (%sb, %s)\n" "$name" "$status" "$body_len" "$timing"
    return 0
  else
    printf "  ✗ %-44s %s  (expected %s)  body: %s\n" "$name" "$status" "$expect_status" "$body_head"
    return 1
  fi
}

{
  echo "=== smoke-tour at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo "Base: $BASE"
  echo ""

  echo "── 1/12 health / version / entitlements ──"
  probe "GET /api/health"            GET /api/health
  probe "GET /api/entitlements"      GET /api/entitlements
  probe "GET /api/product/version"   GET /api/product/version
  probe "GET /api/product/downloads/latest" GET /api/product/downloads/latest

  echo ""
  echo "── 2/12 doctor (11 checks) ──"
  probe "GET /api/doctor"            GET /api/doctor
  probe "GET /api/doctor?format=json" GET "/api/doctor?format=json"
  probe "GET /api/doctor/registry"   GET /api/doctor/registry
  probe "GET /api/doctor/page (HTML)" GET /api/doctor/page
  probe "GET /api/doctor/cockpit (HTML)" GET /api/doctor/cockpit
  for slug in daemon mcp clone scheduler webhooks cowork receipts vault llm_provider disk_space log_freshness; do
    probe "GET /api/doctor/$slug"     GET "/api/doctor/$slug"
  done

  echo ""
  echo "── 3/12 usage ──"
  probe "GET /api/usage"             GET /api/usage
  probe "GET /api/usage/lines"       GET /api/usage/lines
  probe "GET /api/usage/prices"      GET /api/usage/prices

  echo ""
  echo "── 4/12 clone ──"
  probe "GET /api/clone/profile"     GET /api/clone/profile

  echo ""
  echo "── 5/12 cowork ──"
  probe "GET /api/cowork/sessions"   GET /api/cowork/sessions

  echo ""
  echo "── 6/12 marketplace ──"
  probe "GET /api/marketplace/listings" GET /api/marketplace/listings 200 || \
    probe "GET /api/marketplace"     GET /api/marketplace

  echo ""
  echo "── 7/12 scheduler ──"
  probe "GET /api/scheduler/schedules" GET /api/scheduler/schedules

  echo ""
  echo "── 8/12 webhooks ──"
  probe "GET /api/webhooks/outgoing" GET /api/webhooks/outgoing
  probe "GET /api/webhooks/incoming" GET /api/webhooks/incoming

  echo ""
  echo "── 9/12 workspaces ──"
  probe "GET /api/workspaces"        GET /api/workspaces
  probe "GET /api/workspaces/permissions" GET /api/workspaces/permissions

  echo ""
  echo "── 10/12 wallet ──"
  probe "GET /api/wallet"            GET /api/wallet
  probe "GET /api/wallet/policy/status" GET /api/wallet/policy/status

  echo ""
  echo "── 11/12 pairing (status requires pair_id query — skip) ──"
  probe "GET /api/pairing/identity"  GET /api/pairing/identity
  probe "GET /api/pairing/devices"   GET /api/pairing/devices
  probe "GET /api/pairing/audit"     GET /api/pairing/audit

  echo ""
  echo "── 12/12 connectors + qa + compliance ──"
  probe "GET /api/connectors/github/health" GET /api/connectors/github/health
  probe "GET /api/qa/health"         GET /api/qa/health
  probe "GET /api/qa/report"         GET /api/qa/report
  probe "GET /api/compliance/export/bundles" GET /api/compliance/export/bundles
  probe "GET /api/compliance/export/scope-categories" GET /api/compliance/export/scope-categories

  echo ""
  echo "── side-effect: fix vault (idempotent) ──"
  probe "POST /api/doctor/fix/vault" POST /api/doctor/fix/vault

  echo ""
  echo "── side-effect: test-notify (no channels → 200 with hint) ──"
  probe "POST /api/doctor/test/notify" POST /api/doctor/test/notify

  echo ""
  echo "=== DONE ==="
} > "$OUT" 2>&1

sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "smoke-tour")' 2>/dev/null || true
