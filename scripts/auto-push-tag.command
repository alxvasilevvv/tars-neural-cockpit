#!/usr/bin/env bash
# auto-push-tag.command — non-interactive git push of a single tag.
# Output to .auto-push-tag.txt. Triggered via Spotlight by Claude.

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.auto-push-tag.txt"
# Default: most recent tag by creation date (annotated > lightweight).
DEFAULT_TAG="$(git tag --sort=-creatordate 2>/dev/null | head -1)"
TAG="${1:-${DEFAULT_TAG:-v9.1.1}}"

{
  echo "=== auto-push-tag run at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo "Pushing tag: $TAG"
  echo ""
  if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "── push ──"
    git push origin "$TAG" 2>&1
  else
    echo "Tag '$TAG' does not exist locally. Aborting."
  fi
  echo ""
  echo "=== DONE ==="
} > "$OUT" 2>&1

sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "auto-push-tag")' 2>/dev/null || true
