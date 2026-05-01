# Wave 52 handoff — Black-screen fix at dev 127.0.0.1:5174

**Symptom:** Dev server at `http://127.0.0.1:5174/` shows entire viewport black. Hero, content, everything black.

**Diagnosis:** Three combined causes from your recent desktop-mode refactor.

## Root causes (in order of impact)

### 1 · Hero `<Suspense fallback={null}>` strands the veil overlay

`src/components/Hero.tsx:114` — when `ShaderAnimation` lazy chunk is loading (or fails to load), the Suspense fallback returns `null`. The veil overlay below it (`rgba(7,7,10,0.78)` radial gradient) still renders on top of nothing. Whole viewport reads as ~78% black.

**Fixed:** Suspense `fallback` now renders an on-brand transparent gradient layer so the veil never paints over a void.

### 2 · `ShaderAnimation` silently fails on broken WebGL contexts

`src/components/ui/shader-lines.tsx` — `THREE.WebGLRenderer` constructor can fail (no GPU, headless browser, CSP sandbox, blocked context). Old code blindly appended `renderer.domElement` which defaults to opaque black canvas. Combined with #1 above = full black.

**Fixed:**
- Added pre-flight WebGL probe via `canvas.getContext("webgl2"|"webgl")` — bails out cleanly to fallback gradient if no WebGL.
- Wrapped `WebGLRenderer` constructor in try/catch with `setGlFailed(true)` on failure.
- Added `renderer.setClearColor(0x000000, 0)` so the canvas is transparent (not solid black) even if shader compilation half-fails.
- When `glFailed=true`, the container div renders an on-brand radial gradient (indigo → violet → cyan tint) instead of a broken canvas.

### 3 · Service Worker still serves stale precache

`public/sw.js:25` — `VERSION = "tars-v9.0"` hadn't changed since the desktop-mode refactor. Visitors who loaded the page before the refactor get the old precached `/` document on every reload, including hard reload (precache wins).

**Fixed:** Bumped to `tars-v9.0.1`. New SW will activate, blow away old precache, fetch the new bundle.

## Files changed

- `experiments/neural-showcase-v3/src/components/Hero.tsx` — Suspense fallback now a gradient
- `experiments/neural-showcase-v3/src/components/ui/shader-lines.tsx` — WebGL probe + try/catch + transparent clear + CSS fallback
- `experiments/neural-showcase-v3/public/sw.js` — VERSION bump to `tars-v9.0.1`

## What Cursor needs to do

```bash
cd ~/Documents/Claude/Projects/Jarvis/jarvis

# 1) Pull (Claude has uncommitted fix patches)
git status

# 2) Sanity check the three files exist with my edits
git diff experiments/neural-showcase-v3/src/components/Hero.tsx
git diff experiments/neural-showcase-v3/src/components/ui/shader-lines.tsx
git diff experiments/neural-showcase-v3/public/sw.js

# 3) Type-check
cd experiments/neural-showcase-v3
npx tsc --noEmit -p tsconfig.app.json
# expect: 0 errors

# 4) Restart dev server (kill old)
pkill -f "vite" 2>/dev/null
npm run dev
# open http://127.0.0.1:5174/
# expect: hero renders with shader OR with brand gradient fallback, not black

# 5) If still black after restart — flush SW manually:
#   DevTools → Application → Service Workers → Unregister
#   DevTools → Application → Cache Storage → delete all tars-v9.0* entries
#   Hard reload (⌘⇧R)
# After SW v9.0.1 activates, future updates will auto-flush.

# 6) Test in incognito to confirm fresh boot path
# Open chrome --incognito http://127.0.0.1:5174/

# 7) Commit + push as one rolled-up commit
git add -A
git commit -m "fix(hero): black-screen at dev 5174 — shader init + Suspense fallback + SW cache

Three combined causes after desktop-mode refactor:
- Hero Suspense fallback returned null; veil overlay paints over void
- ShaderAnimation didn't guard WebGLRenderer constructor; broken canvas
  paints solid black underneath the veil
- SW precache version pinned at v9.0; users get stale broken bundle

Fixes:
- Hero.tsx: Suspense fallback renders an on-brand gradient
- shader-lines.tsx: WebGL probe + try/catch + transparent clear + CSS
  fallback gradient when glFailed=true
- sw.js: VERSION bump to v9.0.1 to invalidate old precache

Closes Wave 52 black-screen regression."

git push origin main
```

## Verification checklist

After push, on a fresh incognito window at `http://127.0.0.1:5174/`:

| # | Expected | Notes |
|---|---|---|
| 1 | Hero renders with shader animation visible | Real WebGL path |
| 2 | Or brand-gradient fallback visible | If WebGL disabled — should still look on-brand |
| 3 | Title "Your AI / Your machine / Your terms" readable | No veil-on-void darkness |
| 4 | DownloadStrip card visible | z-30 content unobscured |
| 5 | Console clean | No "WebGL" / "shader" errors blocking |
| 6 | DevTools → Application → Service Workers shows tars-v9.0.1 active | Old cache evicted |
| 7 | Other routes (`/cockpit`, `/install`, `/onboarding`) render normally | Same Suspense pattern was only on Hero |

## If user still reports black after these fixes

Likely candidates beyond what I've patched:
- Browser extension injecting CSS that hides content (try incognito)
- macOS Reduced Transparency setting interacting with `backdrop-filter` — separate issue
- Cursor's own desktop-mode `isDesktopShell()` returning true incorrectly — need to verify `import.meta.env.VITE_TARS_DESKTOP` is actually `undefined` in browser dev (shouldn't be set unless explicitly passed in `pnpm tauri:dev`)

If you suspect #3 (desktop-mode false-positive), add debug log in `src/lib/shell.ts`:
```ts
console.log("[shell] VITE_TARS_DESKTOP =", import.meta.env.VITE_TARS_DESKTOP);
```
…and check browser console. Should be `undefined` for plain `npm run dev`. If it's `"1"` or truthy — vite config or env-loading is leaking.

## Why this isn't a launch blocker for `tars.meeet.world`

The same fix lands on prod via the next push. Production users on `tars.meeet.world` haven't loaded the broken SW yet (Lovable build is not yet shipped), so they'll get the v9.0.1 SW from first visit. Local devs need the manual SW flush once.

## Quick promt — copy-paste this to Cursor

```
Прочитай docs/HANDOFF_WAVE_52.md.

Claude закрыл регрессию чёрного экрана на dev 5174 — три фикса в трёх файлах
уже лежат локально в working tree:

- experiments/neural-showcase-v3/src/components/Hero.tsx
- experiments/neural-showcase-v3/src/components/ui/shader-lines.tsx
- experiments/neural-showcase-v3/public/sw.js

Сделай:
1. git diff на эти три файла, убедись что патчи правильные
2. cd experiments/neural-showcase-v3 && npx tsc --noEmit -p tsconfig.app.json
3. pkill vite; npm run dev; открой инкогнито 127.0.0.1:5174
4. Проверь — hero рендерится либо с shader, либо с brand gradient fallback, не чёрный
5. Если всё ок — git add -A && git commit (сообщение в HANDOFF_WAVE_52.md разделе "What Cursor needs to do" под пунктом 7) && git push origin main

Если что-то падает на шаге 2 — пинг сюда.
```
