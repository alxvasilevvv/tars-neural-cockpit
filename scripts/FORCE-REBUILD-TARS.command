#!/usr/bin/env bash
# FORCE-REBUILD-TARS.command — W291
#
# Full rebuild + bring TARS to a working demo state:
#   1. Force Rust recompile (touch main.rs)
#   2. Start backend on :8765 if not already up (with .env vars)
#   3. Clear WKWebView localStorage so the welcome greeting fires
#   4. Build + install + launch /Applications/TARS.app

set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO="$(pwd)"

echo "=== FORCE-REBUILD-TARS at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "repo: $REPO"
echo ""

# ── 1. Force Rust recompile ─────────────────────────────────────────────
echo "── force Rust recompile: touch src/main.rs ──"
touch "${REPO}/desktop/src-tauri/src/main.rs"
echo "    ✓ touched"
echo ""

# ── 2. Make sure backend is running with ElevenLabs (start if not, OR restart if key not loaded) ────
echo "── ensure backend on :8765 with ElevenLabs active ──"
BE_UP=0
ELN_UP=0
HEALTH="$(curl -sS --max-time 2 http://127.0.0.1:8765/api/a11y/health 2>/dev/null)"
if [ -n "$HEALTH" ]; then
  BE_UP=1
  ELN_UP=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(1 if d.get('capabilities',{}).get('tts_cloud_elevenlabs') else 0)" 2>/dev/null || echo 0)
  if [ "$ELN_UP" = "1" ]; then
    echo "    ✓ already running with ElevenLabs"
  else
    echo "    backend up but ElevenLabs NOT loaded — killing for restart"
    if command -v lsof >/dev/null 2>&1; then
      PIDS="$(lsof -tiTCP:8765 -sTCP:LISTEN 2>/dev/null || true)"
      [ -n "$PIDS" ] && kill -9 $PIDS 2>/dev/null && sleep 2
    fi
    BE_UP=0
  fi
else
  echo "    backend down — starting it"
fi

if [ $BE_UP -eq 0 ]; then
  # Find Python
  PY="${REPO}/.venv/bin/python"
  if [ ! -x "$PY" ]; then PY="$(command -v python3 || true)"; fi
  if [ -z "${PY:-}" ] || [ ! -x "$PY" ]; then
    echo "    ✗ no python found — backend can't start automatically"
    echo "      run scripts/FINAL-DEMO-READY.command manually"
  else
    # Export .env into the child env, line by line (bulletproof, no source magic)
    while IFS= read -r LINE; do
      CLEAN="${LINE#"${LINE%%[![:space:]]*}"}"
      [[ -z "$CLEAN" || "$CLEAN" == \#* ]] && continue
      if [[ "$CLEAN" =~ ^[A-Z_][A-Z0-9_]*= ]]; then
        KEY="${CLEAN%%=*}"
        VAL="${CLEAN#*=}"
        VAL="${VAL#\"}"; VAL="${VAL%\"}"
        VAL="${VAL#\'}"; VAL="${VAL%\'}"
        export "${KEY}=${VAL}"
      fi
    done < "${REPO}/.env" 2>/dev/null || true

    # Also start meeet mock on :8766 if needed (auth flow needs it)
    if ! curl -sS --max-time 1 http://127.0.0.1:8766/health >/dev/null 2>&1; then
      echo "    starting meeet mock on :8766"
      PYTHONPATH="${REPO}" nohup "$PY" -m uvicorn scripts.meeet_mock.server:app \
        --host 127.0.0.1 --port 8766 \
        > "${REPO}/.MEEET-MOCK.txt" 2>&1 &
      sleep 2
    fi

    echo "    starting tars backend on :8765"
    nohup "$PY" -m uvicorn web_extras.app:app \
      --host 127.0.0.1 --port 8765 \
      > "${REPO}/.TARS-BACKEND.txt" 2>&1 &
    # Wait up to 10s for it to come up.
    for i in 1 2 3 4 5 6 7 8 9 10; do
      sleep 1
      if curl -sS --max-time 1 http://127.0.0.1:8765/api/a11y/health >/dev/null 2>&1; then
        echo "    ✓ backend up after ${i}s"
        BE_UP=1
        break
      fi
    done
    if [ $BE_UP -eq 0 ]; then
      echo "    ✗ backend didn't come up in 10s — see .TARS-BACKEND.txt"
    fi
  fi
fi

# Verify ElevenLabs is active
if [ $BE_UP -eq 1 ]; then
  ELN="$(curl -sS --max-time 3 http://127.0.0.1:8765/api/a11y/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if d.get('capabilities',{}).get('tts_cloud_elevenlabs') else 'no')" 2>/dev/null || echo 'unknown')"
  echo "    ElevenLabs active: $ELN"
fi
echo ""

# ── 3. Clear WKWebView localStorage so greeting fires on launch ─────────
WK_LS="$HOME/Library/Containers/world.meeet.tars/Data/Library/WebKit/WebsiteData/LocalStorage"
echo "── clear WKWebView localStorage (welcome greeting fires fresh) ──"
if [ -d "$WK_LS" ]; then
  rm -f "$WK_LS"/*.localstorage* 2>/dev/null || true
  echo "    ✓ cleared $WK_LS"
else
  echo "    (no container yet — first launch, nothing to clear)"
fi
echo ""

# ── 4. Delegate to REBUILD-TARS-APP.command ─────────────────────────────
echo "── delegate to REBUILD-TARS-APP.command ──"
bash "${REPO}/scripts/REBUILD-TARS-APP.command"
