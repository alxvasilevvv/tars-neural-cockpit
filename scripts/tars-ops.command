#!/usr/bin/env bash
# tars-ops.command — single-entry automation menu for TARS operator.
#
# Double-click in Finder, or Cmd+Space → "tars-ops" → Enter.
# Pops a native macOS dialog with common ops; output lands in
# .tars-ops-output.txt next to the repo root for Claude/Cursor to
# read in the next chat session.
#
# Boundary: every operation here is safe to run repeatedly. Anything
# that touches access controls (Apple cert, GH Secrets, Cloudflare
# dashboard) is intentionally OUT of scope — see docs/AUTOMATION.md.

set -uo pipefail

# Locate the repo root regardless of where the script lives.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OUT="${REPO_ROOT}/.tars-ops-output.txt"
LOG_PREFIX="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Helpers ───────────────────────────────────────────────────────────

# AppleScript "choose from list" wrapper. Pops up a native dialog
# with our options and returns the index (1..N) of the choice.
pick_op() {
  /usr/bin/osascript <<'APPLESCRIPT'
set ops to {¬
  "1 — Status (5 sec: git + CI + prod)", ¬
  "2 — Push (git push origin main)", ¬
  "3 — Verify (full E2E sweep — 6 dl URLs + install.sh + tests)", ¬
  "4 — Diagnose (quick triage of broken-looking state)", ¬
  "5 — Tag release (vX.Y.Z + push tag → CI release)", ¬
  "6 — Cursor sync (append SYNC marker to AGENT_HANDOFF.md)", ¬
  "7 — Open output file (.tars-ops-output.txt)" ¬
}
set picked to choose from list ops with title "TARS Ops" with prompt "What do you want to do?" default items {"1 — Status (5 sec: git + CI + prod)"} OK button name "Run" cancel button name "Cancel"
if picked is false then
  return ""
else
  return item 1 of picked
end if
APPLESCRIPT
}

# Native macOS notification when an op finishes.
notify() {
  local title="$1"
  local msg="$2"
  /usr/bin/osascript -e "display notification \"${msg//\"/}\" with title \"${title//\"/}\""
}

# Each op writes its own block into $OUT; this header keeps log readable.
op_header() {
  {
    echo ""
    echo "═════════════════════════════════════════════════════════════"
    echo "[$LOG_PREFIX] $1"
    echo "═════════════════════════════════════════════════════════════"
    echo ""
  } >> "$OUT"
}

# Ops ──────────────────────────────────────────────────────────────

op_status() {
  op_header "STATUS"
  {
    echo "── git ──"
    echo "HEAD: $(git rev-parse --short HEAD) — $(git log -1 --pretty=%s)"
    echo "Ahead of origin/main: $(git rev-list --count origin/main..HEAD 2>/dev/null || echo '?')"
    echo "Working tree: $(git status --porcelain | wc -l | tr -d ' ') changes"
    echo ""
    echo "── prod ──"
    echo -n "tars.meeet.world/api/product/version: "
    curl -s --max-time 5 https://tars.meeet.world/api/product/version | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version','?'))" 2>/dev/null || echo "unreachable"
    echo ""
    echo "── ci (release-desktop-tagged.yml, last 3) ──"
    if command -v gh >/dev/null 2>&1; then
      gh run list --repo alxvasilevvv/tars-neural-cockpit --workflow release-desktop-tagged.yml --limit 3 2>&1 | tail -4
    else
      echo "(gh CLI not installed)"
    fi
  } >> "$OUT" 2>&1
}

op_push() {
  op_header "PUSH"
  {
    local ahead
    ahead=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "0")
    if [ "$ahead" = "0" ]; then
      echo "Nothing to push — already up to date."
    else
      echo "Pushing $ahead commit(s) to origin/main..."
      git push origin main 2>&1
      echo ""
      echo "If CF Pages auto-rebuild is wired, it'll start within ~30 seconds."
      echo "Run option 3 (Verify) in 2-3 minutes to confirm the deploy landed."
    fi
  } >> "$OUT" 2>&1
}

op_verify() {
  op_header "VERIFY (full E2E sweep)"
  {
    echo "[1/4] /api/product/version"
    curl -s --max-time 8 https://tars.meeet.world/api/product/version
    echo ""
    echo ""

    echo "[2/4] All 6 /dl/ URLs"
    for f in TARS_9.1.0_aarch64.dmg TARS_9.1.0_x64.dmg TARS_9.1.0_amd64.AppImage TARS_9.1.0_amd64.deb TARS_9.1.0_x64-setup.exe TARS_9.1.0_x64_en-US.msi; do
      code=$(curl -sI --max-time 8 "https://tars.meeet.world/dl/$f" | head -1 | awk '{print $2}')
      if [ "$code" = "200" ] || [ "$code" = "302" ]; then
        echo "  ✓ $f → HTTP $code"
      else
        echo "  ✗ $f → HTTP $code"
      fi
    done
    echo ""

    echo "[3/4] /install.sh"
    curl -sI --max-time 8 https://tars.meeet.world/install.sh | head -2
    echo ""

    echo "[4/4] Cowork pytest sweep"
    python3 -m unittest tests.test_cowork_store tests.test_cowork_presence tests.test_cowork_edge_cases 2>&1 | tail -3
  } >> "$OUT" 2>&1
}

