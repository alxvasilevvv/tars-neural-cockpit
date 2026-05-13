#!/usr/bin/env bash
# test-categories.command — run pytest by category for faster diagnostic.
# Kills any hung previous pytest first.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.test-results-full.txt"
export PYTHONPATH="$(pwd)"
export PYTEST_DONT_REWRITE=1

# Kill any hung pytest from prior run.
pkill -9 -f "pytest tests/" 2>/dev/null || true
sleep 1

set -a
[ -f .env ] && source .env
set +a

# Disable network-heavy tests via env vars (tests use these guards).
export MEEET_MODE=mock
export TARS_TESTING=1
export TARS_DOCTOR_DAEMON_HEARTBEAT_TIMEOUT_S=2
export PYTHONUNBUFFERED=1
unset ANTHROPIC_API_KEY  # forces tests to use mock client paths
unset OPENAI_API_KEY

run_cat() {
  local name="$1"
  local pattern="$2"
  local start=$(date +%s)
  local outfile="/tmp/test-$name.log"

  echo ""
  echo "── [$name] starting ──"
  ./.venv/bin/pytest $pattern \
    --tb=line \
    -q \
    --no-header \
    --color=no \
    -x \
    -o "addopts=" \
    2>&1 | tail -50 > "$outfile" &
  local PID=$!

  # 60s hard limit per category via background kill
  ( sleep 60 && kill -9 $PID 2>/dev/null ) &
  local KILLER=$!

  wait $PID 2>/dev/null
  local rc=$?
  kill $KILLER 2>/dev/null

  local end=$(date +%s)
  local elapsed=$((end - start))
  echo "── [$name] done rc=$rc in ${elapsed}s ──"
  tail -20 "$outfile"
}

{
  echo "=== test-categories start at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""
  ./.venv/bin/python --version
  echo "PYTHONPATH: $PYTHONPATH"
  echo "MEEET_MODE: $MEEET_MODE"
  echo ""

  # Quick wins (no network, no slow IO)
  run_cat "doctor"        "tests/test_doctor.py"
  run_cat "doctor_fixers" "tests/test_doctor_fixers.py"
  run_cat "doctor_router" "tests/test_doctor_router.py"
  run_cat "daemon"        "tests/test_daemon.py"
  run_cat "clone_sync"    "tests/test_clone_sync.py"
  run_cat "notifications" "tests/test_imessage.py tests/test_telegram_notify.py tests/test_email_notify.py tests/test_fanout_all.py"
  run_cat "billing"       "tests/test_meeet_billing_usage.py"
  run_cat "cowork"        "tests/test_cowork_*.py"
  run_cat "mcp"           "tests/test_mcp_*.py"
  run_cat "receipts"      "tests/test_receipts_*.py"
  run_cat "voice"         "tests/test_voice_*.py"
  run_cat "supervisor"    "tests/test_supervisor*.py"
  run_cat "marketplace"   "tests/test_marketplace*.py"

  echo ""
  echo "=== DONE ==="
} > "$OUT" 2>&1

sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "test-categories")' 2>/dev/null || true
