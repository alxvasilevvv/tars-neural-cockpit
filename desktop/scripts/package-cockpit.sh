#!/usr/bin/env bash
# Build apps/cockpit/ and stage its dist into desktop/src-tauri/web/ so
# Tauri's `frontendDist` points at a freshly built cockpit bundle.
#
# History:
#   - Pre-W308 step 3: this script was a no-op verifier; the shipping
#     bundle lived as a committed pre-built tree under
#     desktop/src-tauri/web/ (copied from the deleted
#     experiments/neural-showcase-v3 SPA). That tree is preserved as
#     desktop/src-tauri/web-legacy/ for emergency rollback (see
#     docs/handoff/W308_PRE_FLIGHT_FINDINGS.md).
#   - W308 step 3+: the cockpit is built from apps/cockpit/ on every
#     desktop dev/build (Vite, multi-page, vanilla TS).
#
# Flags:
#   --skip-build   Reuse an existing apps/cockpit/dist/ tree (CI).
#   --legacy       Stage desktop/src-tauri/web-legacy/ instead — used
#                  only for emergency parity checks; not for release.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$DESKTOP_ROOT/.." && pwd)"
COCKPIT_ROOT="$REPO_ROOT/apps/cockpit"
WEB_DEST="$DESKTOP_ROOT/src-tauri/web"
LEGACY_SRC="$DESKTOP_ROOT/src-tauri/web-legacy"

SKIP_BUILD=0
USE_LEGACY=0
for arg in "$@"; do
  case "$arg" in
    --skip-build) SKIP_BUILD=1 ;;
    --legacy)     USE_LEGACY=1 ;;
    -h|--help)
      sed -n '1,30p' "$0"
      exit 0
      ;;
    *)
      echo "[package-cockpit] unknown flag: $arg" >&2
      exit 64
      ;;
  esac
done

log() { printf '[package-cockpit] %s\n' "$*"; }

if [[ "$USE_LEGACY" -eq 1 ]]; then
  if [[ ! -d "$LEGACY_SRC" ]]; then
    echo "[package-cockpit] --legacy requested but $LEGACY_SRC is missing" >&2
    exit 2
  fi
  log "staging legacy bundle from $LEGACY_SRC"
  rm -rf "$WEB_DEST"
  mkdir -p "$WEB_DEST"
  # Use rsync if available for cleaner output; fall back to cp -R.
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$LEGACY_SRC/" "$WEB_DEST/"
  else
    cp -R "$LEGACY_SRC/." "$WEB_DEST/"
  fi
  log "legacy bundle staged at $WEB_DEST"
  exit 0
fi

if [[ ! -d "$COCKPIT_ROOT" ]]; then
  echo "[package-cockpit] missing $COCKPIT_ROOT — was apps/cockpit/ removed?" >&2
  exit 2
fi

if [[ "$SKIP_BUILD" -eq 0 ]]; then
  if ! command -v pnpm >/dev/null 2>&1; then
    echo "[package-cockpit] pnpm is required to build apps/cockpit/" >&2
    exit 3
  fi
  log "installing apps/cockpit/ deps"
  (cd "$COCKPIT_ROOT" && pnpm install --silent)
  log "building apps/cockpit/ (vite + tsc)"
  (cd "$COCKPIT_ROOT" && pnpm build)
fi

DIST="$COCKPIT_ROOT/dist"
if [[ ! -f "$DIST/index.html" ]]; then
  echo "[package-cockpit] missing $DIST/index.html — did the build fail?" >&2
  exit 4
fi

log "staging $DIST -> $WEB_DEST"
rm -rf "$WEB_DEST"
mkdir -p "$WEB_DEST"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete "$DIST/" "$WEB_DEST/"
else
  cp -R "$DIST/." "$WEB_DEST/"
fi

# Sanity check: Tauri requires index.html at the frontendDist root.
if [[ ! -f "$WEB_DEST/index.html" ]]; then
  echo "[package-cockpit] FATAL: $WEB_DEST/index.html missing after stage" >&2
  exit 5
fi

# W309-prep — prune orphan source-map placeholders.
#
# Vite emits a `.js.map` for every page entry, including pages that
# share the main chunk and never get their own JS file. Result: 100-byte
# empty placeholders (`{"version":3,"sources":[],…}`) whose paired
# `.js` does not exist. Harmless, but the hash churn dirties every
# rebuild's diff in `desktop/src-tauri/web/assets/`.
#
# Survives Vite upgrades (operates on the rsynced output, not Vite
# internals). Path 1 from `W308_PRE_FLIGHT_FINDINGS.md` W309 carry-over
# (PR #186 Claude review recommendation).
if [[ -d "$WEB_DEST/assets" ]]; then
  pruned=0
  while IFS= read -r -d '' mapfile; do
    paired="${mapfile%.map}"
    if [[ ! -f "$paired" ]]; then
      rm "$mapfile"
      pruned=$((pruned + 1))
    fi
  done < <(find "$WEB_DEST/assets" -name '*.js.map' -print0)
  if (( pruned > 0 )); then
    log "pruned $pruned orphan .js.map placeholder(s)"
  fi
fi

log "OK — cockpit bundle staged at $WEB_DEST"
log "    pages: $(cd "$WEB_DEST" && ls *.html | tr '\n' ' ')"
