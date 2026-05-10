# Skill SDK — public spec for the v9.4 marketplace

This is the public contract third-party authors target when
publishing a skill into the TARS marketplace. It supersedes the
internal-only contract that shipped with v8.10 and pins the manifest
+ action shape that v9.4's marketplace REST will accept.

## Manifest schema

Every skill ships a `manifest.signed.json`. The unsigned `manifest.json`
is the canonical document; the signed file appends an ed25519 signature
block (per Issue #27).

```jsonc
{
  "name": "acme.csv-cruncher",          // unique <publisher>.<slug>
  "version": "1.4.2",                   // semver
  "title": "CSV Cruncher",
  "summary": "Parse, query and chart CSV files inline.",
  "publisher": {
    "id": "acme",
    "display": "Acme Labs",
    "url": "https://acme.example",
    "support_email": "skills@acme.example"
  },
  "license": "MIT",
  "homepage": "https://acme.example/skills/csv-cruncher",
  "icon": "icon.png",                   // ≤ 256 KB, square, PNG/SVG
  "screenshots": ["shot-1.png", "shot-2.png"],
  "actions": [                          // see Action contract below
    {
      "id": "csv.parse",
      "title": "Parse CSV",
      "input_schema": "schemas/parse.in.json",
      "output_schema": "schemas/parse.out.json",
      "side_effects": "none"
    }
  ],
  "permissions": ["fs.read"],           // see Permissions section
  "pricing": {
    "model": "subscription",
    "tier": "pro",
    "price_usd_month": 9,
    "free_actions_per_day": 5
  },
  "min_tars_version": "9.4.0",
  "telemetry": "anonymous-usage"
}
```

The signature block (only present in `manifest.signed.json`):

```jsonc
{
  "signature": {
    "algorithm": "ed25519",
    "public_key": "base64(ed25519-pubkey)",
    "signature": "base64(ed25519-signature)",
    "key_fingerprint": "sha256:abc..."
  }
}
```

The signature MUST cover a canonical JSON serialization of the
unsigned manifest (sorted keys, no whitespace).

## Action contract

Each action declares **input** and **output** as JSON Schema
documents. Both schemas are fetched from the relative paths declared
in the manifest.

### Input

- MUST be a JSON Schema draft-07 object.
- All required fields named in `required` are validated before the
  action handler is invoked.
- Unknown properties are passed through unless `additionalProperties:
  false` is set.

### Output

- MUST also be JSON Schema draft-07.
- The runtime validates the handler's return value against this
  schema; failure surfaces as a structured `OutputSchemaViolation`
  receipt and the action is marked failed.

### `side_effects` values

| Value | Meaning |
| --- | --- |
| `none` | pure read; safe to retry indefinitely |
| `local-fs` | writes to the operator's local filesystem |
| `network-egress` | makes outbound HTTP calls |
| `chain-write` | posts a transaction to a blockchain (Solana, EVM, TON) |
| `paid-egress` | calls a paid third-party API on the operator's behalf |

Any action with `side_effects` other than `none` triggers a HIL
prompt by default unless the operator has approved the skill at the
required risk tier.

## Permissions

Skills declare the permission scopes they need. Granting happens at
install time and can be revoked from the cockpit.

| Permission | Grants |
| --- | --- |
| `fs.read` | read files inside the operator-selected scope |
| `fs.write` | write files inside the operator-selected scope |
| `net.fetch` | make outbound HTTP requests to operator-allowlisted hosts |
| `wallet.read` | read wallet balances (no signing) |
| `wallet.sign` | request a signature from the operator's wallet |
| `memory.read` | read the operator's memory pack |
| `memory.write` | write to the operator's memory pack |
| `receipts.write` | append receipts to the operator's ledger |

A skill that requests `wallet.sign` or `fs.write` is automatically
flagged "elevated" in the marketplace listing.

## Pricing model

Three pricing models are accepted:

1. **Free** — no charge, the skill must declare `model: "free"`.
2. **One-time** — single up-front purchase, declare
   `model: "one-time"` + `price_usd: <amount>`.
3. **Subscription** — recurring monthly billing, declare
   `model: "subscription"` + `price_usd_month: <amount>` and an
   optional `free_actions_per_day` quota for evaluation.

Pricing is denominated in USD and settled via meeet.world's billing
adapter. SOL or $MEEET payment is supported for marketplace
transactions but always converted to the operator's USD-denominated
invoice for receipt purposes.

## Revenue share

The marketplace splits revenue **70/30** in favor of the publisher.

- 70 % of every transaction (one-time or subscription period) goes to
  the publisher's payout wallet.
- 30 % is retained by the marketplace to cover relayer fees, payment
  processing, and platform support.
- Payouts are batched weekly via the off-chain escrow adapter and
  anchored on Solana via Merkle root for verifiability.
- Refunds inside the 7-day window deduct from the next payout cycle;
  beyond 7 days they are processed as a courtesy from the platform's
  share at the publisher's request.

## Security review checklist for marketplace acceptance

Before a skill is listed on the public marketplace, the publisher
must clear this review.

1. **Manifest signature.** ed25519 signature verifies against a
   publicly registered publisher key (per Issue #27).
2. **Schema completeness.** Every action has both an input and output
   JSON Schema; both validate against draft-07.
3. **Permission minimalism.** The declared permissions match what the
   action handlers actually call. Reviewer runs the skill in a
   sandbox and observes syscalls / network requests.
4. **No prompt-injection sinks.** Any string interpolation into LLM
   prompts is escaped or templated; no raw-string concatenation of
   untrusted input into a system prompt.
5. **No outbound credential exfiltration.** The skill does not POST
   environment variables, files matching common secret patterns
   (`*.pem`, `id_rsa`, `.env`), or wallet keys to any host.
6. **Idempotency.** Actions marked `side_effects: none` are pure;
   actions with side effects publish a receipt with an idempotency
   key so retries are safe.
7. **Rate limit discipline.** External API calls respect the
   declared rate limits; the skill backs off on 429 responses
   instead of hot-looping.
8. **Documentation.** README has a one-screen quickstart, a complete
   list of actions with examples, and a clearly stated privacy
   policy.
9. **Dependency hygiene.** `npm audit` / `pip-audit` clean; no
   transitive dependency with a known critical CVE.
10. **Refund and support contact.** A working `support_email` and a
    refund policy linked from the marketplace listing.

A skill that fails any item is rejected with a structured report; the
publisher resubmits after fixes.
