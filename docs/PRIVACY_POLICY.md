# TARS — Privacy Policy

> **Effective:** 2026-04-29 (v1.0).
> **Issued by:** meeet.world LLC, Delaware. Contact:
> privacy@meeet.world.
> **DPA available** on request from legal@meeet.world for Business
> tier customers.

This policy describes what data TARS and meeet.world collect, why,
how long, and your rights.

The short version: **almost nothing**. TARS is local-first by
design. Most of the things you'd expect a SaaS to collect — your
prompts, your files, your conversations, your AI model outputs —
**stay on your machine** and never reach any server we control.

---

## 1. Scope

This policy applies to:

- Use of the **TARS Software** (open-source, MIT, on your machine).
- Use of **Cloud Features** delivered via meeet.world.
- Visits to **meeet.world** marketing site.

It does **not** apply to:

- Cloud LLM providers (Anthropic, OpenAI, etc.) — see § 3 for their
  policies.
- Third-party skills you install from the marketplace — each has
  its own privacy posture, surfaced in the marketplace listing.
- Your Solana wallet provider — Phantom, Backpack, etc. each have
  their own policies.

---

## 2. What we collect

### 2.1 What we do **not** collect (default behaviour)

- Prompts.
- Files you ingest into TARS.
- Chat history.
- Model outputs.
- Attachment chunks or embeddings.
- AI Clone training state.
- Local memory ledger contents.
- Receipts (on-device only by default).

These all live in `~/.tars/` on your machine. Nothing leaves unless
you explicitly opt in.

### 2.2 What we collect when you create a meeet.world account

- **Account identity:** email or Solana wallet address (one of, your
  choice).
- **Account metadata:** subscription tier, sign-up timestamp,
  preferred language, time zone.
- **Billing info:** if you pay by card, our processor (Stripe) handles
  card data — we see only last-4 digits and expiry. If you pay in
  $MEEET / SOL, we see the wallet transaction.
- **OAuth tokens:** for skills you connect (Slack, GitHub, etc.) —
  scoped to that skill's permissions, encrypted at rest.

### 2.3 What we collect when you opt into Cloud Sync (Pro+)

- **Encrypted ciphertext blobs.** Pre-encrypted on your machine
  with XChaCha20-Poly1305 + per-device wrapped keys (see
  `docs/SECURITY.md` § 7). We **cannot decrypt** these.
- **Event metadata** alongside each blob: `ts`, `kind`, `route`,
  `session_id`, `trace_id`. This is plaintext but contains no
  prompts or content.

### 2.4 What we collect when you use Cloud LLM voices

We don't collect your prompt or response — they go directly from
your machine to the LLM provider.

We do log **usage telemetry** (model id, token count, latency,
USD cost) into the meeet store so the cost ledger can roll up
per-month spend. This is content-free.

### 2.5 What we collect on meeet.world web visits

- **Functional cookies** — session, dark-mode preference.
- **No analytics, no ads, no tracking pixels.** We do not run
  Google Analytics, Mixpanel, Hotjar, or any equivalent.
- **Server logs** — IP address, user agent, requested path,
  timestamp. Retained 30 days for security; rotated otherwise.

### 2.6 What we collect for support tickets

When you email support@meeet.world, we get whatever you write +
your email address. We use this only to respond. You can ask us
to delete the thread anytime.

---

## 3. Sub-processors

We use these third parties only when their feature is opted in:

