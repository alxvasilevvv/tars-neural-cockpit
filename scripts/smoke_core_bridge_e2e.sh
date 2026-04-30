#!/usr/bin/env bash
set -euo pipefail

CORE_BRIDGE_URL="${CORE_BRIDGE_URL:-https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/core-bridge}"
BRIDGE_SHARED_SECRET="${BRIDGE_SHARED_SECRET:-}"
ALLOWED_ORIGIN_CORE="${ALLOWED_ORIGIN_CORE:-https://meeet.world}"
ALLOWED_ORIGIN_TARS="${ALLOWED_ORIGIN_TARS:-https://tars.meeet.world}"

if [[ -z "${BRIDGE_SHARED_SECRET}" ]]; then
  echo "ERROR: BRIDGE_SHARED_SECRET is required"
  exit 1
fi

tmpdir="$(mktemp -d)"
cleanup() {
  rm -rf "${tmpdir}"
}
trap cleanup EXIT

request() {
  local name="$1"
  local method="$2"
  local path="$3"
  local origin="$4"
  local body="${5:-}"

  local hdr="${tmpdir}/${name}.headers"
  local out="${tmpdir}/${name}.body"
  local code

  if [[ -n "${body}" ]]; then
    code="$(curl -sS -o "${out}" -D "${hdr}" -w "%{http_code}" -X "${method}" \
      "${CORE_BRIDGE_URL}${path}" \
      -H "content-type: application/json" \
      -H "x-bridge-secret: ${BRIDGE_SHARED_SECRET}" \
      -H "Origin: ${origin}" \
      --data "${body}")"
  else
    code="$(curl -sS -o "${out}" -D "${hdr}" -w "%{http_code}" -X "${method}" \
      "${CORE_BRIDGE_URL}${path}" \
      -H "x-bridge-secret: ${BRIDGE_SHARED_SECRET}" \
      -H "Origin: ${origin}")"
  fi

  echo "[$name] HTTP ${code}" >&2
  cat "${out}" >&2
  echo >&2
  printf "%s" "${code}"
}

expect_code() {
  local actual="$1"
  local expected="$2"
  local name="$3"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "FAIL: ${name} expected ${expected}, got ${actual}"
    exit 1
  fi
}

health_code="$(request "health" "GET" "/health" "${ALLOWED_ORIGIN_CORE}")"
expect_code "${health_code}" "200" "health"

token_stats_code="$(request "token-stats" "GET" "/token-stats" "${ALLOWED_ORIGIN_TARS}")"
expect_code "${token_stats_code}" "200" "token-stats"

trace_id="trace_core_bridge_e2e_$(date +%s)"
session_id="ses_core_bridge_e2e_$(date +%s)"
relay_payload="$(cat <<EOF
{"kind":"core.bridge.smoke","trace_id":"${trace_id}","session_id":"${session_id}","contract_version":"1.0.0","payload":{"source":"control-tower","step":"relay-event-e2e"}}
EOF
)"

relay_code="$(request "relay-event" "POST" "/relay-event" "${ALLOWED_ORIGIN_TARS}" "${relay_payload}")"
expect_code "${relay_code}" "200" "relay-event"

unauth_code="$(curl -sS -o "${tmpdir}/unauth.body" -w "%{http_code}" -X GET \
  "${CORE_BRIDGE_URL}/health" \
  -H "Origin: ${ALLOWED_ORIGIN_CORE}")"
echo "[unauthorized-health] HTTP ${unauth_code}"
cat "${tmpdir}/unauth.body"
echo
expect_code "${unauth_code}" "401" "unauthorized health"

blocked_origin_code="$(curl -sS -o "${tmpdir}/blocked.body" -w "%{http_code}" -X POST \
  "${CORE_BRIDGE_URL}/relay-event" \
  -H "content-type: application/json" \
  -H "x-bridge-secret: ${BRIDGE_SHARED_SECRET}" \
  -H "Origin: https://evil.example" \
  --data "${relay_payload}")"
echo "[blocked-origin-relay] HTTP ${blocked_origin_code}"
cat "${tmpdir}/blocked.body"
echo
expect_code "${blocked_origin_code}" "403" "blocked origin relay"

if ! rg -q '"persisted":true' "${tmpdir}/relay-event.body"; then
  echo "FAIL: relay-event did not report persisted=true"
  exit 1
fi

echo "PASS: core-bridge e2e smoke is healthy"
