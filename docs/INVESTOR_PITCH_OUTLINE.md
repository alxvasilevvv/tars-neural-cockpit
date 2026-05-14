# TARS — Investor Pitch Outline (Series A)

> **Author:** Claude lane, 2026-05-15.
> **Audience:** Alien (founder), the pitch coach, the first 5 investors.
> **Scope:** 12-slide deck outline + talking points + anti-objections.
> **Status:** outline only. The actual deck (Keynote/Figma) is built from
> this outline by a designer; the substance does not change.
> **Companion docs:** `ROADMAP_POST_GA.md` (slide 11 use of funds bridge),
> `PRICING_ECONOMICS_v9.2.md` (slide 8 business model numbers),
> `COMPETITIVE_ANALYSIS_CURSOR.md` (slide 7 differentiation table).

This is a 12-slide deck. Each slide has: title, three bullet contents,
visual hint, and 60-90 seconds of talking points. Total run time: 18-20
minutes. Q&A: 25-30 minutes.

---

## Slide 1 — Title

**Title.** TARS — AI cockpit for everything not code.

**Three bullets.**
- One install, voice + chat + agents, runs on your Mac.
- Local-first, receipt-anchored, multi-LLM council.
- v10.0 GA shipped 2026-05-22.

**Visual hint.** Single full-bleed shot of the cockpit at rest — robot
avatar centered, voice prompt visible, the three modes (cockpit /
project / cowork) glowing at the bottom edge. Dark theme. No nav chrome.

**Talking points (60s).**
"Cursor solved AI-native coding. We're doing for everything else what
Cursor did for code. TARS is a desktop cockpit that orchestrates AI
agents across the rest of your work — wealth, product, health, family,
entrepreneurship, the things you spend the other 80% of your day on.
It's local-first, it's cryptographically receipt-anchored, and it
shipped v10.0 GA this week."

---

## Slide 2 — Problem

**Title.** Cursor for code. ChatGPT-tab-soup for the rest of life.

**Three bullets.**
- Knowledge workers have 7-12 AI tools open at once. None of them talk.
- The "do everything" AI desktop (Claude Desktop, ChatGPT Desktop) is
  a chat surface, not an agent cockpit.
- 80% of high-value work is not coding. There is no Cursor for it.

**Visual hint.** Side-by-side: left is a screenshot of a busy desktop
with 9 browser tabs open (ChatGPT, Gemini, Claude, Notion AI, Linear AI,
Granola, Cal, Gmail draft, a fourth chat). Right is TARS — one window.

**Talking points (60s).**
"Knowledge workers today juggle 7-12 AI tools. None integrate. None
remember context across tools. None take action — they're all chat
surfaces. The best agentic surface in market — Cursor — is locked
inside an IDE for engineers. The rest of us are stuck with ChatGPT
tabs. We see this every day in our own work and in the 200 waitlist
signups who told us why they're here."

---

## Slide 3 — Market

**Title.** $50B AI tools, $200B+ vertical SaaS — and they're converging.

**Three bullets.**
- AI tools market: $50B 2026, $200B by 2030 (Gartner).
- Vertical SaaS market: $200B+ today (BVP).
- TARS sits at the convergence: horizontal AI cockpit + vertical packs.

**Visual hint.** Two-circle Venn diagram: "AI tools" left circle,
"Vertical SaaS" right circle, TARS logo in the intersection. Below: a
single $-axis arrow showing CAGR 2026-2030.

**Talking points (60s).**
"The AI tools market is $50B today and trending to $200B by 2030.
Vertical SaaS — the per-industry tools that real businesses pay for —
is already $200B+ today. These two markets are converging. The winners
will be AI-native cockpits that ship a horizontal product with vertical
packs. TARS already ships 7 packs day-one: wealth, product, brand,
entrepreneur, health, family, science."

---

## Slide 4 — Solution

**Title.** Voice-first, local-first, on-chain audit, 7 domain packs.

