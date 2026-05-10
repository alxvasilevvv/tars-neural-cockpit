# Marketplace v0 (Wave 106)

Contract version: **1.0**

In-process registry + browse + install for community-published
playbooks, skills, templates and report templates. Local-only
ratings (no central backend until v9.3). No payouts yet — every
listing in v0 ships as `price: free`.

## Listing schema

```jsonc
{
  "id":              "mlst_seed_fund_pack",        // string, prefix mlst_
  "kind":            "playbook",                    // playbook | skill | template | report_template
  "name":            "Fund Operator Pack",
  "slug":            "fund-operator-pack",
  "description":     "...",
  "author":          { "handle": "tars-core", "url": "https://tars.meeet.world" },
  "version":         "1.0.0",
  "tags":            ["fund", "lp", "deal"],
  "category":        "fund",                        // free-form (used for sidebar chips)
  "install_payload": { ... },                       // see below
  "preview_url":     "/workshop/materials#fund",
  "ratings":         { "count": 47, "avg": 4.7 },
  "price":           "free",                        // free | one-time | subscription
  "license":         "MIT",
  "created_at":      1746835200.0,
  "updated_at":      1746835200.0
}
```

## Install payload formats

| `format`            | Shape                                                                                  | Effect                                                                            |
|---------------------|----------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| `playbook_bundle`   | `{ "format": "playbook_bundle", "source_dir": "playbooks/_workshop/<vertical>" }`      | Copies the workshop pack into `~/.tars/marketplace/installed/<id>/`.              |
| `playbook_inline`   | `{ "format": "playbook_inline", "recipe": { ... } }`                                   | Writes `recipe.json` straight to the install dir.                                 |
| `report_template`   | `{ "format": "report_template", "kind": "pptx", "slug": "lp-quarterly" }`              | Records a pointer; renderer (Wave 103) owns the actual template.                  |
| `skill_module`      | `{ "format": "skill_module", "module": "pdf_redactor" }`                               | Records a pointer; the SDK loads the skill at runtime.                            |
| URL string (`*.json`) | `"https://example.com/listing.json"`                                                  | Fetches via `urllib.request` with 10 s timeout, stored as `payload.json`.         |
| URL string (`*.zip`)  | `"https://example.com/listing.zip"`                                                   | Same, stored as `payload.zip` (no auto-extract in v0).                            |

## Signing scheme (recommended)

Listings MAY include `install_payload.signature` as a hex-encoded
ed25519 signature over the canonical JSON of the rest of the
payload. The installer:

1. Records `signature_absent` in the audit log when no signature is present.
2. Records `signature_present_unverified_v0` when a signature is on the
   payload but the v0 verifier cannot resolve a trusted public key.
3. Real verification (with a curated key list distributed via the
   meeet.world relayer) lands in v9.3 alongside payouts.

The audit log is persisted in `installed.audit_json` and surfaced
in the `install` response so the FE can show a "signature absent"
warning chip if desired.

## Rating system

**v0 is local-only.** Ratings live in `~/.tars/marketplace/ratings.sqlite`.

- Identity: `anonymise_rater(email)` returns a SHA-256 hex digest
  with a fixed salt. Empty / unauthenticated requests collapse to
  the literal `"anonymous"` bucket.
- Anti-double-vote: `UNIQUE (listing_id, rater)` constraint.
  Re-submitting from the same rater updates the existing row in
  place (the FE shows the latest comment).
- Aggregates: computed on read (`AVG(score)`, `COUNT(*)`).
- Centralised ratings + reviews land in **v9.3** alongside payouts.

## HTTP surface

| Method | Path                                                  | HIL gate? | Notes                                                       |
|--------|-------------------------------------------------------|-----------|-------------------------------------------------------------|
| GET    | `/api/marketplace/listings`                           | no        | Filters: `category`, `kind`, `q`, `min_rating`.             |
| GET    | `/api/marketplace/listings/{id}`                      | no        | Single listing + decorated `installed` flag.                |
| POST   | `/api/marketplace/listings/{id}/install`              | yes       | Body: `{ "target": "personal" \| "workspace" }`.            |
| GET    | `/api/marketplace/installed`                          | no        | Filters: `kind`, `category`.                                |
| POST   | `/api/marketplace/installed/{id}/uninstall`           | yes       | —                                                           |
| POST   | `/api/marketplace/listings/{id}/rate`                 | no        | Body: `{ score: 1..5, comment?, rater_email? }`.            |
| GET    | `/api/marketplace/listings/{id}/ratings`              | no        | Returns aggregate + recent ratings.                         |
| POST   | `/api/marketplace/registry/refresh`                   | no        | Force re-fetch the upstream manifest (1 h cache otherwise). |
| POST   | `/api/marketplace/listings/{id}/preview`              | no        | Returns sample inputs / outputs for the preview modal.      |

The HIL gate routes through `web_extras/policy_gate.require_confirm`
so it is a no-op unless `TARS_REQUIRE_OPERATOR_CONFIRM=1`.

## Roadmap to payouts (v9.3+)

1. Centralised ratings: aggregate ingestion (operators opt in).
2. Curated trust list (ed25519 keys distributed via meeet.world).
3. Stripe-replacement payouts in $MEEET / SOL (per the v8.10 work).
4. 70 / 30 author / platform split (matches Wave 96).
5. Featured listings + leaderboards (recycle the Wave 80 graph).

## How to publish a listing

Today (v0): open a PR against
[`alxvasilevvv/tars-marketplace`](https://github.com/alxvasilevvv/tars-marketplace)
that appends a new entry to `registry.json` matching the schema
above. CI on the marketplace repo validates the JSON.

The bundled seed (`backend/core/marketplace/seed.py`) is consulted
when the upstream URL is unreachable.
