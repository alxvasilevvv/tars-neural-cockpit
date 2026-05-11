# Press kit — TARS v9.1.0

> Single source of truth for journalists, podcast hosts, and partner
> blogs covering TARS. All assets are CC-BY-4.0 with attribution
> "Built with TARS — tars.meeet.world".
>
> Honesty principle from `docs/WHAT_WORKS.md` — every claim has a file
> path or route in the open-source repo.

---

## One-paragraph product description

```
TARS is a local-first AI cockpit for Mac, built for fund operators,
quant teams, and founders who can't ship their prompts and files to
a third-party AI cloud. Inside the cockpit: a multi-LLM council of
six domain agents (wealth, health, family, product, brand,
entrepreneur), a planner that chains them, a playbook engine with
real cron, and a signed receipt ledger that hash-chains every action
and optionally anchors batches to the Solana memo program. Real
OAuth connectors for Slack, Gmail, Calendar, and GitHub. Voice in
and out. An embedded SOL/EVM/TON wallet. A B2B operator suite
(/dashboard, /onboard/org, /workshop/*, /files, /reports,
/marketplace, /inbox, /compliance, /workspaces, /admin/perf) and a
4-phase workshop product for funds and quant teams. MIT licensed,
no telemetry, no account required for the local mode. Source code
and capability ledger at github.com/<org>/jarvis.
```

*(~155 words — trim from the bottom if a publication needs ~75)*

### One-sentence (for newsletters)

```
TARS is an open-source, local-first AI cockpit for Mac with a
multi-LLM council, real Slack/Gmail/Calendar/GitHub connectors, a
hash-chained receipt ledger anchored on Solana, and a B2B workshop
suite for funds and quant teams.
```

### One-line (for social cards)

```
Local-first AI cockpit for Mac. Open-source, MIT, audit-ready.
```

---

## Founder bio

> *(Operator: replace with your real bio before sending the press kit.
> Suggested template below.)*

```
Alien is the founder of TARS and the operator of meeet.world.
He has spent the last several years building developer tools and
on-chain infrastructure, with a focus on local-first software and
operator ergonomics. TARS is his attempt to give fund partners,
quant teams, and solo founders an AI cockpit they fully own —
no SaaS lock-in, no telemetry, no third-party clouds touching
their work product.

Reach: hello@meeet.world
Twitter / X: @meeet_world (or operator's personal handle)
GitHub: github.com/<operator-handle>
```

*(~80 words)*

---

## Logo files

All brand assets live at:
- `experiments/neural-showcase-v3/public/badge/` (web-served)
- `desktop/src-tauri/web/badge/` (bundled with the .dmg)

| Asset | Path | Usage |
| --- | --- | --- |
| Built-with-TARS, dark | `/badge/built-with-tars.svg` | Default for dark backgrounds |
| Built-with-TARS, light | `/badge/built-with-tars-light.svg` | For light/paper backgrounds |
| Built-with-TARS, compact dark | `/badge/built-with-tars-compact.svg` | For navbars + footers |
| Built-with-TARS, compact light | `/badge/built-with-tars-compact-light.svg` | For light navbars |

Public URLs (when site is live):

```
https://tars.meeet.world/badge/built-with-tars.svg
https://tars.meeet.world/badge/built-with-tars-light.svg
https://tars.meeet.world/badge/built-with-tars-compact.svg
https://tars.meeet.world/badge/built-with-tars-compact-light.svg
```

Embed:

```html
<a href="https://tars.meeet.world" rel="noopener">
  <img src="https://tars.meeet.world/badge/built-with-tars.svg"
       alt="Built with TARS" height="32">
</a>
```

---

## Screenshots (placeholder — replace with real PNGs before send)

Each screenshot should be 2560×1600 PNG, dark theme, no watermarks.
Source from the running cockpit with a believable demo workspace
pre-loaded.

| # | Filename (placeholder) | Caption |
| --- | --- | --- |
| 1 | `assets/press-1-cockpit.png` | TARS cockpit — neural brain visual + multi-LLM council |
| 2 | `assets/press-2-dashboard.png` | /dashboard — org KPIs + scheduler + recent receipts |
| 3 | `assets/press-3-workshop-cohort.png` | /workshop/cohort — facilitator dashboard with live SSE attendees |
| 4 | `assets/press-4-compliance.png` | /compliance — audit-grade receipt feed + export bundle |
| 5 | `assets/press-5-marketplace.png` | /marketplace — community playbook browse |
| 6 | `assets/press-6-wallet.png` | Embedded wallet — SOL balance + receipt anchor |
| 7 | `assets/press-7-watch-me-work.png` | Watch-me-work timeline — every agent step streamed real-time |
| 8 | `assets/press-8-pricing.png` | /pricing — Free / Pro / Business / Lifetime tiers |