**Three bullets.**
- Voice + chat + agents, one Cmd+Shift+Space cockpit.
- Local-first models (Ollama) or BYO API key — no forced cloud.
- Every consequential action emits a Solana-anchored receipt.

**Visual hint.** Three-pane diagram of the architecture: voice/chat
input -> council (multi-LLM cross-check) -> action with receipt. Domain
packs as horizontal swimlanes underneath.

**Talking points (90s).**
"Four things define TARS architecturally. One: voice-first — a global
shortcut takes you from idle to a voice prompt in 200ms. Two:
local-first — we run on Ollama or your own API key; the user's data
never has to leave the machine. Three: receipt-anchored — every
consequential action gets a cryptographic receipt anchored on Solana,
so audit trails are real. Four: domain packs — seven packs day-one,
each with its own prompt, action vocabulary, and rules. Plus a
marketplace coming in v10.5 so third parties extend it."

---

## Slide 5 — Why now

**Title.** Cursor proved AI-native works in IDEs. Time to extend.

**Three bullets.**
- Cursor: $9B+ valuation, $500M+ ARR, ~12 months from launch.
- LLM API costs fell 20x in 24 months — inference is now a feature, not
  a cost-center.
- Voice + agent stack (Whisper, XTTS-v2, MCP, tool-calling) became
  production-ready in 2025.

**Visual hint.** Three-step timeline: 2023 = "AI is chat", 2024 = "AI
writes code (Cursor)", 2026 = "AI does work (TARS)". The next step in
the timeline is implied: 2028 = "AI is the OS."

**Talking points (60s).**
"Three macro shifts made this a 2026 product, not a 2027 product.
Cursor's valuation arc proved AI-native cockpits work at scale —
investors no longer need to be sold on the category. LLM API costs
fell 20x in two years, which means inference is no longer the cost
constraint it was. And the voice + agent stack — Whisper, XTTS-v2,
MCP, native tool-calling across Anthropic and OpenAI — all matured
in 2025. The window to build the cockpit for non-code work is open
now and closes in 18-24 months."

---

## Slide 6 — Product

**Title.** Live demo — watch a real workflow.

**Three bullets.**
- 90-second voice demo: "Plan my Friday trip to NYC."
- Cockpit shows the agent reasoning, council cross-check, action queue.
- Final state: calendar updated, OOO drafted, hotel held, all receipts
  signed.

**Visual hint.** Embedded GIF or 60-second video that auto-plays in the
deck. Mute audio so it works in a silent room.

**Talking points (90s — live demo).**
This slide is the demo, not the talking points. Walk the room through
a 90-second voice command -> agent reasoning -> action -> receipt loop.
Live demo if the room has bandwidth; pre-recorded video if not. End
with: "You just watched 5 things happen in 90 seconds that would take
20 minutes across 5 apps."

---

## Slide 7 — Differentiation

**Title.** Where we win against Cursor / ChatGPT / Claude Desktop.

**Three bullets.**
- Cursor is locked in an IDE. We run anywhere.
- ChatGPT/Claude Desktop are chat. We are an agent cockpit.
- Both are cloud-first. We are local-first with audit trail.

**Visual hint.** A 5-row x 4-column table. Rows: voice-first, local-first,
agent cockpit, receipt audit, domain packs. Columns: TARS, Cursor,
ChatGPT Desktop, Claude Desktop. TARS column all green; others mostly
empty.

**Talking points (60s).**
"Cursor wins inside an IDE; we win outside. ChatGPT Desktop and Claude
Desktop are chat panels with file uploads — they don't *take action*,
they don't have a council, they don't have receipts, and they don't
ship vertical packs. We're not competing with them on chat quality —
we're a different shape of product. The closest analog is what Cursor
did for code: take the workflow, not just the conversation."

---

## Slide 8 — Business model

**Title.** FREE / PRO / BUSINESS + meeet.world token economy.

**Three bullets.**
- PRO: $20/mo. BUSINESS: $40/seat/mo. On-prem: $1k+/month seat license.
- Alt-pay via $MEEET token (10% discount, drives ecosystem).
- Marketplace v10.5: 30% platform cut, 70% to publishers.

