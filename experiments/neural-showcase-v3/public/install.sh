#!/usr/bin/env bash
# TARS — one-line installer.
#
# Usage:
#   curl -fsSL https://tars.meeet.world/install.sh | bash
#
# What it does (macOS / Linux):
#   1. Detects OS + architecture
#   2. Downloads the matching binary from GitHub Releases (latest tag)
#   3. macOS: copies to /Applications/TARS.app, strips Gatekeeper
#      quarantine attribute (so the "TARS is damaged" warning never
#      shows), launches the app
#   4. Linux: writes to ~/.local/bin/tars, makes it executable,
#      drops a .desktop launcher
#
# Why curl-pipe-bash works here: the script is fetched over HTTPS
# from tars.meeet.world (Cloudflare Pages, immutable build), every
# binary is downloaded from github.com/alxvasilevvv/tars-neural-cockpit
# /releases (also HTTPS + SHA-tagged). No `sudo` is required —
# everything lands in user-writable paths.
#
# To inspect before running:
#   curl -fsSL https://tars.meeet.world/install.sh | less
#
# Released by meeet.world under MIT.

set -euo pipefail

# B-017: source repo is private, so we no longer hit github.com /
# api.github.com directly (those return 404 to anonymous callers).
# Everything routes through the same-origin tars.meeet.world surface:
#   - GET /api/product/version    → { version: "9.1.0", ... }
#   - GET /dl/<filename>          → Pages Function proxies to GitHub
#                                   via GITHUB_RELEASE_TOKEN (op env)
TARS_ORIGIN="${TARS_ORIGIN:-https://tars.meeet.world}"
TARS_VERSION_ENDPOINT="${TARS_ORIGIN}/api/product/version"
TARS_DL_BASE="${TARS_ORIGIN}/dl"
TARS_BLUE="\033[1;34m"
TARS_CYAN="\033[1;36m"
TARS_DIM="\033[2m"
TARS_OK="\033[1;32m"
TARS_ERR="\033[1;31m"
TARS_RESET="\033[0m"

banner() {
  echo -e "${TARS_BLUE}"
  echo -e "  ████████╗ █████╗ ██████╗ ███████╗"
  echo -e "  ╚══██╔══╝██╔══██╗██╔══██╗██╔════╝"
  echo -e "     ██║   ███████║██████╔╝███████╗"
  echo -e "     ██║   ██╔══██║██╔══██╗╚════██║"
  echo -e "     ██║   ██║  ██║██║  ██║███████║"
  echo -e "     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝"
  echo -e "${TARS_RESET}"
  echo -e "  ${TARS_CYAN}meeet.world${TARS_RESET} · neural cockpit · local-first"
  echo
}

err() { echo -e "${TARS_ERR}error:${TARS_RESET} $*" >&2; exit 1; }
info() { echo -e "${TARS_DIM}→${TARS_RESET} $*"; }
ok() { echo -e "${TARS_OK}✓${TARS_RESET} $*"; }

require() {
  command -v "$1" >/dev/null 2>&1 || err "missing required command: $1"
}

detect() {
  local uname_s
  local uname_m
  uname_s=$(uname -s)
  uname_m=$(uname -m)
  case "${uname_s}" in
    Darwin) OS="mac" ;;
    Linux)  OS="linux" ;;
    *)      err "unsupported OS: ${uname_s} (Windows: download the .msi from tars.meeet.world/install)" ;;
  esac
  case "${uname_m}" in
    arm64|aarch64) ARCH="arm64" ;;
    x86_64|amd64)  ARCH="x64" ;;
    *)             err "unsupported arch: ${uname_m}" ;;
  esac
  info "detected: ${OS} ${ARCH}"
}