---

## Press contact

```
Email: alienram@icloud.com
Reply SLA: 24 business hours
Time zone: PT (UTC-7)

For embargoed coverage:
- Reply with "EMBARGO" in subject
- Honor: yes, will respect any reasonable embargo with a date

For interviews / podcasts:
- 30-min slots open Tue/Wed/Thu, 9 AM–5 PM PT
- Calendar: link will be added once Calendly / Cal.com is wired
```

---

## Brand palette (from `experiments/neural-showcase-v3/src/index.css`)

```
Background-0:   #000000   (OLED true black, hero canvas)
Background-1:   #0b0b10   (cards, sections)
Background-2:   #14141b   (elevated surfaces, dialogs)

Ink-1 (primary text):    #f5f5f0
Ink-2 (secondary text):  #b0aea4
Ink-3 (muted, AA pass):  #7a786f

Accent (primary CTA):    #6366f1   (meeet brand indigo)
HUD (data viz, lines):   #06b6d4   (brand cyan)
Alert (errors):          #ef4444
Success (confirmations): #34d399

Brand triad:
- Indigo:  #6366f1
- Violet:  #8b5cf6
- Cyan:    #06b6d4
- Orchid:  #a78bfa
- Amber:   #f59e0b   (only used for warnings + reasoning highlights)

Brand sweep (1px hairline at top of every marketing card):
linear-gradient(90deg, transparent 0%, #6366f1 30%, #8b5cf6 50%, #06b6d4 70%, transparent 100%)
```

---

## Typography

```
Display + body: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                "SF Pro Text", "Segoe UI", "Helvetica Neue", Helvetica,
                Arial, sans-serif

Mono / code:    "SF Mono", "JetBrains Mono", "Menlo", "Monaco",
                "Consolas", monospace

Letter-spacing on display headings: -0.02em
Body line-height: 1.6
Heading line-height: 1.15
```

---

## Audio / video assets (optional)

> If a podcast asks for a 30-second intro clip or a press conference
> uses b-roll:

| Asset | Status | Path / URL |
| --- | --- | --- |
| 30s product intro voiceover (XTTS-v2) | Not yet recorded | TBD |
| 60s screencast — onboarding flow | Not yet recorded | TBD |
| 90s screencast — workshop suite walkthrough | Not yet recorded | TBD |
| Founder headshot (1:1, 1024×1024) | Operator to provide | TBD |

Operator: produce these with QuickTime + the cockpit running locally
before the first major press hit.

---

## What journalists usually ask + ready answers

### "How is this different from Claude Desktop / Cursor / Continue?"

```
TARS is a multi-agent operator cockpit — not a chat UI over one
model and not a code editor. The closest analogy is a small operator's
COO: it chains agents, runs scheduled playbooks, logs signed receipts,
and exports an audit-grade compliance bundle. Claude Desktop is one
client over one model. Cursor is for editing code. Continue is a VS
Code extension. Different problem space.
```

### "Why local-first?"

```
The operators we built for — fund partners, quant teams, founders
running outreach — can't ship their prompts and files to third-party
AI clouds for compliance and IP-leak reasons. Local-first means the
LLM call, the memory, the playbooks, and the receipts all live on the
operator's Mac. Bring your own LLM key or run Ollama fully offline.
The whole product runs without a network connection if the operator
chooses Ollama.
```

### "What's $MEEET? Is this a token launch?"

```
No. $MEEET is an existing on-chain credit on Solana for shared compute
on meeet.world (the brother project). TARS does not require it. The
wallet, the relayer integration, and the on-chain receipt anchoring
are all opt-in and can be ignored entirely. There is no TARS token,
no pre-sale, no airdrop tied to this launch.
```

### "What's the business model?"

```
Free local cockpit for solo operators. Pro tier (~$20/mo) for hosted
bridge + premium TTS voices. Business tier for the workshop suite +
cohort facilitator + audit-grade compliance export. Lifetime tier as
a one-time founder thank-you. No "open core" trick — the entire
product is MIT-licensed; the paid tiers buy hosted infra and the
workshop product, not the core code.
```

### "How big is the team?"

```
One founder + one brother running the meeet.world relayer
infrastructure. Solo build pace. Wave 118 of the dev journal at
launch — every wave is a documented unit of work in the repo.
```

### "What's next?"

```
v9.2: Win/Linux Tauri builds (signed). v9.3: multi-tenant data
fencing, marketplace payouts (70/30 author split), AI Clone v1.
Roadmap is in docs/ROADMAP.md.
```
