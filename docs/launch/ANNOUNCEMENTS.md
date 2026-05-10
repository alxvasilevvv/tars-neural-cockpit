# ANNOUNCEMENTS — TARS v9.1.0 launch copy

> All copy is honest per Wave 71-B alignment + WHAT_WORKS.md ledger.
> No marketplace, no live T2T, AI Clone framed as v0.1 (style hint).
> macOS-only for v9.1.0. No emoji, no hype words like "revolutionary".
>
> Ship order: Twitter thread first, HN within 30 min, Reddit + email
> within 2 hours, Product Hunt next morning.

---

## Twitter / X thread (6 tweets)

**1/ (hero)**
```
TARS is live.

A local-first AI agent for your Mac. Runs offline, owns its own
memory, can drive your machine when you let it.

Open source, no telemetry, no marketplace, no SaaS lock-in.

https://tars.meeet.world
```

**2/ (local-first)**
```
2/ Local-first means: the model, the memory, the receipts — all
on your laptop. You own the SQLite file. You own the keys.

If our servers vanish tomorrow, your TARS keeps working. That is
the whole point.
```

**3/ (multi-LLM council)**
```
3/ TARS doesn't pick a side in the LLM wars.

Bring your own keys: Anthropic, OpenAI, Gemini, Ollama, or any
OpenAI-compatible endpoint. Six domain agents (wealth, health,
family, product, brand, entrepreneur) route to whichever model
you trust for that task.
```

**4/ (Mac operator)**
```
4/ It can also drive your Mac.

Sort downloads, summarize PDFs, run shell, scrape a page, anchor
a receipt to Solana. Every action is logged to a signed receipt
ledger so you can replay what the agent did.

Watch-me-work timeline is real, not a mock.
```

**5/ ($MEEET economy)**
```
5/ Optional: $MEEET, an on-chain credit for shared compute and
agent-to-agent escrow on meeet.world.

You can ignore it entirely and just run TARS local with your
own keys. Or opt in if you want T2T plumbing later this year.
Your call.
```

**6/ (closing)**
```
6/ Honest scope for v9.1.0:

- macOS only (Win/Linux later)
- AI Clone is v0.1, style hint not full clone
- Marketplace is not live yet

Full ledger of what works:
https://github.com/<org>/jarvis/blob/main/docs/WHAT_WORKS.md

Thank you to the early-access cohort. Pull is open.
https://tars.meeet.world
```

---

## Hacker News post

**Title:**
```
TARS — local-first AI agent for Mac (open source)
```

**URL field:** `https://tars.meeet.world`

**Body (~270 words):**

```
Hi HN. I've been building TARS for the past several months and
v9.1.0 ships today. It's an open-source, local-first AI agent
that runs as a Tauri app on macOS.

What it actually does in v9.1.0:

- Runs a local Python sidecar (FastAPI) that you bring keys to.
  Anthropic, OpenAI, Gemini, Ollama, or any OpenAI-compatible
  endpoint. No accounts required to use it.
- Six domain "council" agents (wealth, health, family, product,
  brand, entrepreneur) plus a planner that chains agents and
  writes signed receipts to a local SQLite ledger.
- Operator skills for the Mac: sort downloads, summarize PDFs,
  ingest .ics calendars, run shell with budget caps, scrape pages.
  Every action is HIL-gateable.
- A "watch-me-work" timeline streamed over WebSocket from the
  orchestrator — it's real events, not a demo loop.
- TTS via XTTS-v2 with system fallback, STT via Whisper API.
- An optional bridge to meeet.world for $MEEET credits and a
  TARS-to-TARS handshake (mock escrow only in this release).

Honest scope, because over-claiming wastes everyone's time:

- macOS arm64 only. Windows / Linux pyoxidizer pipeline is in
  v9.2.
- AI Clone ships as v0.1: a style-hint layer, not a fine-tuned
  per-user model.
- Marketplace UI exists, the live registry does not.
- T2T handshake is wired but escrow is mocked.

Full capability ledger with file paths:
https://github.com/<org>/jarvis/blob/main/docs/WHAT_WORKS.md

The .dmg is signed and notarized. The Tauri updater key is real
(minisign). Source, install script, and one-curl bootstrap are at
https://tars.meeet.world.

Happy to answer anything about the architecture, the local-first
choices, or where it falls short.
```

---

## Reddit

### r/macapps

**Title:**
```
[Release] TARS — local-first AI agent for Mac (open source, BYOK, signed .dmg)
```

**Body (~200 words):**

```
Built a Tauri app that runs an offline-first AI agent on macOS.
v9.1.0 just shipped.

What you get:

- Signed, notarized .dmg (Apple Developer ID). No "right-click → Open"
  workaround.
- Bring your own LLM keys: Anthropic, OpenAI, Gemini, local Ollama,
  or any OpenAI-compatible endpoint. No account, no telemetry.
- Six domain agents (wealth, health, family, product, brand,
  entrepreneur) + a planner that chains them.
- Mac operator skills: sort Downloads folder, summarize PDFs,
  run shell commands with budget caps, ingest .ics calendars,
  scrape pages.
- Voice in/out: XTTS-v2 TTS with system fallback, Whisper STT
  if you provide a key.
- Local SQLite memory + signed receipt ledger. You own the file.
- Cmd+Shift+Space global shortcut, menu-bar tray, deep-link tars://.

Honest limits in v9.1.0: macOS only (arm64; x64 falls back via
Rosetta). Marketplace UI is there but the registry is not live yet.
AI Clone is v0.1 — it's a style hint, not a fine-tuned per-user
model.

Source + .dmg + one-curl install: https://tars.meeet.world
Full capability ledger: see WHAT_WORKS.md in the repo.

Feedback welcome.
```

