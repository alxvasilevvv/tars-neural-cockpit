# Twitter / X thread — TARS v9.1.0 launch

TARS v9.1.0 is out today. Local-first AI agent runner for Mac (arm64), Windows, and Linux. Multi-LLM council, scheduler, webhooks, marketplace, Cowork multiplayer backend. Built under meeet.world. Runs on your machine, not ours.
\n
Install on Mac, Windows, or Linux with one line:

bash <(curl -fsSL https://tars.meeet.world/install.sh)

Mac Intel falls back via Rosetta. The installer clears the xattr quarantine bit for you.
\n
What it does: agent runs can fan out to Claude, GPT, Gemini, and a local Ollama model in a single council step, then reconcile. Same runtime drives a Mac operator that can act on your machine. Ollama-only runs work fully offline.
\n
Local-first means your prompts, files, and intermediate state stay on your box. No required cloud account for the core runner. You bring your own provider keys, or skip them entirely and run Ollama.
\n
Honest status: Cowork multiplayer UI is NOT in this release — backend module only, frontend lands in v9.1.1. Mac build is ad-hoc codesigned, not Apple-notarized yet. Working on both.
\n
Docs, downloads, one-line install: https://tars.meeet.world
