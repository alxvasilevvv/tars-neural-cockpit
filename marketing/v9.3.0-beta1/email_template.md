# Early-access email — TARS v9.3.0-beta1

> Audience: pre-launch waitlist (collected via /waitlist on tars.meeet.world).
> Sender: Alien <alienram@icloud.com>
> Reply-to: same.
> ESP: Postmark transactional. No tracking pixel. Plain-text companion auto-generated.

---

## Subject line — 5 A/B variants

| Variant | Subject | Expected appeal |
|---|---|---|
| A | `TARS v9.3.0-beta1 — your early-access link is here` | direct, transactional |
| B | `you waited for this one — TARS Wave A is live` | personal, urgency |
| C | `the Cursor parity wave shipped (and you have a build)` | technical, framed |
| D | `your TARS download (plus a meeet.world Ultra invite)` | benefit-led, layered |
| E | `built it. shipped it. yours.` | minimalist, paul-g voice |

Recommend **A** as default send. **C** as A/B counter for the technical segment of the list.

---

## Preheader (90 char max)

`Signed installer, Ultra invite code, and a one-week feedback ask. Mac for now; Linux soon.`

Char count: 88 / 90.

---

## Body (~250 words)

Subject: TARS v9.3.0-beta1 — your early-access link is here

Hey {{first_name}},

You signed up to be on the list six months ago, before TARS had a working cockpit. Tonight it does.

v9.3.0-beta1 ships Wave A — thirteen waves of work in one tag, all aimed at closing the Cursor parity gap for everything-not-code. The four panels that were missing (models switcher, MCP servers, rules engine, @-mention context) are in. The Cmd+K palette is rewritten. The consumption console is wired through every metered call. Voice cockpit actually works.

Your signed installer is here (link expires in 14 days):

→ {{signed_download_url}}

It is a beta. Mac-only this round; Windows and Linux build from source. Brother is shipping the meeet.world billing endpoints later this week — until then, the topup prompt opens the dashboard. STT needs `OPENAI_API_KEY` or whisper.cpp installed; otherwise it falls back to text input gracefully.

Two asks:

1. **One week of real usage**, then tell me where it broke. Reply to this email — it lands in my actual inbox, not a queue. Five sentences is plenty. The bug reports from this list have shaped every wave since W67.

2. **Try meeet.world Ultra free for 30 days** — your invite code: `{{ultra_invite_code}}`. Redeem at meeet.world/redeem. This is the cloud-model tier; if you only ever want local, ignore it and keep the Skip button on the auth screen.

Thanks for waiting. The next email goes out when Wave B closes (~3 weeks).

— Alien

PS — the doctor page (`/api/doctor/page` in the app) tells you exactly what is broken if something is. Trust it.

---

## Footer

```
TARS is built by Alien. Billed through meeet.world.
You receive this because you joined the early-access waitlist at tars.meeet.world.
Unsubscribe: {{unsubscribe_url}} (one click, no follow-up)
```

---

## Send notes

- **Segment:** all waitlist subscribers with `verified=true` AND `created_at < 2026-05-15` (everyone who waited for this build).
- **Throttle:** 200/min. Postmark default rate.
- **Track:** open rate (Postmark default — pixel-less; uses link clicks). Click rate on the signed download link is the primary KPI. Reply rate is the secondary (genuine engagement signal).
- **Variant split:** 50/50 on A vs C for the first 1000 recipients; pick winner for the remainder by 24h click rate.
- **Follow-up:** none. One email. The next contact point is the Wave B announcement in ~3 weeks.
