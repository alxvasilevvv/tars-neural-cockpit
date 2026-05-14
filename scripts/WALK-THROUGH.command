#!/usr/bin/env bash
# WALK-THROUGH.command — W231
#
# Double-click in Finder to:
#   1. ensure backend is up (start if missing)
#   2. ensure ~/.tars/meeet_token exists (write local-only stub if missing)
#   3. curl-walk the full user journey (status / briefing / agents /
#      connectors / entitlements / doctor / digest / vision / a11y /
#      voice)
#   4. print a happy-path summary: green / yellow / red counts +
#      remediation hints per red
#
# Output mirrored to .WALK-THROUGH.txt at the repo root so the terminal
# can auto-close in 5s while leaving an artifact behind.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.WALK-THROUGH.txt"

PORT="${PORT:-8765}"
BASE="http://127.0.0.1:${PORT}"

# colour palette (only if stdout is a tty; we re-open to OUT below so
# they always look plain in the file)
G=""; Y=""; R=""; X=""

green_count=0
yellow_count=0
red_count=0
red_hints=()

step() {
  # step <label> <url-path> [extra args to curl]
  local label="$1"; shift
  local path="$1"; shift
  local code
  local body_file
  body_file="$(mktemp -t walkthrough.XXXXXX)"
  code=$(curl -sS -o "$body_file" -w "%{http_code}" \
    --connect-timeout 3 --max-time 8 \
    "${BASE}${path}" "$@" 2>/dev/null || echo "000")
  local size; size=$(wc -c <"$body_file" | tr -d ' ')
  case "$code" in
    200|201)
      echo "  ${G}OK${X}  $label  -> ${code}  ${size}B"
      green_count=$((green_count + 1))
      ;;
    202|204)
      echo "  ${Y}OK${X}  $label  -> ${code}  (accepted/empty)"
      green_count=$((green_count + 1))
      ;;
    503)
      echo "  ${Y}WARN${X} $label  -> 503 (subsystem disabled — usually expected)"
      yellow_count=$((yellow_count + 1))
      ;;
    000)
      echo "  ${R}DOWN${X} $label  -> backend unreachable"
      red_count=$((red_count + 1))
      red_hints+=("$label: backend at ${BASE} is not reachable")
      ;;
    *)
      echo "  ${R}FAIL${X} $label  -> ${code}"
      red_count=$((red_count + 1))
      local snippet
      snippet=$(head -c 200 "$body_file" 2>/dev/null)
      red_hints+=("$label (${code}): $snippet")
      ;;
  esac
  rm -f "$body_file"
}

post_step() {
  # post_step <label> <url-path> <json-body>
  local label="$1"; shift
  local path="$1"; shift
  local body="$1"; shift
  local code
  local body_file
  body_file="$(mktemp -t walkthrough.XXXXXX)"
  code=$(curl -sS -o "$body_file" -w "%{http_code}" \
    --connect-timeout 3 --max-time 10 \
    -H 'Content-Type: application/json' \
    -d "$body" \
    "${BASE}${path}" 2>/dev/null || echo "000")
  case "$code" in
    200|201|202|204)
      echo "  ${G}OK${X}  $label  -> ${code}"
      green_count=$((green_count + 1))
      ;;
    503)
      echo "  ${Y}WARN${X} $label  -> 503 (subsystem disabled — expected when feature isn't wired)"
      yellow_count=$((yellow_count + 1))
      ;;
    000)
      echo "  ${R}DOWN${X} $label  -> backend unreachable"
      red_count=$((red_count + 1))
      red_hints+=("$label: backend at ${BASE} is not reachable")
      ;;
    *)
      echo "  ${R}FAIL${X} $label  -> ${code}"
      red_count=$((red_count + 1))
      local snippet
      snippet=$(head -c 200 "$body_file" 2>/dev/null)
      red_hints+=("$label (${code}): $snippet")
      ;;
  esac
  rm -f "$body_file"
}

{
  echo "=== WALK-THROUGH at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo "base: $BASE"
  echo ""

  echo "-- [1/4] backend up? --"
  if curl -sS -o /dev/null --connect-timeout 2 "${BASE}/api/health" 2>/dev/null; then
    echo "  backend already responding on :${PORT}"
  else
    echo "  not running. starting via scripts/backend_tars_up.sh ..."
    bash scripts/backend_tars_up.sh 2>&1 | tail -5
    sleep 4
    if curl -sS -o /dev/null --connect-timeout 2 "${BASE}/api/health" 2>/dev/null; then
      echo "  backend up after restart"
    else
      echo "  WARN backend still unreachable — subsequent steps will be red"
    fi
  fi
  echo ""

  echo "-- [2/4] meeet token? --"
  TOKEN_PATH="${HOME}/.tars/meeet_token"
  if [ -s "$TOKEN_PATH" ]; then
    SIZE=$(wc -c <"$TOKEN_PATH" | tr -d ' ')
    echo "  ${G}OK${X} token present (${SIZE} bytes at ${TOKEN_PATH})"
  else
    echo "  no token at ${TOKEN_PATH}; writing local-only stub..."
    mkdir -p "${HOME}/.tars"
    chmod 700 "${HOME}/.tars" 2>/dev/null || true
    printf 'local-only-walkthrough-%s' "$(date +%s)" > "$TOKEN_PATH"
    chmod 600 "$TOKEN_PATH" 2>/dev/null || true
    echo "  ${Y}wrote local-only stub (offline-only mode)${X}"
  fi
  echo ""

  echo "-- [3/4] curl-walk user journey --"
  step "status     " "/api/health"
  step "briefing   " "/api/briefing/today"
  step "agents     " "/api/agents"
  step "connectors " "/api/connectors"
  step "entitlements" "/api/entitlements"
  step "doctor     " "/api/doctor"
  step "digest/last" "/api/digest/latest"
  step "vision     " "/api/vision/health" -X GET
  step "a11y       " "/api/a11y/health" -X GET
  # voice/transcribe and voice/command are owned by another lane; we
  # ping them but tolerate 200/empty or 503 gracefully (handled in
  # status table above).
  post_step "voice/command" "/api/voice/command" '{"transcript":"privet","lang":"ru-RU"}'
  echo ""

  echo "-- [4/4] summary --"
  total=$((green_count + yellow_count + red_count))
  echo "  green:  $green_count / $total"
  echo "  yellow: $yellow_count / $total"
  echo "  red:    $red_count / $total"
  if [ "$red_count" -gt 0 ]; then
    echo ""
    echo "  RED hints (fix order: top-down):"
    for h in "${red_hints[@]}"; do
      echo "    - $h"
    done
    echo ""
    echo "  Common fixes:"
    echo "    * backend unreachable -> run scripts/backend_tars_up.sh"
    echo "    * 404 errors          -> router not registered; check web_extras/app.py"
    echo "    * 500 errors          -> tail /tmp/tars-backend-${PORT}.log"
  fi
  echo ""
  echo "=== WALK-THROUGH done ==="
} > "$OUT" 2>&1

# also dump to stdout for the terminal window
cat "$OUT"

sleep 5
osascript -e 'tell application "Terminal" to close (every window whose name contains "WALK-THROUGH")' 2>/dev/null || true
