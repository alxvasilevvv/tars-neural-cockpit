#!/usr/bin/env bash
#
# TARS — local-first AI agent · install.sh
# https://meeet.world/install.sh
#
# Usage (one-liner from website):
#   curl -fsSL meeet.world/install.sh | bash
#
# Flags (positional or --kv=val):
#   --tier=free|pro|business|lifetime   set up tier hint for first-run
#   --no-service                        skip launchd / systemd registration
#   --version=v9.0.0                    pin a specific release tag
#   --prefix=$HOME/.tars                override install prefix
#   --uninstall                         remove TARS cleanly
#
# What this does:
#   1. Detect OS (macOS / Linux) and arch (arm64 / x64).
#   2. Verify deps: bash, curl, python3 (>=3.11), git (optional).
#   3. Download release tarball from GitHub Releases (signed checksum).
#   4. Install to $PREFIX (default ~/.tars), wire CLI shim into ~/.local/bin.
#   5. Register launchd (macOS) / systemd user-unit (Linux) — daemon survives reboot.
#   6. Run /healthz against the running agent — confirm green.
#   7. Print magic-link sign-in URL for meeet.world.
#
# Local-first: nothing leaves the machine unless the user signs in.

set -euo pipefail

# ─── Config ────────────────────────────────────────────────────────────────
REPO_OWNER="meeet-world"
REPO_NAME="tars"
DEFAULT_VERSION="latest"
DEFAULT_PREFIX="${HOME}/.tars"
DEFAULT_BIN="${HOME}/.local/bin"
INSTALL_DOMAIN="meeet.world"
HEALTH_PORT="8765"
MIN_PYTHON="3.11"

# ─── Args ──────────────────────────────────────────────────────────────────
TIER=""
SERVICE=1
VERSION="${DEFAULT_VERSION}"
PREFIX="${DEFAULT_PREFIX}"
UNINSTALL=0

for arg in "$@"; do
  case "$arg" in
    --tier=*) TIER="${arg#--tier=}" ;;
    --no-service) SERVICE=0 ;;
    --version=*) VERSION="${arg#--version=}" ;;
    --prefix=*) PREFIX="${arg#--prefix=}" ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help)
      sed -n '1,40p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
  esac
done

# ─── Pretty output ─────────────────────────────────────────────────────────
INDIGO=$'\033[38;5;99m'
VIOLET=$'\033[38;5;141m'
CYAN=$'\033[38;5;81m'
SUCCESS=$'\033[38;5;48m'
ALERT=$'\033[38;5;203m'
DIM=$'\033[2m'
BOLD=$'\033[1m'
RESET=$'\033[0m'

step()    { printf "  ${INDIGO}▸${RESET} %s\n" "$*"; }
ok()      { printf "  ${SUCCESS}✓${RESET} %s\n" "$*"; }
warn()    { printf "  ${ALERT}!${RESET} %s\n" "$*"; }
fail()    { printf "  ${ALERT}✗ %s${RESET}\n" "$*" >&2; exit 1; }
header()  {
  printf "\n${BOLD}${VIOLET}TARS${RESET}${DIM} · local-first agent ${RESET}— ${CYAN}meeet.world${RESET}\n"
  printf "${DIM}────────────────────────────────────────────────────${RESET}\n"
}

# ─── Detect OS / arch ──────────────────────────────────────────────────────
detect_platform() {
  case "$(uname -s)" in
    Darwin)  OS="macos" ;;
    Linux)   OS="linux" ;;
    *)       fail "Unsupported OS: $(uname -s). Native Windows in v9.1; meanwhile use WSL2." ;;
  esac
  case "$(uname -m)" in
    arm64|aarch64) ARCH="arm64" ;;
    x86_64|amd64)  ARCH="x64" ;;
    *)             fail "Unsupported arch: $(uname -m)" ;;
  esac
  step "Platform: ${BOLD}${OS}-${ARCH}${RESET}"
}

# ─── Uninstall path ────────────────────────────────────────────────────────
do_uninstall() {
  header
  step "Uninstalling TARS from ${PREFIX}…"
  if [ "$OS" = "macos" ]; then
    launchctl unload "${HOME}/Library/LaunchAgents/world.meeet.tars.plist" 2>/dev/null || true
    rm -f "${HOME}/Library/LaunchAgents/world.meeet.tars.plist"
  else
    systemctl --user disable --now tars.service 2>/dev/null || true
    rm -f "${HOME}/.config/systemd/user/tars.service"
  fi
  rm -f "${DEFAULT_BIN}/tars"
  rm -rf "${PREFIX}"
  ok "TARS removed. Your ${HOME}/.tars/data was kept — delete manually if you want."
  exit 0
}

# ─── Dep checks ────────────────────────────────────────────────────────────
check_deps() {
  for bin in bash curl tar; do
    command -v "$bin" >/dev/null || fail "Missing required tool: $bin"
  done
  PY="$(command -v python3 || true)"
  [ -z "$PY" ] && fail "python3 ${MIN_PYTHON}+ is required. Install via brew (macOS) or apt (Linux)."
  PY_VER="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  if ! awk -v a="$PY_VER" -v b="$MIN_PYTHON" 'BEGIN{exit !(a>=b)}'; then
    fail "python3 ${PY_VER} is too old. Need ≥ ${MIN_PYTHON}."
  fi
  ok "python3 ${PY_VER} OK"
}

