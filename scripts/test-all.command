#!/usr/bin/env bash
# test-all.command — run the full pytest suite on Alien's Mac via .venv.
#
# Captures:
#   - per-category counts (passed/failed/skipped/errors)
#   - first 30 lines of failures for triage
#   - total wall-time
# Writes to .test-results-full.txt for sandbox to read back.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.test-results-full.txt"
export PYTHONPATH="$(pwd)"

# Load .env for any test that touches env-keyed config.
set -a
[ -f .env ] && source .env
set +a

START=$(date -u +%s)

{
  echo "=== test-all start at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""
  echo "── env summary ──"
  ./.venv/bin/python --version
  ./.venv/bin/pip show pytest 2>/dev/null | head -2
  echo "PYTHONPATH: $PYTHONPATH"
  TOTAL_TESTS=$(find tests/ -name "test_*.py" -type f | wc -l | tr -d ' ')
  echo "Test files: $TOTAL_TESTS"
  echo ""
  echo "── running pytest --tb=short ──"
  echo ""

  # Run the full suite. -q for quiet (less verbose), --tb=short for short traces.
  # pytest itself has --timeout if pytest-timeout installed; otherwise rely on
  # individual test asyncio.timeout()s.
  ./.venv/bin/pytest tests/ \
    --tb=short \
    -q \
    --no-header \
    --color=no \
    2>&1 | tee /tmp/test-all-raw.txt | tail -200

  RC=${PIPESTATUS[0]}
  END=$(date -u +%s)
  ELAPSED=$((END - START))

  echo ""
  echo "── summary ──"
  echo "Exit code: $RC"
  echo "Wall time: ${ELAPSED}s"
  echo ""
  # Extract counts from pytest output (e.g. "5 passed, 3 failed, 2 skipped")
  grep -E "(passed|failed|error|skipped|warning)" /tmp/test-all-raw.txt | tail -5
  echo ""
  echo "── any FAILED tests (first 40) ──"
  grep "^FAILED" /tmp/test-all-raw.txt | head -40
  echo ""
  echo "── any ERROR tests (first 30) ──"
  grep "^ERROR" /tmp/test-all-raw.txt | head -30
  echo ""
  echo "=== DONE ==="
} > "$OUT" 2>&1

sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "test-all")' 2>/dev/null || true
