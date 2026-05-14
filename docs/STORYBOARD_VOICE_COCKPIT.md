# Voice Cockpit — Storyboard (W230)

**Aesthetic:** TARS minimalism (Interstellar black monolith, deliberate
motion) fused with JARVIS density (Iron-Man concentric rings,
holographic HUD, audio-reactive particles). Not Tony Stark's hologram
floating in a lab — this is a real desktop dashboard for a cockpit user.

**Surface:** `desktop/src-tauri/web/index.html` — the Tauri WebView shell
that runs post-auth.

**Palette tokens (CSS custom properties):**

| Token            | Value                  | Purpose                            |
|------------------|------------------------|------------------------------------|
| `--vc-bg`        | `#000`                 | Stage background                   |
| `--vc-mono-fill` | `#0a0a14 → #050509`    | Monolith body gradient             |
| `--vc-strip-a`   | `#06b6d4` (cyan)       | Light strip / inner ring (speaking)|
| `--vc-strip-b`   | `#8b5cf6` (violet)     | Light strip / outer ring (listen)  |
| `--vc-ring`      | `rgba(167,139,250,.7)` | Default ring stroke                |
| `--vc-hud`       | `#06b6d4`              | HUD text                           |
| `--vc-hud-soft`  | `rgba(6,182,212,.18)`  | HUD background tint                |
| `--vc-glitch`    | `#a78bfa`              | Scan / glitch overlay              |

All values exist as fallbacks if `:root` doesn't define them (the file
already declares `--accent`, `--accent-hot`, `--text`, `--muted`).

**State machine:** `body[data-vc-state]` switches between
`idle | listening | thinking | speaking`. Every keyframe / opacity ramp /
ring formation is driven through `[data-vc-state="…"]` selectors so JS
doesn't ever touch styles directly. Drives audio hum volume too.

**Reduced-motion fallback (global):** wrapped in
`@media (prefers-reduced-motion: reduce)` — kills all rotation,
breath, scan-line, glitch, and particle drift. Static layout still
reads: monolith + a single ring + HUD chrome. State changes become
opacity-only.

---

## Frame 1 — Boot

The very first paint after auth resolves. Monolith fades up from pure
black; a vertical light strip "charges" bottom-to-top over ~1.2 s.

```
+----------------------------------------------------------+
|                                                          |
|                                                          |
|                          .                               |
|                          |                               |
|                          #  <- monolith fading 0->1      |
|                          #                               |
|                          #  <- strip charges from bottom |
|                          #     (clip-path inset(100% 0 0 0) |
|                          #      -> inset(0 0 0 0))       |
|                          |                               |
|                          '                               |
|                                                          |
+----------------------------------------------------------+
```

- **State class:** `data-vc-state="idle"` + transient `.vc-booting`
  (removed after 1.5 s via `setTimeout`).
- **Easing:** `cubic-bezier(.2, .8, .2, 1)` ("entry curve"), 1200 ms.
- **Opacity ramp:** `.monolith { opacity: 0 -> 1 }`,
  `.monolith-strip { clip-path: inset(100% 0 0 0) -> inset(0 0 0 0) }`.
- **Rings:** invisible (`opacity: 0`).
- **HUD:** present but `opacity: 0` -> `0.6` at 800 ms.
- **Particles:** not initialised yet (deferred to `requestIdleCallback`).
- **Hum:** silent.
- **A11y:** under reduced-motion the strip appears at full height
  immediately; only opacity 0->1 runs.

---

## Frame 2 — Idle

Default resting state. The monolith breathes; faint particle dust
drifts in the 800x600 region around it; the hum is at -24 dB (vol 0.06).

```
+----------------------------------------------------------+
| STATE  IDLE                                LAT  37 ms    |
| LEVEL  0.00                                              |
| TIER   FREE                                              |
|                                                          |
|              .   .                .    .                 |
|         .         .     .     .          .               |
|             .          #                  .   .          |
|       .                #          .                      |
|           .    .       #     .       .     .             |
|      .                 #                    .            |
|            .     .     #                                 |
|       .                #     .    .                      |
|                  .     |            .                    |
| +--------------------+ '                                 |
| | > you:  ...        |                                   |
| | < TARS: standing by|                  O======  Cmd+Shift+Space  |
| |   status: idle     |                  ^ mic button     |
| +--------------------+                                   |
+----------------------------------------------------------+
```

