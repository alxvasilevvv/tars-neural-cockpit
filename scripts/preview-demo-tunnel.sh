#!/usr/bin/env bash
# Historical helper for the removed neural-showcase-v3 tunnel demo.
set -euo pipefail
echo "preview-demo-tunnel: the standalone showcase SPA was removed from this repo." >&2
echo "Use \`make desktop-dev\` (bundled static shell) or point your own UI at the API." >&2
exit 2
