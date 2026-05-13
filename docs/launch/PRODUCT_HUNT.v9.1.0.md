# Product Hunt — TARS v9.1.0 launch

**Tagline (≤60 chars):**
Local-first AI agent for Mac with a multi-LLM council

**Description (≤260 chars):**
TARS is a local-first AI agent runner. It runs agents on your machine, fans queries out to a council of Claude, GPT, Gemini, and Ollama, and reconciles the answers. Includes scheduler, webhooks, marketplace, and Cowork multiplayer backend. Mac, Windows, Linux.

---

**First comment (≈300 words):**

Hi PH — I'm the maker. TARS started a year ago as an internal tool at meeet.world. We kept hitting the same wall: any serious agent workflow needed more than one model, but stitching providers together inside a closed cloud product felt wrong. So we made the runner local-first and made multi-provider a first-class primitive instead of a hack.

What's in v9.1.0, shipping today:

- Local agent runner — agents, state, and tool calls execute on your machine
- Multi-LLM council — a single step can call Claude, GPT, Gemini, and Ollama, then reconcile
- Scheduler — cron-style triggers for agent runs
- Webhooks — inbound/outbound, for piping TARS into the rest of your stack
- Marketplace — install community plugins and agent recipes
- B2B workshop suite — facilitator tooling we built for our own client workshops
- Cowork multiplayer session backend — the API and server module

Install (Mac arm64, Windows x64, Linux x64):

    bash <(curl -fsSL https://tars.meeet.world/install.sh)

Mac Intel works via Rosetta. The installer handles the xattr quarantine flag because the Mac build is ad-hoc codesigned for now.

What's NOT in this release, to be straight:

- The Cowork multiplayer frontend — backend module ships, UI lands in v9.1.1
- Apple notarization — in progress, install.sh covers the gap
- Anything that requires the marketplace to be busy on day one — please be patient with us

Roadmap next: v9.1.1 Cowork UI, notarized Mac build, a Windows MSI signed with an EV cert, and broader Ollama model presets.

Site, docs, downloads: https://tars.meeet.world

Happy to answer anything in the comments.
