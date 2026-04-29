#!/usr/bin/env bash
# Build Showcase, run vite preview. If cloudflared is installed, also open a temporary public URL.
# Optional: brew install cloudflare/cloudflare/cloudflared
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHOWCASE="$ROOT/experiments/neural-showcase-v3"
PREVIEW_HOST="${PREVIEW_HOST:-127.0.0.1}"
PREVIEW_PORT="${PREVIEW_PORT:-4173}"

cd "$SHOWCASE"
npm run build --silent

if command -v cloudflared >/dev/null 2>&1; then
  echo "Preview: http://${PREVIEW_HOST}:${PREVIEW_PORT}  (cloudflared will print a public URL)"
  npm run preview -- --host "${PREVIEW_HOST}" --port "${PREVIEW_PORT}" &
  PREVIEW_PID=$!
  sleep 2
  cloudflared tunnel --url "http://${PREVIEW_HOST}:${PREVIEW_PORT}" || true
  kill "${PREVIEW_PID}" 2>/dev/null || true
else
  echo "Local preview only. For a public URL: brew install cloudflare/cloudflare/cloudflared"
  exec npm run preview -- --host "${PREVIEW_HOST}" --port "${PREVIEW_PORT}"
fi
