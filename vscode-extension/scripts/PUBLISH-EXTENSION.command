#!/usr/bin/env bash
# PUBLISH-EXTENSION.command — publish tars-tab to VS Code Marketplace.
#
# Prereqs (one-time, see docs/VSCODE_MARKETPLACE_LAUNCH.md):
#   1. Create an Azure DevOps Personal Access Token (PAT) with
#      `Marketplace > Manage` scope.
#   2. Register the `meeet-world` publisher at
#      https://marketplace.visualstudio.com/manage
#   3. Export the PAT before running this script:
#        export VSCODE_PUBLISH_TOKEN=...
#   4. Drop a real 128x128 icon.png into the extension root.
#
# Usage:
#   ./scripts/PUBLISH-EXTENSION.command            # publish current version
#   ./scripts/PUBLISH-EXTENSION.command patch      # vsce publish patch
#   ./scripts/PUBLISH-EXTENSION.command minor      # vsce publish minor
#   ./scripts/PUBLISH-EXTENSION.command major      # vsce publish major
#
# Aborts cleanly (non-zero exit, no side effects) when:
#   - VSCODE_PUBLISH_TOKEN is unset
#   - icon.png is still the placeholder text file
#   - node / npm are missing
#   - tsc compile fails

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG="${SCRIPT_DIR}/.PUBLISH-EXTENSION.txt"

exec > >(tee "${LOG}") 2>&1

echo "==> tars-tab marketplace publish $(date -u +%FT%TZ)"
echo "==> extension dir: ${EXT_DIR}"

# ---------- preflight --------------------------------------------------

if [ -z "${VSCODE_PUBLISH_TOKEN:-}" ]; then
  cat >&2 <<'EOF'
!! VSCODE_PUBLISH_TOKEN is not set.

   Create a PAT at https://dev.azure.com/<your-org>/_usersSettings/tokens
   with `Marketplace > Manage` scope, then re-run as:

     export VSCODE_PUBLISH_TOKEN=...your-pat...
     ./scripts/PUBLISH-EXTENSION.command

   Aborting without publishing. No changes were made.
EOF
  exit 64
fi

ICON="${EXT_DIR}/icon.png"
if [ ! -f "${ICON}" ]; then
  echo "!! icon.png is missing at ${ICON}. Aborting." >&2
  exit 65
fi

# Real PNGs begin with the 8-byte signature 89 50 4E 47 0D 0A 1A 0A.
# Our placeholder is plain UTF-8 text, so this detection is reliable.
if ! head -c 8 "${ICON}" | od -An -tx1 | tr -d ' \n' | grep -qi '^89504e470d0a1a0a$'; then
  cat >&2 <<EOF
!! icon.png is still the placeholder text file.
   Replace it with a real 128x128 PNG before publishing.

   See: docs/VSCODE_MARKETPLACE_LAUNCH.md  §"Icon"
   See: ${ICON} (top of file has rendering instructions)

   Aborting. No changes were made.
EOF
  exit 66
fi

if ! command -v node >/dev/null 2>&1; then
  echo "!! node is required (https://nodejs.org). Aborting." >&2
  exit 67
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "!! npm is required. Aborting." >&2
  exit 68
fi

cd "${EXT_DIR}"

echo "==> npm install (--no-fund --no-audit)"
npm install --no-fund --no-audit

echo "==> tsc compile"
if ! npx --no-install tsc -p ./; then
  if ! npx tsc -p ./; then
    echo "!! tsc compile failed — fix errors above before publishing." >&2
    exit 69
  fi
fi

# ---------- vsce publish ----------------------------------------------

BUMP="${1:-}"
case "${BUMP}" in
  ""|patch|minor|major) ;;
  *)
    echo "!! Unknown bump argument: '${BUMP}'. Use patch | minor | major (or omit)." >&2
    exit 70
    ;;
esac

VSCE="${EXT_DIR}/node_modules/.bin/vsce"
if [ ! -x "${VSCE}" ]; then
  echo "==> local vsce not found — falling back to npx @vscode/vsce"
  VSCE="npx --yes @vscode/vsce"
fi

echo "==> vsce publish ${BUMP:-(current version)}"
# Pass the PAT via -p so it never gets logged into shell history.
# `set +x` defensively in case the user enabled tracing.
set +x
if [ -n "${BUMP}" ]; then
  ${VSCE} publish ${BUMP} -p "${VSCODE_PUBLISH_TOKEN}" --no-dependencies
else
  ${VSCE} publish -p "${VSCODE_PUBLISH_TOKEN}" --no-dependencies
fi
RC=$?

if [ "${RC}" -ne 0 ]; then
  echo "!! vsce publish exited with ${RC}." >&2
  echo "   Common causes: PAT expired, publisher not registered," >&2
  echo "   version already exists. See:" >&2
  echo "   https://code.visualstudio.com/api/working-with-extensions/publishing-extension" >&2
  exit "${RC}"
fi

echo "==> published. Verify at:"
echo "    https://marketplace.visualstudio.com/items?itemName=meeet-world.tars-tab"
echo "==> done"