# Resolve the latest release version via the same-origin manifest
# endpoint. Falls back to a hard-coded floor only if the network is
# down — the script then refuses to install (better than serving a
# stale .dmg silently).
resolve_latest_tag() {
  require curl
  local body
  body=$(curl -fsSL "${TARS_VERSION_ENDPOINT}" 2>/dev/null || true)
  if [[ -z "${body}" ]]; then
    err "cannot reach ${TARS_VERSION_ENDPOINT} — check your network"
  fi
  local version
  version=$(echo "${body}" \
    | sed -n 's/.*"version" *: *"\([^"]*\)".*/\1/p' \
    | head -1)
  if [[ -z "${version}" ]]; then
    err "version endpoint returned unexpected shape: ${body}"
  fi
  echo "v${version}"
}

# Build the same-origin download URL. The tars.meeet.world Pages
# Function at functions/dl/[file].ts proxies to GitHub Releases
# (private repo) via the operator-set GITHUB_RELEASE_TOKEN.
asset_url() {
  local tag="$1"
  local version="${tag#v}"
  case "${OS}-${ARCH}" in
    mac-arm64)  echo "${TARS_DL_BASE}/TARS_${version}_aarch64.dmg" ;;
    mac-x64)    echo "${TARS_DL_BASE}/TARS_${version}_x64.dmg" ;;
    linux-x64)  echo "${TARS_DL_BASE}/TARS_${version}_amd64.AppImage" ;;
    *)          err "no prebuilt binary for ${OS}-${ARCH} yet" ;;
  esac
}

install_mac() {
  local url="$1"
  local tmpdir
  tmpdir=$(mktemp -d -t tars-installer)
  local dmg="${tmpdir}/tars.dmg"
  local mount="${tmpdir}/mount"
  local app="/Applications/TARS.app"

  require curl
  require hdiutil
  require ditto

  info "downloading installer (~8MB)…"
  curl -fL --progress-bar -o "${dmg}" "${url}"

  info "mounting DMG…"
  mkdir -p "${mount}"
  hdiutil attach "${dmg}" -nobrowse -mountpoint "${mount}" >/dev/null

  info "installing to /Applications/TARS.app…"
  if [[ -d "${app}" ]]; then
    rm -rf "${app}"
  fi
  ditto "${mount}/TARS.app" "${app}"
  hdiutil detach "${mount}" -quiet >/dev/null

  info "stripping Gatekeeper quarantine attribute (Bug-fix: 'TARS is damaged' modal)…"
  xattr -dr com.apple.quarantine "${app}" 2>/dev/null || true

  info "ad-hoc codesigning so Gatekeeper accepts the bundle…"
  codesign --force --deep --sign - "${app}" 2>/dev/null || true

  ok "TARS installed at ${app}"
  echo
  echo -e "  ${TARS_CYAN}launching now…${TARS_RESET}"
  open "${app}"

  rm -rf "${tmpdir}"
}

install_linux() {
  local url="$1"
  local bindir="${HOME}/.local/bin"
  local appdir="${HOME}/.local/share/applications"
  local target="${bindir}/tars"

  require curl
  mkdir -p "${bindir}" "${appdir}"

  info "downloading AppImage (~85MB)…"
  curl -fL --progress-bar -o "${target}" "${url}"
  chmod +x "${target}"

  info "writing desktop launcher…"
  cat > "${appdir}/tars.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TARS
Comment=Local-first neural cockpit · meeet.world
Exec=${target}
Terminal=false
Categories=Office;Development;Utility;
EOF

  ok "TARS installed at ${target}"
  echo
  if [[ ":${PATH}:" != *":${bindir}:"* ]]; then
    echo -e "  ${TARS_CYAN}note:${TARS_RESET} ${bindir} is not in your PATH — add it or run \`${target}\`"
  else
    echo -e "  ${TARS_CYAN}launching now…${TARS_RESET}"
    "${target}" >/dev/null 2>&1 &
  fi
}

main() {
  banner
  detect
  TAG=$(resolve_latest_tag)
  info "latest release: ${TAG}"
  URL=$(asset_url "${TAG}")
  info "asset: ${URL}"
  case "${OS}" in
    mac)   install_mac "${URL}" ;;
    linux) install_linux "${URL}" ;;
  esac
  echo
  ok "done · open meeet.world to claim your handle and earn \$MEEET"
}

main "$@"
