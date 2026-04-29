#!/usr/bin/env bash
# Double-click in Finder to start the v3 marketing site dev server.
set -e
cd "$(dirname "$0")"

PORT=${PORT:-5174}

if [ ! -d node_modules ]; then
  echo "▸ Installing dependencies…"
  npm install --silent
fi

# Open the browser after a small boot delay so Vite is ready.
( sleep 2 && open "http://localhost:${PORT}" ) &

echo "▸ Starting Vite on http://localhost:${PORT}"
echo "  Press Ctrl+C to stop. New terminal will close on exit."
exec npx vite --host 127.0.0.1 --port "${PORT}"
