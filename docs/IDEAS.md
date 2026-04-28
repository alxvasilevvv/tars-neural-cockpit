# TARS — proposals queue

Ideas for the next sprints. Triage by impact × cost and pull into
`AGENT_HANDOFF.md → Pending` once committed to.

## Cross-cutting (meeet × TARS)

1. **Sampler decision events.** ✅ shipped — every council deliberation
   emits `sampler.decision` with `mode`, `models`, `winner`,
   `winning_stance`, `latency_ms`, `tokens_in/out`, `agreement`,
   `contradictions`. Wired in `traders.summarize_market` and
   `business.daily_brief`. Open work: real LLM voice adapter + a
   `route` flag (see #2).
2. **Edge-vs-cloud routing flag.** Tag every event with
   `route="edge" | "cloud" | "fallback"` so meeet can show a routing map per
   user. TARS becomes a primary edge node.
3. **Session graph.** Maintain a `session_id` parent in `trace_scope`; emit
   `session.opened` / `session.closed` with topic and participants. Powers
   "what was this user up to" reconstruction.
4. **Cost ledger.** Emit `usage.tokens` with model + tier + tokens_in/out per
   meaningful call. meeet aggregates dollars and exposes them in a single
   bill across products. (Council Proposals already track `tokens_in/out`;
   plumb them through to a global event.)
5. **Policy guardrail events.** ✅ shipped — `policy.{allowed,blocked,
   queued,confirm,cancelled}` fire on every destructive-action attempt;
   confirmations persist in the SQLite store with token + TTL. Open work:
   confirmation UI in the cockpit and a "policy mode" badge per pack.
26. **Local trace UI.** ✅ infra shipped — `/api/meeet/events` returns the
    SQLite trail with filters by `kind` / `trace_id` / `since` /
    `only_unpushed`. Owner: design — render this on a dedicated page
    in v3.

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

15. **Local trace viewer.** ✅ infra shipped — `GET /api/meeet/events`
    + `/api/meeet/stats`. Frontend page is the next move (owner:
    design). The SQLite source of truth is `~/.tars/meeet.sqlite`.
16. **Encrypted vault.** Wrap the awareness store in libsodium; key stays in
    Keychain. Required before MLM / business adapters touch real data.
17. **Differential telemetry.** Default-off counters with k-anon aggregation
    that meeet can stream anonymised; opt-in switch in settings.
28. **Replay-on-reconnect.** ✅ shipped — `MeeetClient.replay_unpushed`
    + `POST /api/meeet/replay`. Open work: schedule a periodic replay
    (e.g. every 60s) when ingest is configured.

## Operator / cockpit

18. **Council debug panel.** Backend shipped — every deliberation
    persists in `/api/meeet/events?kind=sampler.decision` and
    `traders.summarize_market`/`business.daily_brief` responses carry
    a `council` block. Owner: design — render the dual-voice diff,
    confidence bars, latency, agreement %, contradictions list.
19. **Action playbooks.** ✅ shipped — JSON under
    `playbooks/<pack>/<name>.json`, runner + `/api/playbooks` HTTP
    surface. Sample playbooks: `traders.morning_check`,
    `business.morning_brief`, `mlm.retention_round`. Open work:
    cockpit palette UI, parallel step blocks, schema validator.
20. **Hotkey palette.** ⌘K opens a fuzzy palette over packs, awareness
    sources, playbooks, recent traces.
26. **Awareness ticker.** ✅ shipped — `<AwarenessTicker/>` consumes
    `/api/awareness/stream` SSE in the Cockpit page. Open work:
    sparkline chart variant, replay-from-trace mode.
27. **Smart response renderer.** Cockpit currently shows raw JSON.
    Add per-action templates that pull `summary` / `top_gainers` /
    `at_risk` / `tldr` / `council.summary` into a HUD card on top of
    the JSON viewer.
29. **Pending confirmations panel.** Backend shipped —
    `/api/policy/pending` returns staged tokens with args/preview.
    Owner: design — a left-rail "approval inbox" with one-click
    confirm / cancel and an audit row.
30. **Awareness explorer.** Backend shipped —
    `/api/domains/<slug>/awareness/<id>/snapshot`. Owner: design —
    per-source live preview cards (calendar list, deals pipeline,
    arXiv abstracts).

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
