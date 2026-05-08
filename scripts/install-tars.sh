#!/usr/bin/env sh
# Canonical one-liner entry, mirror of `experiments/neural-showcase-v3/
# public/install.sh` (the file that Cloudflare Pages serves at
# `https://tars.meeet.world/install.sh`).
#
# B-017 (2026-05-08): downloads now go through the same-origin Pages
# Function `functions/dl/[file].ts` instead of github.com/.../releases
# directly — the source repo is private and direct GitHub URLs
# return 404 to anonymous callers. The Function uses a server-side
# `GITHUB_RELEASE_TOKEN` PAT to proxy the binary while keeping the
# repo private.

set -eu

TARS_ORIGIN="${TARS_ORIGIN:-https://tars.meeet.world}"
VER="${TARS_VERSION:-9.1.0}"
DL_BASE="${TARS_ORIGIN}/dl"

os="$(uname -s 2>/dev/null || echo unknown)"
arch="$(uname -m 2>/dev/null || echo unknown)"

if [ "$os" = "Darwin" ]; then
  if [ "$arch" = "arm64" ] || [ "$arch" = "aarch64" ]; then
    f="TARS_${VER}_aarch64.dmg"
  elif [ "$arch" = "x86_64" ] || [ "$arch" = "amd64" ]; then
    f="TARS_${VER}_x64.dmg"
  else
    echo "TARS ${VER}: unsupported Mac arch '${arch}' — see ${TARS_ORIGIN}/install" >&2
    exit 1
  fi
elif [ "$os" = "Linux" ]; then
  f="TARS_${VER}_amd64.AppImage"
elif echo "$os" | grep -qi MINGW || echo "$os" | grep -qi MSYS || echo "$os" | grep -qi CYGWIN; then
  f="TARS_${VER}_x64-setup.exe"
else
  echo "Unsupported OS: ${os} — see ${TARS_ORIGIN}/install" >&2
  exit 1
fi

url="${DL_BASE}/${f}"
echo "Downloading ${url} ..."
if ! curl -fL -o "${f}" "${url}"; then
  echo "" >&2
  echo "ERROR: download failed. Likely cause: GITHUB_RELEASE_TOKEN is not yet" >&2
  echo "set on the tars.meeet.world Cloudflare Pages deploy (B-017 operator" >&2
  echo "step). Verify with:" >&2
  echo "  curl -sI ${TARS_ORIGIN}/dl/${f} | head -1" >&2
  echo "  curl -s  ${TARS_ORIGIN}/dl/${f} | head" >&2
  echo "If you see HTTP 503 + operator_action_required, paste the PAT into" >&2
  echo "Pages env (see functions/dl/[file].ts header for the one-time setup)." >&2
  exit 1
fi
echo "Saved ${f}"
if [ "$os" = "Darwin" ] && [ "${f#*.}" = "dmg" ]; then
  echo "Opening DMG..."
  open "${f}" || true
fi
