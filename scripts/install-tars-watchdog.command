#!/usr/bin/env bash
# install-tars-watchdog.command — register backend-watchdog as a macOS
# LaunchAgent so it autostarts on login and survives reboots.
#
# After install:
#   - Plist at ~/Library/LaunchAgents/com.tars.backend-watchdog.plist
#   - Watchdog runs in background, polls /api/health every 30s,
#     restarts uvicorn if it dies
#   - Logs to ~/.tars/backend-watchdog.log
#
# Uninstall:
#   launchctl unload ~/Library/LaunchAgents/com.tars.backend-watchdog.plist
#   rm ~/Library/LaunchAgents/com.tars.backend-watchdog.plist

cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="$(pwd)/.install-tars-watchdog.txt"
REPO_ROOT="$(pwd)"
PLIST="$HOME/Library/LaunchAgents/com.tars.backend-watchdog.plist"

{
  echo "=== install-tars-watchdog at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo ""
  echo "Repo:  $REPO_ROOT"
  echo "Plist: $PLIST"
  echo ""

  mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.tars"

  # Unload prior version if present so reinstall is idempotent.
  if [ -f "$PLIST" ]; then
    echo "── unloading prior plist ──"
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
  fi

  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.tars.backend-watchdog</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${REPO_ROOT}/scripts/backend-watchdog.command</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${REPO_ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${HOME}/.tars/backend-watchdog-stdout.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME}/.tars/backend-watchdog-stderr.log</string>
  <key>ThrottleInterval</key>
  <integer>10</integer>
</dict>
</plist>
EOF
  echo "    plist written"
  echo ""

  echo "── loading new plist ──"
  launchctl load -w "$PLIST"
  echo ""

  echo "── verify ──"
  launchctl list | grep com.tars.backend-watchdog || echo "    (not listed yet)"
  echo ""

  echo "=== DONE ==="
  echo ""
  echo "Watchdog will autostart on login from now on."
  echo "Stop with: launchctl unload $PLIST"
} > "$OUT" 2>&1

sleep 2
osascript -e 'tell application "Терминал" to close (every window whose name contains "install-tars-watchdog")' 2>/dev/null || true
