#!/usr/bin/env bash
# RELEASE-v9.3.0-beta1.command — W251 one-click cut of the v9.3.0-beta1
# beta tag bundling Wave A (W237-W249).
#
# Steps:
#   1. Verify git working tree clean
#   2. Run SMOKE-TEST.command
#   3. Create annotated tag v9.3.0-beta1
#   4. Push tag to origin (if upstream configured)
#   5. Build .app via REBUILD-TARS-APP.command
#   6. Create GitHub release using `gh release create` (if gh installed)
#   7. Attach the built .dmg as a release asset
#   8. Auto-close Terminal in 8s
#
# Each step prints status and aborts on first failure with a helpful hint.

set -u

cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO="$(pwd)"
LOG="${REPO}/.RELEASE-v9.3.0-beta1.txt"

# Mirror everything below to both terminal and log.
exec > >(tee -a "$LOG") 2>&1

if [ -t 1 ]; then
  G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[34m'; D=$'\033[2m'; X=$'\033[0m'
else
  G=""; R=""; Y=""; B=""; D=""; X=""
fi

TAG="v9.3.0-beta1"
NOTES="docs/RELEASE_NOTES_v9.3.0-beta1.md"

step() { printf "\n${B}── [%s/%s] %s ──${X}\n" "$1" "$2" "$3"; }
ok()   { printf "${G}✓${X} %s\n" "$1"; }
warn() { printf "${Y}⚠${X} %s\n" "$1"; }
fail() {
  printf "${R}✗ %s${X}\n" "$1"
  printf "${R}  hint: %s${X}\n" "$2"
  printf "\n${R}=== ABORTED (release halted at step) ===${X}\n"
  sleep 12
  exit 1
}

echo "=== RELEASE ${TAG} at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "repo: ${REPO}"

# ── 1. Working tree clean ────────────────────────────────────────────
step 1 8 "git working tree clean"
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  git status --short
  fail "working tree has uncommitted changes" \
       "commit or stash everything before tagging — release must be reproducible from a clean state"
fi
ok "working tree clean"

CURRENT_HEAD="$(git rev-parse --short HEAD)"
ok "HEAD = ${CURRENT_HEAD}"

# Tag must not already exist locally.
if git rev-parse --verify --quiet "refs/tags/${TAG}" >/dev/null; then
  fail "tag ${TAG} already exists locally" \
       "delete it first: git tag -d ${TAG}  (and remote: git push --delete origin ${TAG})"
fi
ok "tag ${TAG} is fresh"

# Release notes file must exist.
if [ ! -f "${REPO}/${NOTES}" ]; then
  fail "release notes missing: ${NOTES}" \
       "expected the W251 commit to ship this file alongside the script"
fi
ok "release notes present (${NOTES})"

# ── 2. Smoke test ────────────────────────────────────────────────────
step 2 8 "SMOKE-TEST.command"
if [ ! -x "${REPO}/scripts/SMOKE-TEST.command" ] && [ ! -f "${REPO}/scripts/SMOKE-TEST.command" ]; then
  fail "scripts/SMOKE-TEST.command not found" \
       "this script lives in the repo and verifies all 60+ routes return 2xx"
fi
if ! bash "${REPO}/scripts/SMOKE-TEST.command"; then
  fail "smoke test failed" \
       "fix the failing routes before tagging — see .SMOKE-TEST.txt for details"
fi
ok "smoke test passed"

# ── 3. Annotated tag ─────────────────────────────────────────────────
step 3 8 "create annotated tag ${TAG}"
TAG_MSG="TARS ${TAG} — Cursor parity wave + meeet.world billing rails

Wave A (W237-W249) bundled. 13 waves close the Cursor parity gap and
wire the billing rails the W235 consumption console was waiting for.
All additive — no breaking changes, no migrations.

Highlights:
- Models switcher with live cost labels (W237)
- MCP servers panel (W238)
- Rules system (W239)
- @-mention chat context (W240)
- Background agents tray (W241)
- Tier cap UX (W242)
- Notepad templates (W243)
- Privacy mode + data plane (W244)
- Codebase indexer v0 (W245)
- Cmd+K palette v2 (W246)
- Unified WS real-time event bus (W248)

Full notes: ${NOTES}
"
if ! git tag -a "${TAG}" -m "${TAG_MSG}"; then
  fail "git tag failed" \
       "check that you have signing keys configured if commit.gpgsign is on"
fi
ok "annotated tag ${TAG} created at ${CURRENT_HEAD}"

# ── 4. Push tag to origin ────────────────────────────────────────────
step 4 8 "push tag to origin"
if ! git remote get-url origin >/dev/null 2>&1; then
  warn "no 'origin' remote configured — skipping push (tag is local-only)"
else
  if git push origin "${TAG}"; then
    ok "tag pushed to origin"
  else
    warn "git push failed (may be auth or network) — tag is still local"
    warn "  retry manually:  git push origin ${TAG}"
  fi
fi

# ── 5. Build .app ────────────────────────────────────────────────────
step 5 8 "build TARS.app via REBUILD-TARS-APP.command"
if [ ! -f "${REPO}/scripts/REBUILD-TARS-APP.command" ]; then
  fail "scripts/REBUILD-TARS-APP.command not found" \
       "this script builds the Tauri .app + installs to /Applications/TARS.app"
fi
if ! bash "${REPO}/scripts/REBUILD-TARS-APP.command"; then
  fail "tauri build failed" \
       "see .REBUILD-TARS-APP.txt for the full build log; rust compile errors are usually at the bottom"
fi
ok "TARS.app built and installed to /Applications"

# Find the generated .dmg (Tauri puts it under desktop/src-tauri/target/<target>/release/bundle/dmg/)
DMG=""
for candidate in \
  "${REPO}/desktop/src-tauri/target/aarch64-apple-darwin/release/bundle/dmg"/*.dmg \
  "${REPO}/desktop/src-tauri/target/x86_64-apple-darwin/release/bundle/dmg"/*.dmg \
  "${REPO}/desktop/src-tauri/target/release/bundle/dmg"/*.dmg
do
  if [ -f "$candidate" ]; then
    DMG="$candidate"
    break
  fi
done
if [ -n "$DMG" ]; then
  ok ".dmg located at $(basename "$DMG")"
else
  warn "no .dmg found under desktop/src-tauri/target/*/release/bundle/dmg/"
  warn "  (Tauri may have only produced an .app — GitHub release will skip asset upload)"
fi

# ── 6. GitHub release ────────────────────────────────────────────────
step 6 8 "create GitHub release via gh CLI"
if ! command -v gh >/dev/null 2>&1; then
  warn "gh CLI not installed — skipping GitHub release creation"
  warn "  install:  brew install gh   (then re-run this script to publish)"
  warn "  or create the release manually at the GitHub repo UI"
else
  if ! gh auth status >/dev/null 2>&1; then
    warn "gh CLI installed but not authenticated — skipping release"
    warn "  run:  gh auth login"
  else
    if gh release view "${TAG}" >/dev/null 2>&1; then
      warn "GitHub release ${TAG} already exists — skipping create"
    else
      if gh release create "${TAG}" \
           --title "TARS ${TAG} — Cursor parity wave + meeet.world billing rails" \
           --notes-file "${REPO}/${NOTES}" \
           --prerelease; then
        ok "GitHub release ${TAG} created (prerelease)"
      else
        warn "gh release create failed — tag still exists; retry manually with:"
        warn "  gh release create ${TAG} --notes-file ${NOTES} --prerelease"
      fi
    fi

    # ── 7. Attach .dmg ─────────────────────────────────────────────
    step 7 8 "attach .dmg as release asset"
    if [ -n "$DMG" ]; then
      if gh release upload "${TAG}" "$DMG" --clobber; then
        ok ".dmg attached to ${TAG}"
      else
        warn "asset upload failed — retry manually:"
        warn "  gh release upload ${TAG} '${DMG}' --clobber"
      fi
    else
      warn "no .dmg to attach — skipping"
    fi
  fi
fi

# ── 8. Done ──────────────────────────────────────────────────────────
step 8 8 "wrap up"
ok "release ${TAG} prepared at ${CURRENT_HEAD}"
ok "tag pushed: $(git ls-remote --tags origin 2>/dev/null | grep -q "${TAG}" && echo yes || echo "no — push manually")"
ok ".dmg: ${DMG:-not-built}"
ok "GitHub release page: open https://github.com/$(git config --get remote.origin.url 2>/dev/null | sed -E 's|.*github.com[:/](.*)\.git|\1|')/releases/tag/${TAG}"

echo ""
echo "${G}=== DONE — ${TAG} ready to ship ===${X}"
echo ""
echo "  Terminal will auto-close in 8 seconds…"
sleep 8

# Best-effort terminal close (works in macOS Terminal.app).
osascript -e 'tell application "Terminal" to close (every window whose name contains "RELEASE-v9.3.0-beta1.command")' >/dev/null 2>&1 || true
exit 0
