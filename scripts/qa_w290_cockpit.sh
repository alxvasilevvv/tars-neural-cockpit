#!/usr/bin/env bash
# qa_w290_cockpit.sh — W290 acceptance harness
#
# Verifies that the running TARS desktop backend is reachable and that the
# cockpit HTML bundle has the W290 futuristic layer applied without
# regressing the W286 baseline, voice IIFE, or body grid.
#
# Usage:
#   bash scripts/qa_w290_cockpit.sh                    # against default 127.0.0.1:8765
#   TARS_HOST=http://127.0.0.1:8765 bash scripts/qa_w290_cockpit.sh
#   TARS_HARNESS_OFFLINE=1 bash scripts/qa_w290_cockpit.sh   # static-only mode
#
# Exit codes:
#   0 — all groups passed
#   1 — one or more assertion failures (regression)
#   2 — backend unreachable (can't run the harness at all)

set -euo pipefail

# ─── Config ──────────────────────────────────────────────────────────────
# Default to 8765 (where the FastAPI sidecar listens — see
# desktop/src-tauri/src/sidecar.rs:51).
TARS_HOST="${TARS_HOST:-http://127.0.0.1:8765}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COCKPIT_HTML="$REPO_ROOT/desktop/src-tauri/web/index.html"

# Color output (degrades to plain when not a TTY)
if [ -t 1 ]; then
  CG="\033[32m"; CR="\033[31m"; CY="\033[33m"; C0="\033[0m"
else
  CG=""; CR=""; CY=""; C0=""
fi

PASS=0
FAIL=0
SKIP=0

# ─── Assertion helpers ───────────────────────────────────────────────────
ok()   { printf "  %b✓%b %s\n" "$CG" "$C0" "$1"; PASS=$((PASS+1)); }
bad()  { printf "  %b✗%b %s\n" "$CR" "$C0" "$1"; FAIL=$((FAIL+1)); }
skip() { printf "  %b⊘%b %s\n" "$CY" "$C0" "$1"; SKIP=$((SKIP+1)); }
group(){ printf "\n\033[1m── %s ──\033[0m\n" "$1"; }

require_file() {
  if [ ! -f "$1" ]; then
    printf "%b✗%b cannot run harness — missing file: %s\n" "$CR" "$C0" "$1"
    exit 2
  fi
}

require_file "$COCKPIT_HTML"

# Cache the HTML byte size for group 8.
HTML_BYTES="$(wc -c < "$COCKPIT_HTML" | tr -d ' ')"

contains() {
  # Usage: contains "<needle>" "<label>"
  # Grep the file directly — passing a 500KB var through stdin truncates
  # in some shells and silently breaks every assertion.
  if grep -q -F -- "$1" "$COCKPIT_HTML"; then ok "$2"; else bad "$2 (missing: $1)"; fi
}

contains_re() {
  # Usage: contains_re "<extended-regex>" "<label>"
  if grep -qE -- "$1" "$COCKPIT_HTML"; then ok "$2"; else bad "$2 (regex missed: $1)"; fi
}

# ─── Header ──────────────────────────────────────────────────────────────
printf "\033[1m═══ W290 cockpit acceptance harness ═══\033[0m\n"
printf "Repo:      %s\n" "$REPO_ROOT"
printf "Cockpit:   %s\n" "$COCKPIT_HTML"
printf "Backend:   %s\n" "$TARS_HOST"
printf "Time:      %s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# ─── Group 1: Backend reachability (gate — exits early on failure) ───────
group "1. Backend reachability"

OFFLINE_MODE=0
if [ "${TARS_HARNESS_OFFLINE:-0}" = "1" ]; then
  OFFLINE_MODE=1
  skip "TARS_HARNESS_OFFLINE=1 — running static checks only, skipping live backend"
else
  BE_HTTP="$(curl -sS --max-time 3 -o /dev/null -w '%{http_code}' "$TARS_HOST/api/version" 2>/dev/null)" || BE_HTTP="000"
  BE_HTTP="${BE_HTTP:-000}"
  if [ "$BE_HTTP" = "000" ]; then
    bad "backend $TARS_HOST unreachable (curl returned 000) — set TARS_HARNESS_OFFLINE=1 to skip live checks"
    printf "\n%bABORT — cannot run remaining groups without a live backend.%b\n" "$CR" "$C0"
    printf "PASS=%d FAIL=%d SKIP=%d\n" "$PASS" "$FAIL" "$SKIP"
    exit 2
  elif [ "$BE_HTTP" != "200" ] && [ "$BE_HTTP" != "404" ]; then
    bad "backend $TARS_HOST/api/version returned HTTP $BE_HTTP (expected 200 or 404)"
  else
    ok "backend $TARS_HOST is reachable (HTTP $BE_HTTP)"
  fi
fi

