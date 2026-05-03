#!/usr/bin/env sh
# Canonical one-liner entry for https://meeet.world/install.sh (and mirrors).
# Installs TARS from GitHub Release assets (public repo).
set -eu
VER="${TARS_VERSION:-8.4.0}"
REPO="alxvasilevvv/tars-neural-cockpit"
BASE="https://github.com/${REPO}/releases/download/v${VER}"

os="$(uname -s 2>/dev/null || echo unknown)"
arch="$(uname -m 2>/dev/null || echo unknown)"

if [ "$os" = "Darwin" ]; then
  if [ "$arch" = "arm64" ] || [ "$arch" = "aarch64" ]; then
    f="TARS_${VER}_aarch64.dmg"
  else
    echo "TARS ${VER}: use aarch64 Mac build or download manually from ${BASE}" >&2
    exit 1
  fi
elif [ "$os" = "Linux" ]; then
  f="TARS_${VER}_amd64.AppImage"
elif echo "$os" | grep -qi MINGW || echo "$os" | grep -qi MSYS || echo "$os" | grep -qi CYGWIN; then
  f="TARS_${VER}_x64-setup.exe"
else
  echo "Unsupported OS: $os — see https://tars.meeet.world/install" >&2
  exit 1
fi

url="${BASE}/${f}"
echo "Downloading ${url} ..."
curl -fL -o "${f}" "${url}"
echo "Saved ${f}"
if [ "$os" = "Darwin" ] && [ "${f#*.}" = "dmg" ]; then
  echo "Opening DMG..."
  open "${f}" || true
fi
