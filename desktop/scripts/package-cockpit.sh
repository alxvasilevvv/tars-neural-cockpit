#!/usr/bin/env bash
# Showcase SPA was removed; Tauri bundles the last committed tree under
# src-tauri/web/. This script only verifies the bundle exists.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/src-tauri/web"

if [[ ! -f "$DEST/index.html" ]]; then
  echo "[package-cockpit] missing $DEST/index.html" >&2
  exit 1
fi
echo "[package-cockpit] OK — using bundled web at $DEST"
