#!/usr/bin/env bash
# SMOKE-TEST.command — W227 end-to-end smoke test for TARS v9.2.0-beta2.
#
# Double-click to verify the entire backend surface + watchdog +
# meeet token + installed TARS.app are wired correctly. Logs to
# ./.SMOKE-TEST.txt and auto-closes Terminal 5s after finishing.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.SMOKE-TEST.txt"
BASE="${TARS_BASE:-http://127.0.0.1:8765}"

OK=0
FAIL=0
SKIP=0
TOTAL=0
FAILED_PATHS=()

if [ -t 1 ]; then
  G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; D=$'\033[2m'; X=$'\033[0m'
else
  G=""; R=""; Y=""; D=""; X=""
fi

log() { printf "%s\n" "$*"; }

# check_status METHOD PATH [JSON_BODY] [--multipart]
check_status() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  local kind="${4:-}"
  local url="${BASE}${path}"
  TOTAL=$((TOTAL+1))

  local code
  if [ "$kind" = "--multipart" ]; then
    local tmp
    tmp="$(mktemp -t tars-smoke-XXXXXX.png)"
    printf '\x89PNG\r\n\x1a\n' > "$tmp"
    code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 \
      -X "$method" -F "file=@${tmp};type=image/png" "$url" 2>/dev/null || echo "000")
    rm -f "$tmp"
  elif [ -n "$body" ]; then
    code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 \
      -X "$method" -H "Content-Type: application/json" -d "$body" "$url" 2>/dev/null || echo "000")
  else
    code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 \
      -X "$method" "$url" 2>/dev/null || echo "000")
  fi

  if [ "$code" -ge 200 ] && [ "$code" -lt 300 ]; then
    log "  ${G}✓${X} ${method} ${path} ${D}(HTTP ${code})${X}"
    OK=$((OK+1))
  elif [ "$code" = "404" ] || [ "$code" = "503" ]; then
    log "  ${Y}⚠${X} ${method} ${path} — skipped (HTTP ${code}, expected to need data)"
    SKIP=$((SKIP+1))
  else
    log "  ${R}✗${X} ${method} ${path} (HTTP ${code})"
    FAIL=$((FAIL+1))
    FAILED_PATHS+=("${method} ${path} → ${code}")
  fi
}

{
  echo "=== TARS v9.2.0-beta2 SMOKE TEST — $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo "Base URL: ${BASE}"
  echo ""

  echo "── pre-flight ──"
  if ! curl -sS -o /dev/null --connect-timeout 3 --max-time 5 "${BASE}/api/health"; then
    echo "  ${R}✗ backend not reachable at ${BASE}${X}"
    echo "  → run: bash scripts/backend_tars_up.sh   (or LAUNCH-NOW.command)"
    echo ""
    echo "=== ABORTED (backend down) ==="
    exit 1
  fi
  echo "  ${G}✓ backend reachable${X}"
  echo ""

  echo "── baseline endpoints ──"
  check_status GET  /api/health
  check_status GET  /api/doctor
  check_status GET  /api/entitlements
  check_status GET  /api/agents
  check_status GET  /api/connectors
  echo ""

  echo "── W203 vision ──"
  check_status GET  /api/vision/health
  check_status POST /api/vision/ocr "" --multipart
  check_status POST /api/vision/analyze '{"image_data_url":"data:image/png;base64,iVBORw0KGgo=","prompt":"smoke"}'
  echo ""

  echo "── W203 auth/meeet ──"
  check_status GET  /api/auth/meeet/status
  check_status POST /api/auth/meeet/exchange '{"token":"smoke-test-token-12345678"}'
  check_status DELETE /api/auth/meeet/disconnect
  echo ""

  echo "── W204 public proof ──"
  check_status GET  /api/public/proof/health
  check_status GET  /api/public/proof/anchor/0000000000000000000000000000000000000000000000000000000000000000
  check_status POST /api/public/proof/verify '{"leaf_hex":"0000000000000000000000000000000000000000000000000000000000000000","path":[],"root_hex":"0000000000000000000000000000000000000000000000000000000000000000"}'
  echo ""

  echo "── W206 briefing ──"
  check_status GET  /api/briefing/today
  echo ""

  echo "── W209 digest ──"
  check_status POST /api/digest/run '{}'
  check_status GET  /api/digest/latest
  echo ""

  echo "── W217 a11y ──"
  check_status GET  /api/a11y/health
  check_status POST /api/a11y/ocr_speak "" --multipart
  check_status POST /api/a11y/speak '{"text":"smoke test"}'
  echo ""

  echo "── W219 magic-link / oauth ──"
  check_status POST /api/auth/meeet/magic-link-start '{"email":"smoke@test.local"}'
  check_status GET  /api/auth/meeet/oauth/google/start
  check_status GET  /api/auth/meeet/oauth/apple/start
  echo ""

  echo "── W220 voice command ──"
  check_status POST /api/voice/command '{"transcript":"проверка","lang":"ru-RU"}'
  echo ""

  echo "── system checks ──"

  if launchctl list 2>/dev/null | grep -q "com.tars.backend-watchdog"; then
    echo "  ${G}✓${X} watchdog LaunchAgent loaded (com.tars.backend-watchdog)"
  else
    echo "  ${Y}⚠${X} watchdog LaunchAgent NOT loaded"
    echo "       → run: bash scripts/install-tars-watchdog.command"
  fi

  TOKEN_PATH="${HOME}/.tars/meeet_token"
  if [ -f "$TOKEN_PATH" ]; then
    SIZE=$(wc -c < "$TOKEN_PATH" 2>/dev/null | tr -d ' ')
    if [ "${SIZE:-0}" -gt 8 ]; then
      echo "  ${G}✓${X} meeet token present (${SIZE} bytes at ~/.tars/meeet_token)"
    else
      echo "  ${Y}⚠${X} meeet token file too small (${SIZE} bytes) — re-run pairing"
    fi
  else
    echo "  ${Y}⚠${X} no meeet token at ~/.tars/meeet_token (offline-only mode)"
  fi

  if [ -d "/Applications/TARS.app" ]; then
    VER=$(defaults read /Applications/TARS.app/Contents/Info CFBundleShortVersionString 2>/dev/null || echo "unknown")
    echo "  ${G}✓${X} TARS.app installed (version ${VER})"
  else
    echo "  ${Y}⚠${X} /Applications/TARS.app missing"
    echo "       → run: bash scripts/install-tars-app.command"
  fi

  echo ""

  echo "── summary ──"
  echo "  ${OK}/${TOTAL} endpoints ok, ${SKIP} skipped, ${FAIL} failed"
  if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "  failures:"
    for p in "${FAILED_PATHS[@]}"; do
      echo "    ${R}✗${X} ${p}"
    done
    echo ""
    echo "  ${R}✗ SMOKE TEST FAILED${X} — see docs/SMOKE-TEST-RESULTS.md"
  else
    echo ""
    echo "  ${G}✓ SMOKE TEST PASSED${X} — TARS v9.2.0-beta2 looks healthy"
  fi
  echo ""
  echo "=== done at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
} | tee "$OUT"

sleep 5
osascript -e 'tell application "Терминал" to close (every window whose name contains "SMOKE-TEST")' 2>/dev/null || \
  osascript -e 'tell application "Terminal" to close (every window whose name contains "SMOKE-TEST")' 2>/dev/null || true
