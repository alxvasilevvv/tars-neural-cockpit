# Reddit — TARS v9.1.0 launch posts

---

## r/MacApps

**Title:**
TARS v9.1.0 — local-first AI agent for Mac with a one-line installer

**Body (~250 words):**

Hi r/MacApps — shipping TARS v9.1.0 today and wanted to share it here because the Mac side is where most of the work went.

TARS is a local-first AI agent runner. The runtime, scheduler, webhooks, and Cowork session backend all run on your machine — no required cloud account. There's a Mac operator built on the same runtime, so you can give an agent a task and have it act on the box rather than just chat.

It's a native Mac arm64 build. Mac Intel works through Rosetta. Install is one line:

    bash <(curl -fsSL https://tars.meeet.world/install.sh)

The installer clears the xattr quarantine bit for you, because the Mac build is ad-hoc codesigned — Apple notarization is the next thing on the list, not done yet. That's the main caveat I want flagged upfront. If you'd rather wait for a notarized build, totally fair.

Multi-provider is built in: a single agent step can hit Claude, GPT, Gemini, and a local Ollama model and reconcile. You bring your own keys, or run Ollama only and stay fully offline.

Other things in v9.1.0: plugin marketplace, scheduler, webhooks, B2B workshop suite, and the Cowork multiplayer backend module (UI lands in v9.1.1 — not in this release).

Backed by meeet.world. Site, docs, downloads: https://tars.meeet.world

I'm a beginner-friendly thread, ask anything — install issues, Mac permissions, how the operator works, why local-first, why not just a wrapper around one provider.

---

## r/LocalLLaMA

**Title:**
TARS v9.1.0 — local-first agent runner with multi-LLM council (Ollama + Claude/GPT/Gemini)

**Body (~250 words):**

Hi r/LocalLLaMA — releasing TARS v9.1.0 today and this subreddit is the audience I most care about for the council piece.

Short version: TARS is a local-first agent runner. Mac arm64, Windows, Linux x64 installers. The whole runtime — agent state, scheduler, webhooks, Cowork session backend, marketplace — runs on your machine. No required cloud account.

The reason I'm posting here: multi-LLM council is a first-class primitive. A single agent step can fan out to Claude, GPT, Gemini, and a local Ollama model, then reconcile. You configure which providers are eligible per step. Ollama-only runs work fully offline — no provider keys, nothing leaves the box. That includes prompts, files, and intermediate state.

Install (one line, picks the right arch):

    bash <(curl -fsSL https://tars.meeet.world/install.sh)

Mac Intel falls back via Rosetta. Installer handles xattr because the Mac build is ad-hoc codesigned. Apple notarization is not done yet — flagging this honestly. Windows/Linux x64 are clean.

Privacy posture: your provider keys are stored locally, the runner makes provider calls directly from your machine, and there is no telemetry pipe back to meeet.world for agent content. Marketplace and update checks are network calls; the agent runtime is not.

Other v9.1.0 bits: scheduler, webhooks, plugin marketplace, B2B workshop suite, Cowork multiplayer backend module (frontend UI lands in v9.1.1 — not in this release).

Site, docs, install: https://tars.meeet.world

I'm a beginner-friendly thread, ask anything — Ollama model compatibility, council reconciliation behavior, offline mode, key handling.
