#!/usr/bin/env bash
# probe-meeet-billing.command — verify the meeet billing usage path end-to-end.
#
# Posts a $0.001 delta via post_operator_usage_delta() with the current
# BRIDGE_SHARED_SECRET. Reports:
#   - is_remote_billing_configured() result
#   - actual HTTP response from the meeet edge function
#
# Use after brother completes A1 (BRIDGE_SHARED_SECRET on Supabase).
# Before A1 → expect 401 / non-200. After A1 → expect 200 OK.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.probe-meeet-billing.txt"
export PYTHONPATH="$(pwd)"

# Load .env into shell so the python child inherits MEEET_* + BRIDGE_*
set -a
[ -f .env ] && source .env
set +a

{
  echo "=== probe-meeet-billing at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""
  echo "── env summary ──"
  echo "TARS_BILLING_SOURCE: ${TARS_BILLING_SOURCE:-(unset)}"
  echo "MEEET_BILLING_BASE_URL: ${MEEET_BILLING_BASE_URL:-(unset)}"
  echo "MEEET_BILLING_API_KEY: $(echo "${MEEET_BILLING_API_KEY:-}" | sed 's/./*/g' | head -c 8)…"
  echo "BRIDGE_SHARED_SECRET: $(echo "${BRIDGE_SHARED_SECRET:-}" | head -c 8)…$(echo "${BRIDGE_SHARED_SECRET:-}" | tail -c 5)"
  echo ""
  echo "── probe: post_operator_usage_delta(0.001) ──"
  ./.venv/bin/python -c "
import asyncio
import sys
from backend.core.meeet_billing.client import (
    is_remote_billing_configured,
    post_operator_usage_delta,
)

async def main():
    print('is_remote_billing_configured:', is_remote_billing_configured())
    result = await post_operator_usage_delta(0.001, trace_id='probe-w196-end-to-end')
    print('response:', result)
    return 0 if result.get('ok') else 1

sys.exit(asyncio.run(main()))
"
  echo ""
  echo "=== DONE ==="
} > "$OUT" 2>&1

sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "probe-meeet-billing")' 2>/dev/null || true