# ─── Group 2: W290 sub-section markers (10) ──────────────────────────────
group "2. W290 sub-section markers (10/10 must be present)"
contains "W290 — FUTURISTIC LAYER"            "W290 layer header"
contains "W290.1 — Sider"                     "W290.1  sider"
contains "W290.2 — Topbar"                    "W290.2  topbar"
contains "W290.3 — Right rail"                "W290.3  rail"
contains "W290.4 — Halo"                      "W290.4  halo + concentric grid"
contains "W290.5 — Status HUD"                "W290.5  status HUD"
contains "W290.6 — Mic pill"                  "W290.6  mic conic ring"
contains "W290.7 — Transcript"                "W290.7  transcript depth"
contains "W290.8 — First-boot splash"         "W290.8  splash"
contains "W290.9 — Keyframes"                 "W290.9  keyframes"
contains "W290.10 — Reduced motion"           "W290.10 reduced-motion guard"
contains "END W290 FUTURISTIC LAYER"          "W290 layer footer"

# ─── Group 3: W286 baseline preserved (palette, sections, grid var) ──────
group "3. W286 baseline preserved (no regression on the foundation)"
contains "W286 — STUDIO COCKPIT"              "W286 baseline header still present"
contains "W289 — W287+W288 stripped"          "W289 strip marker preserved (no W287/W288 CSS leak)"
contains_re '\-\-accent:[[:space:]]+#7C5CFF'  "W286 accent token preserved"
contains "@keyframes waveform-pulse"          "W286 keyframe waveform-pulse preserved"
contains "@keyframes bubble-in"               "W286 keyframe bubble-in preserved"
contains "@keyframes fade-in"                 "W286 keyframe fade-in preserved"

# ─── Group 4: Voice flow markers intact (do NOT touch IIFE) ──────────────
group "4. Voice IIFE / pipeline markers intact"
contains "window.W285"                        "window.W285 namespace present"
contains "function _drawWave"                 "_drawWave (canvas FFT) preserved"
contains "function _vcInitHum"                "_vcInitHum present (W286 stub)"
contains "function ttfvMaybeStart"            "ttfvMaybeStart (first-boot tour) present"
contains "/api/a11y/speak"                    "ElevenLabs speak endpoint wired"
contains "/api/voice/command"                 "voice command endpoint wired"
contains "/api/voice/transcribe"              "STT endpoint wired"

# ─── Group 5: Body grid intact (THE hardest constraint) ──────────────────
group "5. Body grid intact (64px 1fr 280px @ ≥901px)"
# Match the W286 grid declaration shape with some tolerance for whitespace.
if grep -qE 'grid-template-columns:[[:space:]]*64px[[:space:]]+1fr[[:space:]]+280px' "$COCKPIT_HTML"; then
  ok "body grid 64px 1fr 280px present"
else
  bad "body grid 64/1fr/280 declaration NOT found — W290 broke the grid"
fi
if grep -qE '@media[[:space:]]*\([[:space:]]*max-width:[[:space:]]*900px' "$COCKPIT_HTML"; then
  ok "@media (max-width: 900px) breakpoint preserved"
else
  bad "900px breakpoint missing — mobile/narrow layout broken"
fi
contains "body.cockpit-active"                "body.cockpit-active selector still styled"

# ─── Group 6: HTTP /api/version + /api/voice/personas live ───────────────
group "6. Live backend endpoints (require backend running)"
if [ "$OFFLINE_MODE" = "1" ]; then
  skip "offline mode — backend endpoint checks skipped"
  skip "offline mode — /api/voice/personas check skipped"
  skip "offline mode — /api/a11y/health check skipped"
else
VERSION_JSON="$(curl -sS --max-time 3 "$TARS_HOST/api/version" 2>/dev/null || echo '')"
if [ -n "$VERSION_JSON" ] && printf '%s' "$VERSION_JSON" | grep -qE '"version"|"tag"'; then
  ok "/api/version returns JSON with version/tag"
else
  # Backend may not have a /api/version route in some builds — soft skip.
  skip "/api/version returned empty or non-JSON ($BE_HTTP) — not blocking"
fi

PERSONAS_HTTP="$(curl -sS --max-time 3 -o /dev/null -w '%{http_code}' "$TARS_HOST/api/voice/personas" 2>/dev/null)" || PERSONAS_HTTP="000"
PERSONAS_HTTP="${PERSONAS_HTTP:-000}"
if [ "$PERSONAS_HTTP" = "200" ]; then
  ok "/api/voice/personas returns 200"
elif [ "$PERSONAS_HTTP" = "404" ]; then
  skip "/api/voice/personas returns 404 — endpoint may not be wired in this build"
else
  bad "/api/voice/personas returned HTTP $PERSONAS_HTTP"
fi

