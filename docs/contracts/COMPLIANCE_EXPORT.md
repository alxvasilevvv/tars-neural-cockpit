# COMPLIANCE_EXPORT contract — Wave 104

Audit-grade compliance export bundle. A single command produces a
`tar.gz` every B2B accountant or auditor will accept.

Contract version: **1.0**.

---

## Bundle structure

```
audit-<UTC-timestamp>.tar.gz
├── README.md                       # auto-generated, explains layout + verification
├── manifest.json                   # versioning + per-file sha256 index + signing key fp
├── signature.txt                   # ed25519 signature over manifest.json bytes
├── receipts/
│   ├── YYYY-MM-DD.ndjson           # one file per UTC day (source-of-truth)
│   ├── merkle_roots.json           # daily Merkle roots (+ optional Solana txid)
│   └── chain_verification.json     # per-day verify_chain result at bundle time
├── cohort/
│   ├── cohorts.json                # all cohort summaries
│   └── <cohort_id>.json            # attendees + per-attendee timeline
├── connectors/
│   ├── slack.json | gmail.json | calendar.json | github.json
│   └── README.txt
├── hil/
│   ├── approval_log.json           # action_type, decided_by, decided_at, reason, outcome
│   └── README.txt
├── outreach/
│   ├── drafts.json | sends.json | recipients.json
├── files/
│   ├── manifest.json               # id, name, hash, size, category, tags
│   └── blobs/<file_id>             # ONLY when scope contains "blobs"
├── wallet/
│   └── audit.json                  # wallet/audit.py + wallet.* receipts
├── org/
│   ├── info.json | invites.json
├── playbooks/runs.json
├── agents/definitions.json
└── webhooks/
    ├── outgoing.json | incoming.json
```

---

## Verification recipe (3 steps)

1. **Recompute file hashes.** For every entry in
   `manifest.json.files[*]`, recompute `sha256` over the extracted
   bytes and compare against the stored value.
2. **Verify the signature.** Read `signature.txt`, base64-decode the
   `signature_b64`, and verify it against `manifest.json` bytes
   using the ed25519 public key stored in
   `manifest.json.signing_key_b64` (or the equivalent
   `public_key_b64` line in `signature.txt`).
3. **Replay the chain.** For every `receipts/*.ndjson` file, walk
   line-by-line and re-derive the canonical sha256 over
   `(prev_hash, ts, type, actor, resource, payload)`. Each receipt's
   `hash` must match, and the next receipt's `prev_hash` must equal
   this one's `hash`. Compare to `chain_verification.json`.

The bundled verifier (`backend.core.compliance_export.verifier.verify_bundle`)
performs all three steps. Auditors can also use it via the
`POST /api/compliance/export/verify` endpoint without any other TARS
state.

---

## Signing scheme

The bundle is signed with the **host receipt key** introduced in
Wave 95 (see `RECEIPTS.md`). That ed25519 keypair lives at
`~/.tars/host-key.json` (override via `TARS_RECEIPT_HOST_KEY_PATH`).
The public key is embedded in the manifest itself so a verifier
needs nothing besides the bundle and the `cryptography` library.

The signature payload is the deterministic
`json.dumps(manifest, indent=2, sort_keys=True)` serialisation of
the manifest dict — same canonical form everywhere.

---

## GDPR export

`POST /api/compliance/gdpr-export` (or
`backend.core.compliance_export.gdpr.export_user_data`) builds a
single-user data export for Article 15 ("right of access")
requests. Output: `~/.tars/exports/gdpr-<userhash>-<ts>.tar.gz`.
Same shape as the audit bundle but scoped to one subject.

---

## PII redaction

`backend.core.compliance_export.redaction` redacts emails, phone
numbers, IPv4/IPv6, credit-card-like sequences, and US SSNs with
`[REDACTED:type:hash]` tokens. The hash is deterministic per input
string so an auditor can still join records that share a value
without ever seeing it.

Two entry points:

- `redact_pii(bundle_path)` — re-emit a redacted bundle from disk
  (invalidates the original signature; treat as new artifact).
- `redact_bytes(data)` — used inline by `build_bundle(..., redact_pii=True)`.

Schemes: `default` (all categories), `minimal` (email only).

---

## Recommended retention

Keep export bundles for **7 years** per most fund regulations
(SEC 17a-4, MiFID II Art. 16, FINRA 4511). Store the bundle
alongside the host signing-key fingerprint
(`manifest.signing_key_fingerprint`) so future auditors can
confirm provenance.

---

## HTTP surface

| Method | Path                                            | Notes                |
| ------ | ----------------------------------------------- | -------------------- |
| POST   | `/api/compliance/export/bundle`                 | HIL-gated generate   |
| GET    | `/api/compliance/export/bundles`                | list past            |
| GET    | `/api/compliance/export/bundles/{id}`           | single status        |
| GET    | `/api/compliance/export/bundles/{id}/download`  | tarball download     |
| DELETE | `/api/compliance/export/bundles/{id}`           | HIL-gated delete     |
| POST   | `/api/compliance/export/verify`                 | multipart upload     |
| POST   | `/api/compliance/gdpr-export`                   | single-user export   |
| GET    | `/api/compliance/export/scope-categories`       | available categories |

The `bundle` and `DELETE` endpoints route through
`web_extras.policy_gate.require_confirm` so the HIL gate (Wave 76)
kicks in when `TARS_REQUIRE_OPERATOR_CONFIRM=1`.