| Sub-processor | Purpose | Data shared |
|---------------|---------|-------------|
| **Anthropic** (US) | Cloud LLM voice (Claude) | Prompt + response, when you select a Claude voice. Governed by [Anthropic DPA](https://www.anthropic.com/legal/data-processing-agreement). They commit to **not training** on API traffic. |
| **OpenAI** (US) | Cloud LLM voice (GPT) | Same. Governed by [OpenAI DPA](https://openai.com/policies/data-processing-agreement). |
| **Google** (US) | Cloud LLM voice (Gemini) — opt-in | Same. Governed by Google Cloud DPA. |
| **xAI**, **Mistral**, **DeepSeek**, **Together AI** | Optional cloud LLM voices | Same — selectable per voice; their respective DPAs apply. |
| **Stripe** (US) | Card payment processing | Card data, billing address. Governed by [Stripe DPA](https://stripe.com/legal/dpa). |
| **GitHub Releases / S3** (US) | Installer / .dmg distribution | None — anonymous downloads. |
| **Solana network** (decentralised) | Solana memo anchoring (audit) + $MEEET | Hash digests of receipt batches; on-chain wallet transactions. |
| **Cloudflare** (US) | CDN, DDoS protection, marketing site | Server logs (IP, UA, path). |

We do not engage any sub-processor not on this list. If we add one,
you'll get 30 days' notice via email + cockpit banner.

---

## 4. International transfers

meeet.world LLC is in the US (Delaware). When you use Cloud Features
from outside the US, your encrypted ciphertext + metadata is
transferred to US servers. For EU/UK/CH residents, transfers rely on
**Standard Contractual Clauses** (2021/914/EU). DPA available on
request includes the SCCs as Annex 1.

---

## 5. How long we keep things

| Data | Retention | Reason |
|------|-----------|--------|
| Encrypted ciphertext (sync) | While subscription is active + 30 days after | Recovery window |
| Account identity | While account is open | Service delivery |
| Billing records | 7 years | Tax law |
| Usage telemetry | 24 months, then aggregated | Cost ledger continuity |
| Server logs | 30 days | Security |
| Support tickets | 18 months, then anonymised | Continuity |
| OAuth tokens | While the skill is connected | Service delivery |
| $MEEET wallet activity | Permanent (on-chain — outside our control) | Solana ledger |

Delete account = delete all 1, 5, 6, 7 above within 30 days.
Billing (2) keeps until tax law allows purge.

---

## 6. Your rights

Wherever you live, you can:

- **Access** what we have on you — Settings → Data → Export.
- **Correct** account metadata (email, time zone) — Settings →
  Account.
- **Delete** your account + all associated data — Settings →
  Account → Delete account, or email privacy@meeet.world.
- **Export** your data in JSON + SQLite — Settings → Data → Export.

EU/EEA/UK residents additionally have:

- Right to **restrict processing** — pause the service while we
  investigate a dispute.
- Right to **object** to certain processing (we don't do
  marketing-style profiling, so this rarely applies).
- Right to **lodge a complaint** with your local Data Protection
  Authority.

California residents have rights under CCPA / CPRA, including the
right to **opt out of sale** — note that we do not sell data, so
this right is auto-fulfilled by default.

---

## 7. Children's privacy

TARS is not directed at children. We don't knowingly collect data
from anyone under 13 (US/EU) or 16 (other jurisdictions per local
law). If you believe a child has created an account, email
privacy@meeet.world and we'll delete it.

---

## 8. Security

See `docs/SECURITY.md` for the full model. Highlights:

- **Encryption at rest** for sync ciphertext (XChaCha20-Poly1305).
- **Encryption in transit** via TLS 1.3 for all meeet.world endpoints.
- **Master keys** stay in macOS Keychain / Windows DPAPI / iOS
  Secure Enclave / Android Keystore — they never reach our
  servers.
- **Coordinated disclosure** at security@meeet.world (90 days,
  hall of fame).

---

## 9. Cookies

Functional cookies only:

| Cookie | Purpose | Duration |
|--------|---------|----------|
| `tars_session` | Authenticated session for the cockpit | Session |
| `tars-theme` | Dark / light mode preference | 1 year |
| `tars_lang` | Language preference (when set) | 1 year |
| `__cf_bm` | Cloudflare bot management | 30 minutes |

No advertising or analytics cookies.

---

## 10. Changes to this policy

Material changes (new sub-processor, new data type collected,
expanded retention) — 30 days' notice via email + cockpit banner.
Non-material — 7 days. Version history at
[docs/legal/archive/](https://github.com/meeet-world/tars/tree/main/docs/legal/archive).

---

## 11. Contact

- **Privacy questions:** privacy@meeet.world
- **Security disclosure:** security@meeet.world (90-day, see
  `docs/SECURITY.md` § 10)
- **Legal:** legal@meeet.world
- **Mailing address:** provided on request to verify identity
  before processing requests under § 6.

EU residents — Data Protection Officer: dpo@meeet.world.

---

*Pin this file: `docs/PRIVACY_POLICY.md`. Web rendering:
[/privacy](https://meeet.world/privacy).*
