#!/usr/bin/env bash
# CHECK-MEEET-LIVE.command — W233
#
# Double-clickable diag that probes the 4 endpoints the brother must ship
# on api.meeet.world for TARS auth to work live. Prints a green/red
# checklist, writes .CHECK-MEEET-LIVE.txt, and (if all 4 are green AND
# the local .env is still MEEET_MODE=mock) prompts via osascript to flip
# the local .env to MEEET_MODE=live.
#
# The 4 endpoints are documented in
# docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md.

set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.CHECK-MEEET-LIVE.txt"

# --- Load MEEET_BASE_URL from .env ----------------------------------------
MEEET_BASE_URL=""
MEEET_MODE_CURRENT=""
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env 2>/dev/null || true
  set +a
fi
MEEET_BASE_URL="${MEEET_BASE_URL:-https://api.meeet.world}"
MEEET_BASE_URL="${MEEET_BASE_URL%/}"
MEEET_MODE_CURRENT="${MEEET_MODE:-live}"

# probe_endpoint METHOD PATH [BODY_JSON]
# Returns: "ok|<status>"        -> 2xx
#          "client|<status>"    -> 4xx (endpoint exists, request rejected -- counts as live)
#          "server|<status>"    -> 5xx
#          "404|404"            -> 404 = not deployed
#          "unreachable|0"      -> connection refused / DNS / timeout
probe_endpoint() {
  local method="$1"; local path="$2"; local body="${3:-}"
  local url="${MEEET_BASE_URL}${path}"
  local code
  if [ "$method" = "POST" ]; then
    code=$(curl -sS -o /dev/null -w "%{http_code}" \
      --max-time 8 \
      -X POST \
      -H "Content-Type: application/json" \
      -H "User-Agent: TARS-CHECK-MEEET-LIVE/W233" \
      -d "${body:-{}}" "$url" 2>/dev/null || echo "000")
  else
    code=$(curl -sS -o /dev/null -w "%{http_code}" \
      --max-time 8 \
      -H "User-Agent: TARS-CHECK-MEEET-LIVE/W233" \
      "$url" 2>/dev/null || echo "000")
  fi
  case "$code" in
    000) echo "unreachable|0" ;;
    404) echo "404|404" ;;
    2*)  echo "ok|$code" ;;
    4*)  echo "client|$code" ;;
    5*)  echo "server|$code" ;;
    *)   echo "unknown|$code" ;;
  esac
}

verdict_line() {
  local label="$1"; local res="$2"
  local kind="${res%%|*}"
  local code="${res##*|}"
  case "$kind" in
    ok)          printf "  %-34s -> OK (%s) live\n" "$label" "$code" ;;
    client)      printf "  %-34s -> OK (%s) endpoint deployed (request rejected, counts as live)\n" "$label" "$code" ;;
    server)      printf "  %-34s -> WARN (%s) endpoint deployed but 5xx\n" "$label" "$code" ;;
    404)         printf "  %-34s -> FAIL 404 not deployed\n" "$label" ;;
    unreachable) printf "  %-34s -> FAIL unreachable (DNS / TCP / timeout)\n" "$label" ;;
    *)           printf "  %-34s -> ? %s\n" "$label" "$code" ;;
  esac
}

# Count: any of ok|client|server counts as "endpoint exists".
is_live() {
  local res="$1"
  local kind="${res%%|*}"
  case "$kind" in
    ok|client|server) return 0 ;;
    *) return 1 ;;
  esac
}

{
  echo "=== CHECK-MEEET-LIVE at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo "MEEET_BASE_URL: ${MEEET_BASE_URL}"
  echo "MEEET_MODE (local .env): ${MEEET_MODE_CURRENT}"
  echo ""
  echo "Probing 4 endpoints brother must ship..."
  echo ""

  r1=$(probe_endpoint POST "/api/magic-link/start"        '{"email":"probe@tars.local","client":"tars-desktop","return_to":"tars://auth"}')
  r2=$(probe_endpoint POST "/api/magic-link/redeem"       '{"code":"probe","email":"probe@tars.local"}')
  r3=$(probe_endpoint GET  "/api/oauth/google/start?return=tars://auth")
  r4=$(probe_endpoint GET  "/api/oauth/apple/start?return=tars://auth")
  r5=$(probe_endpoint GET  "/api/me")

  echo "meeet.world live readiness:"
  verdict_line "POST /api/magic-link/start"   "$r1"
  verdict_line "POST /api/magic-link/redeem"  "$r2"
  verdict_line "GET  /api/oauth/google/start" "$r3"
  verdict_line "GET  /api/oauth/apple/start"  "$r4"
  verdict_line "GET  /api/me"                 "$r5"
  echo ""

  live_count=0
  is_live "$r1" && live_count=$((live_count+1))
  is_live "$r2" && live_count=$((live_count+1))
  is_live "$r3" && live_count=$((live_count+1))
  is_live "$r4" && live_count=$((live_count+1))
  me_live="no"
  is_live "$r5" && me_live="yes"

  echo "Verdict: ${live_count}/4 auth endpoints live, /api/me live=${me_live}"
  if [ "$live_count" -eq 4 ] && [ "$me_live" = "yes" ]; then
    echo "  can switch MEEET_MODE=live? yes (all green)"
    FLIP_OK=1
  else
    echo "  can switch MEEET_MODE=live? no (brother still has work to do)"
    FLIP_OK=0
  fi
  echo ""
  echo "Reference: docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md"
  echo "=== DONE ==="
  echo "FLIP_OK=${FLIP_OK}"
  echo "CURRENT_MODE=${MEEET_MODE_CURRENT}"
} | tee "$OUT"

FLIP_OK=$(grep -E "^FLIP_OK=" "$OUT" | tail -1 | cut -d= -f2)
CURRENT_MODE=$(grep -E "^CURRENT_MODE=" "$OUT" | tail -1 | cut -d= -f2)

if [ "${FLIP_OK:-0}" = "1" ] && [ "${CURRENT_MODE:-}" = "mock" ]; then
  ANSWER=$(osascript <<'OSA' 2>/dev/null || echo "No"
display dialog "meeet.world is live on all 4 brother endpoints, but your local .env still has MEEET_MODE=mock.

Flip MEEET_MODE=mock -> MEEET_MODE=live now?

(.env will be edited in place; a .env.bak-w233 backup will be written.)" buttons {"No", "Yes"} default button "Yes" with title "TARS -- CHECK-MEEET-LIVE"
set ans to button returned of result
return ans
OSA
)
  if [ "$ANSWER" = "Yes" ]; then
    cp .env .env.bak-w233 2>/dev/null || true
    sed -i.tmp 's/^MEEET_MODE=mock$/MEEET_MODE=live/' .env && rm -f .env.tmp
    {
      echo ""
      echo "=== .env flipped MEEET_MODE=mock -> MEEET_MODE=live ==="
      grep -E "^MEEET_MODE=" .env || true
      echo "Backup: .env.bak-w233"
      echo "Restart the backend (PID will reload MEEET_MODE on next request only if you re-exec)."
    } | tee -a "$OUT"
  else
    echo "User declined .env flip. MEEET_MODE stays as ${CURRENT_MODE}." | tee -a "$OUT"
  fi
fi

sleep 5
osascript -e 'tell application "Терминал" to close (every window whose name contains "CHECK-MEEET-LIVE")' 2>/dev/null || true
osascript -e 'tell application "Terminal" to close (every window whose name contains "CHECK-MEEET-LIVE")' 2>/dev/null || true