### r/MacOS (adapted, lighter on dev jargon)

**Title:**
```
TARS v9.1.0 — open-source AI agent app for Mac, runs offline with your own keys
```

**Body (~190 words):**

```
After several months of work, I'm releasing a Mac app that runs
an AI agent locally on your machine instead of through a third-party
SaaS.

The pitch:

- Native Mac app (signed and notarized .dmg).
- You bring your own AI key — Anthropic Claude, OpenAI, Gemini, or
  a local Ollama model. Nothing leaves your laptop unless you tell
  it to.
- It can do practical Mac stuff: clean up Downloads, summarize PDFs
  you drop on it, read your calendar (.ics), run shell commands
  with a budget cap, scrape web pages, talk to you with TTS.
- Memory and history live in a SQLite file you own. If my servers
  disappear, your TARS keeps working.
- Optional integration with meeet.world for shared compute credits;
  ignore it if you don't care.

Honest scope: Mac only for now (Apple Silicon best, Intel works
under Rosetta). No marketplace yet. No Windows or Linux build yet.

Free and open source. Install: https://tars.meeet.world

Curious what r/MacOS thinks of the local-first angle.
```

### r/SideProject

**Title:**
```
After 9 months solo, I shipped TARS — local-first AI agent for Mac
```

**Body (~200 words):**

```
Started this as a "what if I owned my AI assistant the way I own
my notes" experiment in late 2025. v9.1.0 ships today.

Stack:

- Tauri (Rust shell) + Python FastAPI sidecar
- SQLite for everything (chat, memory, receipts, ledger)
- ed25519-signed receipts, minisign-signed Tauri updates
- BYOK: any OpenAI-compatible LLM, plus Anthropic and Gemini
- Optional Solana memo anchoring for receipt batches
- Cloudflare Pages landing + GitHub Actions release pipeline

What I learned:

- Cutting features feels great. Wave 71 was just "delete things
  that aren't real" and the product got dramatically better.
- A WHAT_WORKS.md ledger that marketing has to be a strict subset
  of saved me from over-claiming on the landing page twice.
- Tauri + a signed updater is genuinely a small team's secret
  weapon now.

Honest v9.1.0 scope: macOS only, AI Clone is v0.1 style-hint,
marketplace UI without live registry. All listed in the README.

Source + .dmg: https://tars.meeet.world

Happy to dig into the architecture or the cutting-features story
if anyone is curious.
```

---

## Email blast — waitlist

**Subject:**
```
TARS is live
```

**From:** Alien <hello@meeet.world>

**Body (~150 words):**

```
You signed up for early access months ago. Today TARS v9.1.0 is
in your hands.

One-curl install for macOS:

  curl -fsSL https://tars.meeet.world/install.sh | sh

Or grab the signed .dmg directly:

  https://tars.meeet.world

Once installed, three things to try:

1. Drop a PDF on the cockpit and ask "summarize this in five
   bullets" — local TTS reads it back.
2. Open the Operator panel and ask it to "sort my Downloads folder
   by file type" — every action is logged to your local receipt
   ledger.
3. Bring your own key (Anthropic, OpenAI, Gemini, or Ollama) in
   Settings. Nothing leaves your laptop unless you tell it to.

Honest scope: macOS only for v9.1.0. Windows and Linux later this
year. Full WHAT_WORKS ledger linked from the site.

Thank you for waiting. Reply to this email if anything is broken.

— Alien
```

---

## Product Hunt

**Tagline (max 60 chars):**
```
Local-first AI agent for Mac. Your keys, your machine.
```
(53 chars)

**Description (~60 words):**

```
TARS is an open-source AI agent that runs on your Mac, not in
someone else's cloud. Bring your own LLM key (Anthropic, OpenAI,
Gemini, or local Ollama). Six domain agents, a planner, voice
in/out, Mac operator skills, and a signed receipt ledger you
fully own. macOS only for now. No telemetry, no marketplace
lock-in, no SaaS.
```

**Image captions (3):**

1. ```
   Cockpit view — drop a PDF, ask anything, watch your local
   council answer. Voice in/out included.
   ```

2. ```
   Watch-me-work timeline — every agent step streamed in real
   time and signed to your local receipt ledger.
   ```

3. ```
   Bring your own key — Anthropic, OpenAI, Gemini, or local
   Ollama. Switch providers per-task. No account required.
   ```

---

## Notes for the operator

- Replace `<org>` placeholders in HN / Reddit copy with the
  actual GitHub org slug before posting.
- Twitter thread: schedule tweets 1 minute apart so the thread
  unfurls as a thread, not a reply chain.
- HN: don't use "Show HN" prefix — founder-posted launches don't
  need it and the HN guidelines specifically say so.
- Reddit: post r/macapps first (most receptive), then r/MacOS
  ~30 min later, then r/SideProject the next morning. Don't
  cross-post all three at once or the spam filter eats them.
- Product Hunt: schedule for 12:01 AM PT to get the full 24-hour
  voting window.
- Email blast: send through whatever the waitlist is on
  (Postmark / Resend / etc.), not a personal Gmail.
