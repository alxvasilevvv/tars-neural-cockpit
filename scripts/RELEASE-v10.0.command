#!/usr/bin/env bash
# RELEASE-v10.0.command — W267 one-click cut of the v10.0.0 GA tag.
#
# Drops the -rc.1 suffix from every version constant, runs the final
# QA gate (FINAL-QA-GATE.command), tags, pushes, builds, releases on
# GitHub, attaches the .dmg, optionally publishes the VS Code
# extension, and prints an announce summary.
#
# Aborts on ANY FINAL-QA-GATE failure — there is no path to a broken
# GA tag.
#
# Usage: bash scripts/RELEASE-v10.0.command
#   ENV overrides:
#     RELEASE_v10_AUTO_PUSH=0   skip git push (test the script locally)
#     RELEASE_v10_SKIP_VSCE=1   skip `vsce publish` step
#     RELEASE_v10_DRY_RUN=1     verify gates + bump versions but don't tag

set -u

cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO="$(pwd)"
LOG="${REPO}/.RELEASE-v10.0.txt"

exec > >(tee -a "$LOG") 2>&1

if [ -t 1 ]; then
  G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[34m'; D=$'\033[2m'; X=$'\033[0m'
else
  G=""; R=""; Y=""; B=""; D=""; X=""
fi

FROM_VERSION="10.0.0-rc.1"
TO_VERSION="10.0.0"
TAG="v${TO_VERSION}"
NOTES_RC="docs/RELEASE_NOTES_v10.0-rc1.md"
NOTES_GA="docs/RELEASE_NOTES_v10.0.md"

DRY="${RELEASE_v10_DRY_RUN:-0}"
AUTO_PUSH="${RELEASE_v10_AUTO_PUSH:-1}"
SKIP_VSCE="${RELEASE_v10_SKIP_VSCE:-0}"

step() { printf "\n${B}── [%s/%s] %s ──${X}\n" "$1" "$2" "$3"; }
ok()   { printf "${G}✓${X} %s\n" "$1"; }
warn() { printf "${Y}⚠${X} %s\n" "$1"; }
fail() {
  printf "${R}✗ %s${X}\n" "$1"
  printf "${R}  hint: %s${X}\n" "$2"
  printf "\n${R}=== ABORTED ===${X}\n"
  sleep 6
  exit 1
}

echo "=== RELEASE ${TAG} at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "repo: ${REPO}"
echo "from: ${FROM_VERSION}  →  to: ${TO_VERSION}"
echo "dry-run: ${DRY}   auto-push: ${AUTO_PUSH}   skip-vsce: ${SKIP_VSCE}"

# ── 1. FINAL-QA-GATE — every gate must be green ──────────────────────
step 1 9 "FINAL-QA-GATE (8 sub-gates)"
if [ ! -x "${REPO}/scripts/FINAL-QA-GATE.command" ] && [ ! -f "${REPO}/scripts/FINAL-QA-GATE.command" ]; then
  fail "scripts/FINAL-QA-GATE.command missing" \
       "this script was shipped W267 alongside RELEASE-v10.0.command"
fi
if ! bash "${REPO}/scripts/FINAL-QA-GATE.command"; then
  fail "FINAL-QA-GATE failed — release halted" \
       "fix the failing gate per .FINAL-QA-GATE.txt and re-run this script"
fi
ok "all 8 sub-gates green"

# ── 2. Working tree clean ────────────────────────────────────────────
step 2 9 "git working tree clean"
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  git status --short
  fail "uncommitted changes in working tree" \
       "commit / stash everything before tagging — a GA tag must be reproducible"
fi
CURRENT_HEAD="$(git rev-parse --short HEAD)"
ok "HEAD = ${CURRENT_HEAD}"

if git rev-parse --verify --quiet "refs/tags/${TAG}" >/dev/null; then
  fail "tag ${TAG} already exists locally" \
       "delete it first: git tag -d ${TAG} (and remote: git push --delete origin ${TAG})"
fi
ok "tag ${TAG} is fresh"

# ── 3. Bump versions: 10.0.0-rc.1 → 10.0.0 ──────────────────────────
step 3 9 "version bump"
VERSION_FILES=(
  "desktop/package.json"
  "desktop/src-tauri/tauri.conf.json"
  "desktop/src-tauri/Cargo.toml"
  "web_extras/app.py"
  "backend/core/observability/otel.py"
  "backend/core/product/manifest.py"
  "backend/core/mcp/tools.py"
  "web_extras/routers/github.py"
  "web_extras/routers/awareness.py"
)
bumped=0
for f in "${VERSION_FILES[@]}"; do
  if [ ! -f "${REPO}/${f}" ]; then
    warn "${f} missing — skipping"
    continue
  fi
  if grep -q "${FROM_VERSION}" "${REPO}/${f}"; then
    sed -i.bak "s/${FROM_VERSION}/${TO_VERSION}/g" "${REPO}/${f}" && rm "${REPO}/${f}.bak"
    bumped=$((bumped+1))
    ok "bumped ${f}"
  else
    warn "${f} did not contain ${FROM_VERSION} — already bumped?"
  fi
done
echo "bumped ${bumped} files"

# Also bump on-prem image tags + install.sh.
for f in scripts/ONPREM-DEPLOY/install.sh scripts/ONPREM-DEPLOY/Dockerfile.backend \
         scripts/ONPREM-DEPLOY/Dockerfile.frontend scripts/ONPREM-DEPLOY/docker-compose.yml \
         scripts/ONPREM-DEPLOY/.env.onprem.example docs/ONPREM_DEPLOYMENT_GUIDE.md \
         README.md TARS_MASTER_DOC.md CHANGELOG.md PROJECT_INDEX.md
do
  if [ -f "${REPO}/${f}" ] && grep -q "${FROM_VERSION}\|v${FROM_VERSION}" "${REPO}/${f}"; then
    sed -i.bak "s/${FROM_VERSION}/${TO_VERSION}/g; s/v${FROM_VERSION}/v${TO_VERSION}/g" \
      "${REPO}/${f}" && rm "${REPO}/${f}.bak"
    ok "bumped ${f}"
  fi
done

# Generate the GA release notes file from the rc1 notes (no manual fork).
if [ -f "${REPO}/${NOTES_RC}" ] && [ ! -f "${REPO}/${NOTES_GA}" ]; then
  sed "s/${FROM_VERSION}/${TO_VERSION}/g; s/Wave A + B + C bundled/v10.0 GA/g" \
    "${REPO}/${NOTES_RC}" > "${REPO}/${NOTES_GA}"
  ok "generated ${NOTES_GA} from ${NOTES_RC}"
fi

if [ "${DRY}" = "1" ]; then
  warn "DRY RUN — stopping after version bump (no tag, no push, no build)"
  echo "Inspect with: git diff   then  git checkout -- ."
  exit 0
fi

# Commit the version bump.
git add -A
if ! git commit -m "v10.0.0: bump versions from rc.1 → GA"; then
  warn "nothing to commit (versions were already at GA?)"
else
  ok "committed version bump"
fi
CURRENT_HEAD="$(git rev-parse --short HEAD)"

# ── 4. Annotated tag ─────────────────────────────────────────────────
step 4 9 "create annotated tag ${TAG}"
TAG_MSG="TARS ${TAG} — General Availability

First non-rc release. Bundles every wave from v9.3 (W237-W249) through
v10.0-rc1 (W260-W264) plus the W266/W267 GA-hardening pass:

* W266 — perf suite (5 SLOs: chat / voice / metering / audit / composer)
* W267 — FINAL-QA-GATE: pytest + smoke + perf + codesign + scripts +
         docs + json/yaml + version-consistency

All gates green per scripts/FINAL-QA-GATE.command (.FINAL-QA-GATE.txt).
"
if ! git tag -a "${TAG}" -m "${TAG_MSG}"; then
  fail "git tag failed" \
       "if commit.gpgsign is on, configure your signing key"
fi
ok "annotated tag ${TAG} created at ${CURRENT_HEAD}"

# ── 5. Push tag ──────────────────────────────────────────────────────
step 5 9 "push tag to origin"
if [ "${AUTO_PUSH}" = "0" ]; then
  warn "RELEASE_v10_AUTO_PUSH=0 — skipping push (tag is local-only)"
elif ! git remote get-url origin >/dev/null 2>&1; then
  warn "no 'origin' remote — skipping push"
else
  if git push origin HEAD && git push origin "${TAG}"; then
    ok "branch + tag pushed to origin"
  else
    warn "git push failed — tag is local; retry: git push origin ${TAG}"
  fi
fi

# ── 6. Build TARS.app + .dmg ─────────────────────────────────────────
step 6 9 "build TARS.app"
if [ ! -f "${REPO}/scripts/REBUILD-TARS-APP.command" ]; then
  fail "scripts/REBUILD-TARS-APP.command missing" \
       "this script builds the Tauri .app + installs to /Applications/TARS.app"
fi
if ! bash "${REPO}/scripts/REBUILD-TARS-APP.command"; then
  fail "tauri build failed" \
       "see .REBUILD-TARS-APP.txt for the build log"
fi
ok "TARS.app built and installed"

# Find the .dmg (Tauri convention; same lookup as RELEASE-v10.0-rc1).
DMG=""
for candidate in \
  "${REPO}/desktop/src-tauri/target/aarch64-apple-darwin/release/bundle/dmg"/*.dmg \
  "${REPO}/desktop/src-tauri/target/x86_64-apple-darwin/release/bundle/dmg"/*.dmg \
  "${REPO}/desktop/src-tauri/target/release/bundle/dmg"/*.dmg
do
  if [ -f "$candidate" ]; then DMG="$candidate"; break; fi
done
if [ -n "$DMG" ]; then ok ".dmg located: $(basename "$DMG")"; else warn "no .dmg produced"; fi

# ── 7. GitHub release ────────────────────────────────────────────────
step 7 9 "GitHub release via gh CLI"
if ! command -v gh >/dev/null 2>&1; then
  warn "gh CLI not installed — create the release manually at github.com"
elif ! gh auth status >/dev/null 2>&1; then
  warn "gh installed but not authenticated — run 'gh auth login'"
elif gh release view "${TAG}" >/dev/null 2>&1; then
  warn "GitHub release ${TAG} already exists — skipping create"
else
  if gh release create "${TAG}" \
       --title "TARS ${TAG} — General Availability" \
       --notes-file "${REPO}/${NOTES_GA}"; then
    ok "GitHub release ${TAG} created"
    if [ -n "$DMG" ]; then
      gh release upload "${TAG}" "$DMG" --clobber && ok ".dmg attached" || warn ".dmg upload failed"
    fi
  else
    warn "gh release create failed — retry: gh release create ${TAG} --notes-file ${NOTES_GA}"
  fi
fi

# ── 8. VS Code marketplace publish (tars-tab, W254) ──────────────────
step 8 9 "VS Code marketplace publish"
if [ "${SKIP_VSCE}" = "1" ]; then
  warn "RELEASE_v10_SKIP_VSCE=1 — skipping vsce publish"
elif [ ! -d "${REPO}/vscode-extension" ]; then
  warn "vscode-extension/ missing — skipping vsce publish"
elif ! command -v vsce >/dev/null 2>&1; then
  warn "vsce CLI not installed (npm i -g @vscode/vsce) — skipping"
else
  pushd "${REPO}/vscode-extension" >/dev/null
  if vsce publish; then
    ok "tars-tab published to VS Code Marketplace"
  else
    warn "vsce publish failed — re-run manually after verifying publisher creds"
  fi
  popd >/dev/null
fi

# ── 9. Announce ──────────────────────────────────────────────────────
step 9 9 "announce"
ok "TARS ${TAG} shipped at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""
echo "${G}=== v10.0.0 GA — TAGGED + SHIPPED ===${X}"
echo ""
echo "Next steps (operator-driven):"
echo "  - Tweet thread: docs/MARKETING_v10.0/twitter.md (regenerate from rc1)"
echo "  - HN launch:    docs/MARKETING_v10.0/hn.md"
echo "  - PH launch:    docs/MARKETING_v10.0/product_hunt.md"
echo "  - Newsletter:   docs/MARKETING_v10.0/email.md"
echo ""
echo "Logs: ${LOG}"
echo ""
echo "Terminal closes in 6s…"
sleep 6
osascript -e 'tell application "Terminal" to close (every window whose name contains "RELEASE-v10.0.command")' >/dev/null 2>&1 || true
exit 0
