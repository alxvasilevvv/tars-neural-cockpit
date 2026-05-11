# Hacker News submission — TARS v9.1.0

> Submitted by the operator (not "Show HN" — founder-posted launches don't
> need it; HN guidelines are explicit about that).
> Honesty principle from `docs/WHAT_WORKS.md` — every claim below has a
> file path or a route in the repo.

---

## Title (60 chars max)

**Primary (62 chars — trim "open-source" if you want exactly 60):**

```
TARS v9.1.0 – Local-first AI cockpit for Mac (open-source, MIT)
```

**Backup (58 chars):**

```
TARS – Local-first AI cockpit for Mac, MIT, on-chain receipts
```

---

## URL

```
https://tars.meeet.world
```

---

## First-comment seed (~250 words)

> Post this as the first comment yourself within ~30 seconds of the
> submission appearing, so context is at the top of the thread.

```
Operator here. Quick honesty pass on what TARS v9.1.0 is and isn't.

What it is: a Tauri-shell Mac app with a Python sidecar. Inside is
a council of six domain agents (wealth / health / family / product /
brand / entrepreneur), a planner that chains them, a playbook engine
(real cron, restart-safe), a receipt ledger (hash-chained, Merkle-
rooted, optionally anchored to Solana memo), local SQLite memory
with FTS5 search, voice in/out (XTTS-v2 + Whisper), and an embedded
wallet (SOL / EVM / TON).

Connectors are real OAuth, not mocks: Slack, Gmail, Calendar, GitHub.
Telegram bridge for notifications. Webhooks (incoming + outgoing,
HMAC-signed delivery + inbox).

The B2B layer on top is a workshop suite for fund / quant teams
(8 routes, real cohort SSE, ROI calc, self-assessment quiz, materials
hub) plus an org operator console (/dashboard, /onboard/org, /inbox,
/files, /reports, /compliance, /marketplace, /admin/perf).

What it is NOT (yet):

- Multi-tenant data fencing — single-operator only in v9.1.0,
  proper workspace isolation lands in v9.3.
- Marketplace payouts — browse works, the 70/30 split lives in v9.3.
- AI Clone v1 — what ships is v0.1, a style-hint extractor, not a
  fine-tuned per-user model.
- Mac-only. Win/Linux Tauri builds later this year.

Full capability ledger (everything has a file path):
https://github.com/<org>/jarvis/blob/main/docs/WHAT_WORKS.md

Happy to answer anything. Built this solo on top of a brother's
meeet.world relayer for the on-chain bits.
```

*(~245 words)*

---

## Anticipated objections + ready answers

### "Yet another agent framework"

```
Fair. The differentiator is local-first + receipt ledger + B2B
operator suite, not the agent loop itself. If you only want an
agent loop, langchain / autogen / CrewAI all do that fine. TARS
is for the operator who needs to ship a signed audit bundle to
a regulator next Tuesday.
```

### "What's the $MEEET token? Is this a coin scam?"

```
$MEEET is an on-chain credit on Solana for shared compute on
meeet.world (the brother's project). TARS the app does not
require it. You can run TARS fully local with your own LLM key
and never touch a wallet. The wallet is opt-in; the receipt
anchoring is opt-in; the relayer is opt-in. There is no token
sale, no pre-sale, no airdrop tied to TARS. If you want zero
token exposure, leave MEEET_MODE unset.
```

### "Privacy — what leaves my machine?"

```
By default, three things can leave: (1) the LLM call to whichever
provider you BYO-keyed, (2) connector OAuth refresh to Google /
Slack / GitHub, (3) optional Solana memo for receipt anchoring.
Nothing else. No telemetry, no analytics, no usage tracking.
The one synthetic monitor that pings public routes runs against
the marketing site, not against your sidecar.

Settings -> Network shows every outbound endpoint and lets you
disable the relayer + anchor with one toggle.
```

### "Why Tauri and not Electron?"

```
Cold-start, RAM, and the Rust shell lets us ship a real menu-bar
agent with global Cmd+Shift+Space and tray icon without an extra
process. The sidecar crash watcher (Wave 61) is in Rust, polls
the FastAPI heartbeat, and respawns deterministically.
```

### "Mac-only is a dealbreaker"

```
Understood. Tauri makes Win / Linux mostly portable; the holdup
is Apple notarization is paid for and Win / Linux signing infra
isn't. v9.2 brings unsigned dev builds for both, v9.3 brings
signed installers. The roadmap is in docs/ROADMAP.md.
```

### "How is this different from Cursor / Continue / Claude Desktop?"

```
Cursor is for editing code. Continue is a VS Code extension.
Claude Desktop is one client over one model. TARS is a cockpit
for a multi-agent operation: chain agents, run playbooks, log
signed receipts, export an audit bundle. Closer to a small
operator's COO than to a coding assistant.
```

### "Receipt anchor on Solana — why?"

```
Cheap (sub-cent per Merkle root), fast finality, and the memo
program is a clean primitive for "here is a hash, please timestamp
it". We batch many receipts into one Merkle tree per anchor so
cost per receipt rounds to zero. EVM equivalent ships if there
is demand.
```

---

## Operator timing notes

- Post Tuesday or Wednesday, 8:00–8:30 AM PT (peak HN traffic
  window for working hours US).
- Avoid posting on Mondays (HN crowd is catching up on the weekend
  queue) or Fridays (drops off the front page over weekend).
- After submission, refresh the new-page until the title appears,
  then post the first-comment seed within 30 seconds.
- Engage every reply within 5 minutes for the first 90 minutes.
  Long, thoughtful replies > short defensive ones.
- If the post stalls below the front page after 90 minutes, do
  NOT delete and resubmit — that violates HN guidelines. Try
  again next week with a different angle (story-shaped title:
  "Why I built a local-first AI cockpit instead of using Cursor").
