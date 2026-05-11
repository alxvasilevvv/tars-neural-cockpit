# Email — Waitlist launch blast

> Send to: everyone who signed up via the `/#waitlist` form on the
> landing page. List lives in whatever the operator's ESP is
> (Postmark / Resend / etc — see `docs/INTEGRATION_FOR_BROTHER.md`).
>
> Send time: 9 AM PT on launch day, after the HN post and Twitter
> thread have gone up so the link feels alive.
>
> Honesty principle: only claim what's in `docs/WHAT_WORKS.md`.
> No "battle-tested at 500 funds", no "thousands of users".

---

## Subject

```
TARS is live — your first action in <60 seconds
```

Backup subjects (A/B test):

```
The wait is over — TARS v9.1.0 is yours
```

```
You signed up months ago. Today is the day.
```

---

## Pre-header (preview text, ~90 chars)

```
Three things you can try right now. Signed .dmg ships this week.
```

---

## Plain-text version

```
Hi,

You signed up for early access to TARS. Today, v9.1.0 is live.

Three things you can do RIGHT NOW (<60 seconds each):

1. Try the web cockpit.
   Go to https://tars.meeet.world and click "Open Cockpit".
   Drop a PDF, ask "summarize in five bullets". Local TTS reads
   it back if you turn on voice.

2. Book a workshop.
   If you run a fund, quant team, or org — book a 30-min
   discovery call to see the workshop suite in action.
   https://tars.meeet.world/workshop

3. Install the Mac app.
   The signed .dmg ships THIS WEEK (Apple notarization in flight).
   In the meantime: the web cockpit gives you the full feature
   set, just runs in your browser instead of as a native app.
   When the .dmg lands, you'll get a follow-up with a one-click
   download link.

What's actually in v9.1.0:

- Multi-LLM council (Anthropic / OpenAI / Gemini / Ollama)
- Real OAuth connectors (Slack / Gmail / Calendar / GitHub)
- Signed receipt ledger (hash-chained + Solana memo anchor)
- Voice in/out (XTTS-v2 + Whisper)
- Wallet (SOL / EVM / TON)
- B2B operator suite (/dashboard, /onboard/org, /workshop/*,
  /files, /reports, /marketplace, /inbox, /compliance)
- 7 vertical bundles for one-click setup

Honest scope on day one:
- macOS only (Win/Linux later this year)
- Multi-tenant data fencing in v9.3
- Marketplace browse works, payouts in v9.3
- AI Clone is v0.1, style hint not full clone

Full ledger: https://github.com/<org>/jarvis/blob/main/docs/WHAT_WORKS.md

Reply to this email if anything is broken or you want to chat.
I'm one person, I read every reply.

— Alien

---
You're getting this because you signed up at https://tars.meeet.world.
To unsubscribe, click here: {{unsubscribe_url}}
TARS / meeet.world / hello@meeet.world
```

---

