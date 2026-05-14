# Show HN — TARS v9.3.0-beta1

> Channel: Hacker News (Show HN)
> Target word count: ~400 words
> Title (80-char limit): "Show HN: TARS v9.3.0-beta1 – local-first AI cockpit with on-chain receipts"
> URL: https://tars.meeet.world/download
> Tone: plain, technical, no marketing fluff

---

## Title

`Show HN: TARS v9.3.0-beta1 – local-first AI cockpit with on-chain receipts`

## Body (~400 words)

Hi HN. I have spent the last six months building TARS — what Cursor is to code, but for everything that is not code: legal, finance, trading, health, ops, research.

The trigger was personal. I live in Cursor when I write software. The moment I close the IDE, every other "AI assistant" I tried wanted my data on their cluster, my identity in their dashboard, my keys in their settings page. None of it felt like Cursor. None of it respected the fact that my contracts, my charts, my medical records are not someone else's training set.

So I built TARS. The constraints I set myself:

**What runs locally.** The app is Tauri, native macOS. All user data lives in 9 SQLite files under `~/.tars/` — chats, memory, codebase index, tasks, notepad, doctor logs, rules, MCP config, receipts. The backend is uvicorn on `:8765`, also local. Voice is real (whisper.cpp by default; OpenAI Whisper API if you bring a key). No telemetry to me. No model calls unless you explicitly enable a provider.

**What goes on-chain.** Every action — model call, agent run, voice synth, receipt verify — emits a hash-chained receipt. Receipts are Merkle-batched and anchored as a Solana memo at a configurable cadence. The chain proves I did not retroactively edit your audit log. It does not put your data on chain — only the root.

**What goes through meeet.world.** Identity (magic-link), billing (the consumption console reads tier caps and surfaces topups), and the marketplace (Wave 106). meeet.world is my brother's project; the contract between us is a tight handful of HTTP endpoints and a shared secret. If meeet is down, TARS runs in local-only mode forever — there is a "Skip" button on the auth screen.

**What v9.3.0-beta1 specifically adds (Wave A, W237-W249):**

- Models switcher with per-request cost labels (Claude / OpenAI / OpenRouter / Ollama)
- MCP servers panel — list, toggle, test connection
- Rules system — `.tars/rules.yml` + per-pack overlay
- @-mention chat context — `@file:`, `@docs:`, `@web:`, `@code:`, `@recent:`, `@agent:`
- Cmd+K palette v2 — fuzzy across actions, files, docs, recents, agents, settings
- Codebase indexer v0 — tree-sitter, multi-language, sqlite-vec embeddings
- Unified WS event bus — one socket replaces seven polling clients
- Tier cap UX wired through the consumption console
- Privacy mode + data plane: `local` / `cloud` / `cloud_redacted`

**Honest limitations.** STT needs `OPENAI_API_KEY` or `whisper.cpp` installed — gracefully falls back to text input. Mac-only signed installer this week; Windows/Linux build from source. My brother is shipping the meeet.world billing endpoints this week — until then, the topup prompt opens the dashboard.

Source: https://github.com/alienram/jarvis
Notes: docs/RELEASE_NOTES_v9.3.0-beta1.md

Genuinely curious what HN thinks. Especially about the on-chain receipt model — I have not seen anyone wire Merkle roots into an action ledger as a primary product feature, and I want to know if it is a good idea or a clever solution to a non-problem.
