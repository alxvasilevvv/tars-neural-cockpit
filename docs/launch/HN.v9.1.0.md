# Hacker News — TARS v9.1.0 launch

**Title:**
Show HN: TARS — local-first AI agent for Mac with multi-LLM council

**Body (200 words):**

TARS is a local-first AI agent runner I've been building under meeet.world. v9.1.0 shipped today. It runs on your machine — agents, scheduler, webhooks, marketplace, and the Cowork multiplayer session backend are all local services. No SaaS account required to use the core runner.

The angle that ended up mattering most in practice is the multi-LLM council: a single agent run can fan out to Claude, GPT, Gemini, and a local Ollama model, then reconcile. You pick which providers you trust for which step. Ollama-only runs work offline.

Install (Mac arm64, Windows, Linux x64):

    bash <(curl -fsSL https://tars.meeet.world/install.sh)

Mac Intel falls back via Rosetta. The installer also handles the xattr quarantine bit because the Mac build is ad-hoc codesigned — Apple notarization is not done yet, that's the biggest rough edge. The other honest caveat: the Cowork multiplayer UI is not in this release. The backend module ships and exposes the API, but the frontend lands in v9.1.1.

Also included: B2B workshop suite, scheduler, webhooks, plugin marketplace.

Site, docs, download: https://tars.meeet.world

Happy to answer anything about the council reconciliation logic, the agent runtime, or why local-first.
