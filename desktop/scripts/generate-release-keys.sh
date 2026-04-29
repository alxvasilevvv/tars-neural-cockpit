#!/usr/bin/env bash
# generate-release-keys.sh — mint a fresh Tauri/minisign signing
# keypair for the desktop release pipeline.
#
# What it does:
#   1. Runs `tauri signer generate -w <secret_path>` (Tauri 2 wraps
#      minisign). Prompts you twice for a passphrase.
#   2. Prints the **public** key to stdout — copy that into
#      `desktop/src-tauri/tauri.conf.json -> plugins.updater.pubkey`.
#   3. Prints two ready-to-paste GitHub secret values:
#         TAURI_SIGNING_PRIVATE_KEY            (base64-wrapped private)
#         TAURI_SIGNING_PRIVATE_KEY_PASSWORD   (the passphrase you chose)
#
# Why a script and not docs:
#   Phase L9 release pipeline expects exactly this format. Doing it
#   by hand is one of the easiest ways to leak a private key, so we
#   gate it behind a single command that writes to a file the user
#   chooses (default: a path under ~/.tars-release-keys/) and never
#   prints the secret to stdout.
#
# Usage:
#     bash desktop/scripts/generate-release-keys.sh \
#         [--out ~/.tars-release-keys/tars-desktop.key]
#
# After it finishes:
#     - Commit the new public key into tauri.conf.json.
#     - Add the printed GitHub secrets via:
#           gh secret set TAURI_SIGNING_PRIVATE_KEY < tars-desktop.key
#           gh secret set TAURI_SIGNING_PRIVATE_KEY_PASSWORD
#
# This script never uploads anything anywhere. Everything is local.

set -euo pipefail

SECRET_DIR="${HOME}/.tars-release-keys"
SECRET_PATH="${SECRET_DIR}/tars-desktop.key"
PATCH_TAURI="0"
TAURI_CONF="$(cd "$(dirname "$0")/.." && pwd)/src-tauri/tauri.conf.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)
      SECRET_PATH="$2"
      SECRET_DIR="$(dirname "$SECRET_PATH")"
      shift 2
      ;;
    --patch-tauri-conf)
      PATCH_TAURI="1"
      shift
      ;;
    --tauri-conf)
      TAURI_CONF="$2"
      shift 2
      ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if ! command -v tauri >/dev/null 2>&1; then
  echo "[generate-release-keys] installing @tauri-apps/cli locally"
  npm install -g @tauri-apps/cli@^2 >/dev/null
fi

mkdir -p "$SECRET_DIR"
chmod 700 "$SECRET_DIR"

if [[ -f "$SECRET_PATH" ]]; then
  echo "[generate-release-keys] refusing to overwrite existing key at $SECRET_PATH" >&2
  echo "                        rm it first or pass --out <new_path>" >&2
  exit 3
fi

echo "[generate-release-keys] writing private key to $SECRET_PATH"
echo "                       you will be asked for a passphrase TWICE."
tauri signer generate -w "$SECRET_PATH"

# Tauri prints the matching public key as <secret>.pub
PUB_PATH="${SECRET_PATH}.pub"
if [[ ! -f "$PUB_PATH" ]]; then
  echo "[generate-release-keys] expected public key at $PUB_PATH (tauri-signer didn't emit it)" >&2
  exit 4
fi

chmod 600 "$SECRET_PATH" || true

PUB_KEY_RAW="$(cat "$PUB_PATH")"

echo
echo "──────────────────────────────────────────────────────────────"
echo "  Public key  →  paste into desktop/src-tauri/tauri.conf.json"
echo "                 plugins.updater.pubkey"
echo "──────────────────────────────────────────────────────────────"
echo "$PUB_KEY_RAW"
echo "──────────────────────────────────────────────────────────────"
echo

if [[ "$PATCH_TAURI" == "1" ]]; then
  if [[ ! -f "$TAURI_CONF" ]]; then
    echo "[generate-release-keys] tauri.conf.json not found at $TAURI_CONF" >&2
    exit 5
  fi
  # Use python rather than sed: the value is JSON-encoded, contains
  # newlines, and the surrounding line is line-wrapped. python keeps
  # JSON validity guaranteed.
  python3 - "$TAURI_CONF" "$PUB_KEY_RAW" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
pubkey = sys.argv[2]
data = json.loads(path.read_text("utf-8"))
plugins = data.setdefault("plugins", {})
updater = plugins.setdefault("updater", {})
updater["pubkey"] = pubkey
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"[generate-release-keys] patched {path} -> plugins.updater.pubkey")
PY
fi
echo
echo "  GitHub secrets to add (run this on the same machine):"
echo
echo "    gh secret set TAURI_SIGNING_PRIVATE_KEY < $SECRET_PATH"
echo "    gh secret set TAURI_SIGNING_PRIVATE_KEY_PASSWORD"
echo
echo "  Once both are set, push a tag like 'desktop-v1.0.0' to trigger"
echo "  .github/workflows/release-desktop.yml."
echo
echo "  Backup advice: copy '$SECRET_PATH' to a hardware token or"
echo "  encrypted offline drive. Losing this key forces every existing"
echo "  installation to do a hard reinstall (the auto-updater will"
echo "  refuse mismatched signatures)."
echo
