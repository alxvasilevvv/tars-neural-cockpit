#!/usr/bin/env bash
# Copy the freshly-built cockpit dist into Tauri's web-bundled root.
# Run from the repo root: bash desktop/scripts/package-cockpit.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$(cd "$ROOT/../experiments/neural-showcase-v3" && pwd)/dist"
DEST="$ROOT/src-tauri/web"

if [[ ! -d "$SRC" ]]; then
  echo "[package-cockpit] missing build at $SRC" >&2
  echo "                  run \`pnpm --dir experiments/neural-showcase-v3 build\` first." >&2
  exit 1
fi

rm -rf "$DEST"
mkdir -p "$DEST"
cp -R "$SRC"/* "$DEST"/
echo "[package-cockpit] copied $(ls -1 "$DEST" | wc -l | tr -d ' ') entries → $DEST"
