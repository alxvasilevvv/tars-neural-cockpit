# TARS v9.3.0-beta1: closing the Cursor gap, on our terms

> ~800 words. For tars.meeet.world/blog.
> Author: Alien. Date: 2026-05-15.

---

For three years, Cursor has been the best argument for what "AI for X" can feel like. Density. Fast keys. Local files. Inline magic that knows where you live in the tree. Anyone who has shipped real code in 2025 has felt the gap close — every other AI tool sits a half-step behind because Cursor figured out the *interface*, not just the model.

The frustration that built TARS was simple: that magic stops at the IDE boundary. The moment I close Cursor, my entire non-code life — contracts, P&Ls, charts, briefings, medical files, trades, taxes — collapses back into a graveyard of ChatGPT tabs and Notion macros. Half a step behind. Forever.

So we built TARS. v9.3.0-beta1 ships today, and it is the first release where I can honestly say: same interface, same speed, same magic — but pointed at everything that is not code.

## What we shipped this week

Wave A is thirteen waves of work compressed into one tag. The headline is Cursor parity. The four panels TARS was visibly missing — models switcher, MCP servers, rules engine, @-mention context — all landed in W237 through W240. They are not lifted; they are translated. The models switcher reads cost-per-1k-tok live from the provider registry and labels every dropdown entry with a real dollar number, because we already meter every call through the consumption console (W235). The MCP panel surfaces the real bridge that has been quietly running since W150. The rules engine reads `.tars/rules.yml` with a per-pack overlay, so the legal pack and the finance pack can disagree on tool allowlists without stepping on each other. And @-mentions resolve into a unified popup that knows about files, docs, web pages, code symbols, recent chats, and agents — six namespaces, one keystroke.

Behind those four panels, the substrate got an upgrade. Cmd+K palette v2 (W246) replaces the v1 we shipped in W57 — fuzzy match across actions, files, docs, recents, agents, and settings, ~10ms on five thousand entries. Codebase indexer v0 (W245) is tree-sitter incremental, multi-language, sqlite-vec for symbol embeddings; that is what `@code:` resolves against. The unified WebSocket event bus (W248) replaces seven separate polling loops with one socket and typed envelopes — status, agents, usage, briefing, doctor, notepad, MCP, all push. The cockpit feels different. It feels real.

And then the part that actually pays the bills. The tier cap UX (W242) reads from the W235 consumption console, surfaces a soft warning at 80% and a hard block at 100%, and routes the topup prompt through the meeet.world rail. Privacy mode (W244) gives you three data planes — local, cloud, cloud-with-redaction — per call, per agent, or globally, with the active plane always visible in the status bar. Receipts include the plane. The background agents tray (W241) makes long-running tasks visible the way they should have been all along. Notepad templates (W243) turn any chat into a reusable AI workflow with a slash recall.

## The bigger bet

TARS is built on four convictions, in priority order:

**Local-first is not a niche.** Your data lives in 9 SQLite files in `~/.tars/`. The app is a Tauri bundle that boots in under 600ms. There is no cluster. There is no telemetry. The cloud is an opt-in delivery channel for models — not a kidnapper for everything else.

**Receipts are the only honest interface.** Every action — a model call, an agent run, a voice synth, a file ingestion — emits a hash-chained receipt. Receipts are Merkle-batched and anchored as a Solana memo at a configurable cadence. The chain proves we cannot retroactively edit your audit log. For the B2B Workshop tier this is the *only* feature that matters.

**Domain packs beat one-size assistants.** Seven life domains today — legal, finance, health, trading, ops, research, entrepreneur. Each pack ships its own rules overlay, agent set, and consumption budget. The Cursor of legal looks different from the Cursor of trading. We let them.

**Voice changes everything.** The cinematic monolith is not decoration. It is what you talk to. Voice cockpit, voice command parser, voice-driven panel switching. The keyboard is for power users; voice is for everyone else.

## What's next (Wave B preview)

- Multi-project codebase indexer + workspace switcher
- MCP add-server UI (currently YAML-only)
- AI Clone v0.3 — real fine-tuned per-user clone
- Marketplace payouts (the 70/30 share for skill authors)
- Signed Windows and Linux installers

Brother is shipping the meeet.world billing endpoints this week. Once those flip live, the topup prompt closes inline; until then, it links to the dashboard.

## Try it

Download: https://tars.meeet.world/download (signed installer drops this week)
Source: https://github.com/alienram/jarvis
Notes: docs/RELEASE_NOTES_v9.3.0-beta1.md

Free tier forever. Skip the login on first boot — TARS runs local-only and never phones home.

If something breaks, the doctor page (`/api/doctor/page`) tells you why. If it does not, write to me at alienram@icloud.com. I read every email.

— Alien
