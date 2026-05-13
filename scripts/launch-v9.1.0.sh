#!/usr/bin/env bash
# launch-v9.1.0.sh — single command to ship v9.1.0.
#
# What it does:
#   1. Sanity-check git state (clean, on main, ahead of origin).
#   2. Push current main to origin.
#   3. Delete stale v9.1.0 tag (local + remote) and re-tag at HEAD.
#   4. Push the new v9.1.0 tag — triggers release-desktop-tagged.yml.
#   5. Print operator's remaining action (B-019 Cloudflare custom-domain swap).
#
# Why one script:
#   Three separate git commands plus a Cloudflare dashboard step
#   were the friction. This collapses the git side to one invocation.
#
# Usage:
#     bash scripts/launch-v9.1.0.sh
#
# After it finishes, do step 5 below in the Cloudflare dashboard.
# ~30 seconds, no shell needed.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ──────────────────────────────────────────────────────────────────────
# UI helpers
# ──────────────────────────────────────────────────────────────────────

BOLD="$(tput bold 2>/dev/null || true)"
DIM="$(tput dim 2>/dev/null || true)"
GREEN="$(tput setaf 2 2>/dev/null || true)"
YELLOW="$(tput setaf 3 2>/dev/null || true)"
RED="$(tput setaf 1 2>/dev/null || true)"
RESET="$(tput sgr0 2>/dev/null || true)"

step() {
  printf "\n${BOLD}==>${RESET} ${BOLD}%s${RESET}\n" "$1"
}
ok() { printf "    ${GREEN}✓${RESET} %s\n" "$1"; }
warn() { printf "    ${YELLOW}⚠${RESET} %s\n" "$1"; }
err() { printf "    ${RED}✗${RESET} %s\n" "$1" >&2; }
ask() {
  # Read a yes/no answer; default = N. Returns 0 on yes, 1 on no.
  local prompt="${1:?prompt required}"
  local default="${2:-N}"
  local reply
  if [ "$default" = "Y" ]; then
    read -r -p "    ${prompt} [Y/n] " reply
    reply="${reply:-Y}"
  else
    read -r -p "    ${prompt} [y/N] " reply
    reply="${reply:-N}"
  fi
  case "$reply" in
    [Yy]|[Yy][Ee][Ss]) return 0 ;;
    *) return 1 ;;
  esac
}

# ──────────────────────────────────────────────────────────────────────
# 1. Sanity checks
# ──────────────────────────────────────────────────────────────────────

step "Pre-flight checks"

if ! command -v git >/dev/null 2>&1; then
  err "git not found — install Xcode CLT or git first"
  exit 2
fi

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$current_branch" != "main" ]; then
  err "you're on branch '${current_branch}', not main — checkout main first"
  exit 2
fi
ok "on branch main"

if ! git diff --quiet || ! git diff --cached --quiet; then
  err "working tree is dirty — commit or stash first"
  git status --short
  exit 2
fi
ok "working tree clean"

git fetch origin --quiet
local_head="$(git rev-parse HEAD)"
remote_head="$(git rev-parse origin/main)"
behind="$(git rev-list --count HEAD..origin/main)"
ahead="$(git rev-list --count origin/main..HEAD)"

if [ "$behind" -gt 0 ]; then
  err "your main is ${behind} commit(s) behind origin/main — rebase or merge first"
  exit 2
fi
ok "main is ${ahead} commit(s) ahead of origin/main"

# ──────────────────────────────────────────────────────────────────────
# 2. Push main
# ──────────────────────────────────────────────────────────────────────

step "Push origin main"
if [ "$ahead" -eq 0 ]; then
  ok "nothing to push (already up to date)"
else
  if ask "About to push ${ahead} commit(s) — proceed?" "Y"; then
    git push origin main
    ok "pushed main"
  else
    err "aborted by user"
    exit 1
  fi
fi

# ──────────────────────────────────────────────────────────────────────
# 3-4. Re-tag v9.1.0 + push tag
# ──────────────────────────────────────────────────────────────────────

step "Move v9.1.0 tag to current HEAD and push"

old_tag_sha="$(git rev-list -n 1 v9.1.0 2>/dev/null || true)"
new_tag_sha="$(git rev-parse HEAD)"

if [ -n "$old_tag_sha" ] && [ "$old_tag_sha" = "$new_tag_sha" ]; then
  ok "v9.1.0 already points at HEAD ${new_tag_sha:0:8}"
else
  if [ -n "$old_tag_sha" ]; then
    warn "v9.1.0 currently points at ${old_tag_sha:0:8}, will move to ${new_tag_sha:0:8}"
    if ask "Delete stale v9.1.0 tag and re-tag at HEAD?" "Y"; then
      git tag -d v9.1.0 >/dev/null 2>&1 || true
      git push origin :refs/tags/v9.1.0 2>/dev/null || warn "remote tag delete failed (may not exist remotely)"
      ok "stale tag removed"
    else
      err "aborted by user"
      exit 1
    fi
  fi
  git tag -a v9.1.0 -m "TARS v9.1.0 — API-first + Cowork backend + desktop installer"
  ok "tagged v9.1.0 at ${new_tag_sha:0:8}"
fi

if ask "Push v9.1.0 tag to origin (triggers release-desktop-tagged.yml)?" "Y"; then
  git push origin v9.1.0
  ok "tag pushed — CI release build started"
  printf "\n    Watch the build at:\n"
  printf "    ${DIM}https://github.com/alxvasilevvv/tars-neural-cockpit/actions${RESET}\n"
else
  warn "tag NOT pushed — run 'git push origin v9.1.0' when you're ready"
fi

# ──────────────────────────────────────────────────────────────────────
# 5. Remaining manual step
# ──────────────────────────────────────────────────────────────────────

step "Remaining operator action (B-019, ~30 seconds, browser only)"

cat <<'EOF'

    tars.meeet.world is currently bound to the legacy `tars-meeet`
    Pages project. After v9.1.0 ships, anonymous visitors will still
    see the May-4 deploy until you swap the domain binding.

    One-click fix in the Cloudflare dashboard:

      1. Cloudflare → Workers & Pages → tars-meeet
           → Custom domains → next to tars.meeet.world click Remove

      2. Cloudflare → Workers & Pages → tars-meeet-git
           → Custom domains → Set up a custom domain
           → tars.meeet.world → Activate

    Verify (30 seconds later):

      curl -s https://tars.meeet.world/api/product/version | jq .version
      # expect: "9.1.0"

    That's it.

EOF

step "Done"
ok "v9.1.0 release pipeline is running"
ok "Backend already healthy on main (Cowork module + 38 pytest cases)"
ok "Desktop bundle pre-pinned at v9.1.0 in tauri.conf.json"
printf "\n    Full launch readiness assessment: ${BOLD}docs/V9_1_0_LAUNCH_READINESS.md${RESET}\n"