- **State class:** `data-vc-state="idle"`.
- **Animation:** `.monolith` runs `monolith-breath 4s ease-in-out
  infinite` — opacity 0.6 -> 0.9, scaleY 1.00 -> 1.015.
- **Strip:** opacity tied to `--mic-level` (0 here) -> 0.35 baseline.
- **Rings:** middle ring `opacity: 0.08` (just a hint of the geometry),
  outer ring hidden, inner ring hidden.
- **Particles:** drift slow (vx, vy in +/- 0.05 px/frame),
  `opacity: 0.15 + (--mic-level * 0.45)`.
- **HUD chips:** glass-morph (`backdrop-filter: blur(8px)`,
  `border: 1px solid rgba(6,182,212,.25)`).
- **Hum:** 0.06 volume, 80+120+160 Hz oscillator stack.
- **A11y:** reduced-motion kills breath + drift; HUD opacity 0.6 static.

---

## Frame 3 — Wake (`Cmd+Shift+Space`)

User hits the global shortcut (or clicks mic). A scan line sweeps
top-to-bottom in ~250 ms; the monolith brightens; the three rings
materialise from `scale(0.85)` to `scale(1.0)`.

```
+----------------------------------------------------------+
|   ==================================== <- scan           |
|                                                          |
|                    +-----------+                         |
|                  /    +-----+    \                       |
|                 /   /  | . |  \   \    <- rings appear   |
|                |   |   | # |   |   |                     |
|                |   |   | # |   |   |   inner  r=80       |
|                |   |   | # |   |   |   middle r=130      |
|                 \   \  | # |  /   /    outer  r=200      |
|                  \    +-----+    /                       |
|                    +-----------+                         |
+----------------------------------------------------------+
```

- **State class:** `data-vc-state="listening"`.
- **Wake transient:** add `.vc-wake-flash` for 250 ms — a CSS overlay
  that translates a 4 px-tall cyan strip from `top: -10%` to
  `top: 110%`, with `box-shadow: 0 0 24px var(--vc-strip-a)`.
- **Rings entry:** `transform: scale(.85) -> scale(1)`, easing
  `cubic-bezier(.16, 1, .3, 1)` ("snap-out"), 400 ms.
- **Monolith brightness:** `box-shadow` cyan halo grows to
  `0 0 80px rgba(6,182,212,.55)`.
- **Hum:** ramp 0.06 -> 0.12 over 200 ms.
- **A11y:** reduced-motion replaces the scan with a static `opacity:1`
  full-height bar that fades in/out over 150 ms.

---

## Frame 4 — Listening

The real working state. Rings rotate continuously; the outer ring
deforms with audio FFT (16 control points each driven by a frequency
bin); the live transcript streams into the bottom-left panel.

```
+----------------------------------------------------------+
| STATE  LISTENING                          LAT  37 ms     |
| LEVEL  0.42                                              |
| TIER   FREE                                              |
|                                                          |
|                  / \      - - -                          |
|                 /   \   /        \    <- outer ring      |
|                |    | |  -- --   | |     deforming with  |
|                |    | | /      \ | |     FFT bins        |
|                | >> | | | # .  | | |                     |
|                |    | | | #    | | |  <- middle ring     |
|                |    | | \      / | |     16 ticks        |
|                 \   /   \      /      <- inner ring      |
|                  \ /      - - -          dashed, spin    |
| +--------------------------------+                       |
| | > "open agents tab"            |                       |
| | < TARS: standing by            |                       |
| |   status: listening... 0.42    |                       |
| +--------------------------------+                       |
+----------------------------------------------------------+
```

- **State class:** `data-vc-state="listening"`.
- **Inner ring:** `r=80`, dashed (`stroke-dasharray: 4 6`),
  `animation: ring-spin-cw 18s linear infinite`.
- **Middle ring:** 16 tick marks (`<line>` at every 22.5deg), each
  tick's opacity = `0.2 + (--mic-level * 0.8)`.
- **Outer ring:** `<path d="...">` with `d` recomputed every
  `requestAnimationFrame` from 16 FFT bins; radius oscillates
  `200 + bin * 30`.
- **Easing:** rotation is linear (mechanical feel); the FFT path uses
  smooth cubic Bezier between control points so spikes never feel
  jagged.
- **Monolith strip:** opacity = `0.4 + (--mic-level * 0.6)`, also
  scaleY-stretches subtly (`scaleY(1 + level * 0.05)`).
