#!/usr/bin/env bash
# fix-all-warns.command — close the 3 WARNs on the doctor dashboard.
#
# 1. POST /api/doctor/fix/vault   → creates ~/.tars/vault
# 2. python -m backend.core.daemon --install → LaunchAgent → daemon writes heartbeat
# 3. Restart uvicorn so TARS_SCHEDULER_ENABLED=1 (already in .env) takes effect
#
# All output to .fix-all-warns.txt for sandbox verification.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.fix-all-warns.txt"
PORT="${PORT:-8765}"

{
  echo "=== fix-all-warns at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""
  echo "── step 1/3: POST /api/doctor/fix/vault ──"
  curl -sS -X POST "http://127.0.0.1:${PORT}/api/doctor/fix/vault" \
    -H 'Content-Type: application/json' | head -40
  echo ""
  echo ""
  echo "── step 2/3: install tars-daemon LaunchAgent ──"
  export PYTHONPATH="$(pwd)"
  ./.venv/bin/python -m backend.core.daemon --install 2>&1 | head -30
  echo ""
  echo "Waiting 6s for daemon first tick…"
  sleep 6
  echo ""
  echo "── step 3/3: restart backend (TARS_SCHEDULER_ENABLED=1 in .env) ──"
  bash scripts/backend_tars_up.sh 2>&1 | tail -20
  echo ""
  echo "── final summary GET /api/doctor?format=json (counts only) ──"
  curl -sS "http://127.0.0.1:${PORT}/api/doctor?format=json" 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin); \
        c={'ok':0,'warn':0,'fail':0,'skip':0}; \
        [c.__setitem__(r['status'], c[r['status']]+1) for r in d]; \
        print('Counts:', c); \
        [print(f\"  {r['slug']}: {r['status']} — {r.get('summary','')}\") for r in d]"
  echo ""
  echo "=== DONE ==="
} > "$OUT" 2>&1

sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "fix-all-warns")' 2>/dev/null || true