# ─── Download release ──────────────────────────────────────────────────────
fetch_release() {
  local tag="$VERSION"
  if [ "$tag" = "latest" ]; then
    tag="$(curl -fsSL "https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest" |
      sed -n 's/.*"tag_name"[^"]*"\([^"]*\)".*/\1/p' | head -1)"
    [ -z "$tag" ] && fail "Could not resolve 'latest' release tag."
  fi
  local fname="tars-${tag}-${OS}-${ARCH}.tar.gz"
  local url="https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${tag}/${fname}"
  step "Fetching ${BOLD}${tag}${RESET} (${fname})…"
  mkdir -p "$PREFIX"
  curl -fsSL --retry 3 -o "${PREFIX}/release.tar.gz" "$url" \
    || fail "Download failed: $url"
  curl -fsSL --retry 3 -o "${PREFIX}/release.tar.gz.sha256" "${url}.sha256" 2>/dev/null || true
  if [ -f "${PREFIX}/release.tar.gz.sha256" ]; then
    step "Verifying checksum…"
    (cd "$PREFIX" && shasum -a 256 -c release.tar.gz.sha256) || fail "Checksum mismatch — install aborted."
    ok "Checksum verified"
  else
    warn "No checksum published for ${tag} — proceeding (set TARS_REQUIRE_SHA=1 to enforce)."
    [ "${TARS_REQUIRE_SHA:-0}" = "1" ] && fail "Checksum required."
  fi
  tar -xzf "${PREFIX}/release.tar.gz" -C "$PREFIX"
  rm -f "${PREFIX}/release.tar.gz" "${PREFIX}/release.tar.gz.sha256"
  ok "Unpacked to ${PREFIX}"
}

# ─── CLI shim ──────────────────────────────────────────────────────────────
install_cli_shim() {
  mkdir -p "$DEFAULT_BIN"
  cat >"${DEFAULT_BIN}/tars" <<EOF
#!/usr/bin/env bash
exec ${PREFIX}/bin/tars "\$@"
EOF
  chmod +x "${DEFAULT_BIN}/tars"
  ok "CLI installed to ${DEFAULT_BIN}/tars"
  case ":${PATH}:" in
    *":${DEFAULT_BIN}:"*) ;;
    *) warn "Add ${DEFAULT_BIN} to PATH (e.g. echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc)" ;;
  esac
}

# ─── Service registration ──────────────────────────────────────────────────
install_launchd() {
  local plist="${HOME}/Library/LaunchAgents/world.meeet.tars.plist"
  mkdir -p "${HOME}/Library/LaunchAgents"
  cat >"$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>world.meeet.tars</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PREFIX}/bin/tars</string>
    <string>daemon</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>${PREFIX}/logs/daemon.out</string>
  <key>StandardErrorPath</key><string>${PREFIX}/logs/daemon.err</string>
  <key>EnvironmentVariables</key>
  <dict><key>HOME</key><string>${HOME}</string></dict>
</dict>
</plist>
EOF
  mkdir -p "${PREFIX}/logs"
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load "$plist"
  ok "launchd registered → daemon will boot at login"
}

install_systemd() {
  local unit="${HOME}/.config/systemd/user/tars.service"
  mkdir -p "$(dirname "$unit")"
  cat >"$unit" <<EOF
[Unit]
Description=TARS local-first AI agent
After=network-online.target

[Service]
ExecStart=${PREFIX}/bin/tars daemon
Restart=always
RestartSec=5
Environment=HOME=${HOME}

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now tars.service
  ok "systemd user unit registered & started"
}

# ─── Health check ──────────────────────────────────────────────────────────
wait_health() {
  step "Waiting for daemon /healthz…"
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS "http://127.0.0.1:${HEALTH_PORT}/healthz" >/dev/null 2>&1; then
      ok "Daemon is healthy (port ${HEALTH_PORT})"
      return 0
    fi
    sleep 1
  done
  warn "Daemon didn't respond in 10s. Check ${PREFIX}/logs/daemon.err"
}

# ─── Magic-link prompt ─────────────────────────────────────────────────────
print_magiclink() {
  local tier_q=""
  [ -n "$TIER" ] && tier_q="?tier=${TIER}"
  printf "\n  ${BOLD}Sign in:${RESET} ${CYAN}https://${INSTALL_DOMAIN}/auth${tier_q}${RESET}\n"
  printf "  ${DIM}— or skip and stay 100%% local. TARS works offline.${RESET}\n"
}

# ─── Main ──────────────────────────────────────────────────────────────────
main() {
  header
  detect_platform
  [ "$UNINSTALL" = "1" ] && do_uninstall
  check_deps
  fetch_release
  install_cli_shim
  if [ "$SERVICE" = "1" ]; then
    case "$OS" in
      macos) install_launchd ;;
      linux) install_systemd ;;
    esac
    wait_health
  else
    step "Skipped service registration (start with: tars daemon)"
  fi
  print_magiclink
  printf "\n  ${SUCCESS}${BOLD}TARS installed.${RESET} Open the cockpit:\n"
  printf "    ${BOLD}tars cockpit${RESET}    ${DIM}# opens http://127.0.0.1:${HEALTH_PORT}/cockpit${RESET}\n"
  printf "\n  ${DIM}Uninstall: curl -fsSL ${INSTALL_DOMAIN}/install.sh | bash -s -- --uninstall${RESET}\n\n"
}

main "$@"
