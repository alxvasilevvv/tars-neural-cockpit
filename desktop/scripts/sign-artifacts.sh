#!/usr/bin/env bash
# Sign every Tauri installer + tarball under <bundle_dir> with the
# minisign key from $TAURI_SIGNING_PRIVATE_KEY (+ optional
# $TAURI_SIGNING_PRIVATE_KEY_PASSWORD). Writes `<artifact>.sig`
# sidecar files that `backend/core/product/updater.py` picks up.
#
# Phase L9 L3. Local sanity check:
#
#     export TAURI_SIGNING_PRIVATE_KEY=$(cat dev-minisign.key | base64)
#     bash desktop/scripts/sign-artifacts.sh src-tauri/target/release/bundle
#
# In CI the env vars come from GitHub Actions secrets.
set -euo pipefail

BUNDLE_DIR="${1:?usage: sign-artifacts.sh <bundle_dir>}"

if [[ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" ]]; then
  echo "[sign-artifacts] no TAURI_SIGNING_PRIVATE_KEY in env — skipping (dev mode)."
  exit 0
fi

if ! command -v tauri >/dev/null 2>&1; then
  echo "[sign-artifacts] installing @tauri-apps/cli for tauri-signer"
  npm install -g @tauri-apps/cli@^2 >/dev/null
fi

# Tauri 2 expects the secret in $TAURI_SIGNING_PRIVATE_KEY (raw or
# base64). The signer writes <artifact>.sig sidecar files which the
# updater channel publisher will pick up automatically.
mapfile -t targets < <(find "$BUNDLE_DIR" -type f \
  \( -name "*.dmg" -o -name "*.app.tar.gz" -o -name "*.msi" \
     -o -name "*Setup.exe" -o -name "*.AppImage" -o -name "*.deb" \
     -o -name "*.tar.gz" \) | sort)

if [[ ${#targets[@]} -eq 0 ]]; then
  echo "[sign-artifacts] no installers under $BUNDLE_DIR — nothing to sign."
  exit 0
fi

for art in "${targets[@]}"; do
  echo "[sign-artifacts] signing $art"
  tauri signer sign \
    --private-key "$TAURI_SIGNING_PRIVATE_KEY" \
    ${TAURI_SIGNING_PRIVATE_KEY_PASSWORD:+--password "$TAURI_SIGNING_PRIVATE_KEY_PASSWORD"} \
    "$art"
  if [[ ! -f "$art.sig" ]]; then
    echo "::error::missing $art.sig — tauri signer did not emit a sidecar"
    exit 2
  fi
done

echo "[sign-artifacts] signed ${#targets[@]} artifact(s)"
