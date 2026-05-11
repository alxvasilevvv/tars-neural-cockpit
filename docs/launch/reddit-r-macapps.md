# r/macapps post — TARS v9.1.0

> Tone: builder sharing what they shipped, not marketing.
> Lead with what problem solved + how, end with link + MIT.
> Honesty principle: only claim what's in `docs/WHAT_WORKS.md`.
>
> Note: r/macapps mods are strict on "ad-like" posts. Lead with the
> tech, not the pitch. Mention $MEEET / on-chain only briefly to
> avoid the "crypto bro" pattern-match.

---

## Title

```
[Showcase] TARS — open-source local-first AI cockpit for Mac (MIT)
```

Backup titles:

```
I shipped a local-first AI cockpit for Mac (open-source, MIT)
```

```
TARS v9.1.0 — local-first multi-LLM cockpit, runs offline with Ollama
```

---

## Body (~400 words)

```
Hey r/macapps,

Spent the last several months building TARS — a local-first AI
cockpit that runs as a native Mac app instead of through someone
else's cloud. v9.1.0 just shipped and I wanted to share the
technical bits because this sub seems to like that.

What it is

A Tauri-shell Mac app (Rust + WebView) with a Python FastAPI
sidecar. The sidecar runs a "council" of six domain agents
(wealth / health / family / product / brand / entrepreneur), a
planner that chains them, a playbook engine with real cron
(restart-safe, persisted), local SQLite memory with FTS5 search,
voice in/out (XTTS-v2 + Whisper API), and an embedded wallet for
the optional on-chain receipt anchoring.

How local is "local-first"?

The model call, the chat history, the memory, the playbooks, the
receipt ledger — all on your Mac in a SQLite file you own. Bring
your own LLM key (Anthropic / OpenAI / Gemini) or run Ollama
fully offline. Three things can leave your machine if you opt
in: (1) the LLM call to your chosen provider, (2) connector OAuth
to Google / Slack / GitHub, (3) Solana memo for receipt batch
anchoring. Everything else stays on your laptop.

Mac-native bits I'm proud of

- Cmd+Shift+Space global shortcut, menu bar tray, tars://
  deep links
- Sidecar crash watcher in Rust — polls the FastAPI heartbeat,
  respawns deterministically (Tauri-native, no Node)
- Window state persisted across launches (tauri-plugin-window-state)
- Signed updater (minisign) so you don't trust GitHub Releases
  on its own
- One-curl install: curl -fsSL https://tars.meeet.world/install.sh | sh

Honest scope

- macOS only for now (Apple Silicon best, Intel under Rosetta).
  Win/Linux Tauri builds later this year.
- Signed .dmg lands this week (Apple Developer ID is in the
  pipeline). Until then, brew tap or unsigned build with
  right-click -> Open.
- AI Clone is v0.1 — it's a style hint, not a per-user fine-tuned
  model. v1 ships in v9.3.
- Marketplace UI is there but the registry is not live yet.

Multi-LLM council voting was the most fun to build — six domain
agents weigh in on a prompt and the planner picks/synthesizes
the answer. It actually works pretty well for ambiguous "should
I do X" questions.

MIT licensed, no telemetry, no account required for the local mode.

tars.meeet.world if curious. Repo's in the README.

Happy to answer anything technical.
```

*(~415 words — well within Reddit's effective attention budget)*

---

## Operator notes

- Post Tuesday or Wednesday between 9 AM and 11 AM ET (peak r/macapps
  traffic).
- Use the `[Showcase]` tag — r/macapps requires it for self-promo posts.
- Be in the comments for the first 2 hours — Reddit penalizes posts
  whose authors disappear.
- Do NOT cross-post to r/MacOS in the same hour — Reddit's spam
  filter catches that. Wait 30 min minimum.
- If anyone asks about the on-chain bit, the honest reply is "it's
  optional, ignore the wallet entirely if you just want a local
  cockpit." Don't volunteer the crypto angle in top-level replies.
- Mods sometimes pull posts for "too marketing-y". If that happens,
  message the mod team with the build path and a link to the MIT
  repo — they usually reinstate.
