# Twitter / X thread — TARS v9.1.0 launch

> 10-tweet thread. Each tweet ≤ 280 chars. No emojis (max 1 per tweet).
> Honesty principle: only claim what ships per `docs/WHAT_WORKS.md`.
> See also `docs/launch/ANNOUNCEMENTS.md` (Wave 77, shorter 6-tweet variant)
> — this file is the longer launch-day thread.
>
> Schedule each tweet 60s apart so they unfurl as a thread, not a chain.

---

## 1/10 — Hook + key claim

```
TARS v9.1.0 ships today.

Local-first AI cockpit for Mac. Multi-LLM council, real
connectors (Slack / Gmail / Calendar / GitHub), receipt
ledger anchored on Solana, audit-grade compliance export.

Built for funds, quant teams, founders.

https://tars.meeet.world
```

`[IMG: hero.png]`
*(266 chars)*

---

## 2/10 — Why we built it

```
2/ The reason: every "AI assistant" in 2026 ships your prompts,
your files, and your work product to someone else's GPU.

That is fine for some. Not for a fund partner sending an LP
report draft, not for a quant prototyping a strategy, not for
a founder writing an investor email.

So: local first.
```

*(279 chars — at the limit, ok)*

---

## 3/10 — Architecture differentiator

```
3/ Local-first means the model call, the memory, the receipts,
and the playbook engine all live on your laptop.

Bring your own key (Anthropic / OpenAI / Gemini) or run Ollama
fully offline. Your SQLite file is yours. If our servers vanish
tomorrow, your TARS keeps working.
```

`[IMG: architecture-diagram.png]`
*(278 chars)*

---

## 4/10 — B2B operator suite

```
4/ Inside the cockpit:

/dashboard - org KPIs
/onboard/org - 5-min company setup
/workshop/* - 8 workshop pages (incl. cohort SSE)
/inbox - HIL approval queue
/files /reports /compliance /marketplace
/admin/perf

Built for one operator running an entire org.
```

`[IMG: dashboard.png]`
*(275 chars)*

---

## 5/10 — Workshop product for funds

```
5/ Workshop suite lets a fund or quant team onboard their own
agent in 4 phases (Intake -> Design -> Test -> Deploy).

20+ starter playbooks across 5 verticals. ROI calculator.
Self-assessment quiz. Facilitator dashboard with live SSE
attendee tracking. Materials hub.
```

`[IMG: workshop-cohort.png]`
*(274 chars)*

---

## 6/10 — Compliance + receipts

```
6/ Every action TARS takes is a signed receipt: hash-chained,
Merkle-rooted, optionally anchored to Solana memo.

/compliance exports an audit-grade bundle (CSV + PDF + JSON
manifest + verifier script). Auditors can replay the chain
offline. No "trust me", just hashes.
```

`[IMG: compliance.png]`
*(272 chars)*

---

## 7/10 — Wallet + on-chain

```
7/ Native wallet: SOL + EVM + TON. Balance, spend, sign.

Receipt batches anchor to Solana memo so a customer can verify
"this report was produced by this agent at this time" without
trusting our infra.

Optional. Ignore the wallet entirely if you just want a local
cockpit.
```

`[IMG: wallet.png]`
*(279 chars)*

---

## 8/10 — Open-source + MIT

```
8/ TARS is MIT-licensed.

Backend (FastAPI), Tauri shell, frontend, playbooks, the
council, the receipt verifier, the workshop suite — all in
the repo. No "open core" trick, no encrypted blobs.

You can fork it, host it, or audit it line-by-line.

github.com/<org>/jarvis
```

*(279 chars — replace `<org>` before posting)*

---

## 9/10 — Pricing

```
9/ Pricing:

- Free: full local cockpit, BYO key
- Pro: hosted bridge + premium voices
- Business: workshop suite + cohort + audit export
- Lifetime: one-time, founder thank-you tier

Free is not crippled. The whole local-first product runs on Free.
See /pricing.
```

`[IMG: pricing.png]`
*(269 chars)*

---

## 10/10 — CTA + thanks

```
10/ Honest scope for v9.1.0:

- macOS only (signed .dmg this week)
- AI Clone is v0.1, style hint only
- Marketplace browse works, payouts in v9.3
- Multi-tenant fencing in v9.3

Full ledger: github.com/<org>/jarvis/blob/main/docs/WHAT_WORKS.md

Thank you to the early-access cohort.

https://tars.meeet.world
```

`[IMG: bracket.png]`
*(279 chars — at the limit)*

---

## Operator notes

- Replace `<org>` with the actual GitHub org slug before posting.
- Schedule tweets 60s apart so the thread unfurls properly.
- Image placeholders: produce 1024×512 PNGs from the cockpit
  pages. The `experiments/neural-showcase-v3/public/badge/` folder
  has brand assets you can borrow.
- After tweet 10/10, pin the first tweet to your profile for 7 days.
- Engage with replies in the first 90 minutes — the algorithm rewards it.
- If a tweet runs long after a real-world edit, trim adjective first,
  not claim. Never trim into the WHAT_WORKS.md line.
