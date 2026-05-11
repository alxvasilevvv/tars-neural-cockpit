# r/SaaS post — TARS v9.1.0

> Tone: founder sharing what they shipped. r/SaaS audience cares
> about ICP / GTM / ROI more than the runtime architecture.
> Lead with the B2B operator suite + workshop product + ROI.
> Honesty principle: only claim what's in `docs/WHAT_WORKS.md`.

---

## Title

```
Shipped TARS v9.1.0 — local-first AI cockpit + B2B workshop suite for funds
```

Backup titles:

```
After 9 months solo, I shipped a B2B AI operator suite (open-source)
```

```
TARS — local-first AI for fund / quant / founder operators (MIT)
```

---

## Body (~400 words)

```
Hey r/SaaS,

Solo founder, just shipped TARS v9.1.0. Wanted to share because the
business model + scope was the hardest part and there might be a
useful pattern here for other builders.

The thesis

Every "AI for X" SaaS in 2026 is a hosted UI over OpenAI/Anthropic
with a markup. Fine for B2C. Bad fit for the operator I kept
meeting at events: a fund partner, a quant team, a small founder
running outreach themselves. They couldn't ship their prompts and
files to a third-party SaaS for compliance / leak reasons.

So: local-first cockpit + a B2B layer on top.

The product (what actually ships v9.1.0)

CORE (free, MIT, runs on your Mac):
- Multi-LLM council (Anthropic / OpenAI / Gemini / Ollama)
- Six domain agents + planner + playbook engine (real cron)
- Signed receipt ledger (hash-chained + Merkle-rooted, Solana anchor)
- Voice in/out, wallet (SOL/EVM/TON), local SQLite memory
- Real connectors: Slack / Gmail / Calendar / GitHub (OAuth)
- Webhooks (signed delivery + inbox)

B2B SUITE (paid Business tier):
- /workshop/* — 8 workshop pages: Intake → Design → Test → Deploy
- /workshop/cohort — facilitator dashboard with real SSE attendees
- /workshop/roi — interactive ROI calculator
- /workshop/assess — pre-workshop self-assessment quiz
- /onboard/org — 5-minute company onboarding wizard
- /dashboard /inbox /files /reports /compliance /marketplace
- 7 vertical bundles for one-click setup

7-vertical bundle generator means a fund / DAO / family office /
SaaS / quant / operator gets a starter agent + playbooks + emails
in one click instead of building from scratch.

ROI for the typical fund customer

Weekly LP report draft: 4 hours -> 10 minutes (the rest of the
40-min slot is partner review).

Audit-grade compliance bundle: 2 days of compliance officer time
-> a button click that spits CSV + PDF + JSON manifest + verifier
script.

Honest scope

- macOS only on day one (signed .dmg this week)
- Multi-tenant data fencing in v9.3 (single-operator only now)
- Marketplace browse works, payouts ship in v9.3
- AI Clone is v0.1 (style hint, not full fine-tune)

Pricing: Free for solo / local. Pro ~$20/mo for hosted bridge.
Business for the workshop suite. Lifetime is a one-time founder
thank-you tier.

tars.meeet.world if curious. MIT, no lock-in.

Happy to dig into the GTM, the cutting-features story (Wave 71
was just "delete things that aren't real" and the product got
visibly better), or the workshop product if anyone is building
something similar.
```

*(~410 words)*

---

## Operator notes

- Post Tuesday morning, 9–11 AM ET. r/SaaS US-leaning audience.
- Lead with the thesis; r/SaaS pattern-matches "yet another AI
  wrapper" instantly. The "couldn't ship their files to third-party
  SaaS" framing is what makes it different.
- Be ready for "what's the moat" questions. Honest answer: open-source
  + receipt ledger trust pattern + B2B workshop motion. Not "AI
  better than competitors".
- Avoid mentioning $MEEET token in the top-level post — r/SaaS
  audience tunes out at the first whiff of crypto. Mention it only
  if asked, and frame as "optional on-chain receipt anchoring."
- Be in the comments for the first 2 hours minimum.
- If asked "how do you make money?", be specific: Business tier,
  workshop facilitation, no rug-pull on the open-source core.
