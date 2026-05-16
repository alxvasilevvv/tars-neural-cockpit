# W290 — Handoff to Cursor: futuristic UI/UX redesign of TARS cockpit

## Context

After two weeks of design iteration (W277 → W283 → W286 → W287 → W288), the
TARS cockpit was hard-reset back to the **W286 clean baseline** (no scanner
rings, no rich-studio overlays, no overlapping tiles). The baseline works but
visually reads as a generic Linear/Granola clone — not futuristic enough for
the presentation.

The user installed the **futuristic-ui-ux-designer** Claude Code skill
(from `https://mcpmarket.com/tools/skills/futuristic-ui-ux-designer`) via
`scripts/INSTALL-FUTURISTIC-UI-SKILL.command`. The skill is now discoverable
in `~/.claude/skills/` and `~/.agents/skills/`.

## Files in scope

- `desktop/src-tauri/web/index.html` — single-file Tauri cockpit (~482 KB).
  All cockpit CSS lives between lines ~2169–2700 (W286 baseline). JS bottom
  half. Backup of the previous W287+W288 attempt is at
  `desktop/src-tauri/web/index.html.bak-w289`.
- `scripts/FORCE-REBUILD-TARS.command` — rebuilds + installs + relaunches the
  Tauri app. Also resets `~/.tars/state.json:first_boot_done=false` so the
  first-boot voice greeting fires next launch.
- `scripts/INSTALL-FRESH-TARS.command` — installs the freshly built `.app`
  without recompiling (useful when only HTML changed and the bundle is fresh).

## Hard constraints — do NOT regress

1. **No background hum.** `_vcInitHum` and `_vcSetHumVolume` must stay
   no-op (W286-2). Earlier builds had 3 oscillators + LFO drone.
2. **Single CSS layer for the cockpit.** Do not stack W230-W288 style
   archaeology. The W286 block (`/* W286 — STUDIO COCKPIT */`) is the only
   active layer. Add ONE new clearly-marked block — never re-introduce the
   stripped W287/W288 markers.
3. **No `display: grid !important` on `body`** unless every breakpoint
   (incl. ≤900px) is covered. The previous W288 grid override caused the
   sider+rail to disappear when the Tauri window was <800px.
4. **`bundle: { active: false }` in `tauri.conf.json`** — DMG bundling
   fails on this machine. `tauri build` exits non-zero but `.app` builds
   successfully. The rebuild script already handles this.
5. **Voice flow stays intact.** Greeting fires via `ttfvMaybeStart()` on
   first boot. ElevenLabs Adam (`pNInz6obpgDQGcFmaJgB`) is configured via
   `ELEVENLABS_API_KEY` in `.env`. The `speak()` in FB namespace parses
   JSON `{audio_url: "data:audio/mpeg;base64,…"}` from `/api/a11y/speak`,
   NOT raw blob.
6. **First-boot mic permission is non-blocking** (fire-and-forget). Do not
   `await getUserMedia()` before showing the greeting.

## Suggested skill workflow

1. Invoke the `futuristic-ui-ux-designer` skill (it should auto-trigger on
   words like "futuristic", "cockpit redesign", "high-end SaaS dashboard").
2. Reference these inspiration anchors: Mass Effect Andromeda HUD, Stripe
   Atlas dashboards, Linear's command palette, Apollo GraphQL Studio.
3. Constrain palette to current tokens: `--accent: #7C5CFF` (indigo),
   `--bg: #0a0a0f`, `--text-primary: #f7f7fa`. Inter for sans, JetBrains
   Mono for code.
4. Spacing rhythm: 4px grid. Sider 240px (collapses to 56px ≤900px).
   Rail 320px. Cockpit fills the rest.
5. The `<canvas id="vcWaveCanvas">` is already wired to a WebAudio FFT —
   reuse `_drawWave(t)` to render whatever waveform style fits the new
   design instead of replacing the canvas pipeline.
6. Verify: run `scripts/FORCE-REBUILD-TARS.command`. The script auto-touches
   `main.rs` (Cargo cache invalidation), rebuilds, installs to
   `/Applications/TARS.app`, clears Gatekeeper quarantine, launches.

## Acceptance test

Open the app. Within 3 seconds:
- Auth screen → "Continue local-only →" works
- Cockpit appears with the new visual treatment, no overlaps
- ElevenLabs Adam voice greets in English on first boot
- Mic button responds to click (toggle state visible)
- Text input accepts a command and posts to `/api/chat`
- No console errors related to `_w287InjectRichStudio` /
  `_w288InjectFuturistic` (both are no-ops, calls are removed)

## Quick-look at the skill once installed

```bash
SKILL_DIR=$(find ~/.claude/skills ~/.agents/skills -maxdepth 2 -type d \
            -iname '*futuristic*ui*ux*' 2>/dev/null | head -1)
cat "$SKILL_DIR/SKILL.md"
```
