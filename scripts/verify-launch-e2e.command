#!/usr/bin/env bash
# verify-launch-e2e.command — full post-launch verification.
#
# Double-click in Finder → opens Terminal → runs full sweep →
# writes to .verify-launch-e2e.txt next to itself.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.verify-launch-e2e.txt"

# Run everything, redirect all output to the file (no shell-history pollution).
{
  echo "=== verify-launch-e2e run at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""

  echo "[1] /api/product/version"
  curl -s --max-time 8 https://tars.meeet.world/api/product/version
  echo ""
  echo ""

  echo "[2] /api/product/downloads"
  curl -s --max-time 8 https://tars.meeet.world/api/product/downloads | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'product={d.get(\"product\")} version=({d.get(\"releases\",[{}])[0].get(\"version\")})')
artifacts = d.get('releases',[{}])[0].get('artifacts', [])
print(f'  {len(artifacts)} artifacts:')
for a in artifacts:
    print(f'    {a.get(\"os\"):>7} {a.get(\"arch\"):>7} {a.get(\"kind\"):>9} {a.get(\"filename\")}')
" 2>&1
  echo ""

  echo "[3] All 6 /dl/ artifact URLs"
  for f in \
    "TARS_9.1.0_aarch64.dmg" \
    "TARS_9.1.0_x64.dmg" \
    "TARS_9.1.0_amd64.AppImage" \
    "TARS_9.1.0_amd64.deb" \
    "TARS_9.1.0_x64-setup.exe" \
    "TARS_9.1.0_x64_en-US.msi"; do
    code=$(curl -sI --max-time 8 "https://tars.meeet.world/dl/$f" | head -1 | awk '{print $2}')
    if [ "$code" = "200" ] || [ "$code" = "302" ]; then
      echo "  ✓ $f → HTTP $code"
    else
      echo "  ✗ $f → HTTP $code (expected 200 or 302)"
    fi
  done
  echo ""

  echo "[4] /install.sh availability"
  ct=$(curl -sI --max-time 8 https://tars.meeet.world/install.sh | grep -i "^content-type:" | head -1 | tr -d '\r')
  hdr=$(curl -sI --max-time 8 https://tars.meeet.world/install.sh | head -1 | tr -d '\r')
  echo "  $hdr"
  echo "  $ct"
  first=$(curl -s --max-time 8 https://tars.meeet.world/install.sh | head -1)
  echo "  first line: $first"
  echo ""

  echo "[5] Vitest in experiments/neural-showcase-v3"
  if [ -f experiments/neural-showcase-v3/node_modules/.bin/vitest ]; then
    cd experiments/neural-showcase-v3 && ./node_modules/.bin/vitest run 2>&1 | tail -20
    cd ../..
  else
    echo "  (node_modules absent — run 'cd experiments/neural-showcase-v3 && npm install' first)"
  fi
  echo ""

  echo "[6] Cowork pytest sweep"
  python3 -m unittest tests.test_cowork_store tests.test_cowork_presence tests.test_cowork_edge_cases 2>&1 | tail -3
  echo ""

  echo "[7] Git state"
  echo "  HEAD: $(git rev-parse --short HEAD) — $(git log -1 --pretty=%s)"
  echo "  ahead of origin/main: $(git rev-list --count origin/main..HEAD)"
  echo "  status: $(git status --short | head -3)"
  echo ""

  echo "=== DONE ==="
} > "$OUT" 2>&1

echo "Output written to: $OUT"
echo "Closing in 3 seconds..."
sleep 3
