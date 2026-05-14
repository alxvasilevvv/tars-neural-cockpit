# Product Hunt launch — TARS v9.3.0-beta1

> Channel: Product Hunt
> Launch day: 2026-05-15 (PT 00:01)
> Maker: Alien
> Hunter: TBD

---

## Tagline (60 char hard limit)

`Cursor for everything-not-code. Local-first. Voice-native.`

Char count: 58 / 60.

---

## Description (240 char hard limit)

TARS is a local-first AI cockpit. The Cursor density and Cmd+K speed, pointed at legal / finance / trading / health / ops — not code. Voice-driven. On-chain receipts for every action. Billed through meeet.world. Free tier forever.

Char count: 234 / 240.

---

## Top comment (founder's first reply, ~150 words)

I have been a Cursor user since the day Sourcegraph announced it killed Sourcegraph for me. The IDE got 10x better, and then I closed it and my entire non-code life went back to ChatGPT tabs and Notion macros.

That asymmetry kept me up.

TARS is what I built to close it. A Tauri app, 9 SQLite files under ~/.tars/, a uvicorn backend on :8765, whisper.cpp for voice. Every action emits a hash-chained receipt. Identity and billing route through my brother's meeet.world rail.

v9.3.0-beta1 is Wave A — the Cursor parity wave. Models switcher, MCP panel, rules, @mentions, Cmd+K v2, consumption console. Thirteen waves of work in one tag.

It is a beta. STT needs your own key or whisper.cpp installed. Mac-only signed installer for now. Tell me where it breaks — I read every comment and reply same-day.

— Alien

---

## Gallery descriptions (5 screenshots)

**1. Cockpit hero — voice cockpit with the monolith ambient**
"The cinematic cockpit. Talk to it. Type at it. The monolith pulses when TARS is thinking. Cmd+Shift+Space toggles it from anywhere."

**2. @mentions resolver popup**
"Type @ in the chat. Resolver popup for files, docs, web pages, code symbols, recent chats, agents. Same primitive Cursor uses for code — pointed at your whole life."

**3. Cmd+K palette v2**
"Fuzzy search across actions, files, docs, recents, agents, settings. ~10ms across 5k entries. Recents bubble to top. Keyboard-only navigation."

**4. Consumption console + tier cap banner**
"Every metered action is a usage event. Live cost-per-request labels. Soft warning at 80%, hard block at 100%. Topup routes through meeet.world. No surprise invoices, ever."

**5. Settings — MCP servers panel + rules editor**
"Wire any MCP server (local stdio or remote SSE). Toggle, health-check, test-connection. Rules in .tars/rules.yml with per-pack overlay and schema validation. The Cursor power-user surface, ported."

---

## Five anticipated FAQ replies

**Q: How is this different from open-interpreter / continue.dev / aider?**

Those are great tools for code. TARS is what you reach for when you close the IDE — taxes, contracts, charts, briefings, voice. Different surface, different primitives (voice cockpit, domain packs, receipts), same local-first soul.

**Q: What models does it support?**

Anthropic (Claude family), OpenAI (4 / 5 / o-series), OpenRouter (everything), Ollama (local). Switch per-conversation in the header dropdown or by voice ("switch to claude haiku"). Cost-per-request label is live.

**Q: Is the on-chain receipt thing a gimmick?**

It is a hash-chained action log, Merkle-batched and anchored to Solana as a memo. The chain proves I cannot retroactively edit your audit log; it does not put your data on-chain. For B2B compliance (the Workshop tier) this is the only feature that matters.

**Q: Pricing?**

Free forever for local-only mode. meeet.world subscription unlocks cloud models, the marketplace, and the AI Clone. The consumption console shows real numbers — no annual prepay, no enterprise sales call to see pricing.

**Q: Why "TARS"?**

Interstellar. The monolith shape, the humor setting, the "honesty 90%" vibe. I like robots that tell you what they did.