**Visual hint.** Four revenue streams arranged like a Sankey diagram:
PRO subs, BUSINESS subs, on-prem licenses, marketplace cuts. Width
proportional to forecast Y2 revenue.

**Talking points (90s).**
"Four revenue streams. Self-serve subscriptions at $20/mo PRO and
$40/seat/mo BUSINESS — the same shape as Cursor and the same shape the
market is comfortable underwriting. On-prem licensing at $1k+/seat/month
for regulated buyers, which is the highest-LTV stream and the one we
get to charge enterprise SaaS rates on. The marketplace, opening
v10.5 — we take 30% on third-party skills, which is the App Store
model and the SaaS-friendly version of platform extraction. And the
$MEEET token economy — users can pay in $MEEET at a 10% discount,
which both drives ecosystem activity and reduces customer acquisition
cost in the crypto-native segment. Day-one $MEEET is opt-in, never
mandatory."

---

## Slide 9 — Traction

**Title.** v10.0 GA shipped. Waitlist. On-prem leads.

**Three bullets.**
- v10.0 GA shipped 2026-05-22 — 267 commits since v9.1.0 (10 months
  ago).
- X waitlist signups (update with actual number on launch eve).
- Y on-prem leads in pipeline (update with actual qualified-lead count).

**Visual hint.** Three big numbers, side by side, each with a tiny
trend sparkline below: signups, leads, GitHub stars.

**Talking points (60s).**
"v10.0 GA shipped this week. We have X waitlist signups (replace with
the real number — 200 baseline at the time of this draft). Y on-prem
leads in pipeline (replace with real — pre-launch baseline is 3 warm,
target 10 qualified by T+30). What matters more than the numbers is
the velocity: 267 commits in 10 months by one founder + Claude lane,
working in public, with full receipts on every line of work. The same
discipline that let one operator ship v10.0 GA is how we'll out-ship
better-funded teams in the next 18 months."

(Note: actual X and Y numbers must be filled in 24h before the pitch
from the live dashboard. Don't quote stale numbers.)

---

## Slide 10 — Team

**Title.** Built by 1 founder + Claude lane. Brother runs meeet.world.

**Three bullets.**
- Alien — founder, ex-[fill in], shipped 267 commits in 10 months.
- Brother — runs meeet.world (the $MEEET economy + auth layer).
- AI orchestra — Claude lane + Cursor lane, treated as engineering
  capacity, not a tool.

**Visual hint.** Three portraits in a row. Below each: a one-line role
description + one credibility data point (commit count, prior exit,
domain expertise).

**Talking points (60s).**
"This is a tiny team by design. One founder, one brother running the
adjacent token economy at meeet.world, and an AI orchestra — Claude as
the lead-dev lane, Cursor as the implementation lane — that we manage
the way a tech lead manages an offshore team. This structure is the
story. We built a v10 GA product, with full audit trails and on-prem
deployment, with the headcount of a typical seed-stage team that
shipped half as much. The Series A funds the next layer — distribution,
sales, the brother's runway, and 3-4 first hires."

---

## Slide 11 — Use of funds

**Title.** $X over 18 months — distribution, sales, on-prem GTM.

**Three bullets.**
- 40% distribution: paid acquisition, content, conference circuit.
- 25% brother's runway: meeet.world stays alive 2 years out.
- 25% sales hires: 1 founding sales (on-prem), 1 SE, 1 ops.
- 10% reserve / runway buffer.

**Visual hint.** A pie chart with the four wedges labelled. Below the
chart: monthly burn projection 18-month timeline.

**Talking points (90s).**
"Use of funds, in priority order. Distribution is the largest chunk —
40% — because we have a working product and the bottleneck now is
reach. Brother's runway is 25% because the meeet.world layer is a
non-trivial part of the product story and it cannot fail. Sales hires
are 25% — one founding sales engineer who can close the on-prem
deals, one customer-facing SE, one ops person to handle the
procurement-friendly paperwork. 10% buffer because we won't get
everything right. The bridge slide to the roadmap: this round funds
us through v11.0 Agentic OS, which is the inflection point where the
always-on substrate either compounds or doesn't."

---

## Slide 12 — Ask

**Title.** Raising $X at $Y valuation. Lead investor sought.

**Three bullets.**
- $X over 18-month runway, 18-24 month milestone to v11.0 GA.
- $Y pre-money valuation (set with banker; placeholder until lead
  signals).
- Closing target: 2026-Q3.

**Visual hint.** A single large pull-quote — Alien's voice — under a
plain ask: "We are building the cockpit for everything you don't code."

**Talking points (60s).**
"We are raising $X at $Y pre-money. We're looking for a lead investor
who understands AI-native product timing and is comfortable with a
founder-AI-orchestra team structure. We have 3 prior conversations
that signalled interest pre-launch; the post-GA week is the right
moment to formalize. Target close: Q3 2026."

---

## Anti-objections — prepare answers, expect these questions

### "What about Cursor doing the same?"

"Cursor is fundamentally a VS Code fork. To enter our market — voice +
agent cockpit for non-code work — Cursor would have to either ship a
non-IDE surface (huge product redirect, distracts from their core
moat) or extend their IDE to non-developers (zero TAM, dev tools don't
fit accountants). The structural cost for Cursor to enter our market
is higher than the structural cost for us to extend our wedge. That's
the moat."

### "What about open-source alternatives?"

"Two open-source candidates: Open Interpreter (great, but a CLI tool —
no cockpit, no receipts, no marketplace), and AnythingLLM (great as a
chat surface, but not voice-first, not agentic, not local-first by
default). The OSS field is crowded with chat surfaces and CLIs. The
cockpit shape — voice + multi-LLM council + receipts + packs — is
specifically a product surface that requires sustained product
discipline, not a community-built tool. And our backend is MIT-
licensed for the on-prem deployment — the commercial moat is the
hosted relayer, the meeet.world auth, and the curated marketplace.
We're not threatened by OSS; we ride on it."

