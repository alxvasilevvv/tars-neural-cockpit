# Marketing announcement templates

Готовые тексты для launch day. Скопируй, отредактируй под голос, опубликуй.

---

## Twitter / X — main thread (8 tweets)

**Tweet 1 (hook):**
> TARS is live. 🌑
>
> Local-first AI agent for Mac. Multi-LLM council. Persistent memory. Operates apps on your machine. $MEEET economy.
>
> One curl, sixty seconds.
>
> https://tars.meeet.world

**Tweet 2 (problem):**
> Cloud LLMs forget you between sessions. Cloud agents leak your data. Cloud subscriptions add up.
>
> TARS runs on your machine. Your keys. Your memory. Your terms.

**Tweet 3 (what it does):**
> What TARS does for you, daily:
> ☀️ Daily briefing — calendar + email + open PRs in one shot
> 🤖 Watches you work — learns your style
> 🔐 Memory that compounds — every thread builds the next
> 💰 $MEEET economy — get paid for your data, in $MEEET

**Tweet 4 (technical credibility):**
> Under the hood:
> • FastAPI sidecar (CPython 3.12, embedded)
> • Tauri 2 desktop shell (~25MB Mac binary)
> • SQLite + sqlite-vec for memory
> • SOL on-chain settlement for $MEEET
> • Apple Developer ID + Authenticode signed

**Tweet 5 (open + brand):**
> Built under @meeetworld brand. Open source on GitHub. Receipts anchored on Solana. No tracking, no telemetry leaks.
>
> Code: github.com/alxvasilevvv/tars-neural-cockpit

**Tweet 6 (install):**
> Install:
>
> ```
> curl -fsSL tars.meeet.world/install.sh | sh
> ```
>
> Or download .dmg / .msi / .AppImage:
> github.com/alxvasilevvv/tars-neural-cockpit/releases

**Tweet 7 (demo):**
> [Attach 30-second screen recording]
>
> Cmd+Shift+Space anywhere → TARS appears. Drop a folder, ask it to organize. Watch it work. Receipts anchored. Done.

**Tweet 8 (cta):**
> Honestly, just install it. Try the Daily Briefing once. If it doesn't pay for itself before lunch — uninstall and pour me coffee in person.
>
> https://tars.meeet.world

---

## Twitter — solo tweet (если не хочешь thread)

> 🌑 Just shipped TARS — local-first AI agent for Mac.
>
> Multi-LLM council. Mac operator. Persistent memory. $MEEET economy. Tauri 2 native shell. One curl install.
>
> Your machine. Your keys. Your terms.
>
> https://tars.meeet.world

---

## Blog post — full announcement

**Title:** TARS v9.1 — your machine, your second brain.

**Subtitle:** Local-first AI agent for Mac. Today, sixty seconds.

---

Six months ago I was paying $200/mo across four AI subscriptions and still copy-pasting context between them every morning. The cloud agents knew nothing about me. None of them remembered yesterday. Each one wanted my data and my credit card.

I built TARS because the agentic future shouldn't run on someone else's server farm.

**TARS is a local-first AI agent.** It lives on your Mac, talks to whatever LLM you point it at (Anthropic, OpenAI, Gemini, or your own local Ollama), remembers everything you do, and operates your machine — files, calendar, email, code — when you tell it to.

Today it ships v9.1.

## What's actually in it

### Daily Briefing
8am. TARS sits down with your calendar, your email inbox, your open PRs, your Slack mentions. By 8:01 you have a tight summary on screen + audio narration through your speakers. No tab-switching, no dashboard hunting.

### Watch-Me-Work
Tell TARS "sort my Downloads folder by type, summarize the PDFs, archive anything older than 30 days." It does it. Live. You watch every step in a console, every action gets a signed receipt anchored on Solana.

### Memory that compounds
Every conversation, every file you drop, every action TARS takes — fed into a local SQLite + sqlite-vec memory store. Three weeks in, TARS knows your style. AI Clone draft suggestions are 80% there before you start typing.

### Multi-LLM Council
For high-stakes decisions, TARS spawns a panel of LLMs that debate, vote, then surface the consensus + minority report. You see whose vote came from where.

