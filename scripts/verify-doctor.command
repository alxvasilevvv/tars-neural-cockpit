#!/usr/bin/env bash
# verify-doctor.command — query /api/doctor and write summary to disk.
cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.verify-doctor.txt"
PORT="${PORT:-8765}"

{
  echo "=== verify-doctor at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""
  RESPONSE=$(curl -sS "http://127.0.0.1:${PORT}/api/doctor?format=json" 2>&1)
  # Try to parse — the endpoint may return either a list or {results:[...]}
  echo "$RESPONSE" | python3 -c "
import json, sys
raw = sys.stdin.read()
try:
    d = json.loads(raw)
except json.JSONDecodeError as e:
    print('JSON parse failed:', e)
    print('Raw:', raw[:500])
    sys.exit(1)
rows = d if isinstance(d, list) else d.get('results', d.get('checks', []))
counts = {'ok':0, 'warn':0, 'fail':0, 'skip':0}
for r in rows:
    s = r.get('status', '?')
    counts[s] = counts.get(s, 0) + 1
print('Counts:', counts)
print('Total:', sum(counts.values()))
print()
for r in rows:
    slug = r.get('slug', '?')
    status = r.get('status', '?').upper()
    summary = r.get('summary', '')[:80]
    print(f'  {status:4} {slug:18} — {summary}')
"
  echo ""
  echo "=== DONE ==="
} > "$OUT" 2>&1

sleep 1
osascript -e 'tell application "Терминал" to close (every window whose name contains "verify-doctor")' 2>/dev/null || true
