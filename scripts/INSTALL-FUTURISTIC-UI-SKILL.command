#!/usr/bin/env bash
# INSTALL-FUTURISTIC-UI-SKILL.command — W290
#
# Installs the "futuristic-ui-ux-designer" Claude Code skill via skillfish,
# then fixes the well-known path mismatch (skillfish drops in ~/.agents/skills/,
# Claude Code reads ~/.claude/skills/) by symlinking. After this runs, the
# skill is discoverable by Claude Code / Cursor / Copilot in future sessions.
#
# Source: https://mcpmarket.com/tools/skills/futuristic-ui-ux-designer
# Repo:   naveedtechlab/hackathon-2-todo

set -u
cd "$(dirname "${BASH_SOURCE[0]}")"

LOG="$(dirname "$0")/../.INSTALL-FUTURISTIC-UI-SKILL.txt"
exec > >(tee "$LOG") 2>&1

echo "════════════════════════════════════════════════════════════════"
echo "  W290 — Install futuristic-ui-ux-designer skill"
echo "  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "════════════════════════════════════════════════════════════════"
echo ""

# ── 1. Sanity: need Node/npx ───────────────────────────────────────
if ! command -v npx >/dev/null 2>&1; then
  echo "✗ npx not found. Install Node 20+ from https://nodejs.org"
  sleep 8; exit 1
fi
echo "✓ npx: $(command -v npx)"
echo "  node: $(node --version 2>/dev/null || echo unknown)"
echo ""

# ── 2. Run skillfish ───────────────────────────────────────────────
echo "── npx skillfish add naveedtechlab/hackathon-2-todo ui-ux-futuristic-designer ──"
npx -y skillfish add naveedtechlab/hackathon-2-todo ui-ux-futuristic-designer || {
  RC=$?
  echo ""
  echo "⚠ skillfish exit $RC. Trying alternate slug 'futuristic-ui-ux-designer'..."
  npx -y skillfish add naveedtechlab/hackathon-2-todo futuristic-ui-ux-designer || {
    echo "✗ both slugs failed. Inspect log: $LOG"
    sleep 10; exit 2
  }
}
echo ""

# ── 3. Find where it landed ────────────────────────────────────────
AGENTS_DIR="$HOME/.agents/skills"
CLAUDE_DIR="$HOME/.claude/skills"
echo "── locating installed skill ──"
SKILL_PATH=""
for CAND in "$AGENTS_DIR/ui-ux-futuristic-designer" \
            "$AGENTS_DIR/futuristic-ui-ux-designer" \
            "$CLAUDE_DIR/ui-ux-futuristic-designer" \
            "$CLAUDE_DIR/futuristic-ui-ux-designer"; do
  if [ -d "$CAND" ]; then SKILL_PATH="$CAND"; break; fi
done
if [ -z "$SKILL_PATH" ]; then
  echo "  ⚠ couldn't auto-locate. Searching ~/.agents and ~/.claude..."
  FOUND="$(find "$HOME/.agents" "$HOME/.claude" -maxdepth 4 -type d \
           \( -iname '*futuristic*ui*ux*' -o -iname '*ui*ux*futuristic*' \) \
           2>/dev/null | head -1)"
  if [ -n "$FOUND" ]; then SKILL_PATH="$FOUND"; fi
fi
if [ -z "$SKILL_PATH" ]; then
  echo "  ✗ skill folder not found. Manual install required."
  sleep 10; exit 3
fi
echo "  ✓ skill at: $SKILL_PATH"
echo ""

# ── 4. Mirror to ~/.claude/skills so Claude Code / Cursor see it ──
echo "── mirror to ~/.claude/skills ──"
mkdir -p "$CLAUDE_DIR"
TARGET="$CLAUDE_DIR/$(basename "$SKILL_PATH")"
if [ -L "$TARGET" ] || [ -e "$TARGET" ]; then
  echo "  (already present at $TARGET, replacing link)"
  rm -rf "$TARGET"
fi
ln -s "$SKILL_PATH" "$TARGET"
echo "  ✓ linked: $TARGET → $SKILL_PATH"
echo ""

# ── 5. Verify SKILL.md is present ──────────────────────────────────
echo "── verify SKILL.md ──"
SKILL_MD="$SKILL_PATH/SKILL.md"
if [ -f "$SKILL_MD" ]; then
  WORDS="$(wc -w < "$SKILL_MD" | tr -d ' ')"
  echo "  ✓ SKILL.md present ($WORDS words)"
  echo ""
  echo "── first 12 lines of SKILL.md ──"
  head -12 "$SKILL_MD" | sed 's/^/  | /'
else
  echo "  ⚠ no SKILL.md at $SKILL_MD — may be packaged differently"
  ls -la "$SKILL_PATH" | head -20 | sed 's/^/  | /'
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ✅ DONE"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "  Skill installed at:"
echo "    $SKILL_PATH"
echo "  Linked into:"
echo "    $TARGET"
echo ""
echo "  Next: open Cursor in this repo, ask Claude Code to use the"
echo "  'futuristic-ui-ux-designer' skill to redesign the TARS cockpit."
echo "  Reference file:"
echo "    desktop/src-tauri/web/index.html"
echo ""
echo "(Window auto-closes in 12s.)"
sleep 12
osascript -e 'tell application "Терминал" to close (every window whose name contains "INSTALL-FUTURISTIC")' 2>/dev/null || true
osascript -e 'tell application "Terminal" to close (every window whose name contains "INSTALL-FUTURISTIC")' 2>/dev/null || true
