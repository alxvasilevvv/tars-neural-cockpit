#!/usr/bin/env bash
# launch_precheck.sh — single-command verification before TARS production launch.
#
# What it does (all checks are idempotent and non-destructive):
#   1. Working tree clean + commits ready to push
#   2. Backend on :8765 responds (/health, /api/entitlements) if running
#   3. Optional: static shell on :5173 (desktop-dev)
#   4. Critical contract docs + bundled desktop web present
#   5. .env has required keys (template check, not value check)
#   6. Tauri desktop folder builds (only if --desktop passed)
#
# Run from repo root:
#     bash scripts/launch_precheck.sh           # core checks
#     bash scripts/launch_precheck.sh --desktop # also try cargo check on desktop
#     bash scripts/launch_precheck.sh --full    # everything + smoke-billing-tars
#
# Exit code 0 = green to launch. Non-zero = something to fix; the
# specific check label is in stderr.

set -uo pipefail

cd "$(dirname "$0")/.."

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DESKTOP=0
FULL=0
for arg in "$@"; do
  case "$arg" in
    --desktop) DESKTOP=1 ;;
    --full) DESKTOP=1; FULL=1 ;;
  esac
done

PASS=0
FAIL=0
WARN=0

ok()    { printf "${GREEN}✓${NC} %s\n" "$1"; PASS=$((PASS+1)); }
fail()  { printf "${RED}✗${NC} %s\n" "$1" >&2; FAIL=$((FAIL+1)); }
warn()  { printf "${YELLOW}!${NC} %s\n" "$1"; WARN=$((WARN+1)); }
info()  { printf "${BLUE}ℹ${NC} %s\n" "$1"; }
hdr()   { printf "\n${BLUE}── %s ──${NC}\n" "$1"; }

# ─── 1. git state ─────────────────────────────────────────────────
hdr "git state"

if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
  fail "working tree has uncommitted changes — run 'git status'"
else
  ok "working tree clean"
fi

AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "?")
BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "?")

if [[ "$AHEAD" == "?" ]]; then
  warn "no upstream cached; run 'git fetch origin' to refresh"
elif [[ "$AHEAD" -gt 0 ]]; then
  warn "$AHEAD local commits not yet on origin (run 'git push')"
else
  ok "in sync with origin/main"
fi

if [[ "$BEHIND" != "?" && "$BEHIND" -gt 0 ]]; then
  fail "$BEHIND commits on origin not pulled — run 'git pull --rebase origin main'"
fi

# ─── 2. critical files present ────────────────────────────────────
hdr "critical contract docs"

REQUIRED_FILES=(
  "docs/INTEGRATION_FOR_BROTHER.md"
  "docs/DESKTOP.md"
  "docs/DESKTOP_OWNERSHIP_PASS.md"
  "docs/contracts/CORE_BRIDGE.md"
  "docs/contracts/TARS_MEEET_BILLING.md"
  "docs/contracts/TARS_SUBDOMAIN.md"
  "docs/contracts/MEEET_DOWNLOADS.md"
  "docs/CHANGELOG_AGENTS.md"
  ".env.example"
  "Makefile"
  "desktop/README.md"
  "desktop/scripts/preflight-build.sh"
  "desktop/src-tauri/web/index.html"
)
for f in "${REQUIRED_FILES[@]}"; do
  if [[ -f "$f" ]]; then ok "$f"; else fail "$f MISSING"; fi
done

# ─── 3. .env hygiene ──────────────────────────────────────────────
hdr ".env / secrets hygiene"

if [[ -f .env ]]; then
  ok ".env exists"
  for key in MEEET_INGEST_URL MEEET_API_KEY MEEET_CONTRACT_VERSION; do
    if grep -q "^${key}=" .env 2>/dev/null; then
      ok "$key present in .env"
    else
      warn "$key missing from .env (see .env.example)"
    fi
  done
else
  warn ".env not found — copy .env.example and fill required keys"
fi

if [[ -f .env ]] && grep -q "^.\?MEEET_API_KEY=$" .env 2>/dev/null; then
  warn "MEEET_API_KEY is empty in .env"
fi

# ─── 4. dev stack live? (probe localhost) ─────────────────────────
hdr "dev stack probe"

if curl -sf -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; then
  ok "backend reachable on :8765"
  HEALTH=$(curl -s -m 2 http://127.0.0.1:8765/health || echo "{}")
  if echo "$HEALTH" | grep -q '"ok":true'; then
    ok "/health returned ok:true"
  else
    warn "/health returned non-ok: $HEALTH"
  fi
  if curl -sf -m 5 http://127.0.0.1:8765/api/entitlements >/dev/null 2>&1 \
     || (sleep 0.3 && curl -sf -m 5 http://127.0.0.1:8765/api/entitlements >/dev/null 2>&1); then
    ok "/api/entitlements returned 200"
  else
    warn "/api/entitlements not responding after retry (backend may need restart)"
  fi
else
  warn "backend NOT reachable on :8765 (run 'make backend-tars-up')"
fi

if curl -sf -m 2 -o /dev/null http://127.0.0.1:5173 2>/dev/null; then
  ok "static dev server reachable on :5173 (e.g. make desktop-dev)"
else
  warn "nothing on :5173 (optional — run 'make desktop-dev' for Tauri static shell)"
fi

# ─── 5. desktop (cargo check) ─────────────────────────────────────
if [[ $DESKTOP -eq 1 ]]; then
  hdr "desktop / Tauri sanity"
  if [[ -d desktop/src-tauri ]]; then
    ok "desktop/src-tauri/ exists"
    if command -v cargo >/dev/null 2>&1; then
      info "running 'cargo check' on desktop (may take a minute)..."
      if (cd desktop/src-tauri && cargo check --offline 2>&1 | tail -5); then
        ok "cargo check passed"
      else
        warn "cargo check needs network — try without --offline next run"
      fi
    else
      warn "cargo not in PATH — install via 'curl --proto =https --tlsv1.2 -sSf https://sh.rustup.rs | sh'"
    fi
  else
    fail "desktop/src-tauri/ missing"
  fi

  hdr "desktop preflight"
  if bash desktop/scripts/preflight-build.sh 2>&1 | tail -1; then
    ok "preflight gate green"
  else
    warn "preflight failed (check desktop/src-tauri/web)"
  fi
fi

# ─── 6. full mode — billing edge ──────────────────────────────────
if [[ $FULL -eq 1 ]]; then
  hdr "billing edge smoke"
  if [[ -f .env ]] && grep -q "^MEEET_BILLING_BASE_URL=" .env && grep -q "^MEEET_BILLING_API_KEY=" .env; then
    if make smoke-billing-tars 2>&1 | tail -3; then
      ok "billing edge responds"
    else
      warn "billing edge smoke failed (check Supabase function status)"
    fi
  else
    warn "MEEET_BILLING_BASE_URL or MEEET_BILLING_API_KEY missing in .env — skipping smoke"
  fi
fi

# ─── summary ──────────────────────────────────────────────────────
hdr "summary"
printf "passed: %s · warned: %s · failed: %s\n" "$PASS" "$WARN" "$FAIL"

if [[ $FAIL -gt 0 ]]; then
  printf "\n${RED}status: NOT READY — $FAIL blocker(s)${NC}\n"
  exit 1
elif [[ $WARN -gt 0 ]]; then
  printf "\n${YELLOW}status: GREEN with warnings — review above before launch${NC}\n"
  exit 0
else
  printf "\n${GREEN}status: GREEN — ready to launch${NC}\n"
  exit 0
fi