## HTML version

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>TARS is live</title>
</head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#e8e8ec;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#0a0a0f;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;background:#12121a;border-radius:12px;border:1px solid #2a2a35;">
          <tr>
            <td style="padding:32px 32px 16px 32px;">
              <h1 style="margin:0 0 8px 0;font-size:28px;font-weight:600;color:#ffffff;letter-spacing:-0.02em;">
                TARS is live
              </h1>
              <p style="margin:0;font-size:15px;color:#9b9bab;">
                You signed up for early access. Today, v9.1.0 is yours.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:0 32px 24px 32px;">
              <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#d8d8e0;">
                Three things you can do right now (each takes under 60 seconds):
              </p>

              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 16px 0;">
                <tr>
                  <td style="padding:16px;background:#1a1a25;border-radius:8px;border:1px solid #2a2a35;">
                    <p style="margin:0 0 8px 0;font-size:14px;font-weight:600;color:#ffffff;">
                      1. Try the web cockpit
                    </p>
                    <p style="margin:0 0 12px 0;font-size:14px;line-height:1.5;color:#9b9bab;">
                      Drop a PDF, ask "summarize in five bullets". Local TTS reads it back.
                    </p>
                    <a href="https://tars.meeet.world" style="display:inline-block;padding:8px 16px;background:#6366f1;color:#ffffff;text-decoration:none;border-radius:6px;font-size:14px;font-weight:500;">Open cockpit</a>
                  </td>
                </tr>
              </table>

              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 16px 0;">
                <tr>
                  <td style="padding:16px;background:#1a1a25;border-radius:8px;border:1px solid #2a2a35;">
                    <p style="margin:0 0 8px 0;font-size:14px;font-weight:600;color:#ffffff;">
                      2. Book a workshop
                    </p>
                    <p style="margin:0 0 12px 0;font-size:14px;line-height:1.5;color:#9b9bab;">
                      Run a fund, quant team, or org? Book a 30-min discovery call.
                    </p>
                    <a href="https://tars.meeet.world/workshop" style="display:inline-block;padding:8px 16px;background:#6366f1;color:#ffffff;text-decoration:none;border-radius:6px;font-size:14px;font-weight:500;">See workshop</a>
                  </td>
                </tr>
              </table>

              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 24px 0;">
                <tr>
                  <td style="padding:16px;background:#1a1a25;border-radius:8px;border:1px solid #2a2a35;">
                    <p style="margin:0 0 8px 0;font-size:14px;font-weight:600;color:#ffffff;">
                      3. Install the Mac app
                    </p>
                    <p style="margin:0 0 12px 0;font-size:14px;line-height:1.5;color:#9b9bab;">
                      Signed .dmg ships this week. The web cockpit has every feature today.
                    </p>
                    <a href="https://tars.meeet.world/install" style="display:inline-block;padding:8px 16px;background:transparent;color:#9b9bab;text-decoration:none;border-radius:6px;font-size:14px;font-weight:500;border:1px solid #2a2a35;">Install instructions</a>
                  </td>
                </tr>
              </table>

              <p style="margin:0 0 8px 0;font-size:13px;line-height:1.6;color:#9b9bab;">
                <strong style="color:#d8d8e0;">Honest scope on day one:</strong>
                macOS only, multi-tenant fencing in v9.3, marketplace payouts in v9.3,
                AI Clone is v0.1 (style hint, not full clone).
              </p>
              <p style="margin:0 0 16px 0;font-size:13px;line-height:1.6;color:#9b9bab;">
                Full capability ledger:
                <a href="https://github.com/jarvis/blob/main/docs/WHAT_WORKS.md" style="color:#a5a5ff;text-decoration:underline;">WHAT_WORKS.md</a>
              </p>

              <p style="margin:24px 0 0 0;font-size:14px;line-height:1.6;color:#d8d8e0;">
                Reply to this email if anything is broken or you want to chat.
                I read every reply.
              </p>
              <p style="margin:8px 0 0 0;font-size:14px;color:#d8d8e0;">
                — Alien
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 32px;border-top:1px solid #2a2a35;">
              <p style="margin:0;font-size:12px;line-height:1.5;color:#6b6b7b;">
                You're getting this because you signed up at
                <a href="https://tars.meeet.world" style="color:#9b9bab;text-decoration:underline;">tars.meeet.world</a>.
                <br>
                <a href="{{unsubscribe_url}}" style="color:#9b9bab;text-decoration:underline;">Unsubscribe</a>
                · TARS · hello@meeet.world
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
```

---

## Operator notes

- Replace `{{unsubscribe_url}}` with the ESP's merge tag (Postmark
  `{{{ pm:unsubscribe }}}`, Resend `{{unsubscribe_url}}`, etc).
- Replace `<org>` in the WHAT_WORKS.md link with the actual GitHub org.
- Send via the ESP, NOT a personal Gmail. Personal Gmail at scale
  trips spam filters and burns the domain reputation.
- Schedule for 9 AM PT (12 PM ET) — peak open rate for B2B / SaaS
  audiences in the US.
- Set the From name to "Alien" or "Alien at TARS" — personal sender
  outperforms brand sender on a launch email.
- Track opens + clicks separately. The "1. Try the web cockpit"
  button is the primary CTA — if it underperforms, swap copy on
  resend to non-openers 48h later.

---

## Legal footer requirements

- Physical mailing address (CAN-SPAM, US recipients)
- One-click unsubscribe (CAN-SPAM + GDPR)
- Sender identity clear in From / Reply-To
- No deceptive subject line — "TARS is live" is honest, "You won
  $1000" would not be
