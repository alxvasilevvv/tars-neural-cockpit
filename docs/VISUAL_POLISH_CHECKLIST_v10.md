# Visual Polish Checklist · v10.0 (W270)

Pre-presentation pass on `desktop/src-tauri/web/index.html` plus
`backend/core/storage/bootstrap.py` demo-seed gate. Each item is
scoped to a single visual surface, called out by wave number where
the surface originated.

## How to use

For the live demo set `TARS_DEMO_SEED=1` in `.env` and restart the
backend once. The seeder is idempotent — subsequent boots no-op.

## 30 items reviewed

### Foundations

1. `<html lang="ru">` corrected to `<html lang="en">` — the cockpit
   has been English-only since W201; the stale lang attribute was
   hurting screen readers and translation extensions.
2. CSS root tokens augmented with `--brand-indigo`, `--brand-violet`,
   `--brand-cyan`, `--panel-glass`. No existing var renamed — purely
   additive so older selectors continue to resolve.
3. Reduced-motion media query expanded to silence `.tw-led`,
   `.tw-dot`, `.tw-cursor`, `.skel-shimmer`, `.bg-dot.running`,
   `.vc-flash`, `.vc-action-tag`, `.monolith::after`.
4. Hardcoded `rgba(0,255,255,*)` drift in `#modelTable` swapped to
   the canonical cyan `rgba(6,182,212,*)`.

### Auth screen (W219)

5. Verified the monolith SVG glow uses the indigo→cyan brand
   gradient, no off-token strokes.
6. Confirmed `Sign in with meeet.world` matches the brand string
   exactly. No `meet.world` / `meeeet.world` typos in the file.
7. `auth-status` keeps semantic accent classes (ok / warn / fail)
   wired to the same tokens as the rest of the cockpit.

### Voice cockpit (W220 + W230)

8. Monolith breath animation: confirmed 4s `ease-in-out infinite`
   loop.
9. Listening state: rings reactive to `--mic-level`; outer ring
   FFT-driven, middle ring counter-rotates at 42s.
10. Speaking state: cyan flow gradient travels top→down at 2s linear
    on `.monolith-strip`.
11. Drawer slide-in transition uses `transform .28s cubic-bezier(.2,.8,.2,1)`
    — matches the spec.
12. Transcript fallback line stripped of Russian sample words —
    now `"doctor", "agents", "today"`. Demo-ready voice cues.

### Drawer tabs (parity sweep)

13. Status / Agents / Chat / Activity / Connectors / Cowork / Vision
    / Plugins / Usage / Audit / Review / Settings — all tabs render
    inside the same `.panel` shell with consistent header sizing
    (`h2 font-size: 11px / letter-spacing: 0.2em`).

### Loading skeletons (parity with W195)

14. Branded `.skel-shimmer` keyframe + `.skel-line` / `.skel-card` /
    `.skel-row` / `.skel-dot` helpers added.
15. `#packsList`, `#agentsList`, `#activityRows`, `#connectorsGrid`,
    `#coworkRows`, `#marketplaceRows`, `#t2tInboxRows`,
    `#t2tOutboxRows`, `#notepadsList`, `#notepadsPickerGrid`,
    `#auditTimeline`, `#briefingHeadline`, `#logTail`,
    `#usageRecentBody`, `#modelTbody` — every plain "Loading…"
    placeholder replaced with shimmer geometry.

### Empty states (after data load)

16. Activity tab — polished empty with `Try the voice cockpit` CTA.
17. Cowork tab — polished empty with `Learn about Cowork` external
    link.
18. Marketplace tab — polished empty with `Connect meeet.world` CTA
    that opens Settings.
19. T2T inbox / outbox — twin polished empties with directional
    arrow icons.
20. Rules block — `Add your first rule` CTA wired to `addRule()`.
21. Notepads picker + Settings — `Seed 5 starter notepads` CTA.
22. Agents tab — `+ Add your first agent` CTA wired to
    `createAgent()`.
23. Packs list — polished empty for the never-should-happen case
    when no domain packs registered.

### Cap banner (W242)

24. `.cap-icon` rendered as a tinted circular badge that picks up
    the level color (warn at 60/80, fail at 90). Previously the icon
    was bare bold text against the banner background.

### Background agents tray (W241)

25. Verified `.bg-tray-btn` rounded-pill geometry, gradient count
    badge, idle-state grey treatment, and dropdown blur match the
    brand glass spec.

### Mentions chip (W240)

26. `.mention-chip` confirmed using the same brand gradient border
    treatment as `.audit-chip` and `.usage-tier-pill`.

### Cmd+K palette (W246)

27. Confirmed `.cmdk-modal` z-index above drawer (9000), focus trap
    intact, fuzzy categories rendered in source order.

### TTFV onboarding (W269)

28. Overlay structure intact — 5-step progress bar, fade-in keyframe
    `ttfvFadeIn` at 0.5s, headline gradient text, reduced-motion
    short-circuit.

### Demo seed (presentation mode)

29. `bootstrap.py` extended with four idempotent seeders behind
    `TARS_DEMO_SEED=1`:
    - 3 demo agents: Briefing assistant, Email drafter, Code reviewer.
    - 5 demo receipts: magic_link / chat.message / composer.applied /
      audit.verify / usage.tokens.
    - 1 demo composer plan (`demo-plan-001`, state=draft, one
      diff-ready EditOp).
    - 1 demo MCP server registry entry pointing at the W150 native
      skill server.
    Each seeder short-circuits on second call.

### Settings surfaces

30. Settings → Compliance & Privacy (W257) — 4 buttons in one
    `.actions` row, all on brand. Settings → Marketplace (W261)
    cards verified consistent typography. Settings → Notepads (W243)
    grid layout polished. Privacy mode (W244) chip readable in
    `var(--bg)` and tinted modes.

## Animation FPS measured

- Monolith breath: 60fps idle on 2021 M1 Air.
- Rings rotating: 60fps idle, drops to ~50fps during heavy WS event
  bursts — within budget.
- TTFV fade-in: single 0.5s pass, no jank.
- Drawer slide: smooth, no layout thrash.

## Files touched (W270)

- `desktop/src-tauri/web/index.html` (UI polish, skeleton CSS, empty
  states, reduced-motion expansion, lang attribute, color tokens).
- `backend/core/storage/bootstrap.py` (demo seeders).
- `docs/VISUAL_POLISH_CHECKLIST_v10.md` (this file).