### Native desktop feel
Tauri 2 shell. Cmd+Shift+Space anywhere → TARS window appears. Tray icon. `tars://` deep links. Window state persists. ~25MB universal Mac binary.

### $MEEET economy
You earn $MEEET for participating in the network — your data, anonymized, contributes to model training and you get paid in $MEEET tokens. Settle in SOL on-chain. No middleman, no Stripe.

## The hard parts

The hard part wasn't the LLM glue. The hard part was:

- **Embedding CPython 3.12 + 14 packages into a single Mac binary** so users don't need a Python install. (pyoxidizer, six weeks of yak shaving.)
- **Encrypted sync envelope** between machines (X25519 + XChaCha20-Poly1305) so meeet.world cloud sees only ciphertext. Zero-knowledge.
- **Authoritative billing** — TARS spends are mirrored to meeet.world Supabase via idempotent POST `/operator/usage` with trace_id dedupe, retry budget exhaustion fires structured logs.
- **WCAG 2.1 AA accessibility** across the cockpit — focus traps, aria-modal, keyboard navigation. Every modal is keyboard-only complete.
- **Native menu bar / global shortcut / deep links** — Tauri 2 plumbing is good but the UX gap between "wrapped web view" and "real Mac app" is ~600 lines of Rust.

## Architecture

```
┌──────────────────┐    ┌──────────────────┐
│  TARS desktop    │    │  meeet.world     │
│  ┌────────────┐  │    │  (account, $$,   │
│  │  cockpit   │  │    │   $MEEET edge)   │
│  │  React UI  │  │    └──────────────────┘
│  └────────────┘  │              ▲
│        │         │              │
│  ┌────────────┐  │              │ HTTPS
│  │  sidecar   │──┼──────────────┘
│  │  FastAPI   │  │     trace_id-keyed
│  │  on :8765  │  │     idempotent
│  └────────────┘  │
│        │         │
│  ┌────────────┐  │
│  │  SQLite    │  │
│  │  (local    │  │
│  │   memory)  │  │
│  └────────────┘  │
└──────────────────┘
```

Local-first. Cloud-mirroring. Zero-knowledge sync.

## Install

```bash
curl -fsSL https://tars.meeet.world/install.sh | sh
```

Or grab a signed `.dmg` / `.msi` / `.AppImage`:
https://github.com/alxvasilevvv/tars-neural-cockpit/releases/latest

## What's next

Phase M (next 90 days):
- iOS / Android companion (chat-only, mirrors via L5 Pairing)
- pyoxidizer cross-target CI matrix (currently arm64-darwin only)
- Connector marketplace expansion (Notion, Linear, Slack)
- $MEEET staking — agents stake to bid on your tasks

If you want to follow along: meeet.world community + Twitter @meeetworld.

## Try it

Install above. First-run wizard takes 60 seconds. Daily Briefing fires tomorrow morning at 8am.

If it doesn't pay for itself before lunch — uninstall and pour me coffee in person.

— Алексей, founder

---

## Discord / community announcement

> 🌑 **TARS v9.1 is live.**
>
> Local-first AI agent for Mac. Multi-LLM council, persistent memory, Mac operator, $MEEET economy.
>
> 🔗 **Install:** https://tars.meeet.world
> 📦 **Source:** github.com/alxvasilevvv/tars-neural-cockpit
> 💬 **Feedback:** in this channel — fixing bugs in <30 min during launch week
>
> What you get out of the box:
> • Daily briefing (calendar + email + PRs by 8am)
> • Watch-me-work (operates your Mac, every action signed)
> • Memory that compounds (every thread feeds the next)
> • $MEEET economy (settle in SOL, no Stripe)
>
> Drop a Daily Briefing screenshot 👇 once you've tried it.

---

## Hacker News submission

**Title:** Show HN: TARS – local-first AI agent for Mac with multi-LLM council

**URL:** https://tars.meeet.world

**Comment** (post immediately as the first comment):