- **Hum:** 0.12 volume.
- **A11y:** reduced-motion freezes rotation; FFT deformation falls back
  to a static circle, opacity still tracks level.

---

## Frame 5 — Thinking

User stopped speaking, audio is being transcribed + dispatched.
Rings collapse inward, a glitch scan plays over the monolith, a small
"processing" arc rotates fast.

```
+----------------------------------------------------------+
| STATE  THINKING                           LAT  37 ms     |
| LEVEL  0.00                                              |
| TIER   FREE                                              |
|                                                          |
|                                                          |
|                       +-----+                            |
|                      /  o    \    <- processing arc      |
|                     |  +--+   |      270deg gap, 0.7s    |
|                     |  |##| _ |      full rotation       |
|                     |  |##|   |  <- glitch scan over body|
|                      \ +--+  /       (CSS clip-path      |
|                       \     /         offset every 80ms) |
|                        -----                             |
|                                                          |
| +--------------------------------+                       |
| | > "open agents tab"            |                       |
| | < thinking...                  |                       |
| |   status: dispatching          |                       |
| +--------------------------------+                       |
+----------------------------------------------------------+
```

- **State class:** `data-vc-state="thinking"`.
- **Rings collapse:** outer ring `scale(1) -> scale(0.7)` 400 ms,
  easing `cubic-bezier(.7, 0, .84, 0)` ("snap-in").
  Middle ring fades to `opacity: 0.15`.
- **Inner ring -> processing arc:** swap `stroke-dasharray` to
  `400 600` so 270deg of the circle is solid and 90deg is gap;
  `animation-duration` becomes `0.7s` (was 18 s).
- **Glitch overlay:** `.monolith-glitch::before` runs
  `keyframes glitch-scan { 0%,100%{clip-path: inset(0 0 0 0)}
  25%{clip-path: inset(10% 0 70% 0); transform: translateX(2px)}
  50%{clip-path: inset(60% 0 20% 0); transform: translateX(-3px)} ... }`,
  240 ms, ease-in-out, plays 3x.
- **Hum:** 0.10 volume (slightly attenuated).
- **A11y:** reduced-motion swaps glitch for a 200 ms opacity 1->0.5->1.

---

## Frame 6 — Speaking

TARS replies via TTS. Rings reform in a cyan-dominant palette; the
monolith's inner strip flows top->bottom synced to speech; captions
render under the monolith.

```
+----------------------------------------------------------+
| STATE  SPEAKING                           LAT  37 ms     |
| LEVEL  0.00                                              |
| TIER   FREE                                              |
|                                                          |
|                  +-----------+                           |
|                /    -------    \     <- inner ring SOLID |
|               |   | .       |   |      now (was dashed)  |
|               |  -| | v     |-  |   <- strip flows down  |
|               |   | | #     |   |      cyan dominant     |
|               |   | | #     |   |                        |
|               |   | | v     |   |                        |
|                \    -------    /                         |
|                  +-----------+                           |
|        +------------------------------+                  |
|        | "Opening agents tab. Three   |  <- captions     |
|        |  agents in your roster."     |                  |
|        +------------------------------+                  |
+----------------------------------------------------------+
```

- **State class:** `data-vc-state="speaking"`.
- **Inner ring:** drops the dash (`stroke-dasharray: 0`), stroke
  shifts to cyan (`var(--vc-strip-a)`), spin slows to 30 s.
- **Outer ring:** static path, no FFT deformation (we don't have STT
  audio output level — could later wire TTS analyser, but skip for
  now).
- **Strip direction:** `monolith-speak-flow` keyframes — a vertical
  gradient `linear-gradient(180deg, transparent, cyan, transparent)`
  with `background-position-y: -100% -> 100%` over 2 s, infinite.
- **Captions:** `.vc-captions` glass card centred under the monolith,
  fades in over 300 ms.
- **Easing:** ring formation `cubic-bezier(.2, .8, .2, 1)` 350 ms.
- **Hum:** muted to 0 (speech should not compete with the drone).
- **A11y:** reduced-motion stops the strip flow; captions remain.

---

## Frame 7 — Action dispatched

A side effect of the assistant's reply (e.g. `open_tab:agents`,
`run_doctor`, `show_today`). A short flash + a tag chip slides down
from `top: -32px` to confirm what happened.

