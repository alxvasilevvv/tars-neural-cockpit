#!/usr/bin/env bash
# Prints whether plugins.updater.pubkey in tauri.conf.json is still the
# placeholder. Does **not** fail the shell — use this in preflight
# checklists and CI messages. For a hard gate, combine with:
#   bash desktop/scripts/updater-pubkey-status.sh | grep -q patched && …
#
# After minting keys:  bash desktop/scripts/generate-release-keys.sh --patch-tauri-conf

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="${ROOT}/src-tauri/tauri.conf.json"

if [[ ! -f "$CONF" ]]; then
  echo "updater_pubkey: MISSING_CONFIG ($CONF)"
  exit 0
fi

if grep -Fq 'TODO_PUBLIC_KEY' "$CONF" 2>/dev/null; then
  echo "updater_pubkey: TODO_PUBLIC_KEY — run generate-release-keys.sh --patch-tauri-conf before shipping installers"
else
  echo "updater_pubkey: patched (minisign pubkey present)"
fi
