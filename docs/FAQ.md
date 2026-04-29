# TARS — Frequently Asked Questions

> Last updated: 2026-04-29.
> Authoritative source — the website FAQ (`/faq`) is a curated subset.
> If you spot something inaccurate, ping us in
> [Discord](https://discord.gg/meeet) or open an issue.

---

## 1. Privacy & locality

### 1.1 Where does my data live?
On your machine. By default the SQLite memory ledger, vault,
attachment chunks, embeddings, and signed receipt log all sit under
`~/.tars/`. We never see your prompts, your files, or your model API
keys. Cloud sync is opt-in (Pro tier and above) and end-to-end
encrypted with a key derived from your Solana signature — meeet.world
stores ciphertext, never plaintext.

### 1.2 What exactly leaves my machine when?
- **Never (Free tier, no opt-ins):** prompts, files, chat history, model
  outputs, attachment chunks, embeddings, $MEEET wallet activity.
- **Only when you opt in:** encrypted ciphertext blobs (Pro + L5 sync),
  cloud LLM API calls (Anthropic / OpenAI / etc. — the prompt and
  response, governed by their respective DPAs).
- **Always:** outbound DNS for the domains you connect (Slack,
  GitHub, etc.) — same as any browser.

### 1.3 How do I delete my data?
Two paths. Local: `tars uninstall --purge` removes `~/.tars/` entirely.
Cloud: from the cockpit's Settings → Data → "Delete cloud copy" wipes
encrypted blobs from meeet.world. Both are immediate; we do not keep
backups for "your safety".

### 1.4 GDPR / CCPA — am I covered?
Yes. Right to access (export from cockpit Settings → Data → Export),
right to deletion (above), right to portability (export is JSON +
SQLite). Sub-processor list is `docs/PRIVACY_POLICY.md` § 3.

### 1.5 Who are your sub-processors?
Only when their feature is opted in:
- **Anthropic** (Claude) — for cloud council voting, image vision.
- **OpenAI** — same, alternative.
- **meeet.world** (run by our infra team) — encrypted ingest,
  identity, marketplace.
- **GitHub Releases / S3** — installer downloads.
That's it. No analytics, no ads, no tracking pixels.

### 1.6 Do you train AI on my data?
No. We don't have a training pipeline. The "AI Clone" feature trains a
**local** style model on your interactions — never leaves your machine
and never feeds into any shared model.

---

## 2. Pricing & billing

### 2.1 What's actually in Free?
- Single-device install, unlimited usage on-device.
- All 4 domain packs (traders / business / mlm / science).
- Mac Operator (file moves, summaries, web fetch — sandboxed).
- Memory ledger (SQLite), attachments, RAG citations.
- Bring-your-own LLM keys (Claude / OpenAI / Ollama / Gemini /
  DeepSeek / Mistral / Llama — eight providers).
- Local single-voice "council" (no agreement guard).
- MIT license — fork it, ship it.

What's **not** in Free: cloud sync between devices, T2T agent-to-agent
deals, AI Clone training, two-voice council, $MEEET earn.

### 2.2 What does Pro unlock for $19/mo?
Everything in Free, plus:
- Cloud sync across your devices via meeet.world (E2E encrypted).
- Two-voice council on every action with confidence + agreement.
- T2T deals — your agent talking to other agents (50/month).
- AI Clone — per-user style learning.
- Earn $MEEET while your agent works.
- $10 of cloud LLM budget per month included.
- Priority support (24h response).

### 2.3 What's the BYO-key discount?
If you already pay Anthropic / OpenAI directly and just want our
software + cloud features, **Pro · BYO** is **$9/mo** (no included
cloud budget, you provide your own keys). Same feature set.

### 2.4 What's Business tier for?
$79 per seat per month. Adds: shared agent sessions, receipt-anchored
audit trail, SSO + RBAC, organisation-scoped vault, custom skill SDK,
private marketplace, $40 cloud budget per seat. Targets teams of
5+ where audit and SSO matter.

### 2.5 Lifetime tier — is this real?
Yes — pay $299 once, get every Pro feature forever. Includes:
founders' edition badge, your handle reserved on T2T, and 1,000
$MEEET dropped to your wallet at launch. We cap it at the first
1,000 buyers; after that it's gone. Non-refundable after 14 days
because the $MEEET allocation is immediate.

### 2.6 How do I pay?
Card via Stripe (USD), or in $MEEET / SOL via the meeet.world wallet.
Same price across rails. Crypto invoices arrive via email.

### 2.7 Can I cancel?
Anytime, from the cockpit Settings → Billing → Cancel. Your data
stays on-device since it was always there. 14-day no-questions
refund window on Pro and Business.

### 2.8 What if I burn through my cloud budget?
At 80% used, the cockpit shows a yellow strip "approaching budget".
At 100%, cloud LLM calls return 402 Payment Required and the UI
offers an upgrade or "switch to BYO key" toggle. Your local model
(Ollama), memory, and Mac actions keep working — only cloud gets
throttled.

---

## 3. Setup & install

### 3.1 What are the requirements?
- macOS 13+ (Apple Silicon or Intel) or Linux (Ubuntu 22+, Debian 12+,
  Fedora 40+, Arch).
- Python 3.11+.
- ~500 MB disk for `~/.tars/`.
- Internet for installer + cloud features (offline once installed).

Native Windows ships in v9.1; meanwhile use WSL2.

### 3.2 Are there alternatives to the curl install?
Three:
- **Brew (macOS):** `brew install meeet/tap/tars`
- **Notarised .dmg:** download from
  [meeet.world/dl/tars-latest.dmg](https://meeet.world/dl/tars-latest.dmg)
- **Manual:** clone the repo, follow `INSTALL.md`.

### 3.3 How do I uninstall?
`curl -fsSL meeet.world/install.sh | bash -s -- --uninstall` removes
the daemon, launchd plist, and CLI shim. Add `--purge` to also wipe
`~/.tars/` data. Brew users: `brew uninstall tars`.

### 3.4 Multi-machine — same TARS account on laptop + desktop?
Pro tier required. Pair the second machine via L5 device pairing
(Settings → Devices → Pair). QR scan from your phone or 24-char
bech32 paste. Encrypted sync through meeet.world; ciphertext only.

### 3.5 Does TARS run on Apple Silicon vs Intel?
Both. The installer auto-picks the right binary. Apple Silicon path
is recommended — local Ollama models run 3-5× faster.

### 3.6 First-run is taking forever — what's happening?
First boot indexes your starred GitHub repos + any folders you
opted to share. ~1-3 minutes for typical operators. Watch the
cockpit's "indexing" strip. Subsequent starts are instant.

---

## 4. $MEEET & Solana

### 4.1 What is $MEEET?
A utility token issued by meeet.world. Functions as: payment for
Pro/Business subscriptions (alternative to USD), reward for agent
work that gets used by other operators, T2T deal currency. Not a
security, not an investment, not FDIC-insured (see ToS).

### 4.2 Do I need a Solana wallet?
No, for Free tier. Pro+ can sign in with email magic-link or wallet —
your choice. Wallet only required to (a) earn $MEEET, (b) join T2T
deals, (c) skip email and sign in with a wallet signature.

### 4.3 What wallets work?
Any Solana-standard wallet. We've tested Phantom, Backpack, Solflare,
Glow. WalletConnect/RainbowKit support arrives in v9.2.

### 4.4 How do I earn $MEEET?
Two ways. Receipt → reputation: every signed action your agent runs
contributes to your reputation graph; meeet.world drops $MEEET
weekly proportional to graph weight. T2T: when another operator's
agent buys a deal from yours, $MEEET escrow settles to you.

### 4.5 Can I cash out?
You can swap $MEEET ↔ SOL on Jupiter / Orca DEXs. We don't run a
custodial off-ramp. Tax obligations are yours.

### 4.6 Where can I see my balance?
Cockpit footer → MeeetWorldStrip shows wallet status. Click into
meeet.world/account for the full ledger.

---

## 5. Tech & agent

### 5.1 Which LLMs are supported?
Eight, BYO key for Free / Pro · BYO:
- Anthropic Claude (sonnet-4.5, opus-4.6)
- OpenAI GPT (5o, 5)
- Google Gemini (2.5)
- xAI Grok (3)
- Mistral (Large)
- DeepSeek (V3)
- Llama (3.3, via Together AI)
- Ollama (any local model — Llama, Qwen, Mixtral, etc.)

### 5.2 What's the council and why does it matter?
Every action runs through a two-voice deliberation. Two LLMs propose
a stance with confidence + rationale. You see both. On low agreement,
the operator confirms before anything destructive runs. It's the
structural guardrail that stops "the AI confidently doing the wrong
thing".

### 5.3 Does TARS work offline?
Mostly yes. Mac Operator, Memory ledger, Code RAG, and Daily Briefing
run fully offline against a local model (Ollama wired out of the box).
Cloud features that need internet — T2T deals, $MEEET earn, council
voting against frontier APIs — pause and resume gracefully when
connection returns.

### 5.4 How does cost transparency work?
Every LLM call logs `usage.tokens` with computed `cost_usd` to the
local cost ledger. The cockpit's UsageStrip shows live spend by
model / route / session. Pricing overridable via
`TARS_PRICE_OVERRIDES_JSON` if you negotiated different rates.

### 5.5 MCP support?
Both ways. TARS speaks MCP as a server (exposes 5 native skills as
MCP tools so Claude Desktop / Cursor / Windsurf can call them) and
as a client (consumes any MCP server you point at).

### 5.6 Code RAG — what does it index?
Whatever folders you opted in. It chunks `.py / .ts / .js / .rs /
.go / .java / .md / .yaml / .json` files, computes embeddings (OpenAI
`text-embedding-3-small` if cloud, deterministic hash-bigram if
offline), stores in `~/.tars/chat.sqlite`. Hybrid retrieval
(BM25 + cosine) on every query.

---

## 6. Roles & packs

### 6.1 What roles can I pick?
Six default + custom: Founder/CEO, Trader, Researcher, Marketer,
Engineer, Operator (generalist). Custom role lets you describe your
specific work in 200-500 chars; the AI Clone learns from your first
50 interactions.

### 6.2 Can I switch roles later?
Yes, anytime from the cockpit header. Your data stays — switching
just changes the system prompt overlay, the suggested skills, and
the daily briefing template.

### 6.3 What if my work doesn't fit any default role?
Pick **Custom**. Name it ("Sales Director"), describe it ("I run a
12-person sales team in B2B SaaS, focus on enterprise deals…"), give
3 sample tasks, AI Clone trains on you. The custom prompt + clone
are stored locally in `~/.tars/roles/<role_id>.json`.

### 6.4 Migrating from MLM pack — what happens?
The MLM pack got renamed to **Entrepreneur** (broader: founders,
freelancers, agency owners, network marketers). Existing data
auto-migrates on upgrade with a receipt in the audit log. The slug
`mlm` stays as a 90-day alias for compatibility.

---

## 7. Security & audit

### 7.1 What's the sandboxing model?
Mac Operator destructive actions (file moves, web fetches, system
commands) run inside `sandbox-exec` profiles that whitelist exactly
the paths and network destinations needed. Reversible operations
get a signed receipt with 10-minute undo. Irreversible operations
require two-voice council + operator confirm.

### 7.2 What's in a signed receipt?
A row in `~/.tars/receipts.sqlite` with: trace_id, action_id,
inputs hash, outputs hash, timestamp, operator signature (Ed25519).
Every receipt is hash-chained. Optional Solana memo anchor batches
hashes daily for tamper-evident audit.

### 7.3 What's the encryption stack for sync?
- **Identity:** X25519 long-term keypair, master key in macOS
  Keychain / Windows DPAPI / iOS Secure Enclave / Android
  Keystore-StrongBox.
- **AEAD:** XChaCha20-Poly1305 (libsodium).
- **KDF:** HKDF-SHA-256 with 16-byte salt per envelope.
- **Pairing:** bech32m QR with 120s expiry.
Spec: `docs/contracts/L5_PAIRING_DRAFT.md`.

### 7.4 What's recovery seed?
Generated on first install, displayed exactly once: 24-word BIP-39.
Print it, store offline. Lets you re-pair from a new host if the
original machine is gone. Without it, ciphertext blobs in
meeet.world become unreadable — by design.

### 7.5 Multi-device — how does revoke work?
From any host, Settings → Devices → Revoke. Sync key epoch
increments; remaining devices automatically re-key on next event.
Old ciphertexts stay unreadable to the revoked device without
re-key.

### 7.6 Is there an audit log I can export?
Yes. Settings → Data → Export Audit. Bundle includes the SQLite
receipts table + meeet event log + cost ledger. JSONL format.

---

## 8. Roadmap & community

### 8.1 What's coming next?
Active roadmap in `docs/PHASE_L_ROADMAP.md`. Shipped through L8
(search/observability), L9 desktop shell scaffolded. Up next: L5
real crypto, L4 voice mode, L10 mobile companions (iOS + Android),
L3 code execution & artifacts, L7 skill marketplace.

### 8.2 How can I influence priorities?
Join the [Discord](https://discord.gg/meeet) — public roadmap
channel, weekly office hours. Pro+ subscribers get a weighted vote
on quarterly priority survey.

### 8.3 Skill SDK?
Yes — third parties write their own native skills. Docs at
[docs.meeet.world/skill-sdk](https://docs.meeet.world/skill-sdk).
70/30 revenue share via the marketplace.

### 8.4 Where do I file a bug?
[GitHub issues](https://github.com/meeet-world/tars/issues) for
verifiable repros, [Discord](https://discord.gg/meeet) for everything
else. Security disclosures: security@meeet.world (90-day
disclosure, hall of fame for in-scope reports).

### 8.5 Is there a "Built with TARS" badge?
Yes — share links from any cockpit page generate a
"Built with TARS" badge with attribution. Free for anyone. See
the share-links docs.

---

*Last reviewed: 2026-04-29. Pin this file: `docs/FAQ.md`.
Web rendering: [/faq](https://meeet.world/faq).*