op_diagnose() {
  op_header "DIAGNOSE (quick triage)"
  {
    echo "── DNS resolution ──"
    dig +short tars.meeet.world | head -3 || echo "dig not available"
    echo ""

    echo "── TLS cert ──"
    echo | openssl s_client -connect tars.meeet.world:443 -servername tars.meeet.world 2>/dev/null | openssl x509 -noout -subject -dates 2>/dev/null || echo "(openssl s_client failed)"
    echo ""

    echo "── Cloudflare headers ──"
    curl -sI --max-time 5 https://tars.meeet.world/ 2>&1 | grep -iE "^(cf-ray|cf-cache|server|x-tars)" | head -5
    echo ""

    echo "── recent CF Pages activity ──"
    if command -v gh >/dev/null 2>&1; then
      gh run list --repo alxvasilevvv/tars-neural-cockpit --limit 5 2>&1 | head -7
    fi
  } >> "$OUT" 2>&1
}

op_tag_release() {
  op_header "TAG RELEASE"
  # Use a dialog to ask for the version.
  local version
  version=$(/usr/bin/osascript -e 'set v to text returned of (display dialog "Tag a release. Format: 9.X.Y (without the v prefix).\n\nThe script will create v<X.Y.Z> and push it." default answer "9.1.1" with title "TARS — Tag release" buttons {"Cancel","Tag"} default button "Tag")')
  if [ -z "$version" ]; then
    echo "(cancelled)" >> "$OUT"
    return
  fi
  {
    echo "Tagging v$version on HEAD ($(git rev-parse --short HEAD))..."
    # Delete any local stale tag of the same name (operator confirmed via dialog).
    git tag -d "v$version" 2>/dev/null || true
    git push origin ":refs/tags/v$version" 2>/dev/null || true
    git tag -a "v$version" -m "TARS v$version"
    git push origin "v$version"
    echo ""
    echo "Tag pushed. CI release-desktop-tagged.yml should start in ~30 sec."
    echo "Watch: https://github.com/alxvasilevvv/tars-neural-cockpit/actions"
  } >> "$OUT" 2>&1
}

op_cursor_sync() {
  op_header "CURSOR SYNC"
  local handoff="$REPO_ROOT/docs/AGENT_HANDOFF.md"
  if [ ! -f "$handoff" ]; then
    echo "AGENT_HANDOFF.md not found" >> "$OUT"
    return
  fi
  local marker_block
  marker_block=$(cat <<EOF

> **>>> SYNC: Claude (auto) · $(date -u +%Y-%m-%dT%H:%M:%SZ) <<<**
>
> Operator ran \`tars-ops\` → "Cursor sync" at the timestamp above.
> Current HEAD: $(git rev-parse --short HEAD) — $(git log -1 --pretty=%s)
> Working tree: $(git status --porcelain | wc -l | tr -d ' ') uncommitted changes.
> Recent commits:
> $(git log -3 --pretty="  - %h %s")
>
> If you're Cursor reading this in a fresh session — pull main, look at
> the recent commits, and either acknowledge or flag anything that
> looks off. Don't \`git reset --hard\`; comment or open an issue.
>
> **>>> END SYNC <<<**

EOF
)
  # Append after the first occurrence of "## SYNC" if exists, otherwise at the top after H1.
  printf "%s\n" "$marker_block" >> "$handoff"
  {
    echo "Appended SYNC marker to docs/AGENT_HANDOFF.md."
    echo "Lines added: $(printf '%s\n' "$marker_block" | wc -l | tr -d ' ')"
    echo ""
    echo "Tip: review with 'git diff docs/AGENT_HANDOFF.md' before committing."
  } >> "$OUT" 2>&1
}

op_open_output() {
  /usr/bin/open "$OUT" 2>/dev/null || echo "open failed"
}

# Main flow ────────────────────────────────────────────────────────

# Ensure log file exists.
touch "$OUT"

pick=$(pick_op)
case "$pick" in
  1*) op_status ;;
  2*) op_push ;;
  3*) op_verify ;;
  4*) op_diagnose ;;
  5*) op_tag_release ;;
  6*) op_cursor_sync ;;
  7*) op_open_output ; exit 0 ;;
  "") echo "(cancelled by user)"; exit 0 ;;
  *)  echo "Unknown selection: $pick" >&2; exit 1 ;;
esac

# After most ops, surface the result via notification + cat tail.
tail -50 "$OUT"
echo ""
echo "Full output → $OUT"

# Try to display a Notification Center toast (may be muted by macOS Focus).
case "$pick" in
  1*) notify "TARS Ops" "Status complete — see .tars-ops-output.txt" ;;
  2*) notify "TARS Ops" "Push done — verify in 2-3 min" ;;
  3*) notify "TARS Ops" "Verify sweep complete" ;;
  4*) notify "TARS Ops" "Diagnose complete" ;;
  5*) notify "TARS Ops" "Release tag pushed — watch CI" ;;
  6*) notify "TARS Ops" "Cursor SYNC marker appended" ;;
esac
