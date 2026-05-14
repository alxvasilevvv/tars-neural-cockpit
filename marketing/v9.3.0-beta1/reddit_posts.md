# Reddit launch posts — TARS v9.3.0-beta1

> Three subreddit-tailored posts, ~200 words each.
> Three different angles. Same product. Same release.

---

## 1. r/LocalLLaMA

**Title:** `TARS v9.3.0-beta1 — local-first AI cockpit (Anthropic/OpenAI/OpenRouter/Ollama, MCP servers, privacy mode)`

Built a Cursor-style cockpit for everything that is not code. Local-first by default.

What is local:

- App is Tauri, native macOS bundle.
- Data: 9 SQLite stores under `~/.tars/` — chats, memory, codebase index, tasks, notepad, doctor logs, rules, MCP config, receipts. No cloud sync unless you flip it on.
- STT: whisper.cpp by default, falls back gracefully if not installed.
- Backend: uvicorn on `:8765`. Single process. No Docker required.

What is configurable per-call:

- **Provider switcher** — Anthropic, OpenAI, OpenRouter, Ollama. Header dropdown shows live cost-per-1k-tok. Voice command "switch to claude haiku" works.
- **MCP servers panel** (W238) — local stdio + remote SSE, toggles, health badges, test connection.
- **Rules system** — `.tars/rules.yml` + per-pack overlay (system prompts, tool allowlists, refusal patterns).
- **Privacy mode** (W244) — three planes: `local`, `cloud`, `cloud_redacted`. Status bar always shows which plane is active. Receipts include the plane.

OpenRouter integration is real — I ship a `check_llm_provider` doctor check that smoke-pings whichever providers you have keys for. No silent failures.

Mac-only signed installer this beta. Source builds clean on Linux.

Source: github.com/alienram/jarvis
Notes: docs/RELEASE_NOTES_v9.3.0-beta1.md

Curious what local-first folks would push back on.

---

## 2. r/macapps

**Title:** `TARS — native Tauri AI cockpit with voice, Cmd+K, Cmd+Shift+Space toggle, codesigned bundle`

Spent the last six months building TARS — a native macOS AI cockpit. Just shipped v9.3.0-beta1.

Mac-native things that matter:

- **Tauri build** (~80MB bundle), not Electron. Cold start under 600ms on M-series.
- **Voice cockpit** with whisper.cpp baked in — full duplex, push-to-talk or wake-word.
- **Cmd+K palette v2** — fuzzy across actions, files, docs, recents, agents, settings. ~10ms on 5k entries. Keyboard-only navigation.
- **Cmd+Shift+Space** global shortcut — toggles cockpit from anywhere.
- **System tray** with menu (status, recent chats, settings, quit).
- **Window state persistence** via tauri-plugin-window-state.
- **Deep links** — `tars://` opens specific surfaces.
- **Codesigned + notarized bundle** dropping this week (Apple Developer cert just cleared).
- **launchd plist** for the background daemon — health-checks, notifications, doctor tail.

The cinematic cockpit is the part I am proud of. It looks like the Interstellar monolith. It actually does work — the ambient layer pulses with model state, the voice level is real, every action emits a receipt with a timestamp and hash.

Free tier forever. No login required (`Skip → local-only` on the auth screen).

Download (signed): https://tars.meeet.world/download

Feedback welcome.

---

## 3. r/selfhosted

**Title:** `TARS v9.3.0-beta1 — self-hostable AI cockpit (uvicorn on :8765, 9 SQLite DBs, no cloud dependency)`

If you want a Cursor-style AI cockpit that does not require any cloud service to be up, here it is.

Architecture:

- **Backend:** FastAPI + uvicorn on `:8765`. Single process. Run with `bash scripts/backend-up.command` or directly via `uvicorn web_extras.app:app --host 127.0.0.1 --port 8765`.
- **Data:** 9 SQLite files under `~/.tars/` — chats, memory, codebase index, tasks, notepad, doctor logs, rules, MCP config, receipts. All file-based. Back up with `cp -R ~/.tars/ ~/backup/`.
- **Frontend:** Tauri-wrapped React UI (also runnable as plain web at `:5174` for dev).
- **Voice:** whisper.cpp (no API), local TTS via macOS `say` fallback.
- **LLM providers:** bring your own key — Anthropic / OpenAI / OpenRouter / Ollama (last one is fully local).
- **MCP bridge** (W150) — real implementation, exposes 5 native skills as tools to any MCP-compliant client.
- **Receipts:** hash-chained ledger. Optional Solana Merkle root anchor (turn off for fully airgapped).
- **No telemetry to me.** No phone-home. The `meeet.world` integration is optional — click "Skip" on first launch and TARS runs FREE tier forever.

The cockpit reads `/api/doctor` for a unified health check across 10+ subsystems. Built-in `--watch` mode tails health drift.

Mac primary, Linux works (systemd user unit for the daemon shipped in W153).

Repo: github.com/alienram/jarvis

---