```
+----------------------------------------------------------+
|                  +- > opened agents -+                   |
|                  +---------------------+  <- tag chip    |
|                                                          |
|                    ------- flash -------                 |
|                  /                       \               |
|                 |      (rings as in F6)   |              |
|                  \                       /               |
|                    -------------------                   |
|                                                          |
+----------------------------------------------------------+
```

- **Tag chip:** new DOM node `.vc-action-tag` appended near top-center;
  CSS animation `tag-drop` translates `translateY(-32px) -> 0`,
  500 ms `cubic-bezier(.34, 1.56, .64, 1)` (overshoot bounce),
  then stays for 1.8 s, then fades + translates up 200 ms.
- **Flash:** `.vc-flash` overlay, full-screen, `background: radial-
  gradient(closest-side, rgba(6,182,212,.18), transparent)`, opacity
  `0 -> 0.6 -> 0` over 320 ms.
- **State class:** unchanged from F6 (`speaking`) — the action chip
  is decoration, not a state.
- **Sound:** could play a 40 ms click cue (deferred — not in W230).
- **A11y:** reduced-motion replaces drop with simple fade-in.

---

## Frame 8 — Drawer open

User clicks ☰ hamburger. The monolith slides ~120 px right, the
800x600 panel containing Status / Agents / Chat / Settings tabs slides
in from the left.

```
+----------------------------------------------------------+
| #==========================#                             |
| #  =  STATUS  AGENTS  ...   #                            |
| #                          #          .                  |
| #  +- /api/doctor -----+   #          |                  |
| #  |  10 ok / 0 warn   |   #          #  <- monolith     |
| #  +-------------------+   #          #     translated   |
| #                          #          #     right        |
| #  +- agents ------------+ #          |                  |
| #  | . planner           | #          '                  |
| #  | . code              | #                             |
| #  +---------------------+ #                             |
| #==========================#                             |
+----------------------------------------------------------+
```

- **State class:** the existing `.cockpit-panel-drawer.show` controls
  the drawer. New: `.voice-cockpit.drawer-open` shifts the stage.
- **Stage offset:** `.voice-cockpit.drawer-open .vc-stage {
  transform: translateX(120px); }`, 280 ms
  `cubic-bezier(.2,.8,.2,1)`.
- **Rings:** unchanged — they just translate with the stage.
- **Hum:** unchanged.
- **A11y:** reduced-motion still translates but jumps without easing
  (`transition: none`).

---

## State summary

| State       | Inner ring     | Middle ring   | Outer ring   | Strip            | Hum  | Particles  |
|-------------|----------------|---------------|--------------|------------------|------|------------|
| `idle`      | hidden         | 0.08 opacity  | hidden       | breath           | 0.06 | slow drift |
| `listening` | dashed, spin   | 16 ticks, lvl | FFT deform   | scale w/ level   | 0.12 | wake up    |
| `thinking`  | proc arc 0.7s  | fades to 0.15 | collapses    | glitch overlay   | 0.10 | freeze     |
| `speaking`  | solid cyan     | 0.4 static    | static       | top->bottom flow | 0    | slow drift |

## Implementation pointers

- All four layers (A monolith, B rings, C HUD, D particles) live
  inside the existing `.vc-stage` container.
- Ring SVG uses a single `<svg viewBox="-250 -250 500 500">` so the
  centre is (0,0) — easier math for path control points.
- Canvas for particles is `position: absolute; inset: 0;
  pointer-events: none; z-index: 0` (below monolith, above stage
  background).
- `vcSetState(state)` is the single entry point — JS never sets
  inline styles for state-driven properties. The data-state selector
  pattern keeps CSS the source of truth.
- `--mic-level` is already wired through `_vcMicLevelLoop` (W229);
  the new layers just read the same custom property.

## Accessibility

- All animations behind `@media (prefers-reduced-motion: reduce)`.
- HUD text contrast: cyan `#06b6d4` on `#000` = 6.1:1 — passes WCAG
  AA for 9px monospace (treated as 'large bold' equivalence by
  typeface).
- Captions / transcript always rendered as real text, never SVG-only.
- ARIA live region on `#vcTranscript` (`aria-live="polite"`) so
  screen readers announce TARS replies without rude interruption.
- Keyboard: `Cmd+Shift+Space` toggles mic, `Esc` closes drawer, focus
  trap inside drawer when open.
