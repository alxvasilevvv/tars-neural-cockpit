#!/usr/bin/env bash
# PACKAGE-EXTENSION.command
# Builds tars-tab .vsix ready to ship.
#
# Usage:
#   ./scripts/PACKAGE-EXTENSION.command
#
# Outputs the .vsix into the extension root and writes a log to
# .PACKAGE-EXTENSION.txt in the same scripts/ folder.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG="${SCRIPT_DIR}/.PACKAGE-EXTENSION.txt"

exec > >(tee "${LOG}") 2>&1

echo "==> tars-tab package build $(date -u +%FT%TZ)"
echo "==> extension dir: ${EXT_DIR}"
cd "${EXT_DIR}"

if ! command -v node >/dev/null 2>&1; then
  echo "!! node is required (https://nodejs.org). Aborting." >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "!! npm is required. Aborting." >&2
  exit 1
fi

echo "==> npm install"
npm install --no-fund --no-audit

echo "==> tsc compile"
npx --no-install tsc -p ./ || npx tsc -p ./

echo "==> vsce package"
# Prefer the locally-pinned vsce devDep so we don't depend on a global install.
if [ -x "node_modules/.bin/vsce" ]; then
  ./node_modules/.bin/vsce package --no-dependencies --out ./
else
  npx --yes @vscode/vsce package --no-dependencies --out ./
fi

VSIX="$(ls -1t *.vsix 2>/dev/null | head -n1 || true)"
if [ -z "${VSIX}" ]; then
  echo "!! no .vsix produced — see log above" >&2
  exit 2
fi

echo "==> built: ${EXT_DIR}/${VSIX}"
echo "==> install locally with:"
echo "    code --install-extension ${VSIX}"
echo "==> done"
