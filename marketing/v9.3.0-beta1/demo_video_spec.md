# Demo video spec — TARS v9.3.0-beta1

> Length: 90 seconds.
> Format: 1920x1080, 60fps. Master file: ProRes 422 HQ. Delivery: H.264 MP4, ~25 Mbps.
> Tone: cinematic, restrained. No stock music drops. Voice-over only where text overlay is insufficient.
> Use this as the storyboard for a contractor or for a Veo / Sora generation pass.

---

## Frame-by-frame storyboard

| t (s) | duration | scene | on-screen text | audio | b-roll |
|---|---|---|---|---|---|
| 00:00 | 3s | **Cold open** — pitch-black frame, single white pixel pulsing center. Two beats. | (none) | low hum at -28dB | — |
| 00:03 | 5s | Pixel resolves into the TARS monolith — black slab, ambient violet rim light. Camera pulls back slowly. | "Cursor was for code." (top, 60% opacity) | hum lifts into a soft drone | monolith ambient |
| 00:08 | 4s | Text replaces. | "Everything else is still ChatGPT tabs." (top, fade) | drone holds | monolith ambient |
| 00:12 | 4s | Hard cut to a Mac desktop. Cursor opens a Terminal window. The user types `bash REBUILD-TARS-APP.command`. Progress bar fills. | "Unbox in 50 seconds." (bottom) | typewriter click on each character | screen recording, 1.2x speed |
| 00:16 | 8s | Time-lapse of the rebuild progress bar — 0% to 100% in 5s real time, compressed. Final beat: "Done. Launching TARS.app." prints in green. | (none — let the script output speak) | terminal click track, ascending pitch | screen recording, 4x speed |
| 00:24 | 4s | TARS.app icon bounces in the Dock. Window opens. Auth screen renders — magic-link field + "Skip — local-only mode" button. Cursor hovers Skip, clicks it. | "Free forever. No login required." (right of click target) | UI tap sound | screen recording, real time |
| 00:28 | 5s | Cockpit boots. Cinematic monolith fades in center frame, dark backdrop, ambient hum rises. Status pill bottom-left: "local mode • doctor: ok • 10/10 checks". | "v9.3.0-beta1 — Wave A." (top right) | drone returns, layered with cockpit ambient | live cockpit |
| 00:33 | 5s | User taps the mic, speaks: "Open agents." Voice level visualizer pulses with the waveform. The agents drawer slides in from the right. | "Voice-native. whisper.cpp baked in." (bottom) | user voice, mic input | live cockpit, voice on |
| 00:38 | 4s | User types `@` in the chat input. Resolver popup appears: `@file:`, `@docs:`, `@web:`, `@code:`, `@recent:`, `@agent:`. User picks `@file:`, types "foo", picks `src/foo.py`. | "@mentions — Cursor primitive, your whole life." (top) | typing click | live cockpit |
| 00:42 | 5s | User types "summarize this file" and hits enter. Streaming response appears. The model dropdown in the header shows "claude-3.5-sonnet · $0.003/req". A small badge appears: "receipt #4471 anchored". | "Every action emits a receipt." (bottom) | streaming token whoosh, soft chime on receipt | live cockpit |
| 00:47 | 5s | User hits Cmd+K. Palette opens. They fuzzy-search "mcp", land on "Settings → MCP Servers", press enter. The settings page slides in. Three MCP servers listed — local stdio + remote SSE. Toggles green. | "Cmd+K palette v2 — 10ms on 5k entries." (top right) | palette open whoosh | live cockpit |
| 00:52 | 6s | Cut to consumption console reveal. Top banner shows "Usage: 32% of monthly tier". Per-day spend chart. Per-action breakdown table. The number ticks up live as the previous summarize call lands as a usage event. | "Consumption console — every token, every receipt." (bottom) | soft tick on each chart update | live cockpit, real data |
| 00:58 | 6s | Cut to the tier cap banner mock-up at 80%. "Soft warning. Topup via meeet.world." button. Cursor hovers but does not click. | "Soft cap at 80%. Hard block at 100%. No surprise invoices." (top) | none — let UI breathe | live cockpit |
| 01:04 | 5s | Wide shot of the cockpit, monolith center, all surfaces visible — header model switcher, status bar, agents tray, mic pill, consumption preview chip. Camera slow zoom out. | "TARS v9.3.0-beta1" (top, large) | drone resolves into a tonal chord | full cockpit |
| 01:09 | 6s | Cut to black. White text fades up. | "TARS — built locally. Billed through meeet.world." (center) | drone holds | — |
| 01:15 | 5s | URL fades up below. | "tars.meeet.world/download" (center, below tagline) | tonal chord resolves | — |
| 01:20 | 10s | Hold black with URL. End card. Subtle pulse of the monolith glyph (⌐■_■) bottom-right. | "v9.3.0-beta1 — beta channel" (footer) | silence, then final low hum fade | — |
| 01:30 | END | — | — | — | — |

---

## Audio direction

- **Bed:** single ambient drone, layered slowly. Reference: Hans Zimmer "Day One" stripped of strings.
- **Voice-over:** none for v1. If we add VO, keep it under 25 seconds total — voice as accent, not narration.
- **UI sound design:** all sounds custom. No stock library. Click is a soft thump at 80Hz; receipt chime is a single bell at 1320Hz with 200ms decay.
- **Loudness:** -16 LUFS integrated. -1 dBTP peak.

## Visual direction

- **Color:** desaturated. Monolith is true black. Accent is violet `#7c3aed` (meeet brand). No gradients in UI shots.
- **Typography:** SF Pro Display for overlays. 200 weight for primary text, 600 for the tagline.
- **Cuts:** never faster than 0.4s. The whole video is twelve cuts; that is the point.

## Distribution targets

- twitter.com — 1080x1080 square crop, captioned hardcoded.
- product hunt gallery — first asset, 1280x720 letterboxed.
- youtube — full 1920x1080, "unlisted" pre-launch then "public" on launch hour.
- landing page hero loop — silent, 1920x1080, autoplay, no audio track.
