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

REPO="alxvasilevvv/tars-neural-cockpit"
GHAPI="https://api.github.com/repos/${REPO}/releases/latest"
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

# Ask the GitHub API for the latest release tag, but tolerate API
# rate-limit failures by parsing the redirect URL of the
# /releases/latest endpoint instead.
resolve_latest_tag() {
  if command -v curl >/dev/null 2>&1; then
    local tag
    tag=$(curl -fsSL "${GHAPI}" 2>/dev/null \
      | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' \
      | head -1 || true)
    if [[ -n "${tag}" ]]; then
      echo "${tag}"
      return
    fi
    # Fallback: follow the latest-release redirect.
    tag=$(curl -fsSLI "https://github.com/${REPO}/releases/latest" \
      | grep -i '^location:' | tail -1 \
      | sed -E 's|.*tag/([^/[:space:]]+).*|\1|' | tr -d '\r')
    if [[ -n "${tag}" ]]; then
      echo "${tag}"
      return
    fi
  fi
  err "cannot resolve the latest release tag — check your network"
}

asset_url() {
  local tag="$1"
  local version="${tag#v}"
  case "${OS}-${ARCH}" in
    mac-arm64)
      echo "https://github.com/${REPO}/releases/download/${tag}/TARS_${version}_aarch64.dmg"
      ;;
    mac-x64)
      echo "https://github.com/${REPO}/releases/download/${tag}/TARS_${version}_x64.dmg"
      ;;
    linux-x64)
      echo "https://github.com/${REPO}/releases/download/${tag}/TARS_${version}_amd64.AppImage"
      ;;
    *)
      err "no prebuilt binary for ${OS}-${ARCH} yet"
      ;;
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