### "What about regulatory risk on $MEEET?"

"Three things de-risk this. One: $MEEET is opt-in. Day-one users can
ignore the token entirely and pay in USD via card or ACH. Two:
$MEEET is not a security under any standard test we've reviewed — it
is a utility token for paying for compute on the meeet.world relayer,
with documented utility on day one. Three: the on-prem product
doesn't touch $MEEET at all; enterprise buyers pay seat licenses in
fiat. The token is upside, not core. If regulation makes the token
unviable in any major jurisdiction, the product survives intact."

### "Why hasn't a big incumbent done this?"

"They have priorities. Anthropic ships Claude Desktop as a chat
surface — different shape of product. OpenAI ships ChatGPT Desktop —
same. Google ships nothing in this shape and Microsoft ships Copilot,
which is wired into Office. None of them ship voice-first, local-first,
receipt-anchored, multi-LLM council. Incumbents have one model loyalty;
we are model-pluralist by design. The combination is hard for
incumbents to replicate without contradicting their distribution
strategy."

### "What if AI inference gets so cheap the moat disappears?"

"The moat isn't inference. The moat is the cockpit — the UX, the
receipt trail, the marketplace, the per-user style learned over time.
Cheap inference makes our product better (lower cost per call) and
makes the chat-surface competitors more commoditized. We benefit
asymmetrically from cheap inference."

---

## Pitch logistics

- **Total deck length:** 12 slides, 18-20 min talking, 25-30 min Q&A.
- **Demo slot:** slide 6. Live demo if bandwidth + setup permit, else
  60-90 second video.
- **Leave-behind:** PDF export of the deck + one-pager + link to live
  demo video on YouTube unlisted.
- **Follow-up:** within 24h, send a thank-you email with the
  leave-behind and the roadmap doc.
- **The single most important slide:** slide 7 (differentiation). If
  the room remembers exactly one slide, this is the one — the table
  shape sticks, the verbal framing of "Cursor for everything not code"
  sticks, and the dismissal of chat-surface competitors sticks.

— end —