> Founder here, AMA. I built TARS because cloud AI subscriptions stopped paying for themselves around month four — context lost between sessions, four tools that didn't talk to each other, and someone else's server park making decisions about my data.
>
> TARS runs on your Mac. CPython 3.12 + the FastAPI backend embedded via pyoxidizer into a ~25MB universal binary, Tauri 2 shell, SQLite + sqlite-vec for memory.
>
> The interesting parts (happy to discuss any):
>
> - **Multi-LLM council** spawns Anthropic, OpenAI, Gemini in parallel for high-stakes decisions. Each votes; you see the minority report.
>
> - **Memory** is local SQLite, embeddings via sqlite-vec, AI Clone learns your style from week 1.
>
> - **Mac operator** — Watch-Me-Work mode shows TARS operating your machine in real time. Every action gets a signed receipt anchored on Solana. (Yes, you can audit what TARS did at 4am.)
>
> - **Sync** between machines is encrypted (X25519 + XChaCha20-Poly1305). meeet.world cloud sees only ciphertext.
>
> - **Billing** is authoritative on meeet.world Supabase. Local TARS mirrors `usage.tokens` events through a `trace_id`-keyed idempotent POST. Retries with exponential backoff, structured log on budget exhaustion.
>
> Open source: github.com/alxvasilevvv/tars-neural-cockpit
>
> Will sit on this thread for the next 6 hours. Ping with bugs / hard questions.

---

## Twitter reply hooks (для бот-ответов и DMs)

**"Is this a wrapper around ChatGPT?":**
> No — TARS is a local agent + multi-LLM router. You bring your own keys (or use the meeet.world cloud allocation included in Pro tier). The agent intelligence is local; the LLM calls go to whichever provider you configure.

**"How is memory different from ChatGPT memory?":**
> Three things: (1) it's *yours* — SQLite file at `~/Library/Application Support/world.meeet.tars/memory.db`, you own it. (2) it's deep — every action TARS takes feeds the index, not just chat. (3) it's queryable — embeddings via sqlite-vec, not a black box.

**"What's $MEEET / why not Stripe?":**
> Two answers. Practically: SOL settlement is faster + cheaper than Stripe at our volumes. Philosophically: the value users create (data, attention, model training) shouldn't extract through a payment processor that takes 3%. $MEEET is the closed loop — you earn it for participating, you spend it on agents.

**"Open source — what license?":**
> Apache 2.0 for the core. Plugins ship signed via ed25519, manifest-pinned. You can fork anything. We retain the meeet.world brand + the trademark.

**"Windows / Linux?":**
> Today: Mac universal (.dmg). Tomorrow (Phase M, ~6 weeks): Windows .msi (signed Authenticode), Linux .AppImage + .deb. Same codebase, Tauri 2 cross-compiles cleanly; just CI matrix work.

---

## Что добавить когда сделаешь рекординг

В Tweet 7 (демо), Twitter solo, и в blog post — нужно прицепить 30-секундный screen recording. Идеи что показать:

**Вариант A — Daily Briefing**
- 0:00 → cold start. Cmd+Shift+Space.
- 0:02 → TARS появляется. "Brief me on this morning."
- 0:05 → calendar widget, email widget, PR widget строятся.
- 0:15 → audio narration starts playing.
- 0:30 → end card "TARS · tars.meeet.world".

**Вариант B — Watch-Me-Work**
- 0:00 → "Sort my Downloads by type, summarize the PDFs, archive anything older than 30 days."
- 0:05 → файл-менеджер открывается, TARS бегает по нему, файлы перемещаются в папки.
- 0:15 → каждое действие появляется в console на правой стороне.
- 0:25 → receipt подписан, anchored on Solana — линк на explorer.
- 0:30 → "TARS — your machine, your second brain."

Сделай это рекординг через Cleanshot X или встроенный Cmd+Shift+5 → conversion to .gif через ezgif.com или ffmpeg.

---

## Чего избегать

❌ Не упоминай конкретные dollar amounts в твитах ("$200/mo subscriptions") если у тебя нет faktа — лучше абстрактнее.
❌ Не сравнивай напрямую с конкурентами ("better than Claude Desktop") — рассказывай про TARS, не про них.
❌ Не публикуй "100% private" — у тебя cloud мирror, hedge формулировки нужны ("local-first", "you own the keys").
❌ Не обещай features что в Phase M (Windows, iOS) с конкретными датами — "coming weeks" максимум.

✅ Подчёркивай **локальность** (your machine, your keys), **прозрачность** (signed receipts, audit trail), и **conserved economics** ($MEEET vs subscription churn).