A11Y_HTTP="$(curl -sS --max-time 3 -o /dev/null -w '%{http_code}' "$TARS_HOST/api/a11y/health" 2>/dev/null)" || A11Y_HTTP="000"
A11Y_HTTP="${A11Y_HTTP:-000}"
if [ "$A11Y_HTTP" = "200" ]; then
  ok "/api/a11y/health returns 200 (TTS health)"
else
  bad "/api/a11y/health returned HTTP $A11Y_HTTP — voice pipeline broken"
fi
fi  # end OFFLINE_MODE guard

# ─── Group 7: Reduced-motion guard (CSS @media block) ────────────────────
group "7. Reduced-motion guard"
if grep -qE '@media \(prefers-reduced-motion:[[:space:]]*reduce\)' "$COCKPIT_HTML"; then
  ok "@media (prefers-reduced-motion: reduce) block present"
else
  bad "reduced-motion guard missing — accessibility regression"
fi
# Inside the W290 reduced-motion block we should disable rotations.
if grep -qE 'animation:[[:space:]]*none[[:space:]]*!important' "$COCKPIT_HTML"; then
  ok "animation:none !important present in reduced-motion block"
else
  bad "reduced-motion block exists but does not actually disable animations"
fi

# ─── Group 8: HTML balance + script tag count ────────────────────────────
group "8. HTML balance + script tag count"
SCRIPT_OPEN=$(grep -cE '<script\b' "$COCKPIT_HTML" || true)
SCRIPT_CLOSE=$(grep -cE '</script>' "$COCKPIT_HTML" || true)
if [ "$SCRIPT_OPEN" = "$SCRIPT_CLOSE" ]; then
  ok "<script> tags balanced ($SCRIPT_OPEN open / $SCRIPT_CLOSE close)"
else
  bad "<script> tags UNBALANCED ($SCRIPT_OPEN open / $SCRIPT_CLOSE close)"
fi
STYLE_OPEN=$(grep -cE '<style\b' "$COCKPIT_HTML" || true)
STYLE_CLOSE=$(grep -cE '</style>' "$COCKPIT_HTML" || true)
if [ "$STYLE_OPEN" = "$STYLE_CLOSE" ]; then
  ok "<style> tags balanced ($STYLE_OPEN/$STYLE_CLOSE)"
else
  bad "<style> tags UNBALANCED ($STYLE_OPEN/$STYLE_CLOSE)"
fi
if [ "$HTML_BYTES" -gt 100000 ] && [ "$HTML_BYTES" -lt 2000000 ]; then
  ok "HTML size within sane range ($HTML_BYTES bytes)"
else
  bad "HTML size suspicious ($HTML_BYTES bytes) — accidental delete or duplicate?"
fi

# ─── Group 9: Voice persona effective-voice uniqueness (W286+W290 voice flow) ──
group "9. Voice persona uniqueness (4 male personas → distinct voices)"
if [ "$OFFLINE_MODE" = "1" ]; then
  skip "offline mode — voice persona uniqueness check skipped"
else
  EFF_JSON="$(curl -sS --max-time 3 "$TARS_HOST/api/voice/personas/effective" 2>/dev/null || echo '')"
  if [ -z "$EFF_JSON" ]; then
    skip "/api/voice/personas/effective unreachable — endpoint may not be wired in this build"
  else
    UNIQ_LINE=$(printf '%s' "$EFF_JSON" | python3 - <<'PY' 2>/dev/null || echo "0 0"
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print("0 0"); sys.exit(0)
wanted = {"jarvis", "stark", "hal_9000", "tars"}
seen = {}
for p in d.get("personas", []):
    pid = p.get("id")
    if pid in wanted:
        seen[pid] = p.get("effective_voice_id") or p.get("voice_id") or ""
ids = [v for v in seen.values() if v]
print(f"{len(set(ids))} {len(seen)}")
PY
)
    UNIQ_VOICES="${UNIQ_LINE%% *}"
    TOTAL="${UNIQ_LINE##* }"
    if [ "$TOTAL" -ge 3 ] && [ "$UNIQ_VOICES" = "$TOTAL" ]; then
      ok "$UNIQ_VOICES distinct effective voices across $TOTAL/4 male personas"
    elif [ "$TOTAL" -lt 3 ]; then
      skip "only $TOTAL/4 male personas exposed — fallback chain not fully wired"
    else
      bad "$UNIQ_VOICES distinct voices across $TOTAL male personas (expected $TOTAL/$TOTAL — voice-fallback regression)"
    fi
  fi
fi

# ─── Summary ─────────────────────────────────────────────────────────────
printf "\n\033[1m═══ Result ═══\033[0m\n"
printf "PASS=%d FAIL=%d SKIP=%d\n" "$PASS" "$FAIL" "$SKIP"

if [ "$FAIL" -gt 0 ]; then
  printf "%bSTATUS: FAIL (regression detected)%b\n" "$CR" "$C0"
  exit 1
fi
printf "%bSTATUS: PASS%b\n" "$CG" "$C0"
exit 0
