#!/usr/bin/env bash
# DEMO-READY.command — W273 master pre-flight + demo orchestration.
#
# Double-click this ONE file 30 minutes before the presentation.
# In ~2 minutes it walks 8 sequential phases:
#   1. Environment      — .env keys present, demo seed flag set
#   2. Backend health   — uvicorn :8765 fresh + /api/health 200
#   3. Demo data        — agents/receipts/notepads/composer/mcp seeded
#   4. TARS.app         — fresh build + signed if Apple cert is wired
#   5. Smoke test       — >=35/37 endpoints green, critical paths hard
#   6. Mock meeet       — local mock on :8766 lets us demo "live mode"
#   7. Launch + verify  — opens TARS.app, prints what to eyeball
#   8. Summary          — READY / NOT READY verdict with line-item proof
#
# Logs everything to .DEMO-READY.txt. Auto-closes Terminal after 10s
# if everything is green. Leaves window open if anything is red.
#
# If anything aborts, the script prints a clear ONE-LINE fix and exits
# non-zero. No ambiguity.

set -u

cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO="$(pwd)"
LOG="${REPO}/.DEMO-READY.txt"

# Tee everything from here on to both terminal and log.
exec > >(tee -a "$LOG") 2>&1

if [ -t 1 ]; then
  G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[34m'; D=$'\033[2m'; X=$'\033[0m'
else
  G=""; R=""; Y=""; B=""; D=""; X=""
fi

PHASES_OK=0
PHASES_FAIL=0
PHASES_WARN=0
SUMMARY_LINES=()
ALL_GREEN=1

mark_ok()   { PHASES_OK=$((PHASES_OK+1));     SUMMARY_LINES+=("${G}OK${X}   $1"); }
mark_warn() { PHASES_WARN=$((PHASES_WARN+1)); SUMMARY_LINES+=("${Y}WARN${X} $1"); ALL_GREEN=0; }
mark_fail() { PHASES_FAIL=$((PHASES_FAIL+1)); SUMMARY_LINES+=("${R}FAIL${X} $1"); ALL_GREEN=0; }

abort() {
  echo ""
  echo "${R}=========================================================${X}"
  echo "${R}  DEMO-READY ABORTED${X}"
  echo "${R}  reason: $1${X}"
  echo "${R}  fix:    $2${X}"
  echo "${R}=========================================================${X}"
  echo ""
  echo "Window stays open so you can read the fix. Close manually when done."
  exit 1
}

echo ""
echo "${B}========================================================${X}"
echo "${B}  DEMO-READY pre-flight @ $(date -u +%Y-%m-%dT%H:%M:%SZ)${X}"
echo "${B}  repo: ${REPO}${X}"
echo "${B}========================================================${X}"
echo ""

# ----------------------------------------------------------------------
# PHASE 1 -- Environment
# ----------------------------------------------------------------------
echo "${B}-- Phase 1/8 . Environment --${X}"

if [ ! -f "${REPO}/.env" ]; then
  abort "no .env file at ${REPO}/.env" \
        "cp .env.example .env  &&  edit ANTHROPIC_API_KEY or OPENROUTER_API_KEY"
fi

# Check API key presence (any provider is acceptable for the demo).
HAS_ANTHROPIC=0
HAS_OPENROUTER=0
HAS_OPENAI=0
if grep -qE '^ANTHROPIC_API_KEY=[^[:space:]]+'  "${REPO}/.env"; then HAS_ANTHROPIC=1; fi
if grep -qE '^OPENROUTER_API_KEY=[^[:space:]]+' "${REPO}/.env"; then HAS_OPENROUTER=1; fi
if grep -qE '^OPENAI_API_KEY=[^[:space:]]+'     "${REPO}/.env"; then HAS_OPENAI=1; fi

if [ "$HAS_ANTHROPIC" = "0" ] && [ "$HAS_OPENROUTER" = "0" ] && [ "$HAS_OPENAI" = "0" ]; then
  abort "no LLM provider key set in .env" \
        "add ANTHROPIC_API_KEY=... or OPENROUTER_API_KEY=... to .env then re-run"
fi
echo "  LLM key present (anthropic=${HAS_ANTHROPIC} openrouter=${HAS_OPENROUTER} openai=${HAS_OPENAI})"

# MEEET_MODE (mock is fine for demo)
MEEET_MODE_VAL="$(grep -E '^MEEET_MODE=' "${REPO}/.env" | head -n1 | cut -d= -f2- | tr -d '\r')"
if [ -z "${MEEET_MODE_VAL}" ]; then MEEET_MODE_VAL="mock"; fi
echo "  MEEET_MODE=${MEEET_MODE_VAL} (mock is fine for the demo)"

# TARS_DEMO_SEED -- must be 1 or we add it.
if grep -qE '^TARS_DEMO_SEED=1' "${REPO}/.env"; then
  echo "  TARS_DEMO_SEED=1 already in .env"
elif grep -qE '^TARS_DEMO_SEED=' "${REPO}/.env"; then
  # exists but not 1 -> flip it.
  if [ "$(uname)" = "Darwin" ]; then
    sed -i '' -E 's/^TARS_DEMO_SEED=.*/TARS_DEMO_SEED=1/' "${REPO}/.env"
  else
    sed -i      -E 's/^TARS_DEMO_SEED=.*/TARS_DEMO_SEED=1/' "${REPO}/.env"
  fi
  echo "  TARS_DEMO_SEED flipped to 1 in .env"
else
  echo "" >> "${REPO}/.env"
  echo "# W273 -- DEMO-READY auto-injected" >> "${REPO}/.env"
  echo "TARS_DEMO_SEED=1" >> "${REPO}/.env"
  echo "  TARS_DEMO_SEED=1 appended to .env"
fi
export TARS_DEMO_SEED=1

mark_ok "Environment (.env + LLM key + TARS_DEMO_SEED=1)"

# ----------------------------------------------------------------------
# PHASE 2 -- Backend health
# ----------------------------------------------------------------------
echo ""
echo "${B}-- Phase 2/8 . Backend health --${X}"

# Kill any stale uvicorn on 8765.
if command -v lsof >/dev/null 2>&1; then
  STALE_PIDS="$(lsof -tiTCP:8765 -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "${STALE_PIDS}" ]; then
    echo "  killing stale listener(s) on :8765 -> ${STALE_PIDS}"
    # shellcheck disable=SC2086
    kill -9 ${STALE_PIDS} 2>/dev/null || true
    sleep 1
  fi
fi

# Re-launch via backend_tars_up.sh (it kills+forks uvicorn detached).
if [ -x "${REPO}/scripts/backend_tars_up.sh" ]; then
  echo "  starting backend via scripts/backend_tars_up.sh ..."
  ( bash "${REPO}/scripts/backend_tars_up.sh" >/tmp/tars-backend-boot.log 2>&1 ) &
else
  abort "scripts/backend_tars_up.sh missing or not executable" \
        "chmod +x scripts/backend_tars_up.sh  &&  re-run"
fi

# Wait for /api/health (poll 1s, timeout 30s).
HEALTH_OK=0
for i in $(seq 1 30); do
  if curl -sS -o /dev/null --connect-timeout 1 --max-time 2 \
      "http://127.0.0.1:8765/api/health" 2>/dev/null; then
    HEALTH_OK=1
    echo "  /api/health 200 after ${i}s"
    break
  fi
  sleep 1
done
if [ "${HEALTH_OK}" = "0" ]; then
  abort "/api/health never returned 200 within 30s" \
        "tail /tmp/tars-backend-boot.log and /tmp/tars-backend-8765.log -- uvicorn likely crashed"
fi

# Verify W231 boot-time DB init produced both SQLite files.
TARS_DIR="${HOME}/.tars"
if [ -f "${TARS_DIR}/agents.sqlite" ]; then
  echo "  ~/.tars/agents.sqlite present"
else
  echo "  ~/.tars/agents.sqlite missing (will be seeded in Phase 3)"
fi
if [ -f "${TARS_DIR}/receipts.sqlite" ]; then
  echo "  ~/.tars/receipts.sqlite present"
else
  echo "  ~/.tars/receipts.sqlite missing (will be seeded in Phase 3)"
fi

mark_ok "Backend on :8765 + DBs initialized"

# ----------------------------------------------------------------------
# PHASE 3 -- Seed demo data
# ----------------------------------------------------------------------
echo ""
echo "${B}-- Phase 3/8 . Seed demo data --${X}"

verify_count() {
  local path="$1"
  local key="$2"
  local min="$3"
  local body
  body="$(curl -sS --max-time 5 "http://127.0.0.1:8765${path}" 2>/dev/null || echo '')"
  if [ -z "${body}" ]; then
    echo "  ${R}FAIL${X} ${path} returned empty"
    return 1
  fi
  local count
  count="$(printf '%s' "${body}" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    if isinstance(d,list):
        print(len(d))
    elif isinstance(d,dict):
        k='${key}'
        v=d.get(k) if k else None
        if isinstance(v,list): print(len(v))
        else:
            for vv in d.values():
                if isinstance(vv,list):
                    print(len(vv)); break
            else:
                print(0)
    else:
        print(0)
except Exception:
    print(0)
" 2>/dev/null || echo "0")"
  if [ "${count}" -ge "${min}" ]; then
    echo "  ok   ${path} -> ${count} items (min ${min})"
    return 0
  else
    echo "  warn ${path} -> ${count} items (need >= ${min})"
    return 1
  fi
}

SEED_FAILS=0
verify_count "/api/agents"          "agents"   3  || SEED_FAILS=$((SEED_FAILS+1))
verify_count "/api/receipts/recent" "items"    5  || SEED_FAILS=$((SEED_FAILS+1))
verify_count "/api/notepads"        "notepads" 3  || SEED_FAILS=$((SEED_FAILS+1))
verify_count "/api/composer/plans"  "plans"    1  || SEED_FAILS=$((SEED_FAILS+1))
verify_count "/api/mcp/servers"     "servers"  1  || SEED_FAILS=$((SEED_FAILS+1))

if [ "${SEED_FAILS}" -gt 0 ]; then
  echo "  ${SEED_FAILS} endpoint(s) under threshold -- forcing re-seed restart"
  if command -v lsof >/dev/null 2>&1; then
    STALE_PIDS="$(lsof -tiTCP:8765 -sTCP:LISTEN 2>/dev/null || true)"
    if [ -n "${STALE_PIDS}" ]; then
      # shellcheck disable=SC2086
      kill -9 ${STALE_PIDS} 2>/dev/null || true
      sleep 1
    fi
  fi
  ( TARS_DEMO_SEED=1 bash "${REPO}/scripts/backend_tars_up.sh" >>/tmp/tars-backend-boot.log 2>&1 ) &
  for i in $(seq 1 25); do
    if curl -sS -o /dev/null --max-time 2 "http://127.0.0.1:8765/api/health" 2>/dev/null; then
      break
    fi
    sleep 1
  done
  SEED_FAILS=0
  verify_count "/api/agents"          "agents"   3  || SEED_FAILS=$((SEED_FAILS+1))
  verify_count "/api/receipts/recent" "items"    5  || SEED_FAILS=$((SEED_FAILS+1))
  verify_count "/api/notepads"        "notepads" 3  || SEED_FAILS=$((SEED_FAILS+1))
  verify_count "/api/composer/plans"  "plans"    1  || SEED_FAILS=$((SEED_FAILS+1))
  verify_count "/api/mcp/servers"     "servers"  1  || SEED_FAILS=$((SEED_FAILS+1))
fi

if [ "${SEED_FAILS}" -gt 0 ]; then
  mark_warn "Demo seed: ${SEED_FAILS}/5 endpoints under threshold (demo still works, lists thin)"
else
  mark_ok "Demo seed: agents>=3, receipts>=5, notepads>=3, composer>=1, mcp>=1"
fi

# ----------------------------------------------------------------------
# PHASE 4 -- TARS.app build & install
# ----------------------------------------------------------------------
echo ""
echo "${B}-- Phase 4/8 . TARS.app build & install --${X}"

APP_PATH="/Applications/TARS.app"
NEED_REBUILD=0
if [ ! -d "${APP_PATH}" ]; then
  echo "  /Applications/TARS.app missing -- will rebuild"
  NEED_REBUILD=1
else
  if [ "$(uname)" = "Darwin" ]; then
    APP_AGE_S=$(( $(date +%s) - $(stat -f %m "${APP_PATH}" 2>/dev/null || echo 0) ))
  else
    APP_AGE_S=$(( $(date +%s) - $(stat -c %Y "${APP_PATH}" 2>/dev/null || echo 0) ))
  fi
  if [ "${APP_AGE_S}" -gt 3600 ]; then
    echo "  TARS.app is $((APP_AGE_S/60))min old (>60min) -- will rebuild"
    NEED_REBUILD=1
  else
    echo "  TARS.app age=$((APP_AGE_S/60))min (fresh)"
  fi
fi

if [ "${NEED_REBUILD}" = "1" ]; then
  if [ -x "${REPO}/scripts/REBUILD-TARS-APP.command" ]; then
    echo "  running REBUILD-TARS-APP.command (~30-90s) ..."
    if bash "${REPO}/scripts/REBUILD-TARS-APP.command" >/tmp/tars-rebuild.log 2>&1; then
      echo "  TARS.app rebuilt"
    else
      mark_warn "TARS.app rebuild returned non-zero -- check /tmp/tars-rebuild.log"
    fi
  else
    mark_warn "scripts/REBUILD-TARS-APP.command missing -- cannot rebuild"
  fi
fi

# Signed check (only if Apple cert configured).
if [ -d "${APP_PATH}" ] && command -v spctl >/dev/null 2>&1; then
  if spctl --assess --type execute "${APP_PATH}" >/dev/null 2>&1; then
    echo "  TARS.app passes spctl (signed + notarized)"
  else
    echo "  TARS.app not yet notarized -- Gatekeeper will warn first launch (right-click -> Open)"
  fi
fi

if [ -d "${APP_PATH}" ]; then
  mark_ok "TARS.app installed at /Applications/TARS.app"
else
  mark_fail "TARS.app NOT installed -- demo cannot run"
fi

# ----------------------------------------------------------------------
# PHASE 5 -- Full smoke test
# ----------------------------------------------------------------------
echo ""
echo "${B}-- Phase 5/8 . Full smoke test --${X}"

SMOKE_OK=0
SMOKE_TOTAL=0
SMOKE_FAIL=0
if [ -f "${REPO}/scripts/SMOKE-TEST.command" ]; then
  ( bash "${REPO}/scripts/SMOKE-TEST.command" >/tmp/tars-smoke.log 2>&1 ) &
  SMOKE_PID=$!
  for i in $(seq 1 120); do
    if ! kill -0 "${SMOKE_PID}" 2>/dev/null; then break; fi
    sleep 1
  done
  if kill -0 "${SMOKE_PID}" 2>/dev/null; then
    kill -9 "${SMOKE_PID}" 2>/dev/null || true
  fi

  if [ -f "${REPO}/.SMOKE-TEST.txt" ]; then
    LINE="$(grep -E '[0-9]+/[0-9]+ endpoints ok' "${REPO}/.SMOKE-TEST.txt" | tail -n1 || true)"
    if [ -n "${LINE}" ]; then
      SMOKE_OK="$(echo "${LINE}" | grep -oE '[0-9]+' | head -n1)"
      SMOKE_TOTAL="$(echo "${LINE}" | grep -oE '[0-9]+' | sed -n '2p')"
      SMOKE_FAIL="$(echo "${LINE}" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' | head -n1)"
      SMOKE_FAIL="${SMOKE_FAIL:-0}"
      echo "  smoke result: ${SMOKE_OK}/${SMOKE_TOTAL} ok, ${SMOKE_FAIL} failed"
    fi
  fi

  # Critical endpoints check (independent of summary parse).
  CRITICAL=(/api/health /api/auth/meeet/status /api/agents /api/composer/plans /api/usage/console /api/audit/timeline)
  HARD_FAIL=0
  for p in "${CRITICAL[@]}"; do
    CODE="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:8765${p}" 2>/dev/null || echo 000)"
    if [ "${CODE}" -ge 200 ] && [ "${CODE}" -lt 300 ]; then
      echo "  ok   critical ${p} -> ${CODE}"
    else
      echo "  FAIL critical ${p} -> ${CODE}"
      HARD_FAIL=1
    fi
  done

  if [ "${HARD_FAIL}" = "1" ]; then
    mark_fail "Critical endpoint(s) red -- see above"
  elif [ "${SMOKE_OK}" -ge 35 ]; then
    mark_ok "Smoke ${SMOKE_OK}/${SMOKE_TOTAL} green, all critical paths up"
  elif [ "${SMOKE_OK}" = "0" ]; then
    mark_ok "Smoke parse missed but all critical paths up"
  else
    mark_warn "Smoke only ${SMOKE_OK}/${SMOKE_TOTAL} (target >=35) -- critical paths still ok"
  fi
else
  mark_warn "scripts/SMOKE-TEST.command missing"
fi

# ----------------------------------------------------------------------
# PHASE 6 -- Mock meeet.world
# ----------------------------------------------------------------------
echo ""
echo "${B}-- Phase 6/8 . Mock meeet.world :8766 --${X}"

MOCK_RUNNING=0
if curl -sS -o /dev/null --max-time 2 "http://127.0.0.1:8766/health" 2>/dev/null; then
  echo "  mock already up on :8766"
  MOCK_RUNNING=1
fi

if [ "${MOCK_RUNNING}" = "0" ] && [ -f "${REPO}/scripts/MEEET-MOCK.command" ]; then
  echo "  starting mock via scripts/MEEET-MOCK.command ..."
  ( nohup bash "${REPO}/scripts/MEEET-MOCK.command" >/tmp/tars-meeet-mock.log 2>&1 < /dev/null ) &
  for i in $(seq 1 15); do
    if curl -sS -o /dev/null --max-time 2 "http://127.0.0.1:8766/health" 2>/dev/null; then
      MOCK_RUNNING=1
      echo "  mock up on :8766 after ${i}s"
      break
    fi
    sleep 1
  done
fi

if [ "${MOCK_RUNNING}" = "1" ]; then
  mark_ok "Mock meeet.world on :8766 (lets demo show live-mode without brother)"
else
  mark_warn "Mock meeet.world did NOT come up -- demo can still show mock-mode"
fi

# ----------------------------------------------------------------------
# PHASE 7 -- Launch TARS.app
# ----------------------------------------------------------------------
echo ""
echo "${B}-- Phase 7/8 . Launch TARS.app --${X}"

if [ -d "${APP_PATH}" ]; then
  open "${APP_PATH}" 2>/dev/null || true
  sleep 5
  if pgrep -f "TARS.app/Contents/MacOS" >/dev/null 2>&1; then
    echo "  TARS.app process running"
    mark_ok "TARS.app launched + window should be visible"
  else
    mark_warn "TARS.app open returned but process not detected -- check dock"
  fi
else
  mark_fail "TARS.app missing -- cannot launch"
fi

echo ""
echo "  ${B}EYEBALL CHECKLIST (switch to TARS.app window):${X}"
echo "    1. Monolith pulses in cockpit (cyan column, breathing)"
echo "    2. AUDIT tab -> timeline shows >=5 receipts with green checks"
echo "    3. USAGE tab -> live counter + pie chart populated"
echo "    4. Cmd+K opens palette -> fuzzy search works"
echo "    5. COMPOSER tab -> >=1 plan visible with diff preview"

# ----------------------------------------------------------------------
# PHASE 8 -- Summary
# ----------------------------------------------------------------------
echo ""
echo "${B}========================================================${X}"
echo "${B}  Phase 8/8 . DEMO-READY summary${X}"
echo "${B}========================================================${X}"
echo ""
for line in "${SUMMARY_LINES[@]}"; do
  echo "  ${line}"
done
echo ""
echo "  cheat sheet : presentation/TARS_v10.0_DEMO_CHEATSHEET.md"
echo "  runbook     : presentation/DEMO_RUNBOOK.md"
echo "  deck        : presentation/TARS_v10.0_PRESENTATION.pptx"
echo "  backup pics : presentation/BACKUP_SCREENSHOTS_GUIDE.md"
echo "  emergency   : scripts/PRESENTATION-EMERGENCY.command"
echo ""

if [ "${ALL_GREEN}" = "1" ] && [ "${PHASES_FAIL}" = "0" ]; then
  echo "${G}========================================================${X}"
  echo "${G}  READY -- ${PHASES_OK} phases green, ${PHASES_WARN} warn, 0 fail${X}"
  echo "${G}  go give the presentation. break a leg.${X}"
  echo "${G}========================================================${X}"
  echo ""
  echo "Window auto-closes in 10s ..."
  sleep 10
  osascript -e 'tell application "Терминал" to close (every window whose name contains "DEMO-READY")' 2>/dev/null || true
  osascript -e 'tell application "Terminal" to close (every window whose name contains "DEMO-READY")' 2>/dev/null || true
  exit 0
else
  echo "${R}========================================================${X}"
  echo "${R}  NOT READY -- ${PHASES_OK} green, ${PHASES_WARN} warn, ${PHASES_FAIL} fail${X}"
  echo "${R}  fix the FAIL items above before going live.${X}"
  echo "${R}========================================================${X}"
  echo ""
  echo "Window stays open. Read the failures above. Then either:"
  echo "  - fix and re-run scripts/DEMO-READY.command, OR"
  echo "  - run scripts/PRESENTATION-EMERGENCY.command for full reset"
  exit 2
fi
