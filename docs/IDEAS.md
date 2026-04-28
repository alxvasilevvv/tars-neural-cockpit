# TARS — proposals queue

Ideas for the next sprints. Triage by impact × cost and pull into
`AGENT_HANDOFF.md → Pending` once committed to.

## Cross-cutting (meeet × TARS)

1. **Sampler decision events.** Mirror the meeet sampler: emit
   `sampler.decision` with `mode` (single | dual_vote | n_vote | arbiter),
   `models`, `winner`, `latency_ms`, `tokens`. Lets meeet build per-model
   leaderboards across products.
2. **Edge-vs-cloud routing flag.** Tag every event with
   `route="edge" | "cloud" | "fallback"` so meeet can show a routing map per
   user. TARS becomes a primary edge node.
3. **Session graph.** Maintain a `session_id` parent in `trace_scope`; emit
   `session.opened` / `session.closed` with topic and participants. Powers
   "what was this user up to" reconstruction.
4. **Cost ledger.** Emit `usage.tokens` with model + tier + tokens_in/out per
   meaningful call. meeet aggregates dollars and exposes them in a single
   bill across products.
5. **Policy guardrail events.** Emit `policy.allowed` / `policy.blocked` for
   every Mac-actions call. meeet can audit destructive intent globally.

## Domain pack improvements

6. **Real adapters, behind feature flags.**
   - `traders.binance_pull_klines` (read-only).
   - `business.hubspot_pull_pipeline` (read-only).
   - `mlm.tg_outreach_draft` (returns markdown, no auto-send).
   - `science.arxiv_search` ✅ shipped — `science.search_literature`
     against the public Atom API.
   - `science.summarize_paper` ✅ shipped — Atom by id, returns
     title/authors/tldr/abstract.
   - `traders.fetch_quote` ✅ shipped — DexScreener public search.
   - `traders.summarize_market` ✅ shipped — basket aggregation +
     bias + dispersion contradictions.
   - `business.kpi_snapshot`, `business.daily_brief` ✅ shipped —
     local JSON-backed.
   - `mlm.downline_snapshot`, `mlm.retention_alert` ✅ shipped —
     local CSV-backed; `score_recruit`, `generate_post` upgraded to
     deterministic heuristics.
   Each remaining adapter must call
   `meeet.emit("integration.<vendor>.<call>", ...)`.
7. **Pack composition.** Allow stacking — e.g. "business + science" for
   research-heavy founders. Composition resolves overlapping action ids
   with a deterministic priority.
8. **Per-pack memory partitions.** Memory keys prefixed with the pack slug
   so domain context cannot bleed.
9. **Pack marketplace JSON.** Generate a static `domains.manifest.json` from
   the registry; host it at `/api/domains/manifest` for installer UIs.

## Showcase polish

10. **Idle camera path.** Bezier loop after 12s of no scroll/pointer; resets
    on input. Adds the "alive" feel without forcing engagement.
11. **GLB asset slot UI.** Drag-and-drop a GLB onto the page in dev to
    preview alternate cores; persist to `localStorage` until cleared.
12. **Audio.** ✅ shipped (lib/sound.ts) — ambient hum + UI cues +
    SoundToggle, muted by default. Open work: richer ambient bed
    with 4-5 tones + slow LFO; per-route presence (cockpit cooler,
    landing warmer).
13. **Page-to-cockpit transition.** ✅ shipped — `BrowserRouter` +
    `AnimatePresence` blur-slide between `/` and `/cockpit`. Open
    work: shared overlay sweep on route change.
14. **Dark / light variants.** A cooler "studio" lit variant for
    investor screenshots: still minimalist, but white background and ink
    type. Activated by `?theme=studio`.

## Local-first, privacy

15. **Local trace viewer.** Tail `MEEET_LOCAL_LOG` jsonl into a small page
    `frontend/trace.html` with filter chips and timeline.
16. **Encrypted vault.** Wrap the awareness store in libsodium; key stays in
    Keychain. Required before MLM / business adapters touch real data.
17. **Differential telemetry.** Default-off counters with k-anon aggregation
    that meeet can stream anonymised; opt-in switch in settings.

## Operator / cockpit

18. **Council debug panel.** Live view of last N
    `sampler.decision` events with diff between candidates, model latencies,
    and token costs. Operators see why a vote was won.
19. **Action playbooks.** YAML files under `playbooks/<pack>/<task>.yml` —
    multi-step action chains the operator triggers from a palette.
20. **Hotkey palette.** ⌘K opens a fuzzy palette over packs, awareness
    sources, recent traces.
26. **Awareness ticker.** ✅ shipped — `<AwarenessTicker/>` consumes
    `/api/awareness/stream` SSE in the Cockpit page. Open work:
    sparkline chart variant, replay-from-trace mode.
27. **Smart response renderer.** Cockpit currently shows raw JSON.
    Add per-action templates that pull `summary` / `top_gainers` /
    `at_risk` / `tldr` into a HUD card on top of the JSON viewer.

## Engineering

21. **Contract tests against meeet ingest.** A tiny `tests/contracts/`
    that asserts the event schema we emit matches the latest contract pin.
22. **Replay.** A CLI `python -m backend.core.meeet.replay path.jsonl --to
    https://...` so we can re-emit local logs into a fresh ingest.
23. **Docs site.** Build `docs/` into a static site under `dist-docs/` using
    one of the existing scripts (no new deps).

## Branding

24. **TARS one-liner.** Lock the tagline: "TARS — your machine, awakened."
    Carry through hero, app icon, social cards.
25. **Social cards.** Render OG cards from the showcase scene at build time
    (puppeteer is already a transitive of postprocessing dev tooling — no
    new top-level dep). Or fall back to static SVGs.
